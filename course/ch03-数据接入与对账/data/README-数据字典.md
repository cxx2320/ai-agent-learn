# 第 3 章数据集 · 数据字典

> 这套数据模拟一家做 **Amazon 美国站** 的跨境公司 2026 年 11 月的经营数据。
> 不是真实数据，但**字段名、时区、口径、脏数据的形态**都按真实后台报表设计。

---

## ⚠️ 先读这一段

**这份数据是脏的。** 现实里从后台导出的报表从来不会干净，所以我在里面埋了**若干类真实世界最常见的"对不上"**，包括（不限于）：

- 时区不一致
- 取消单、重复抓取
- 缺失值、0 分母
- 重复入账
- 口径不一致（同一件事两套算法）
- 期末未入账

**你的任务不是假设数据是对的，而是找出它们为什么不对。**
如果某个数怎么算都对不上，先怀疑口径和时区，再怀疑自己写错了 SQL。

---

## 文件清单

| 文件 | 行数 | 粒度 | 时区 |
|---|---|---|---|
| `products.csv` | 6 | 一个 ASIN 一行 | — |
| `fx_rate.csv` | 30 | 日 | — |
| `business_report_us.csv` | 180 | ASIN × 日 | **站点时区（PST）** |
| `ads_campaign_daily.csv` | 120 | campaign × 日 | **站点时区（PST）** |
| `ads_search_term_weekly.csv` | 67 | 关键词 × 周 | 站点时区 |
| `erp_orders.csv` | 2031 | 订单行 | **北京时间（UTC+8）** |
| `settlement_detail.csv` | 6071 | 交易流水 | **UTC** |
| `returns.csv` | 51 | 退货单 | 站点时区 |
| `inventory_snapshot.csv` | 6 | ASIN 快照 | — |

> 三个时区同时存在，这就是跨境数据的日常。

---

## 1. products.csv — 商品主数据

| 字段 | 含义 | 备注 |
|---|---|---|
| `asin` | 子体 ASIN | 一个颜色/规格一行 |
| `parent_asin` | 父体 ASIN | 同款不同色挂在同一父体 |
| `sku` | 内部编码 | **注意：可能存在空值** |
| `title_cn` | 中文品名 | |
| `category` | 平台类目 | 决定佣金率 |
| `price_usd` | 标价 | 实际成交价可能因促销不同 |
| `commission_rate` | **配置的**佣金率 | 配置值 ≠ 实际扣费值 |
| `unit_cost_cny` | 采购成本（人民币） | |
| `first_launch_date` | 上架日 | 判断新品/老品 |

---

## 2. business_report_us.csv — 业务报告（流量与转化）

| 字段 | 含义 | 备注 |
|---|---|---|
| `report_date` | 站点日期 | **PST**，不是北京时间 |
| `asin` | 子体 | |
| `sessions` | 访问会话数 | 可能为 0 但仍有订单（数据异常） |
| `page_views` | 页面浏览数 | 一个 session 可多个 view |
| `units_ordered` | 下单件数 | **不含取消单** |
| `ordered_product_sales_usd` | 商品销售额 | **未扣退款、未扣佣金、未税** |
| `units_refunded` | 退款件数 | 按**下单日**归集，不是退款发生日 |
| `refund_amount_usd` | 退款金额 | 同上 |
| `buy_box_pct` | 购物车占有率 | **可能为空** |

**这份报表回答"卖了多少"，不回答"收到多少钱"。**

---

## 3. ads_campaign_daily.csv — 广告活动日报

| 字段 | 含义 |
|---|---|
| `report_date` | 站点日期 |
| `campaign_name` | 广告活动名 |
| `asin` | 主推 ASIN（品牌广告可能挂父体） |
| `impressions / clicks` | 曝光 / 点击 |
| `spend_usd` | 花费 |
| `ad_sales_usd` | 广告销售额（**归因窗口内**） |
| `ad_orders` | 广告订单数 |

**注意**：`ad_sales_usd` 是归因结果，会随时间回溯变化，且同一笔订单**可能被多个 campaign 重复归因**。
所以 `Σ ad_sales` 与业务报告销售额**不相等，也不应该相等**。

