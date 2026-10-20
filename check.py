#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目自检：数据契约 + 产物完整性。

任何改动后跑一遍：
    python3 check.py
通过时输出 OK 并退出 0；失败时逐条列出原因并退出 1。
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

ALLOWED_BASES = {"daily", "weekly", "monthly", "snapshot", "life", None}
ESTIMATED_BASES = {"weekly", "monthly", "life"}

fails = []
warns = []


def fail(msg):
    fails.append(msg)


def warn(msg):
    warns.append(msg)


def load_json(path):
    if not path.exists():
        fail(f"{path.name} 不存在")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        fail(f"{path.name} 解析失败：{e}")
        return None


def check_latest():
    path = DATA / "latest.json"
    if not path.exists():
        # 全新克隆时本来就没有这个文件（它每次运行都会重写，不进版本库）
        warn("还没有采集数据（data/latest.json 不存在），先跑一次 python3 radar.py")
        return None
    latest = load_json(path)
    if latest is None:
        return None

    for key in ("generated_at", "date", "count", "repos"):
        if key not in latest:
            fail(f"latest.json 缺少顶层字段 {key}")

    repos = latest.get("repos") or []
    if not repos:
        fail("latest.json 的 repos 为空")
        return 0
    if latest.get("count") != len(repos):
        fail(f"count={latest.get('count')} 与 repos 实际数量 {len(repos)} 不一致")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(latest.get("date", ""))):
        fail(f"date={latest.get('date')!r} 不是 YYYY-MM-DD")

    seen = set()
    for r in repos:
        name = r.get("repo") or "<无 repo 字段>"

        if not re.fullmatch(r"[^/\s]+/[^/\s]+", str(name)):
            fail(f"{name}: repo 字段不是 owner/name 格式")
        if str(name).lower() in seen:
            fail(f"{name}: 重复条目")
        seen.add(str(name).lower())

        if not r.get("domain"):
            fail(f"{name}: 缺少 domain")

        momentum = r.get("momentum")
        if not isinstance(momentum, (int, float)) or not 0 <= momentum <= 100:
            fail(f"{name}: momentum={momentum!r} 不在 0-100")

        m = r.get("metrics") or {}
        rate_day = m.get("rate_day")
        if not isinstance(rate_day, (int, float)) or rate_day < 0:
            fail(f"{name}: rate_day={rate_day!r} 非法")

        basis = m.get("rate_basis")
        if basis not in ALLOWED_BASES:
            fail(f"{name}: rate_basis={basis!r} 不在允许集合 {sorted(x for x in ALLOWED_BASES if x)}")

        expected_est = basis in ESTIMATED_BASES
        if bool(m.get("estimated")) != expected_est:
            fail(f"{name}: estimated={m.get('estimated')!r} 与 "
                 f"rate_basis={basis!r} 不自洽（应为 {expected_est}）")

        accel = m.get("accel")
        if accel is not None and (not isinstance(accel, (int, float)) or accel <= 0):
            fail(f"{name}: accel={accel!r} 非法（应为 None 或正数）")

        hist = r.get("history")
        if hist is not None and not isinstance(hist, list):
            fail(f"{name}: history 不是数组")

    return len(repos)


def check_history():
    hist = load_json(DATA / "history.json")
    if hist is None:
        return
    if not isinstance(hist, dict):
        fail("history.json 顶层不是对象")
        return
    for key, entry in hist.items():
        pts = (entry or {}).get("points") or []
        if not isinstance(pts, list):
            fail(f"history[{key}]: points 不是数组")
            continue
        for i in range(1, len(pts)):
            try:
                prev, cur = pts[i - 1][1], pts[i][1]
            except (IndexError, TypeError):
                fail(f"history[{key}]: 第 {i} 个点格式不是 [date, stars]")
                break
            if isinstance(prev, int) and isinstance(cur, int) and cur < prev:
                warn(f"history[{key}]: star 在 {pts[i][0]} 从 {prev} 降到 {cur}"
                     f"（仓库被删除、转移或改名？）")
                break


def check_template():
    path = ROOT / "template.html"
    if not path.exists():
        fail("template.html 不存在")
        return
    text = path.read_text(encoding="utf-8")
    if "/*__DATA__*/{}" not in text:
        fail("template.html 里找不到数据占位符 /*__DATA__*/{}")
    if "<script src=" in text:
        fail("template.html 引入了外部脚本，看板必须自包含")
    if re.search(r"@import\s+url", text) or re.search(r"url\(\s*['\"]?https?://", text):
        fail("template.html 引入了外部样式/字体，看板必须自包含")


def check_dashboard(expected_count):
    path = ROOT / "dashboard.html"
    if not path.exists():
        warn("dashboard.html 还没生成（有数据后跑 python3 build_dashboard.py）")
        return
    html = path.read_text(encoding="utf-8")

    # 过期检测：模板或数据比产物新，说明改了东西没重新构建
    stamp = path.stat().st_mtime
    newer = [p.name for p in (ROOT / "template.html", DATA / "latest.json")
             if p.exists() and p.stat().st_mtime > stamp + 1]
    if newer:
        fail(f"dashboard.html 比 {', '.join(newer)} 旧，请重新构建"
             f"（python3 build_dashboard.py）")

    if "/*__DATA__*/{}" in html:
        fail("dashboard.html 里数据占位符没被替换，构建失败")
    if "const DATA = {" not in html:
        fail("dashboard.html 里找不到内联数据")
    if html.count("<script") != html.count("</script>"):
        fail("dashboard.html 的 script 标签不配对")
    if "<script src=" in html:
        fail("dashboard.html 引入了外部脚本，违反自包含约束")

    for bad in ("NaN", ">undefined<", "undefined%"):
        if bad in html:
            fail(f"dashboard.html 里出现 {bad!r}，渲染时有空值泄漏")

    m = re.search(r'"date":"(\d{4}-\d{2}-\d{2})"', html)
    if not m:
        fail("dashboard.html 里找不到日期字段")
    elif expected_count and f'"count":{expected_count}' not in html:
        warn(f"dashboard.html 的 count 与 latest.json（{expected_count}）不一致，"
             f"可能没重新构建")


def main():
    count = check_latest()
    check_history()
    check_template()
    check_dashboard(count)

    for w in warns:
        print(f"WARN  {w}")
    if fails:
        for f in fails:
            print(f"FAIL  {f}")
        print(f"\n{len(fails)} 项失败")
        sys.exit(1)

    if count is None:
        print("OK    尚未采集数据，只校验了模板（先跑 python3 radar.py）"
              + (f"（{len(warns)} 条提醒）" if warns else ""))
        return

    print(f"OK    {count} 个仓库，数据契约与产物均通过检查"
          + (f"（{len(warns)} 条提醒）" if warns else ""))


if __name__ == "__main__":
    main()
