# AGENTS.md

给接手这个项目的 AI Agent（Claude Code / Codex / Cursor / Gemini CLI 等）看的协作说明。

**先读这份，再读 `README.md`。** README 讲「这是什么、怎么用」，这份讲「怎么改才不把东西改坏」。

---

## 0. 一句话概况

Python 采集 GitHub 趋势数据 → 打分 → 把 JSON 内联进 HTML 模板 → 产出一个无依赖的本地看板。没有后端、没有数据库、没有构建工具、没有 `package.json`。

---

## 1. 铁律

这几条是踩过坑之后定下来的，改动时不要绕过。

**① `dashboard.html` 是生成物，禁止手改。**
它由 `build_dashboard.py` 从 `template.html` + `data/latest.json` 生成。手改会在下次构建时被覆盖。要改界面就改 `template.html`，然后跑 `python3 build_dashboard.py`（不需要重新采集）。

**② 不要清空、不要重写 `data/history.json`。**
这是项目唯一的长期资产。每个仓库的 star 历史点都靠它，跑得越久，「增速」才越不依赖榜单推算。删除等于把项目的价值清零。

**③ 指标必须诚实，宁缺勿编。**
- 没有日榜数据就算不出加速度 → `metrics.accel` 保持 `None`，UI 显示「暂无基线」。**不要**用 `1.0` 之类的默认值填坑（这个 bug 修过一次）。
- 推算值必须带 `estimated: true` 和正确的 `rate_basis`，UI 用 `~` 前缀区分于实测的 `+`。**不要把推算值伪装成实测值。**

**④ 不要在循环里随意打 GitHub API。**
匿名限额：Search 10 次/分钟、核心 API 60 次/小时。当前设计只用 2 次 search + 最多 30 次 repo（且有 `data/repos_meta.json` 缓存）。要加 API 调用，先想清楚要不要缓存、要不要 token。

**⑤ `dashboard.html` 必须保持自包含。**
不能引 CDN、外部字体、外部图片。页面自动刷新仅请求本地服务的 `data/latest.json` 和 `data/project_summaries_zh.json`；直接预览模板还会读取本地 `assets/project-avatars.json` 及头像文件，生成看板的头像全部内联；`file://` 下尝试连接 localhost，服务不可用时退回内嵌数据与说明，所以离线双击打开、离线渲染依然可用。图表用内联 SVG / CSS 画，不要引 Chart.js。

**⑥ 所有来自 GitHub / HN 的文本必须经过 `esc()`。**
`template.html` 里的 `esc()` 是唯一转义入口。新增任何渲染路径（新的渲染函数、新的字段）都要过 `esc()`，否则一个带 `<script>` 的仓库描述就能执行。

---

## 2. 架构与数据流

```
                    ┌──────────────────────────┐
                    │  radar.py                │
                    │                          │
  GitHub Trending ──┼─→ collect_trending()     │  10 个抓取点，去重后 ~126 个
  GitHub Search   ──┼─→ collect_new_repos()    │  2 条查询，~80 个（有重叠）
                    │        ↓ merge           │
  data/history.json ┼──→ snapshot_gain()       │  本地快照差（比周榜更准）
                    │        ↓                 │
                    │   enrich() + score()     │  领域分类 + 动量分
  GitHub repo API ──┼─→ enrich_meta()          │  补创建时间（带缓存，省限额）
  HN Algolia      ──┼─→ hn_lookup()            │  只查 momentum 前 30
                    │        ↓                 │
                    │   data/latest.json       │
                    │   data/history.json      │  ← 追加今日快照
                    │   data/snapshots/YYYY-MM-DD.json
                    └────────────┬─────────────┘
                                 ↓
                    build_dashboard.build()
                                 ↓
              template.html ──→ dashboard.html
              （替换 /*__DATA__*/{} 占位符，JSON 内联进 <script>）
```

`radar.py` 打印的步骤编号就是上面的顺序（main() 里用 `step()` 自动递增，不再写死 `[n/6]`），改流程时保持顺序即可。

---

## 3. 文件职责与所有权

