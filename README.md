# GitTrend

一个个人向的 GitHub 趋势监控：每天抓一遍数据，算出「谁在加速」，生成一个可以反复打开、可以筛选、可以点进去看细节的本地看板。

---

## 一、先回答你的问题：有没有现成项目？

有，而且不少，但都只覆盖了其中一半。把它们放在一起看，会发现分成三类：

| 项目 | 形态 | 强在哪 | 差在哪 |
|---|---|---|---|
| [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar) · 63k★ | 多平台热榜聚合 + 推送机器人 | 推送到飞书/钉钉/企微/微信，开箱即用 | 定位是「资讯推送」，不是「趋势发现」。没有 star 增速、加速度、加速度对比，也不按赛道切分 |
| [star-history/star-history](https://github.com/star-history/star-history) · 9.6k★ | star 历史曲线图 | 补全历史、曲线漂亮 | 只服务「你已经知道要看的仓库」。发现新项目这件它不做 |
| [pingcap/ossinsight](https://github.com/pingcap/ossinsight) · 2.5k★ | 全量开源数据排行/对比平台 | 数据最全，可对标、可排名 | 要自建 TiDB 等一堆组件，重；偏「平台」不偏「个人每日扫一眼」 |
| [mshibanami/GitHubTrendingRSS](https://github.com/mshibanami/GitHubTrendingRSS) · 369★ | 把 Trending 变成 RSS | 最轻，一个 feed 搞定 | 只是把榜单搬成 RSS，没有增速、没有去重、没有跨平台讨论信号 |
| [Apify GitHub Trending Tracker](https://apify.com/gochujiang/github-trending-tracker) | 托管爬虫 API | 不用自己维护 | 按量付费，数据仍要你自己消化 |

**结论**：如果你只想要「每天收到一份 Trending 列表」，装 TrendRadar 或订一个 TrendingRSS 就够了，没必要自己写。

但你问的是**「发现前沿项目、发现好概念、发现趋势上升快的」**——这要求三件事同时成立：

1. 不是看总 star，而是看**增速和加速度**（总 star 榜永远被 Django、React 这种巨无霸占着）；
2. 要能识别**新生项目**（几十天内冒出来的，往往才是新概念）；
3. 要能判断**是不是虚火**（有人真在讨论，还是只是刷 star）。

现成工具没有把这三件事合在一起做的，而且它们的输出形态都不是「我自己想怎么看就怎么看」。所以这套东西是自建的，代码很短，改起来没有负担。

---

## 二、这套东西在做什么

### 三层信号，互相校验

**第一层 · GitHub Trending 页面**（10 个抓取点）
日榜、周榜、月榜，加上 Python / TypeScript / Rust / Go / C++ / Jupyter 六个语言榜，再加中文圈榜。去重后通常 120–130 个仓库。

这一层给的是**官方口径的增量**：页面上明确写着「今日 +3856 stars」，这是最可靠的日增数据。

**第二层 · GitHub Search API**（新建仓库探测）
两条查询：「30 天内创建且 star > 400」「90 天内创建且 star > 1500」。

这一层解决的是 Trending 的盲区——爆得太快但还没进榜的、或者语言榜没覆盖到的。这是「新概念」的主要来源。

**第三层 · Hacker News**（讨论热度）
对动量最高的 30 个仓库，用 Algolia API 查近 60 天的相关讨论，统计提及数、总分数、总评论数。

这一层用来分辨真假：一个项目如果 star 涨得猛但 HN 上毫无水花，多半是某个社群内部传播或者在刷；反过来，HN 上 300 分 300 条评论的项目，通常是真的有人在用。

### 动量分怎么算

```
动量 = 52% × 速度 + 23% × 加速度 + 17% × HN热度 + 8% × 新鲜度
```

- **速度**：日均新增 star，取对数归一化（否则一个 2.8 万/天的项目会把所有人压成 0 分）
- **加速度**：当日速率 ÷ 7 日均速。大于 1 说明热度还在往上走，小于 1 说明在退潮。**只有同时有日榜和周榜数据时才算**，缺数据宁可显示「—」也不编一个 1.0
- **HN 热度**：`点数 + 2 × 评论数`，对数归一化
- **新鲜度**：180 天内的新项目给加分，越新加得越多

权重都在 `radar.py` 的 `score()` 里，改一行就能调。

---

## 三、怎么用

```bash
cd "GITHUB 趋势监控给你"
python3 radar.py
```

依赖只有 `requests` 和 `beautifulsoup4`。跑完会生成 `dashboard.html`，双击打开就是看板。

常用参数：

```bash
python3 radar.py --no-hn              # 跳过 HN（快 30 秒）
python3 radar.py --no-meta            # 跳过创建时间补全（省 API 限额）
python3 radar.py --token ghp_xxxx     # 带 token，限额从 60/小时 提到 5000/小时
python3 radar.py --meta-limit 50      # 单轮多补一些创建时间
```

**关于 token**：不带也能跑。匿名状态下 GitHub Search API 是 10 次/分钟（我们只用 2 次），repo API 是 60 次/小时（创建时间补全用，默认 30 次）。补全过的仓库会存进 `data/repos_meta.json` 缓存，**不会重复消耗**，所以跑几天之后就会自己攒齐，不必非要 token。

### 五个视图

- **概览** — 动量前 5 的卡片、领域分布、今日值得注意的四五条自动结论
- **增速榜** — 按今日新增 star 排序，看「谁在猛涨」
- **新项目** — 90 天内创建的项目，按生命期日均 star 排序，看「谁是新物种」
- **领域雷达** — 按赛道分组，看今天的热度集中在哪里
- **全部项目** — 完整表格，点表头排序

左侧可以按领域、语言、最小动量筛选。右上搜索框按 `/` 聚焦、`Esc` 清空。点任意一行打开右侧详情。

---

## 四、数据口径（很重要，别被数字骗了）

不是每个仓库都能拿到「今日新增」。表格里的数字前面有个符号，含义不同：

| 符号 | 来源 | 含义 |
|---|---|---|
| `+` | 日榜标注 / 本地快照差 | 真实日增，最可信 |
| `~` | 周榜 ÷ 7、月榜 ÷ 30、或生命期均速 × 0.35 | 推算值，只能看量级 |

首屏右侧会写明「日榜实测 12 个 · 推算 178 个」。推算值偏多是正常的——GitHub 每天只放出 12 个日榜条目。

另外注意：`morluto/rea` 这种「总星 33 万、本周涨 20 万」的项目，日增 2.8 万是从周榜推算的，它可能今天只涨了 5000、也可能涨了 5 万，周榜给不出更细的答案。**要精确，就多跑几天，让本地快照积累起来**——历史快照差是比周榜更准的口径。

---

## 五、让它每天自动跑

### 方式一：cron（推荐，最省心）

```bash
crontab -e
# 每天早上 9:17 跑一次
17 9 * * * cd "/Users/bmb/AI/Projects/GITHUB 趋势监控/GITHUB 趋势监控给你" && /usr/bin/python3 radar.py >> data/run.log 2>&1
```

选 17 分而不是 0 分，是为了避开整点大家都在跑的时段。

### 方式二：macOS launchd

`~/Library/LaunchAgents/com.bmb.ghradar.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.bmb.ghradar</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/Users/bmb/AI/Projects/GITHUB 趋势监控/GITHUB 趋势监控给你/radar.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/bmb/AI/Projects/GITHUB 趋势监控/GITHUB 趋势监控给你</string>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>17</integer></dict>
  <key>StandardOutPath</key><string>/Users/bmb/AI/Projects/GITHUB 趋势监控/GITHUB 趋势监控给你/data/run.log</string>
  <key>StandardErrorPath</key><string>/Users/bmb/AI/Projects/GITHUB 趋势监控/GITHUB 趋势监控给你/data/run.log</string>
</dict></plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.bmb.ghradar.plist
```

---

## 六、想改的话，改哪里

| 想做的事 | 改哪里 |
|---|---|
| 加一个监控语言 | `radar.py` 里的 `TRENDING_TARGETS`，加一行 `("language=kotlin&since=weekly", "weekly")` |
| 加一个监控领域 | `radar.py` 里的 `DOMAINS`，加一个 `("你的领域", ["关键词1", "关键词2"])` |
| 调整新项目的门槛 | `SEARCH_QUERIES` 里的 star 阈值和天数 |
| 调整打分权重 | `score()` 最后的 `0.52 / 0.23 / 0.17 / 0.08` |
| 改看板配色/字体 | `template.html` 顶部的 CSS 变量 |
| 加一个视图 | `template.html` 里的 `VIEWS` 数组 + 一个 `renderXxx()` 函数 |

改完 `template.html` 之后不需要重跑采集，执行 `python3 build_dashboard.py` 就能重新生成看板（用已有数据）。

---

## 七、文件说明

```
GITHUB 趋势监控给你/
├── radar.py              # 采集 + 打分，主程序
├── build_dashboard.py    # 把数据灌进模板，生成 dashboard.html
├── template.html         # 看板模板（数据占位符在 <script> 里）
├── dashboard.html        # 成品看板，自包含，双击就能开
├── check.py              # 自检：数据契约 + 产物完整性
├── AGENTS.md             # 给 AI Agent 的协作说明（改代码前读这个）
├── CLAUDE.md             # Claude Code 专用补充
└── data/
    ├── latest.json       # 最新一次采集的完整结果
    ├── history.json      # 每个仓库的 star 历史点（曲线和快照差都靠它）
    ├── repos_meta.json   # 创建时间缓存，避免重复消耗 API 限额
    └── snapshots/        # 按日期归档，方便回溯「上周三榜上都有谁」
```

`data/` 目录是这套东西的长期价值所在——跑得越久，快照越多，「增速」就越不依赖榜单推算，越准。

---

## 八、和其他 Agent 一起改这个项目

如果你会用 Claude Code / Codex / Cursor 等多个 Agent 协作，让它们先读 `AGENTS.md`（Claude Code 会自动读 `CLAUDE.md`，里面转指过去）。里面有数据契约、扩展点、已知的坑和多 Agent 分工约定。

改完任何东西，跑一遍自检：

```bash
python3 check.py
```

它会校验 190 个仓库的数据字段是否合法、`estimated` 和 `rate_basis` 是否自洽、看板产物有没有空值泄漏或残留占位符。通过输出 `OK`，否则逐条指出哪个仓库哪个字段有问题。

