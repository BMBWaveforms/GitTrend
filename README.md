<div align="center">

# 🔭 GitTrend

**每天扫描 GitHub,算出「谁在加速」——帮你发现前沿项目,而不是围观总星榜。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![零后端](https://img.shields.io/badge/后端-无-red.svg)](#-零后端零数据库)

一个 `.py` 文件 + 一个 `.html` 文件,双击就能看的本地趋势看板。

</div>

---

## ✨ 它解决什么问题

GitHub Trending 只会告诉你「今天谁最火」,而总星榜永远被 Django、React 这些巨无霸霸占。真正值得早发现的是另一批东西:

> **几十天内冒出来的新项目 · 增速突然抬头的项目 · 以及——它到底是不是虚火。**

GitTrend 每天抓一遍数据,把这三件事合成一个可以反复打开、可以筛选、可以点进去看细节的看板。

现成的工具都只做了一半:TrendRadar 是「资讯推送」不是「趋势发现」,star-history 只服务「你已经知道要看的仓库」。**发现「谁在加速」这件事,没人合在一起做**,所以自己写了一个。

## 🚀 特性

- 📡 **三层信号,互相校验**
  - **GitHub Trending** —— 日/周/月榜 + 6 个语言榜 + 中文圈,拿官方口径的日增
  - **GitHub Search API** —— 抓还没进榜的新项目(30 天 >400★、90 天 >1500★)
  - **Hacker News** —— 用真实讨论热度分辨「真火」还是「刷的」
- 🎯 **动量分,不看总星看加速度** —— 速度 / 加速度 / HN 热度 / 新鲜度,加权求和
- 🧭 **五个视图** —— 概览、涨得最快、新项目、分类分布、全部项目
- 🔍 **能筛选、能搜索** —— 按领域 / 语言 / 最小动量过滤,`/` 聚焦搜索,点任意行看右侧详情
- 💾 **零后端、零数据库、零构建** —— 数据直接内联进 HTML,离线双击即开,不依赖任何 CDN
- 🧾 **数据口径诚实** —— 实测日增标 `+`,推算值标 `~`,拿不到的数据宁可空着,绝不编一个
- 📅 **每天自动跑** —— cron / launchd / 本地服务器三种方式,历史快照越攒越准

## 🎬 预览

<p align="center">
  <img src="assets/screenshot.png" alt="GitTrend 看板预览" width="92%">
</p>

## 🔧 快速开始

只依赖 `requests` 和 `beautifulsoup4`:

```bash
git clone https://github.com/BMBWaveforms/GitTrend.git
cd GitTrend
pip install requests beautifulsoup4
python3 radar.py            # 约 60–90 秒,跑完自动生成 dashboard.html
```

双击生成的 `dashboard.html`,就是完整看板。

常用参数:

```bash
python3 radar.py --no-hn         # 跳过 HN 查询(快 30 秒)
python3 radar.py --token ghp_xxx # 带 GitHub token,限额 60→5000/小时(可选,不带也能跑)
python3 radar.py --loop 360      # 每 6 小时自动采一轮
```

## 🧠 它怎么判断「趋势」

**动量分** = `52% × 速度 + 23% × 加速度 + 17% × HN 热度 + 8% × 新鲜度`

| 维度 | 含义 | 为什么这么设计 |
|---|---|---|
| 🚀 速度 | 日均新增 star | 对数归一化,否则一个日增几万的项目会把所有人压成 0 分 |
| 📈 加速度 | 当日速率 ÷ 7 日均速 | `>1` 热度还在往上走,`<1` 在退潮 |
| 💬 HN 热度 | 讨论点数 + 2×评论数 | 有人真在讨论,才是真火 |
| 🌱 新鲜度 | 180 天内的新项目加分 | 越新加得越多,新概念往往藏在新生项目里 |

## 🔎 关于数据,几句实话

不是每个仓库都能拿到「今日新增」。表格里数字前的符号代表可信度:

| 符号 | 含义 |
|---|---|
| `+` | **真实日增**(日榜标注 / 本地快照差),最可信 |
| `~` | **推算值**(周榜÷7、月榜÷30),只能看量级 |

GitHub 每天只放出 12 条日榜,所以大多数仓库是估算——**这是数据源的限制,不是 bug**。跑得越久,本地快照攒得越多,数字就越脱离榜单推算、越接近真实。

## 🕐 每天自动跑

**cron(最简单):**

```bash
crontab -e
# 每天早上 9:17 跑一次（把 /path/to/GitTrend 换成你的实际路径）
# python 用 `which python3` 查到的绝对路径（macOS Homebrew 通常是 /opt/homebrew/bin/python3）
17 9 * * * cd /path/to/GitTrend && /opt/homebrew/bin/python3 radar.py >> data/run.log 2>&1
```

**配合本地服务器,看板自动刷新:**

```bash
python3 radar.py --loop 360   # 终端 1:每 6 小时采一轮
python3 serve.py              # 终端 2:启动本地服务器,浏览器自动打开看板
```

<details>
<summary>macOS launchd 方式(点开看完整 plist)</summary>

`~/Library/LaunchAgents/com.yourname.ghradar.plist`(把 `/path/to/GitTrend` 换成实际路径):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.yourname.ghradar</string>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/python3</string>
    <string>/path/to/GitTrend/radar.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/GitTrend</string>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>17</integer></dict>
  <key>StandardOutPath</key><string>/path/to/GitTrend/data/run.log</string>
  <key>StandardErrorPath</key><string>/path/to/GitTrend/data/run.log</string>
</dict></plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.yourname.ghradar.plist
```

</details>

## 🤝 想改它 / 一起开发

这个项目刻意保持「一个 py + 一个 html」的最小形态,每个默认值都是踩坑换来的。

- 想加监控语言 / 领域、调打分权重、加视图:改哪里都写清楚了,见 [AGENTS.md](AGENTS.md)
- 改完任何东西跑一遍自检:

```bash
python3 check.py   # 通过输出 OK,否则逐条指出哪个仓库哪个字段有问题
```

## 📂 文件结构

```
GitTrend/
├── radar.py              # 采集 + 打分,主程序
├── template.html         # 看板模板(改 UI 改这里)
├── dashboard.html        # 成品看板(生成物,双击即开)
├── serve.py              # 本地服务器,让看板自动刷新
├── build_dashboard.py    # 用已有数据重建看板
├── check.py              # 自检脚本
├── AGENTS.md             # 给协作 AI Agent 的说明
└── data/                 # 长期价值所在:历史快照、创建时间缓存
```

## 📜 License

[MIT](LICENSE) © 2026 BMBWaveforms