| 文件 | 职责 | 能改吗 |
|---|---|---|
| `radar.py` | 采集、清洗、分类、打分、写数据。**数据层的唯一入口** | ✅ 主战场 |
| `build_dashboard.py` | 将采集数据、中文说明、星星 PNG 和维护者头像内联进模板 | ⚠️ 保持离线自包含 |
| `assets/project-avatars.json`、`assets/project-avatars/` | GitHub 维护者头像来源及缓存，构建时内联 | ✅ 用 `scripts/cache_project_avatars.py` 补充，不依赖在线外链 |
| `assets/star-3d.png` | 总览星星的透明素材；原图与生成提示词同目录留存 | ✅ 更换后重新构建 |
| `data/project_summaries_zh.json` | 中文用途说明及来源；构建时内联 | ✅ 原文变化须重新核对，不能凭项目名编造功能 |
| `template.html` | 看板的全部 UI：CSS + 内联 JSON + 原生 JS（含自动刷新） | ✅ UI 改这里 |
| `dashboard.html` | **生成物** | ❌ 禁止手改 |
| `serve.py` | 本地静态服务器，让看板能自动拉取最新数据 | ⚠️ 基本不用改 |
| `README.md` | 面向人的说明 | ✅ 功能变化时同步 |
| `AGENTS.md` | 本文 | ✅ 协作约定变化时更新 |
| `check.py` | 自检脚本 | ✅ 数据契约变化时同步 |
| `data/latest.json` | 最新一次采集结果 | ❌ 只由 `radar.py` 写 |
| `data/history.json` | star 历史点 | ❌ 只追加，不重写 |
| `data/repos_meta.json` | 创建时间缓存 | ❌ 只由 `enrich_meta()` 写 |
| `data/snapshots/` | 按日期归档 | ❌ 只由 `radar.py` 写 |

**多人/多 Agent 并行时**：`radar.py`（数据层）和 `template.html`（表现层）是两个相对独立的战场，各派一个 Agent 最不容易冲突。两边都改的只有「数据契约」——见第 5 节，改契约前先在两边对齐。

**哪些进版本库**：源码、文档、`data/history.json`、`data/repos_meta.json` 进；`dashboard.html`、`data/latest.json`、`data/snapshots/`、`data/run.log` 被 `.gitignore` 排除——它们每次运行都会整体重写，纳入版本库只会让 diff 变噪音、让并行合并冲突。克隆后先跑 `python3 radar.py` 采集一次（采集结束会顺便生成看板），之后改模板只需 `build_dashboard.py`。**不要 `git add -f` 把它们塞回去。**

---

## 4. 运行与验证

```bash
# 采集 + 生成看板（约 60–90 秒，HN 查询占大头）
python3 radar.py

# 只重新生成看板（改完 template.html 用这个，秒级）
python3 build_dashboard.py

# 自检：数据契约 + 产物完整性（任何改动后都跑一遍）
python3 check.py
```

`check.py` 通过时输出 `OK`；失败会列出具体是哪个字段、哪个仓库，退出码 1。

也要手动看一眼：**改 UI 后必须真的把 `dashboard.html` 打开截图检查**，不要只改代码就宣布完成。重点看三件事：桌面 1440 宽、窄屏 1024 宽、手机 390 宽下有没有横向溢出，表格列有没有错位。

---

## 5. 数据契约

`data/latest.json` 的顶层结构：

```json
{ "generated_at": "2026-10-20 14:25", "date": "2026-10-20", "count": 190, "repos": [ ... ] }
```

单个 repo 对象的关键字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `repo` | str | `owner/name`，全局唯一键（查重时转小写） |
| `desc` / `language` / `stars` / `forks` | | Trending 页面或 Search API 提供，可能为 `null` |
| `gain` | dict | `{daily, weekly, monthly}`，榜单上标注的增量，可能缺项 |
| `windows` | list | 出现在哪些榜：`daily` / `weekly` / `monthly` |
| `created_at` / `age_days` | | 只有富化过或来自 Search 的仓库才有；`age_days` 可为 `null` |
| `domain` | str | 由 `classify()` 得出，取值见 `DOMAINS` |
| `snap_daily` | `[rate, gap]` \| `null` | 本地快照算出的日增 |
| `history` | `[[date, stars], ...]` | 最近 30 个点，给 sparkline 用 |
| `stars_per_day_life` | float \| `null` | 生命期日均 star |
| `momentum` | float | 0–100 |
| `metrics` | dict | 见下 |
| `hn` | dict | `{mentions, points, comments, top}` |

`metrics` 内部是**口径的核心**，改动前务必理解：

| 字段 | 说明 |
|---|---|
| `rate_day` | 日均新增 star，是下面几个候选里最大的一个 |
| `rate_basis` | `daily` / `weekly` / `monthly` / `snapshot` / `life` / `null`，表示 `rate_day` 从哪来 |
| `estimated` | `rate_basis in (weekly, monthly, life)` 时为 `true`，UI 据此显示 `~` |
| `accel` | 当日速率 ÷ 周均速率；**只有同时有日榜和周榜时才有值**，否则 `None` |
| `rate_week` | 周均速，可能为 `null` |
| `hn_score` / `velocity` / `fresh` | 归一化后的分项，0–1 |