---

## 4. ads_search_term_weekly.csv — 搜索词周报（广告优化的核心素材）

| 字段 | 含义 |
|---|---|
| `week_start` / `week_end` | 周区间 |
| `campaign_name` | 归属活动 |
| `keyword` | 用户实际搜索词 |
| `match_type` | exact / phrase / broad |
| `impressions / clicks` | 曝光 / 点击 |
| `spend_usd` | 花费 |
| `ad_sales_usd` | 该词的广告销售额 |
| `ad_orders` | 该词的广告订单 |

**这份数据只有 SP-Auto-WR 一个活动**，且覆盖了该活动约 90% 的花费（其余是商品投放/无搜索词的曝光）。

> 用它找「花了很多钱但一单没出」的词 —— 这是第 2 章场景 B 的真实素材。

---

## 5. erp_orders.csv — ERP 订单（订单级）

| 字段 | 含义 | 备注 |
|---|---|---|
| `order_id` | 平台订单号 | **与结算单可关联** |
| `purchase_date_bj` | 下单时间 | **北京时间** ⚠️ |
| `sku` | 内部编码 | 可能为空 |
| `asin` | 商品 | |
| `quantity` | 件数 | |
| `amount_cny` | 金额（人民币） | 已按 7.12 换算 |
| `status` | shipped / pending / cancelled | **取消单也在里面** |
| `channel` | 渠道 | |

---

## 6. settlement_detail.csv — 结算单（钱的实际流动）

| 字段 | 含义 |
|---|---|
| `transaction_id` | 交易流水号 |
| `posted_date_utc` | 入账日期，**UTC** |
| `settlement_id` | 结算周期编号 |
| `transaction_type` | ProductSales / Commission / FBAFulfillmentFee / Refund / ServiceFee |
| `order_id` | 关联订单（服务费类可能为空） |
| `asin` / `sku` | 商品 |
| `quantity` | 件数 |
| `amount_usd` | 金额，**收入为正、支出为负** |
| `description` | 说明 |

### transaction_type 说明

| 类型 | 方向 | 说明 |
|---|---|---|
| `ProductSales` | + | 买家实付（本金） |
| `Commission` | − | 平台佣金 |
| `FBAFulfillmentFee` | − | FBA 配送费 |
| `Refund` | − | 退款（按**退款发生日**入账） |
| `ServiceFee` | − | 广告费 + 月度仓储费 |

**这份表是财务的唯一真相来源（现金流口径）。**

---

## 7. returns.csv — 退货明细

| 字段 | 含义 |
|---|---|
| `return_date` | 退货发生日 |
| `order_id` | 关联单号（`REF-` 开头，非原订单号） |
| `asin` | 商品 |
| `quantity` | 件数 |
| `reason` | 退货原因（英文原文，**未归类**） |
| `refund_amount_usd` | 退款金额 |

> 原因字段是自由文本，直接统计会有 8 个类别。真实场景里可能有几十种写法 —— 这是第 6 章做文本归类需求的源头。

---

## 8. inventory_snapshot.csv — 库存快照

| 字段 | 含义 |
|---|---|
| `snapshot_date` | 快照日 |
| `available_qty` | 可售库存 |
| `inbound_qty` | 在途库存 |
| `reserved_qty` | 已预留（未发货） |
| `units_7d_avg` | 近 7 日日均销量 |
| `doi` | 可售天数 = available / 7日均销 |

---

## 怎么把它变成数据库

```bash
python load.py          # 生成 crossborder.db（SQLite）
```

然后：

```bash
sqlite3 crossborder.db      # 或 DBeaver / DB Browser 打开
```

建表语句、字段类型、以及一条示例查询都在 `load.py` 里。

---

## 建议先做的三件事

1. 把 9 张表都 `SELECT * LIMIT 5` 看一遍，习惯字段名。
2. 算三个总数：业务报告销售额、结算净额、ERP 有效件数。**它们一定对不上**。
3. 写下你对不上的 3 个猜测，再逐个用 SQL 验证。
