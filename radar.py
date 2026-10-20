#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Trend Radar — 个人向趋势雷达

采集三层信号：
  1. GitHub Trending 页面（daily / weekly / monthly，全站 + 分语言 + 中文圈）
  2. GitHub Search API（新建仓库的爆发式增长）
  3. Hacker News（讨论热度，判断是真人关注还是刷 star）

输出 data/latest.json + data/history.json，并生成自包含的 dashboard.html。

用法:
    python3 radar.py                 # 采集 + 生成看板
    python3 radar.py --no-hn         # 跳过 HN（更快）
    python3 radar.py --token ghp_xx  # 提高 API 限额

环境变量 GITHUB_TOKEN 也可用，未设置时走匿名限额（够用）。
"""

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# ---------------------------------------------------------------- 领域分类规则

DOMAINS = [
    ("AI Agent", [
        "agent", "agentic", "mcp", "multi-agent", "autogen", "swarm", "workflow automation",
        "claude code", "codex", "copilot", "assistant", "browser-use", "computer-use",
        "tool calling", "function calling", "rag", "记忆", "智能体", "工作流",
    ]),
    ("LLM 应用", [
        "llm", "gpt", "chatbot", "prompt", "langchain", "llamaindex", "inference", "vllm",
        "fine-tun", "finetun", "embedding", "vector", "大模型", "对话", "问答", "推理",
    ]),
    ("模型 / 训练", [
        "diffusion", "transformer", "training", "pytorch", "tensor", "cuda", "quantization",
        "dataset", "tokenizer", "multimodal", "vision model", "speech", "tts", "ocr",
        "训练", "模型", "微调", "数据集",
    ]),
    ("AI 基建", [
        "gpu", "inference server", "serving", "mlops", "observability for llm", "eval",
        "benchmark", "sandbox", "model serving", "算力", "推理服务",
    ]),
    ("开发工具", [
        "cli", "ide", "editor", "terminal", "shell", "linter", "formatter", "debugger",
        "build system", "bundler", "testing", "devtool", "developer tool", "code review",
        "编辑器", "开发工具", "终端", "代码",
    ]),
    ("数据 / 数据库", [
        "database", "sql", "postgres", "sqlite", "clickhouse", "duckdb", "query engine",
        "etl", "data pipeline", "olap", "stream processing", "kafka", "数据库", "数据",
    ]),
    ("云原生 / 基础设施", [
        "kubernetes", "k8s", "docker", "container", "terraform", "serverless", "proxy",
        "gateway", "mesh", "devops", "ci/cd", "observability", "monitoring", "云原生", "运维",
    ]),
    ("前端 / Web", [
        "react", "vue", "svelte", "next.js", "nextjs", "tailwind", "css", "frontend",
        "browser", "web app", "ui library", "component", "前端", "组件",
    ]),
    ("移动 / 跨端", [
        "ios", "android", "flutter", "react native", "swiftui", "kotlin", "mobile app",
        "移动端", "客户端",
    ]),
    ("安全", [
        "security", "vulnerability", "pentest", "exploit", "malware analysis", "cve",
        "encryption", "auth", "zero trust", "安全", "漏洞", "加密",
    ]),
    ("效率 / 个人工具", [
        "productivity", "note", "notes", "knowledge base", "second brain", "todo",
        "calendar", "rss", "automation", "personal", "效率", "笔记", "自动化",
    ]),
    ("学习资源", [
        "awesome", "tutorial", "course", "roadmap", "interview", "book", "guide",
        "cheatsheet", "examples", "教程", "学习", "面试", "指南",
    ]),
    ("音视频 / 图形", [
        "video", "audio", "ffmpeg", "image", "svg", "3d", "render", "game engine",
        "shader", "视频", "音频", "图像", "游戏",
    ]),
    ("区块链 / Web3", [
        "blockchain", "ethereum", "solana", "smart contract", "defi", "nft", "web3",
        "钱包", "链上",
    ]),
]


def classify(name: str, desc: str, language: str, fallback_topics=None) -> str:
    text = f"{name} {desc} {' '.join(fallback_topics or [])}".lower()
    best, best_hits = "其他", 0
    for domain, keys in DOMAINS:
        hits = sum(1 for k in keys if k in text)
        if hits > best_hits:
            best, best_hits = domain, hits
    return best


# ---------------------------------------------------------------- 工具函数

def num(s):
    """'58,119' -> 58119 ; '1.2k' -> 1200"""
    if s is None:
        return None
    s = s.strip().replace(",", "").replace(" ", "")
    m = re.match(r"^([\d.]+)\s*([kKmM]?)$", s)
    if not m:
        return None
    v = float(m.group(1))
    unit = m.group(2).lower()
    if unit == "k":
        v *= 1_000
    elif unit == "m":
        v *= 1_000_000
    return int(v)


def get(url, **kw):
    kw.setdefault("timeout", 25)
    kw.setdefault("headers", {})
    kw["headers"].setdefault("User-Agent", UA)
    kw["headers"].setdefault("Accept", "text/html,application/xhtml+xml")
    return requests.get(url, **kw)


# ---------------------------------------------------------------- 1. Trending 页面

TRENDING_TARGETS = [
    # (url_suffix, 采集窗口标签)
    ("since=daily", "daily"),
    ("since=weekly", "weekly"),
    ("since=monthly", "monthly"),
    ("language=python&since=weekly", "weekly"),
    ("language=typescript&since=weekly", "weekly"),
    ("language=rust&since=weekly", "weekly"),
    ("language=go&since=weekly", "weekly"),
    ("language=c%2B%2B&since=weekly", "weekly"),
    ("language=jupyter+notebook&since=weekly", "weekly"),
    ("spoken_language_code=zh&since=weekly", "weekly"),
]


def parse_trending(html: str, window: str):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for art in soup.select("article.Box-row"):
        h2 = art.select_one("h2 a")
        if not h2 or not h2.get("href"):
            continue
        full = h2["href"].strip("/")
        if full.count("/") != 1:
            continue

        desc_el = art.select_one("p")
        desc = desc_el.get_text(" ", strip=True) if desc_el else ""
        lang_el = art.select_one("span[itemprop='programmingLanguage']")
        language = lang_el.get_text(strip=True) if lang_el else ""

        stars = forks = None
        for a in art.select("a"):
            href = a.get("href", "")
            if href.endswith("/stargazers"):
                stars = num(a.get_text(strip=True))
            elif href.endswith("/forks"):
                forks = num(a.get_text(strip=True))

        text = art.get_text(" ", strip=True)
        m = re.search(r"([\d,]+)\s+stars?\s+(today|this week|this month)", text)
        gained = num(m.group(1)) if m else None

        contributors = len(art.select("a[href^='/'][data-hovercard-type='user']"))

        out.append({
            "repo": full,
            "desc": desc,
            "language": language,
            "stars": stars,
            "forks": forks,
            "gained": gained,
            "window": window,
            "contributors": contributors,
        })
    return out


def collect_trending():
    seen = {}
    detail = {}
    for suffix, window in TRENDING_TARGETS:
        url = f"https://github.com/trending?{suffix}"
        try:
            r = get(url)
            if r.status_code != 200:
                print(f"  ! trending {suffix} -> {r.status_code}", file=sys.stderr)
                continue
            items = parse_trending(r.text, window)
        except Exception as e:
            print(f"  ! trending {suffix} 失败: {e}", file=sys.stderr)
            continue

        for it in items:
            key = it["repo"]
            if key not in seen:
                seen[key] = {
                    "repo": key,
                    "desc": it["desc"],
                    "language": it["language"],
                    "stars": it["stars"],
                    "forks": it["forks"],
                    "contributors": it["contributors"],
                    "windows": [],
                }
            rec = seen[key]
            rec["windows"].append(it["window"])
            rec.setdefault("gain", {})
            if it["gained"]:
                # 同一窗口可能多次出现，取最大值
                rec["gain"][it["window"]] = max(rec["gain"].get(it["window"], 0), it["gained"])
            # 描述/star 数补全（有的窗口缺字段）
            if not rec.get("desc") and it["desc"]:
                rec["desc"] = it["desc"]
            if not rec.get("stars") and it["stars"]:
                rec["stars"] = it["stars"]
            if not rec.get("language") and it["language"]:
                rec["language"] = it["language"]
            detail.setdefault(it["window"], 0)
            detail[it["window"]] += 1
        print(f"  · trending[{window}] {suffix}: {len(items)} 条")
        time.sleep(0.6)
    print(f"  · trending 合计去重: {len(seen)} 个仓库")
    return list(seen.values())


# ---------------------------------------------------------------- 2. Search API：新仓库

SEARCH_QUERIES = [
    # (query, 标签, 每页条数)
    ("created:>{d30} stars:>400", "30 天内爆发", 40),
    ("created:>{d90} stars:>1500", "90 天新贵", 40),
]


def collect_new_repos(token=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": UA}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    today = datetime.now(timezone.utc).date()
    out = {}
    for q_tpl, label, per_page in SEARCH_QUERIES:
        q = q_tpl.format(
            d30=(today - timedelta(days=30)).isoformat(),
            d90=(today - timedelta(days=90)).isoformat(),
        )
        url = "https://api.github.com/search/repositories"
        try:
            r = requests.get(url, params={"q": q, "sort": "stars", "order": "desc",
                                          "per_page": per_page},
                             headers=headers, timeout=25)
            if r.status_code != 200:
                print(f"  ! search({label}) -> {r.status_code} {r.text[:120]}", file=sys.stderr)
                continue
            items = r.json().get("items", [])
        except Exception as e:
            print(f"  ! search({label}) 失败: {e}", file=sys.stderr)
            continue

        for it in items:
            out[it["full_name"].lower()] = {
                "repo": it["full_name"],
                "desc": it.get("description") or "",
                "language": it.get("language") or "",
                "stars": it.get("stargazers_count"),
                "forks": it.get("forks_count"),
                "topics": it.get("topics") or [],
                "created_at": (it.get("created_at") or "")[:10],
                "pushed_at": (it.get("pushed_at") or "")[:10],
                "open_issues": it.get("open_issues_count"),
                "homepage": it.get("homepage") or "",
                "source": label,
            }
        print(f"  · search[{label}]: {len(items)} 条")
        time.sleep(2.5)  # 匿名 search 限额 10/min
    return out


# ---------------------------------------------------------------- 3. Hacker News

def hn_lookup(repo: str):
    """返回该仓库在 HN 的讨论热度（近 60 天）。"""
    name = repo.split("/")[-1]
    url = "https://hn.algolia.com/api/v1/search"
    params = {
        "query": name,
        "tags": "story",
        "hitsPerPage": 20,
        "numericFilters": f"created_at_i>{int(time.time()) - 60*86400}",
    }
    try:
        r = requests.get(url, params=params, timeout=15,
                         headers={"User-Agent": UA})
        if r.status_code != 200:
            return None
        hits = r.json().get("hits", [])
    except Exception:
        return None

    rel = [h for h in hits
           if name.lower() in (h.get("title") or "").lower()
           or name.lower() in (h.get("url") or "").lower()]
    if not rel:
        return {"mentions": 0, "points": 0, "comments": 0, "top": None}
    top = max(rel, key=lambda h: (h.get("points") or 0))
    return {
        "mentions": len(rel),
        "points": sum(h.get("points") or 0 for h in rel),
        "comments": sum(h.get("num_comments") or 0 for h in rel),
        "top": {
            "title": top.get("title"),
            "points": top.get("points"),
            "comments": top.get("num_comments"),
            "url": top.get("url") or f"https://news.ycombinator.com/item?id={top.get('objectID')}",
        },
    }


# ---------------------------------------------------------------- 4. 元数据富化

def enrich_meta(repos, token=None, limit=30):
    """Trending 页面不给创建时间。用 repo API 补，结果落缓存，只补一次。
    匿名 60 次/小时，所以默认只补动量最高的一批。"""
    cache_p = DATA / "repos_meta.json"
    cache = {}
    if cache_p.exists():
        try:
            cache = json.loads(cache_p.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    headers = {"Accept": "application/vnd.github+json", "User-Agent": UA}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for r in repos:
        meta = cache.get(r["repo"].lower())
        if meta and not r.get("created_at"):
            r.update(meta)
            if meta.get("topics") and not r.get("topics"):
                r["topics"] = meta["topics"]

    need = [r for r in repos if not r.get("created_at")]
    need.sort(key=lambda x: x.get("momentum", 0), reverse=True)
    fetched = skipped = 0
    for r in need:
        if fetched + skipped >= limit:
            break
        key = r["repo"].lower()
        if key in cache:
            continue
        try:
            resp = requests.get(f"https://api.github.com/repos/{r['repo']}",
                                headers=headers, timeout=20)
        except Exception:
            skipped += 1
            continue
        if resp.status_code == 200:
            j = resp.json()
            meta = {
                "created_at": (j.get("created_at") or "")[:10],
                "stars": j.get("stargazers_count"),
                "forks": j.get("forks_count"),
                "topics": j.get("topics") or [],
                "homepage": j.get("homepage") or "",
            }
            cache[key] = meta
            r.update({k: v for k, v in meta.items() if v not in (None, "", [])})
            fetched += 1
        elif resp.status_code in (403, 429):
            print("  · GitHub API 限额用尽，本轮停止富化（下次运行会继续）", file=sys.stderr)
            break
        else:
            skipped += 1
        time.sleep(0.2)

    cache_p.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"  · 富化 {fetched} 个仓库（缓存共 {len(cache)}）")


# ---------------------------------------------------------------- 5. 历史快照

def load_history():
    p = DATA / "history.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def update_history(history, repos, today):
    for r in repos:
        key = r["repo"].lower()
        h = history.setdefault(key, {"points": []})
        if r.get("stars"):
            pts = h["points"]
            if pts and pts[-1][0] == today:
                pts[-1][1] = max(pts[-1][1], r["stars"])
            else:
                pts.append([today, r["stars"]])
    return history


def snapshot_gain(history, key, days):
    """取 N 天前的快照与本日快照的差值。"""
    h = history.get(key, {}).get("points", [])
    if len(h) < 2:
        return None
    today = datetime.strptime(h[-1][0], "%Y-%m-%d").date()
    target = today - timedelta(days=days)
    # 找最接近 target 且不晚于它的点
    cand = [p for p in h[:-1] if datetime.strptime(p[0], "%Y-%m-%d").date() <= target]
    if not cand:
        cand = h[:-1]
    if not cand:
        return None
    base = cand[-1]
    gap = (today - datetime.strptime(base[0], "%Y-%m-%d").date()).days
    if gap <= 0:
        return None
    delta = h[-1][1] - base[1]
    if delta <= 0:
        return None
    # 归一到每天
    return round(delta / gap, 1), gap


# ---------------------------------------------------------------- 5. 打分

def enrich(repos):
    today = datetime.now(timezone.utc).date()
    for r in repos:
        created = r.get("created_at")
        if created:
            try:
                r["age_days"] = (today - datetime.strptime(created, "%Y-%m-%d").date()).days
            except Exception:
                r["age_days"] = None
        else:
            r["age_days"] = None
        r["domain"] = classify(r["repo"], r.get("desc", ""), r.get("language", ""),
                               r.get("topics"))
    return repos


def score(r):
    # 新项目首发热度：生命期日均 star
    if r.get("age_days") is not None and r["age_days"] > 0 and r.get("stars"):
        r["stars_per_day_life"] = round(r["stars"] / max(r["age_days"], 1), 1)
    else:
        r["stars_per_day_life"] = None

    gain = r.get("gain") or {}
    day = gain.get("daily")
    week = gain.get("weekly")
    month = gain.get("monthly")

    # 每日速率：优先用 trending 自带的当日增量，其次 7 日/30 日均值，
    # 再次本地快照差；都没有时用生命期均速打折估算（新品常见）。
    candidates = []
    if day:
        candidates.append((day, "daily"))
    if week:
        candidates.append((week / 7, "weekly"))
    if month:
        candidates.append((month / 30, "monthly"))
    snap_d = r.get("snap_daily")
    if snap_d:
        candidates.append((snap_d[0], "snapshot"))
    life = r.get("stars_per_day_life")
    if not candidates and life:
        candidates.append((life * 0.35, "life"))  # 生命期均速大约是当前速率的 3 倍

    if candidates:
        rate_day, basis = max(candidates, key=lambda c: c[0])
    else:
        rate_day, basis = 0, None

    # 加速度只在"有当日数据 + 有周均基线"时才有意义，否则留空而不是编一个 1.0
    accel = None
    if day and week and week / 7 > 0.5:
        accel = day / (week / 7)

    # 讨论热度
    hn = r.get("hn") or {}
    hn_raw = (hn.get("points") or 0) + 2 * (hn.get("comments") or 0)
    hn_score = min(1.0, math.log1p(hn_raw) / math.log1p(600))

    velocity = min(1.0, math.log1p(rate_day) / math.log1p(2500))
    accel_n = max(0.0, min(1.0, (accel - 0.8) / 2.2)) if accel else 0.45
    fresh = 0.0
    if r.get("age_days") is not None:
        fresh = max(0.0, min(1.0, (180 - r["age_days"]) / 180))

    momentum = 100 * (0.52 * velocity + 0.23 * accel_n + 0.17 * hn_score + 0.08 * fresh)
    r["metrics"] = {
        "rate_day": round(rate_day, 1),
        "rate_week": round(week / 7, 1) if week else (snap_d[0] if snap_d else None),
        "accel": round(accel, 2) if accel else None,
        "rate_basis": basis,
        "estimated": basis in ("life", "monthly", "weekly"),
        "hn_score": round(hn_score, 2),
        "velocity": round(velocity, 2),
        "fresh": round(fresh, 2),
    }
    r["momentum"] = round(momentum, 1)
    return r


# ---------------------------------------------------------------- 6. 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    ap.add_argument("--no-hn", action="store_true")
    ap.add_argument("--hn-top", type=int, default=30,
                    help="对 momentum 最高的前 N 个仓库查 HN")
    ap.add_argument("--no-meta", action="store_true",
                    help="跳过创建时间补全（省 API 限额）")
    ap.add_argument("--meta-limit", type=int, default=30,
                    help="单轮最多补全多少个仓库的创建时间")
    args = ap.parse_args()

    DATA.mkdir(exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()

    print("[1/6] 抓取 GitHub Trending ...")
    repos = collect_trending()

    print("[2/6] 查询新仓库 ...")
    new_repos = collect_new_repos(args.token)

    # 合并
    by_key = {r["repo"].lower(): r for r in repos}
    for k, nr in new_repos.items():
        if k in by_key:
            by_key[k].update({kk: vv for kk, vv in nr.items()
                              if vv not in (None, "", []) and kk != "repo"})
        else:
            nr.setdefault("windows", [])
            nr.setdefault("gain", {})
            by_key[k] = nr
    repos = list(by_key.values())
    print(f"  · 合并后: {len(repos)} 个仓库")

    print("[3/6] 读历史快照 ...")
    history = load_history()
    for r in repos:
        key = r["repo"].lower()
        r["snap_daily"] = snapshot_gain(history, key, 1)
        r["history"] = history.get(key, {}).get("points", [])[-30:]
    history = update_history(history, repos, today)
    for r in repos:  # 补齐今天这一个点
        r["history"] = history.get(r["repo"].lower(), {}).get("points", [])[-30:]
    (DATA / "history.json").write_text(
        json.dumps(history, ensure_ascii=False), encoding="utf-8")
    print(f"  · 历史库: {len(history)} 个仓库")

    print("[4/6] 计算得分 ...")
    repos = enrich(repos)
    for r in repos:
        score(r)
    repos.sort(key=lambda x: x["momentum"], reverse=True)

    if not args.no_meta:
        print(f"[5/6] 补全创建时间（最多 {args.meta_limit} 个）...")
        enrich_meta(repos, args.token, args.meta_limit)
        repos = enrich(repos)
        for r in repos:
            score(r)
        repos.sort(key=lambda x: x["momentum"], reverse=True)

    if not args.no_hn:
        print(f"[5/6] 查 HN 讨论热度（前 {args.hn_top}）...")
        for i, r in enumerate(repos[:args.hn_top]):
            r["hn"] = hn_lookup(r["repo"])
            if (i + 1) % 10 == 0:
                print(f"  · {i+1}/{min(args.hn_top, len(repos))}")
            time.sleep(0.35)
        for r in repos:  # 重新打分，纳入 HN 信号
            score(r)
        repos.sort(key=lambda x: x["momentum"], reverse=True)

    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    for r in repos:  # 窗口去重，避免 UI 里出现 "weekly / weekly"
        r["windows"] = list(dict.fromkeys(r.get("windows") or []))
    payload = {
        "generated_at": generated,
        "date": today,
        "count": len(repos),
        "repos": repos,
    }
    (DATA / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    snap_dir = DATA / "snapshots"
    snap_dir.mkdir(exist_ok=True)
    (snap_dir / f"{today}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    print("[6/6] 生成看板 ...")
    from build_dashboard import build
    out = build(payload, ROOT / "dashboard.html")
    print(f"  完成 -> {out}")
    print(f"  共 {len(repos)} 个仓库，Top: " +
          ", ".join(f"{r['repo']}({r['momentum']})" for r in repos[:5]))


if __name__ == "__main__":
    main()