改 `score()` 时保持这个不变式：**`estimated` 必须和 `rate_basis` 自洽**。`check.py` 会校验。

---

### 中文说明展示契约

采集 payload 与 `radar.py` 不变。新增独立展示目录 `data/project_summaries_zh.json`，键为小写 `owner/name`，值包含 `summary_zh`、`source_desc`、`source_url`、`source_kind`（`description` / `readme`）及 `reviewed_at`。

`build_dashboard.py` 将目录注入 `/*__SUMMARIES__*/{}`；与原始 payload 一样转义 `</`，保持离线、自包含。页面通过 `summaryEntry()` 同时匹配仓库名和原文，卡片、表格、分类、详情和搜索共用 `projectDescription()`。新增/变化的简介暂时显示原文，不以待补充提示替代用途内容。首次加载与自动刷新同步读取说明目录，目录变化时即使项目时间戳不变也重新渲染；读取失败保留内嵌说明。目录不调用模型，也不自动翻译新项目。更新目录后须重建页面，`check.py` 校验格式、来源和当前覆盖情况。

## 6. 扩展点

| 想做的事 | 改哪里 | 注意 |
|---|---|---|
| 加监控语言 | `radar.py` → `TRENDING_TARGETS` | 加一行 `("language=kotlin&since=weekly", "weekly")`，注意 URL 转义（C++ 是 `c%2B%2B`） |
| 加监控领域 | `radar.py` → `DOMAINS` | 关键词顺序影响分类：命中数最多者胜，同分取先出现的。同时要在 `template.html` 的 `DOMAIN_COLORS` 加颜色，否则回落成灰色 |
| 调新项目门槛 | `radar.py` → `SEARCH_QUERIES` | 星标阈值调高 → 结果更少更"确定"；天数调长 → 覆盖更广但更陈旧 |
| 调打分权重 | `radar.py` → `score()` 末尾四个系数 | 和必须约等于 1，否则分母不对 |
| 加数据源（如 Reddit） | 新写 `collect_xxx()`，在 `main()` 里合并 | **Reddit 的 JSON 接口会返回 403**，别再试；HN 用 Algolia 是通的 |
| 加表格列 | `template.html` → `COLS_ALL` + CSS 网格 + 响应式隐藏规则 | 见下面「坑 ①」 |
| 加视图 | `template.html` → `VIEWS` 数组 + `renderXxx()` + `render()` 里的分发表 | 别忘了 `renderNav()` 里的计数逻辑 |
| 改配色/字体 | `template.html` 顶部 CSS 变量 | 深色底，注意 `--faint` 的对比度（当前 ≈4.8:1，别再调暗） |

---

## 7. 已知的坑

**① 表格列数和 CSS 网格是硬耦合的。**
`.cols` 和 `.row` 都是 8 个网格轨道，每个断点（1080 / 820）都要同时维护「轨道定义」和「隐藏第 n 个 child」两组规则。加一列必须同步改三处，否则列会错位或换行。`row-new` / `cols-new` 是「新项目」视图的独立 6 列网格，它走 `:not()` 排除，改的时候别把两套规则混在一起。

**② `.cols` 的第一个 child 是空占位**（对应行的排名列），所以 `nth-child(n)` 的序号比「第几列」大 1。数错就会隐藏错列。

**③ GitHub Trending 每天只放出 12 条日榜。**
所以 190 个仓库里通常只有 12 个能拿到真实日增，其余靠周榜/月榜/生命期推算。这是数据源的限制，不是 bug，不要试图"补全"。

**④ 数字格式化的单位要显式拼。**
`fmt()` 曾经写成 `n>=1000 ? (n/1000).toFixed(1)`，导致 4100 显示成 `4.1`（少了 k），在 Fork 那一栏骗了很久。改 `fmt()` 时用极端值验算：999 / 1000 / 4100 / 99999 / 254812。

**⑤ 匿名 API 限额是共享的。**
同一天反复跑 `radar.py` 会把 60 次/小时的核心 API 打光，`enrich_meta()` 会打日志跳过——这是预期行为，不是错误。要频繁跑就带 `GITHUB_TOKEN`。

**⑥ 移动端溢出多半是 grid 的 `1fr` 最小宽度问题。**
`.app` 和 `.movers` 都用 `minmax(0,1fr)` 而不是 `1fr`，否则长仓库名会把整页撑宽。改布局时保持这个写法。

---

## 8. 多 Agent 协作约定

**开始前**
1. 读 `AGENTS.md` → `README.md` → `python3 check.py` 确认基线是绿的。
2. 用 `git status` 看有没有别人未提交的改动（项目已是 git 仓库，改动前先确认工作区干净，否则多人并行改同一个文件无法回滚）。

