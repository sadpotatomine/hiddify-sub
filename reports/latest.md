# 节点库维护运行报告

- 批次：`batch-20261022-044941-689036-r1`
- 报告时间（北京时间）：2026-10-22T05:22:43.761852+08:00
- 状态：complete；结果：published
- 异常类型：无；运行阶段：publish
- 合格新增：1；移除：1
- 当前节点数：18
- 订阅远端字节校验：True
- 节点订阅内容发生变化：True

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
    "passed": 5
  },
  "deep.json": {
    "count": 17,
    "passed": 15,
    "incomplete_downloads": 0
  }
}
```
