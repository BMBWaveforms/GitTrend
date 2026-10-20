#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把采集结果内联进 template.html，产出自包含看板。"""

import json
import sys
from pathlib import Path


def build(payload, out_path):
    here = Path(__file__).resolve().parent
    tpl = (here / "template.html").read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("</", "<\\/")
    stamp = "/*__DATA__*/{}"
    if stamp not in tpl:
        raise RuntimeError("template.html 里找不到数据占位符")
    html = tpl.replace(stamp, data)
    out_path = Path(out_path)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def find_payload(here: Path):
    """优先用 latest.json，其次用最新的一份按日归档。都没有就说明还没采集过。"""
    latest = here / "data" / "latest.json"
    if latest.exists():
        return json.loads(latest.read_text(encoding="utf-8"))
    snaps = sorted((here / "data" / "snapshots").glob("*.json"))
    if snaps:
        print(f"latest.json 不存在，回退到归档快照 {snaps[-1].name}", file=sys.stderr)
        return json.loads(snaps[-1].read_text(encoding="utf-8"))
    print(
        "没有可用的采集数据。\n"
        "这个仓库不跟踪 data/latest.json（每次运行都会重写），先跑一次采集：\n\n"
        "    python3 radar.py\n\n"
        "它会顺便把看板也生成出来。",
        file=sys.stderr,
    )
    raise SystemExit(1)


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    payload = find_payload(here)
    print(build(payload, here / "dashboard.html"))
