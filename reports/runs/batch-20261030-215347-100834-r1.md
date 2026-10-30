# 节点库维护运行报告

- 批次：`batch-20261030-215347-100834-r1`
- 报告时间（北京时间）：2026-10-31T03:03:17.528176+08:00
- 状态：failed；结果：unknown
- 异常类型：CalledProcessError；运行阶段：publish
- 合格新增：0；移除：0
- 当前节点数：20
- 订阅远端字节校验：False
- 节点订阅内容发生变化：False

运行方式：Python + sing-box，无需 AI 账号。每完成 5 轮后休息 1 小时，再继续。

质量门槛：连通性检查、完整下载、间隔复测和稳定性检查；无合格候选时不追加。本次通过检查不代表节点全天可用。历史报告保存在 reports/runs/。

检查统计（详情见同目录 JSON）：

```json
{
  "candidates.json": {
    "count": 200,
    "passed": 0
  },
  "screen.json": {
    "count": 200,
    "passed": 2
  },
  "deep.json": {
    "count": 10,
    "passed": 10,
    "incomplete_downloads": 0
  }
}
```
