#!/usr/bin/env python3
"""Monitor live proxies every five hours; never count an unverified outage."""
import concurrent.futures, datetime as dt, hashlib, json, os, subprocess, tempfile, time, urllib.parse, urllib.request
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'clash.yaml'
SUB=ROOT/'nodes-fuzhou-20260929.txt'
HISTORY=ROOT/'.github/node-health-history.json'
ANCHOR=dt.datetime(2026,10,20,11,1,33,tzinfo=dt.timezone.utc)
PERIOD=5*3600
CORE=os.getenv('MIHOMO_BINARY','/tmp/mihomo')
URL=f"https://github.com/{os.getenv('GITHUB_REPOSITORY','sadpotatomine/hiddify-sub')}/actions/runs/{os.getenv('GITHUB_RUN_ID','unknown')}"
TARGETS=['https://www.gstatic.com/generate_204','https://www.cloudflare.com/cdn-cgi/trace']

def signature(p):
    p={k:v for k,v in p.items() if k!='name'}
    return hashlib.sha256(json.dumps(p,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def sub_names(lines):
    names=[]
    for line in lines:
        if not line.strip():continue
        link=urllib.parse.urlsplit(line)
        if not link.scheme or not link.fragment:raise ValueError('Invalid URI / missing node label')
        names.append(urllib.parse.unquote(link.fragment))
    if len(set(names))!=len(names):raise ValueError('Duplicate subscription labels')
    return names

def curl(target,proxy=None):
    args=['curl','-fsSL','--connect-timeout','8','--max-time','18','-o','/dev/null']
    if proxy:args+=['--noproxy','','--proxy',proxy]
    try:return subprocess.run(args+[target],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=23).returncode==0
    except (OSError,subprocess.TimeoutExpired):return False

def ready(port):
    stop=time.monotonic()+10
    while time.monotonic()<stop:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/version',timeout=1) as response:
                if response.status==200:return True
        except Exception:time.sleep(.4)
    return False

def check(item):
    i,proxy=item
    name=proxy['name']; port=19000+i; ctl=20000+i
    results=[]
    for attempt in range(3):
        with tempfile.TemporaryDirectory(prefix='health-') as folder:
            cfg={'mixed-port':port,'allow-lan':False,'mode':'rule','log-level':'warning','ipv6':False,
                 'external-controller':f'127.0.0.1:{ctl}','proxies':[proxy],
                 'proxy-groups':[{'name':'TEST','type':'select','proxies':[name]}],'rules':['MATCH,TEST']}
            path=Path(folder)/'config.yaml'
            path.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False),encoding='utf-8')
            with (Path(folder)/'mihomo.log').open('w') as log:
                try:p=subprocess.Popen([CORE,'-d',folder,'-f',str(path)],stdout=log,stderr=subprocess.STDOUT)
                except OSError:return {'status':'UNKNOWN','attempts':results+['CORE_START_ERROR']}
                try:
                    if not ready(ctl):return {'status':'UNKNOWN','attempts':results+['CORE_NOT_READY']}
                    passed=any(curl(target,f'http://127.0.0.1:{port}') for target in TARGETS)
                    results.append('PASS' if passed else 'UNREACHABLE')
                    if passed:return {'status':'PASS','attempts':results}
                finally:
                    p.terminate()
                    try:p.wait(timeout=5)
                    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
    return {'status':'FAILED_UNREACHABLE','attempts':results}

def streak(rows):
    rows=sorted(rows,key=lambda x:x['cycle'],reverse=True)
    if not rows:return 0
    expected=rows[0]['cycle'];n=0
    for row in rows:
        if row['cycle']!=expected or row['status']!='FAILED_UNREACHABLE':break
        n+=1;expected-=1
    return n

