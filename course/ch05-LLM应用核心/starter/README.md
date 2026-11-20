# 第 5 章 · 起始骨架

```
starter/
├─ data/products.csv        8 个产品（真实感的输入）
├─ prompts/listing_v1.txt   prompt 模板（带硬性要求）
├─ src/listing/
│   ├─ schema.py            校验 + JSON 容错解析      ← TODO
│   ├─ llm.py               模型层（mock / real 双模式）← TODO
│   ├─ prompt.py            模板加载与组装            ← TODO
│   ├─ evaluate.py          规则评分与汇总            ← TODO
│   └─ main.py              CLI + 批量 + 报告          ← TODO
├─ tests/test_listing.py    9 个验收测试（不联网）
└─ run.py                   零安装入口
```

## 快速开始

```bash
cd starter
python run.py --help
python -m unittest discover -s tests -v
```

## 三条规则

1. **先让 9 个测试全绿，再碰真实 API。** 测试全用 mock，不花钱。
2. 不许改 `tests/test_listing.py`（它是验收标准）。
3. `--mock` 必须**幂等**：同样输入两次输出必须一样（方便做快照对比）。

## 没有 API Key 也能学完这一章

`--mock` 模式不联网。真实调用是**可选项**（任务 6）。

参考实现在 `../答案与批改要点.md`。