**改动时**
3. 一次只动一层：要么数据层（`radar.py`），要么表现层（`template.html`）。跨层改动要显式说明「我改了数据契约」。
4. 改了数据契约（新增/重命名字段）→ 同时更新：`radar.py` 的写入、`template.html` 的读取、`check.py` 的校验、本文件第 5 节。
5. 不要顺手"优化"与任务无关的代码。这个项目小，但每个默认值都是踩坑换来的。

**交出去之前**
6. 跑 `python3 check.py`，必须 `OK`。
7. 改了 UI → 必须打开 `dashboard.html` 截图检查桌面/平板/手机三档。
8. 改了采集 → 至少完整跑一次 `python3 radar.py`，确认所有步骤都走完、Top 5 输出正常。
9. 在回复里写清楚：改了哪一层、数据契约有没有变、验证做了什么。**不要只说"已完成"。**

**不要做**
- 不要为了"让数字好看"调整阈值或权重，除非任务明确要求。
- 不要新增依赖（当前只有 `requests` + `beautifulsoup4`）。真要加，说明理由。
- 不要引入构建步骤、打包器、框架。这套东西的价值就是"一个 py 文件 + 一个 html 文件"。
- 不要把 `data/` 加进 `.gitignore` 后删掉——历史和缓存是要跟着项目走的。

---

## 9. 已知不足（可以接手的方向）

- **趋势曲线还没有真正的历史。** sparkline 要跑几天才有形状；跑满两周后才能验证「加速度」的准确性。
- **领域分类靠关键词，会误判。** 现在 190 个里约 20% 落到「其他」，其中有一部分其实能归到 AI Agent。改 `DOMAINS` 关键词可以改善，但要注意别过度拟合今天的榜单。
- **没有去重"同一团队批量发项目"的现象。** 今天 `storytold/` 一个组织占了 5 个位置，这在真实趋势里是有意义的信号，但目前只是散落在各领域里。
- **HN 只查了前 30 个。** 长尾项目的讨论热度是空的，UI 会显示「—」，容易被误读成「没人讨论」。
- **没有告警/推送。** 目前纯看板，没有「某项目日增破千就通知我」这类能力。

### 发现视图的排布

“涨得最快”由 `renderVelocity()` 单独渲染，默认按日均新增降序，以大数字为主、走势为辅，保留总星数、热度、加速和 HN 数据以及排序控件。“新项目”由 `renderNew()` 单独渲染，保留 90 天内范围，按 `age_days` 升序，优先展示创建时间与中文用途。两个视图共用真实维护者头像与详情入口，不复用普通表格的窄屏列宽。

### 项目详情导航

项目详情仅替换右侧主内容区，保留左侧导航与筛选栏。使用同一 HTML 内的独立页面路由 `?repo=owner%2Fname`，不使用浮层。`openProject()` 保存列表筛选、排序及滚动位置，`renderProject()` 渲染详情，浏览器后退或面包屑中的列表入口恢复列表。支持直接链接与刷新；模板预览等待本地数据，构建产物可离线打开详情。主要外链与标题横向排列；维护者、分类和语言集中为标签，创建日期与项目年龄置于指标区底部。面包屑合并首页、来源列表及当前详情导航。移除 GitHub 搜索式“相关讨论”按钮，保留已有 HN 内容、指标及历史；详情不展示“查看原文与来源”折叠区，说明来源仍保存在数据目录中。详情中点击左侧导航或筛选会正常进入对应列表并清除项目路由。修改导航时须检查浏览器前进/后退、刷新、直接链接、未知项目和手机首屏操作可见性。

### HN 讨论与历史趋势契约

本次扩展数据契约：`hn.stories` 最多 6 条，每条含 `id/title/url/source_url/created_at/points/comments`，`url` 指向 HN 帖子；`discussion_count` 为本次检索匹配的去重记录数，非全站穷尽总数。`hn.score_window_days=60`，旧聚合字段与打分仍仅统计近 60 天，归档讨论只供详情阅读。`hn_lookup()` 进行仓库全名历史检索和项目名近期检索，网络失败返回 `None`，无匹配返回空数组。不要为满足展示条数加入无关内容。

详情顺序固定为指标、上榜依据、历史图、社区讨论。`historyPoints()` 去重、排序并取最近 30 条；图表按真实日期间隔定位，以精确数字提示和“图表 / 数据”页签保证可读性，明细在原图表区域内切换，不另加折叠入口。`bindHistoryChart()` 支持点选、键盘与 ResizeObserver，离开详情时释放观察器。测试空、单点、平线、下降、稀疏日期和窄屏；HN 规则运行 `python3 -m unittest discover -s tests`，数据采集改动需完整运行 `radar.py`。
