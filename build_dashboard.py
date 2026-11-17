#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把采集结果内联进 template.html，产出自包含看板。"""

import base64
import json
import sys
from pathlib import Path


def build(payload, out_path):
    here = Path(__file__).resolve().parent
    tpl = (here / "template.html").read_text(encoding="utf-8")
    summaries_path = here / "data" / "project_summaries_zh.json"
    summaries = json.loads(summaries_path.read_text(encoding="utf-8")) if summaries_path.exists() else {}
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("</", "<\\/")
    stamp = "/*__DATA__*/{}"
    if stamp not in tpl:
        raise RuntimeError("template.html 里找不到数据占位符")
    summaries_stamp = "/*__SUMMARIES__*/{}"
    if summaries_stamp not in tpl:
        raise RuntimeError("template.html 里找不到中文说明占位符")
    summaries_json = json.dumps(summaries, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace(stamp, data).replace(summaries_stamp, summaries_json)
    avatars_stamp = "/*__AVATARS__*/{}"
    if avatars_stamp not in tpl:
        raise RuntimeError("template.html 里找不到项目头像占位符")
    avatars = json.loads((here / "assets" / "project-avatars.json").read_text(encoding="utf-8"))
    for entry in avatars.values():
        image_path = (here / entry["src"]).resolve()
        if not image_path.is_relative_to((here / "assets" / "project-avatars").resolve()):
            raise RuntimeError("项目头像路径超出素材目录")
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        entry["src"] = f'data:{entry["mime"]};base64,{encoded}'
    avatars_json = json.dumps(avatars, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace(avatars_stamp, avatars_json)
    icon = here / "assets" / "star-3d.png"
    icon_data = "data:image/png;base64," + base64.b64encode(icon.read_bytes()).decode("ascii")
    icon_src = 'src="assets/star-3d.png"'
    if icon_src not in html:
        raise RuntimeError("template.html 里找不到星星素材引用")
    html = html.replace(icon_src, f'src="{icon_data}"')
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
