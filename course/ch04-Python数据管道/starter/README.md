# 第 4 章 · 起始骨架（你要把它补完）

## 目录

```
starter/
├─ config/settings.yaml     配置（路径、阈值）
├─ .env.example             环境变量样例
├─ src/pipeline/
│   ├─ config.py            读配置            ← TODO
│   ├─ transform.py         纯函数：清洗/汇总/对账/异常   ← TODO（本章重点）
│   ├─ report.py            渲染 Markdown      ← TODO
│   └─ main.py              CLI + 日志 + 退出码 ← TODO
├─ tests/test_pipeline.py   9 个断言，先看它再写代码
├─ output/                  产物（运行时生成）
└─ logs/                    日志（运行时生成）
```

## 怎么开始

```bash
cd starter
python -m unittest discover -s tests -v      # 先看 9 个测试怎么挂的
python -m pipeline.main --help               # 再看 CLI 长什么样
```

## 规则

1. 先让测试全绿，再谈优化。**测试就是验收标准。**
2. `transform.py` 里不许出现 `open()`——纯函数才好测。
3. 不许改 `tests/test_pipeline.py`（那是验收标准；除非你发现它写错了，来问我）。
4. 每完成一个函数就 `python -m unittest` 跑一次。

## 数据从哪来

配置里指向第 3 章的数据集：`../../ch03-数据接入与对账/data/raw`。
所以你**必须先把第 3 章的对账逻辑搞明白**，这章只是把它工程化。

## 参考实现

在 `../答案与批改要点.md` 里（做完再看）。
