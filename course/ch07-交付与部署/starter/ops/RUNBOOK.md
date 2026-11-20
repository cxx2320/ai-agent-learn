# 运维手册（Runbook）· 多站点日报管道

> **写作标准**：半夜三点、脑子不清醒、没参与开发的人，照着做也能恢复。
> 每一条都要能直接执行，不写"检查一下""确认是否正常"这种没法操作的话。

---

## 0. 一分钟判断

```powershell
cd starter
.\deploy\run_daily.ps1 -Date 2026-11-18
```

看最后一行 `=== 结束 exit=N ===`：

| 退出码 | 含义 | 下一步 |
|---|---|---|
| 0 | 正常 | 看 `output/report.md` 抽查 3 个数 |
| 1 | 部分失败（有异常清单） | 看 §2 |
| 2 | 致命（无产物） | 看 §1 |

---

## 1. 任务没跑 / 一上来就 exit=2

### 1.1 先确认它到底有没有被触发

```powershell
Get-ScheduledTask -TaskName DailyReport | Get-ScheduledTaskInfo
```
看 `LastRunTime` 和 `LastTaskResult`。

- `LastRunTime` 是昨天 → **触发没生效**（见 1.3）
- `LastRunTime` 是今天但 `LastTaskResult` 非 0 → 跑了但失败（见 1.2）

### 1.2 手动跑一次，看第一处报错

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\run_daily.ps1 -Date <日期>
```

对照健康检查输出定位：

| 健康检查说 | 原因 | 处置 |
|---|---|---|
| 找不到 business_report_us.csv | 上游没出报表 | 联系运营确认后台下载 |
| 数据新鲜度：最新数据 < 期望 | 数据是旧的 | 重新下载该日期报表 |
| 产物不存在 / 过小 | 管道中途崩了 | 看 `logs/run-*.log` 最后 30 行 |
| 磁盘空间不足 | 日志堆积 | 清理 30 天前的日志 |

### 1.3 触发没生效的三个常见原因

1. 任务计划里写的是**用户密码登录**，密码改过 → 重新输入密码
2. 机器重启后没登录 → 改成"不管用户是否登录都运行"
3. `WorkingDirectory` 没设 → 相对路径全错（本项目已显式指定）

---

## 2. exit=1：产物有，但有异常

打开 `output/anomalies.csv`，按 `severity` 排序：

```powershell
Import-Csv output\anomalies.csv | Sort-Object severity | Format-Table -AutoSize
```

| 异常类型 | 通常含义 | 谁来处理 |
|---|---|---|
| `duplicate_transaction` | 结算重复入账（已自动去重） | 记录，月底找财务核 |
| `sessions_zero` | 埋点异常 | 你（数据侧） |
| `unmapped_sku` | SKU 缺失，订单映射不上 | 运营补档 |
| `high_refund_rate` | 单品退款率超阈值 | 产品/供应链 |
| `low_doi` | 库存周转低于 7 天 | 供应链补货 |

**注意**：exit=1 时产物**是可用的**，先发给业务，再处理异常。

---

## 3. 数字不对（业务说"跟我后台对不上"）

按这个顺序查，**不要跳步**：

1. **日期口径**：业务看的是站点时区还是北京时间？（差 16 小时）
2. **退款口径**：后台销售额是**未扣退款**的毛额，你发的是净额吗？
3. **数据源行数**：`logs/run-*.log` 里 `数据源行数：business=...`，和上次比有没有突变
4. **对账桥**：`output/report.md` 的"对账"段，哪一项异常（佣金/配送费/广告/仓储/退款时点差）
5. **抽 3 个 ASIN** 手工与后台核对，确认是"全错"还是"某个 ASIN 错"

> 全错 → 口径问题；个别错 → 数据问题。

---

## 4. 单日跑为什么对账不平（不是故障）

**现象**：`--start=--end=<某一天>` 时残差巨大（几万），月度跑却是 0。

**原因**：结算单是**滚动账本**，入账比下单晚约 2 天。
单日区间里，分子只有 1 天业务数据，而结算流水覆盖了前后几天。

**正确做法**：
- 日报：只报业务指标，**跳过对账**（`--skip-reconcile`）
- 对账：**按周或按月**跑，或改用"订单级匹配"而不是"日期口径"

**不要做的事**：把容差调大到能过——那等于把检查关掉。

---

## 5. 磁盘满 / 日志太大

```powershell
# 看占用
Get-ChildItem logs,output -Recurse | Measure-Object -Property Length -Sum
# 删 30 天前的日志
Get-ChildItem logs\*.log | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item
```

**保留策略建议**：日志 30 天，产物 90 天（对账要回溯）。

---

## 6. 回滚

```powershell
# 1. 找到上一个能跑的版本
git tag                      # 或看 deploy 目录里的备份
# 2. 切回去
git checkout v0.2
# 3. 立刻跑一次验证
.\deploy\run_daily.ps1 -Date <出问题那天>
```

**回滚验证标准**：健康检查 exit=0，且日期正确。

---

## 7. 联系方式

| 角色 | 谁 | 什么时候找 |
|---|---|---|
| 管道负责人 | （填） | exit=2 且你自己搞不定 |
| 数据源负责人 | （填） | 上游报表没出 |
| 业务确认人 | （填） | 数字口径有分歧 |

> 交接时请把这张表填满。**没人负责的告警等于没有告警。**
