# CLAUDE.md

本项目的完整协作说明在 **`AGENTS.md`**，先读它。这里只放 Claude Code 需要额外注意的事项。

## 硬约束

- `dashboard.html` 是生成物，**不要直接编辑**。改 `template.html` 后跑 `python3 build_dashboard.py`。
- 不要删除或重写 `data/history.json`（项目唯一的长期资产）。
- 指标口径不能"美化"：缺数据就留空，推算值必须带 `estimated: true`。
- 看板必须保持自包含（无 CDN、无外部请求），因为要在 `file://` 下打开。

## 常用命令

```bash
python3 radar.py              # 采集 + 生成看板（~60-90 秒）
python3 build_dashboard.py    # 只重建看板（秒级，改完 template 用这个）
python3 check.py              # 自检，任何改动后必跑
```

## 工作方式

改多文件前先给出计划再动手。改完 UI 要用真实截图确认桌面（1440）、平板（1024）、手机（390）三档没有溢出或列错位——这个项目已经修过两轮网格对齐问题，只看代码容易漏。

改数据层（`radar.py`）要完整跑一次采集；改表现层（`template.html`）只需重建看板。

交付时说明：改了哪一层、数据契约有没有变、做了什么验证。