def run():
    now=dt.datetime.now(dt.timezone.utc)
    cycle=int((now-ANCHOR).total_seconds()//PERIOD)
    if cycle<0:raise RuntimeError('Invalid cycle clock')
    cfg=yaml.safe_load(CONFIG.read_text(encoding='utf-8'))
    proxies=cfg.get('proxies',[])
    if not proxies or not isinstance(proxies,list):raise ValueError('No proxies')
    names=[p['name'] for p in proxies]
    ids=[signature(p) for p in proxies]
    if len(set(names))!=len(names) or len(set(ids))!=len(ids):raise ValueError('Duplicate nodes')
    uris=SUB.read_text(encoding='utf-8').splitlines()
    if set(sub_names(uris))!=set(names):raise ValueError('Clash/subscription out of sync')
    groupnames={g['name'] for g in cfg.get('proxy-groups',[])}
    for group in cfg.get('proxy-groups',[]):
        for ref in group.get('proxies',[]):
            if ref not in names and ref not in groupnames and ref not in ('DIRECT','REJECT'):
                raise ValueError('Broken group reference')
    if not Path(CORE).is_file():raise RuntimeError('Mihomo binary unavailable')
    if not any(curl(target) for target in TARGETS):
        raise RuntimeError('Runner direct HTTPS probes failed: all results unknown')
    state=json.loads(HISTORY.read_text(encoding='utf-8')) if HISTORY.exists() else {'version':1,'nodes':{}}
    if state.get('version')!=1:raise ValueError('Unexpected history schema')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        checks=list(pool.map(check,enumerate(proxies)))
    failures=sum(x['status']=='FAILED_UNREACHABLE' for x in checks)
    correlated=len(proxies)>=5 and failures*4>=len(proxies)*3
    if correlated:
        for x in checks:
            if x['status']=='FAILED_UNREACHABLE':
                x['status']='UNKNOWN';x['attempts'].append('CORRELATED_FAILURE_GUARD')
    delete=[]
    for proxy,key,result in zip(proxies,ids,checks):
        item=state['nodes'].setdefault(key,{'name':proxy['name'],'records':[],'consecutive_failures':0})
        item['name']=proxy['name']
        item['records']=[r for r in item['records'] if r['cycle']!=cycle]
        item['records'].append({'cycle':cycle,'time':now.isoformat(),'run':URL,
                                'status':result['status'],'attempts':result['attempts']})
        item['records']=sorted(item['records'],key=lambda r:r['cycle'])[-12:]
        item['consecutive_failures']=streak(item['records'])
        if item['consecutive_failures']>=3:delete.append(proxy['name'])
    if delete and (len(delete)>=len(proxies) or len(delete)>len(proxies)//2):
        raise RuntimeError('Mass-deletion protection: no files written')
    if delete:
        drop=set(delete)
        cfg['proxies']=[p for p in proxies if p['name'] not in drop]
        for group in cfg.get('proxy-groups',[]):
            if 'proxies' in group:group['proxies']=[x for x in group['proxies'] if x not in drop]
        uris=[line for line in uris if line.strip() and urllib.parse.unquote(urllib.parse.urlsplit(line).fragment) not in drop]
        if set(sub_names(uris))!={p['name'] for p in cfg['proxies']}:
            raise ValueError('Pruning desynchronized subscriptions')
        CONFIG.write_text(yaml.safe_dump(cfg,sort_keys=False,allow_unicode=True),encoding='utf-8')
        SUB.write_text('\n'.join(uris)+'\n',encoding='utf-8')
    counts={x:sum(p['status']==x for p in checks) for x in ['PASS','FAILED_UNREACHABLE','UNKNOWN']}
    state.update(last_cycle=cycle,last_run=now.isoformat(),last_run_url=URL,
                 last_summary={'counts':counts,'correlated_guard':correlated,'removed':delete})
    HISTORY.parent.mkdir(parents=True,exist_ok=True)
    HISTORY.write_text(json.dumps(state,sort_keys=True,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary=f'Cycle {cycle}: {counts}, correlated={correlated}, removed={delete}; {URL}'
    print(summary,flush=True)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
            f.write('### Existing node health\n\n'+summary+'\n')
    if correlated:raise RuntimeError('Correlated failures, recorded as UNKNOWN; do not prune')

if __name__=='__main__':run()
