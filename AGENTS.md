# MOSS 漫画分镜台 — AGENTS.md

本文件是本仓库的最高优先级协作约定。任何智能体（Qoder / Claude / Codex 等）在修改代码前必须先读本文件；若本文件与其他说明冲突，以本文件为准。

## 1. 项目定位

把 NovelAI 法典（quicktagcloud）变成 MOSS 可用的画面词库，围绕“故事 → 分镜页 → 提示词 → 出图 → 画廊”做一套本地漫画生产工具。

核心链路：

```text
故事文本
  → AI（外部，经 MCP）拆成页级分镜
  → 每页从法典选普通 tag
  → 清洗 / 拼接 / 去重
  → ComfyUI(MOSS) 出一张整页图
  → 按项目归档到画廊（按时间或内容排序浏览）
```

明确不做：

- 不在应用内内置 LLM，不保存 API Key；AI 只通过 MCP 调用本项目。
- 第一版不做逐格生成；一页一张，页是生成单位。
- 不做复杂排版/导出；一个项目一个文件夹，画廊只做排序浏览。
- 不依赖 `NovelAI-Tag-local-v1.5.0/` 的运行时代码或服务；旧目录只读参考，保持原样。
- 不在运行时抓 quicktagcloud；先同步到本地 SQLite，再由 MCP / UI 查询。

## 2. 已锁定决策

| 项 | 决定 |
|---|---|
| 技术栈 | FastAPI + SQLite + React 19 / Vite / TypeScript / Tailwind |
| AI 接入 | 只做 MCP（stdio 薄层调本地 FastAPI，不重复业务逻辑） |
| 出图单位 | 一页一张；页级分镜，后续归档到画廊 |
| 词库范围 | 全部法典分批导入；分类与网站一致；按 release 增量更新 |
| 提示词 | tag-first；清洗 NAI 语法；不做强制翻译 |
| 画廊 | 一个项目（漫画）一个文件夹；生成图按时间或内容排序浏览；不做复杂排版/导出 |
| 页面结构 | 5 个路由：/ 检索、/relay 中转站、/presets 预设、/story 故事、/board 分镜台；深色漫画编辑部后台布局 |
| SD 权重 | `{}` 每层 ×1.05，`[]` 每层 ×0.95，数字权重精确转 `(tag:权重)`；负权重进负面提示词 |
| 中转站 | 首页复制即入中转站；可组合、删除、清空、再复制 |
| 故事 | 一个项目绑定一本 Markdown 小说；标题自动分章 |
| 参考项目 | `NovelAI-Tag-local-v1.5.0/` 只读；可参考其 tools 思路，禁止修改与依赖 |

## 3. 目录约定

```text
F:\moss\tag\
  AGENTS.md
  .gitignore
  backend\              FastAPI、SQLite、ComfyUI 适配、业务服务
  frontend\             React + Vite + TS + Tailwind
  mcp_server\             MCP stdio 服务（调 backend HTTP；目录不能叫 mcp，避免遮蔽 SDK）
  tools\                sync_codex.py、calibrate_prompt.py、start.bat 等
  data\                 moss.db、raw\、thumbs\、tag_zh\（不提交）
  projects\             一个项目一个文件夹，存生成图与项目元数据（不提交）
  _scrape\              已下载的原始法典 JSON（不提交）
  NovelAI-Tag-local-v1.5.0\   只读参考（不提交、不修改）

projects\<project>\
  project.json          项目元数据（含画廊排序）
  images\               生成图，文件名带页序与时间
```

## 4. 数据源与同步

法典数据来自站点发布链，不解析 HTML：

```text
https://novelai.quicktagcloud.com/data/current.json
  → releases/<release>/manifest.json（含每个文件的 sha256 / size）
  → <codex>.json / tag_zh/<codex>.json
```

规则：

- `current.json` 指向当前 release；不要硬编码 release id。2026-11-04 时为 `r-a6d5bdd0d0f55311867e`。
- 下载后按 manifest 校验 sha256；缓存到 `data/raw/<release>/`。
- 全量导入元数据；缩略图按需缓存到 `data/thumbs/`，UI 通过 `/api/codex/entries/{id}/thumbnail` 读取，不一次性拉几万张。
- 分类完全照网站：保存 `tree`、每个条目的 `path` 和 `category_path_text`（形如 `A / B / C`）；搜索用完整路径精确匹配或子路径前缀，避免同名分类串结果。
- `tag_zh/*.json` 的 `d` 映射用于中文搜索（英文 tag → 中文）。
- 同步按 contentHash / release 增量；记录 `synced_at`。
- 法典数量与规模（当前）：约 15 本、6.2 万条（含 R18）；所长的非 R18 为 6043 + 304 条。
- R18 本地自用默认显示：后端 API 仍支持 `include_nsfw`，前端检索页和分镜台默认开启 R18，MCP 的 `codex_search` / `prompt_compose` 默认 `include_nsfw=true`；需要安全浏览时显式关闭。
- 内容分级仍保留 `rating` 字段；R18 法典和条目不会被删除，只是在关闭开关时隐藏。
- 法典原文与配图版权归原编纂者；不要把 SQLite、缩略图、原图打进公开仓库或再分发。

## 5. MOSS 提示词清洗规则

用户已实测：MOSS 认普通描述 tag，不认 NAI 画师词表和权重语法。

输入是法典的 NAI tag 串，输出是逗号分隔的普通 tag 串：

1. **丢弃画师标签**：`artist:*` 前缀直接丢；不带前缀但命中站点画师表的名字也丢。
   - 画师表来自 `artist_strings.json` 的 `n45` / `n5` 列表，以及 `artist_index.json`。
   - 匹配前做小写、空白归一、下划线转空格、括号内容归一（如 `sos (adult)` 与 `sos adult`）。
2. **剥权重**：`0.95::tag::`、`1.05::tag::` → `tag`。
3. **剥强调/削弱括号**：`{{{tag}}}`、`[[tag]]` → `tag`；下划线转空格。
4. **负权重拆分**：`-1::curvy,artist collaboration::` 拆成两个 tag；默认进负面提示词。
   - 策略可配置：`to_negative`（默认）/ `drop` / `only_minus2`；首轮出图后再定。
5. **去重与规范化**：保留首次出现顺序，统一逗号，去空项。
6. **画师词典类法典不参与 MOSS 选词**：`artist_*` 法典仍导入、可浏览缩略图，但 `moss_usable=0`，MCP 搜索默认不返回。
7. **可用性标记**：条目过滤后如果只剩质量词/空，标为“仅参考”，不进入默认选词结果；UI 显示过滤明细和原因。

输出示例：

```text
输入：
0.95::hyulla::,0.8::artist:ahemaru::,-1::curvy,artist collaboration::,-2::multiple views::,high detail,masterpiece

正向：
high detail, masterpiece

负向：
curvy, artist collaboration, multiple views

丢弃：
hyulla（画师）, artist:ahemaru（画师）
```

每页最终提示词：

```text
风格块 + 角色锚点 + 页面内容 tag + 选中的法典普通 tag + 质量词
```

负向：

```text
全局负面 + 条目负向 + 负权重 tag
```

默认风格块按项目类型选择：漫画页优先用 `manga-ink`，封面/单幅插画可用 `cinematic-anime`。校准已证明 `black and white manga, pen line art, screentone, cel shading, clean panel borders, dramatic composition` 能出多格黑白漫画页。

## 6. 数据模型（SQLite）

第一版表：

- `codex(id, title, author, version, type, nsfw, source_release, content_hash, tree_json, synced_at)`
- `entry(id, codex_id, title, category_path_json, category_path_text, tags_raw, tags_positive, tags_negative, negative_raw, note, image, image_width, image_height, original, asset_rev, rating, is_new, moss_usable, artist_ratio, extra_json)`
- `entry_tag(entry_id, tag, kind)`（普通 tag / 画师 / 质量词）
- `tag_zh(tag, zh, codex_id)`
- `relay_item(id, content, format, source_entry_id, source_title, created_at)`（旧文本中转，已清空/停用）
- `favorite_entry(id, entry_id, domain, title, image_url, source_title, prompt_nai, prompt_moss, prompt_sd_positive, negative_nai, negative_sd, created_at)`（收藏卡片快照）
- `prompt_preset(id, name, kind, positive, negative, notes, seed, profile_json, preview_image, usage_count, version, created_at, updated_at)`
- `preset_binding(id, project_id, preset_id, order_no, created_at)`（项目级配方锁定）
- `story_doc(project_id, title, markdown, updated_at)`
- `project(id, title, story, style_preset_id, gallery_sort, mode, created_at, updated_at)`（mode: illustration / comic）
- `chapter(id, project_id, title, order_no, summary)`
- `page(id, chapter_id, order_no, summary, layout_note, prompt, negative, seed, status, image_path, kind, scene_id, created_at, updated_at)`
- `story_scene(id, project_id, chapter_title, chapter_index, order_no, title, excerpt, summary, characters, setting, mood, status, page_id, created_at, updated_at)`
- `character(id, project_id, name, anchor_tags, ref_image, notes)`
- `style_preset(id, name, tags)`
- `generation_job(id, page_id, prompt, negative, seed, workflow_profile, comfy_prompt_id, status, output_path, error, started_at, finished_at)`
- `setting(key, value)`

`gallery_sort` 取 `order`（内容/页序，默认）或 `time`（生成时间）。

分类体系：
- `entry.domain` 取 `regular` / `nsfw` / `reference`；`reference` 只放画师词典，不参与 MOSS 选词。
- 常规 8 类：角色与人物、服装与造型、场景与背景、构图与镜头、风格与画风、动作与表情、道具与生物、漫画与杂项。
- NSFW 7 类：单人、双人/多人、关系与取向、非人与异种、情趣服饰、场景与道具、连续/差分/杂项。`R18G/重口` 已硬删除，后续同步继续过滤。
- 多标签：`entry.cat_primary` 主分类 + `cat_labels_json`/`entry_category` 多标签；旧 `category_path_text` 只作来源溯源。
- 分类器：`tools/classify_categories.py`，按条目 rating 优先、codex.nsfw 和 nsfw 标签兜底，再用来源路径 + tag 关键词规则归类。

约定：SQLite WAL；原生 SQL + 编号迁移；不用 ORM；中文搜索先用 `LIKE` + `tag_zh` 反查，不上向量库。

## 7. MCP 工具契约（第一版）

MCP 服务是薄层，调用本地 FastAPI；不直接碰 SQLite 以外的业务逻辑。

- `codex_search(query, domain?, category_id?, codex_id?, include_artist_only=false, include_nsfw=true, limit=20)`
- `codex_suggest(query, limit=20)`
- `codex_get(entry_id)`
- `project_create(title)` / `project_list()` / `project_get(project_id)` / `project_update(project_id, patch)` / `project_delete(project_id)`
- `project_export(project_id)` / `project_import(payload)`
- `style_presets_list()`
- `story_set(project_id, text)`
- `storyboard_save(project_id, pages_json)`：校验 schema，拒绝不存在的 entry_id。
- `page_list(project_id)` / `page_get(page_id)` / `page_update(page_id, patch)` / `page_duplicate(page_id)` / `page_delete(page_id)`
- `project_reorder(project_id, page_ids)`
- `gallery_list(project_id, sort="order"|"time")` → 画廊图片列表
- `character_list(project_id)` / `character_upsert(project_id, body)`
- `prompt_compose(page_id, entry_ids, style_preset_id?, mode="plain", include_nsfw=false)` → 正向 / 负向 / 丢弃明细
- `generate_page(page_id, seed?, profile?)` → `job_id`
- `generate_project(project_id, seed?, profile?)`：按页序串行批量生成
- `job_list(limit?)` / `job_status(job_id)` / `job_cancel(job_id)`
- `schema_get()`：给外部 AI 的项目/分镜 JSON schema 和用法说明
- `relay_list(limit?)` / `relay_add(...)` / `relay_delete(id)` / `relay_clear()`
- `favorite_list(domain?)` / `favorite_ids()` / `favorite_toggle(entry_id)` / `favorite_delete(entry_id)` / `favorite_compose(entry_ids, format)`
- `preset_list()` / `preset_upsert(preset)` / `preset_delete(id)`
- `project_presets(project_id)` / `preset_bind(project_id, preset_id)` / `preset_unbind(project_id, preset_id)`
- `story_get(project_id)` / `story_save(project_id, title, markdown)`
- `story_parse(project_id, markdown?)` / `scene_list(project_id)` / `scene_update(scene_id, patch)` / `scenes_generate(project_id, scene_ids?, seed?, profile?)`

外部 AI 必须先检索、再引用真实 entry_id；项目端负责校验，不能信任 AI 编造的 id。

## 8. ComfyUI 接入

- 地址：`http://127.0.0.1:8188`；ComfyUI 由用户通过 ComfyNexus 或启动脚本启动，应用默认不代管。
- 第一版 profile 使用本机实际能跑的 14 节点工作流：
  `ComfyUI/user/default/workflows/MOSS-Image-25&50步-Spectrum.json`
  - 节点：UNETLoader 28、CLIPLoader 29、VAELoader 27、正向 CLIPTextEncode 25、负向 26、EmptyLatentImage 22、KSampler 16、VAEDecode 23、SaveImage 13、SpectrumMOSSImageAdaptive 30。
  - 注入点：正向 25、负向 26、种子 16、宽高 22、采样参数 16、模型 profile 28/29/27。
- 不要把 MOSS 文件夹里引用 `Moss_image\Moss-dirtyMoss...` / `Krea2\...` 的工作流当基线；本机缺这些模型。
- 模型 profile 必须校验 `/object_info` 或模型目录；缺模型时给明确错误，不静默替换。
- 默认串行队列（一次一个任务）；记录 prompt、seed、workflow、输出路径。
- 通过 `/prompt` 入队，`/history` 或 WebSocket 取进度；产物落到 `projects/<project>/images/`，文件名带页序和时间。
- ComfyUI 未启动时 UI 显示红色状态和启动提示，不要假装成功。
- 本机启动 ComfyUI 烟测需要 `PYTHONIOENCODING=utf-8`，否则 `ComfyUI_JosiaNodes` 的 emoji 日志会在 GBK 控制台抛 UnicodeEncodeError 导致启动失败。

## 9. UI 规范

- 中文界面，英文 tag 保留原文；桌面优先，最小 1280 宽。
- 视觉方向：漫画编辑部，不是通用 AI 后台。墨黑底、纸白画布、朱红强调色；细网格/网点纹理；故事正文用衬线中文字体，tag 用等宽字体；不要紫色渐变/玻璃拟态。
- 布局：左侧固定导航（检索 / 中转站 / 预设 / 故事 / 分镜台）；顶部库切换、搜索、格式切换；内容区独立滚动。
- 首页检索：分类树、图片瀑布流、右侧详情；复制支持 NAI / MOSS / SD 权重三种格式，复制即入中转站。检索默认全库，不按来源法典筛选。
- 中转站：左栏常规收藏、右栏 NSFW 收藏，跨栏多选，底部组合条统一组合/复制；收藏为快照，不依赖复制。
- 页面详情必须展示：最终正向、负向、选中的法典条目、被过滤的 tag 及原因、seed、状态。
- 关键交互：法典拖拽入栈、锁风格/角色、同 seed 重跑、A/B 对比、画廊按时间/内容切换、页序上下移动、删除页、点图查看。

## 10. 里程碑

- **M0**：全量法典同步 → SQLite；中英文搜索/分类浏览；`sanitize_tags()` 金标测试；ComfyUI 烟测（固定 seed 出一张 9:16）；MCP 骨架。状态：已完成。
- **M1**：项目/章节/页数据模型；手动页编辑；提示词编译；单页出图 + 队列/历史 + 项目画廊。
- **M2**：MCP 完整闭环（分镜保存 → 选词 → 出图）；角色圣经；连续性台账；批量生成。
- **M3**：画廊完善（时间/内容排序、项目文件夹管理）；模型 profile 校准；参考图一致性；更多风格预设。
- **M4**：五路由后台重构；分类完整路径；SD 权重转换；中转站、预设库、故事 Markdown、分镜台整合。

## 11. 智能体工作规则

1. 修改前先读本文件和相关代码；拿不准先问，不猜需求。
2. 只改 `F:\moss\tag\` 下的新项目代码；禁止修改 `NovelAI-Tag-local-v1.5.0/`、`ComfyUI_windows_portable/`、`ComfyNexus/`。
3. 不提交 `data/`、`projects/`、`_scrape/`、`.venv/`、`node_modules/`、`dist/`、数据库、图片、密钥；遵守 `.gitignore`。
4. 不执行 `git push`；提交/推送前先征得用户同意。
5. 不内置 LLM 客户端、不保存 API Key；AI 只能走 MCP。
6. 不硬编码模型路径或 release id；从配置/`current.json` 解析并校验。
7. 默认串行出图；不要为了吞吐并发压爆显存。
8. 小步修改，不做无关重构；不留死代码、兼容垫片、调试输出。
9. 后端改动配 pytest；清洗器必须有金标测试；前端改动跑 typecheck/build。
10. 用户可见文案用中文；法典 tag 保留英文；文件 UTF-8；Windows 路径用 `F:\...`，脚本兼容 Git Bash。
11. 数据仅本地个人使用；R18 默认隐藏；不把法典数据/图片用于再分发。
12. 所有 entry_id、模型名、节点名必须来自真实数据/工作流；禁止编造。
13. 生成图按项目归档：一个项目一个文件夹，不把不同漫画的图混在一起；画廊默认按内容/页序排序，可切换时间。

## 12. 当前状态与待定

当前状态：

- M0 已完成：全量法典同步 61979 条，MOSS 可用 37385 条；`sanitize_tags()` 金标测试通过；FastAPI + React 骨架可运行；MCP 已注册 53 个工具。
- M1 基础闭环已验证：项目 → 角色锚点 → 页 refs → 编译提示词 → 生成 9:16 黑白多格漫画页，产物按项目文件夹归档。
- M2 已验证：页面连续性台账、批量串行生成、前端连续性/批量控件可用；两页串行生成成功，页序和黑白漫画风格稳定。
- M2 真实短篇验证：已用项目 API 生成 4 页《第一页·雾林考核》，角色锚点、地点/时间/服装/情绪台账和页序产物均正常。
- M3 管理增强已验证：项目删除、页面复制、页面重排、任务队列、缩略图本地缓存、提示词长度统计、法典筛选、Seed 随机、页级角色选择、多角色隔离和同步清理均已跑通。
- M3 备份迁移已验证：项目导出/导入会创建新项目，并保留 refs、连续性、页序和角色选择映射。
- M3 检索增强已验证：法典筛选支持按 codex 和 top-level category_path 过滤，前端分类下拉可用。
- M3 图生图入口已验证：`init_image_path` 会上传到 ComfyUI 并用 `LoadImage -> VAEEncode -> KSampler` 做变体重绘，能保留版式。
- M3 挑图增强已验证：单页变体列表、生成两个变体、设为当前页、项目列表缩略图、Ctrl/Cmd+S 保存页均已接入。
- M3 稳定性增强：后端启动会恢复 queued/running 任务，能从 ComfyUI history 找回产物；找不到的标记 failed，避免 UI 卡住。
- M3 易用性增强：单页生成也会自动补齐空提示词；全局 mutation 错误 toast；Ctrl+Enter 生成当前页；health/status 显示最近同步时间。
- M3 词库导出：`tools/export_prompts.py` 可导出 MOSS 可用、默认排除 R18 和画师词典的 JSONL/CSV 词库。
- M4 已完成：五路由后台（检索/中转站/预设/故事/分镜台）；分类按完整路径过滤；NAI/MOSS/SD 三种复制格式；复制即入中转站；预设库与分镜台应用；项目绑定 Markdown 小说与章节解析。
- M4 检索修复：关键词为空时可按法典/分类浏览，不再回到空结果；首页默认不预填“森林”。
- M4 本地分级默认：检索页和分镜台默认“常规”库，可一键切 NSFW/参考；MCP 搜索/编译仍默认 `include_nsfw=true`。
- M4 分类重构：已切到常规/NSFW/参考三库；常规 8 类、NSFW 7 类（R18G/重口 1052 条已硬删除）；旧分类保留溯源；分类器统计为常规 17631、NSFW 19462、画师参考 23834。
- M4 来源筛选移除：检索页和分镜台不再按法典来源过滤，默认全库；后续同步会跳过 `nsfw_extreme` 条目。
- M4 收藏中转站：检索卡片心形收藏（快照），TAG 中转站左常规/右 NSFW 双栏，跨栏多选，底部组合条支持 NAI/MOSS/SD 和复制；旧 relay_item 已清空停用。
- M4 配方库：预设升级为风格/角色/负面/场景/组合配方，支持预览、seed、使用次数、版本；项目级绑定后自动进入页提示词，页面未设 seed/profile 时继承配方默认。
- M4 故事与画廊：项目分 illustration/comic；Markdown 标题+`---`切场景；场景可生成插图或分镜页，支持选中确认和自动全部；画廊独立为 `/gallery`，按模式/项目查看；分镜台只显示漫画项目。
- M4 故事工作台：新建作品改为右侧抽屉（标题/模式/风格/作品管理），支持单删和批量删；章节支持弹窗新增和拖拽排序；编辑器/预览自定义右键菜单（复制/粘贴/转移到场景/顶部跳转）；场景卡片支持新增/删除/修改/生成/跳转分镜台。
- 当前数据已清空：项目 0、故事 0、分镜页 0、配方 0、收藏 0；测试图在 `data/_trash_projects_*`，数据库备份在 `data/backups/`。
- 当前数据再次清空（故事工作台验收后）：项目 0、场景 0、页 0、配方 0、收藏 0；备份 `moss-20261106-173550.db`，测试图在最新 `data/_trash_projects_*`。
- 法典抓取已验证；`data/raw/` 和 `_scrape/` 有原始 JSON；数据库在 `data/moss.db`。
- 本机可跑工作流为 14 节点单次 MOSS；ComfyUI 烟测成功，848×1488、seed 12345、约 90 秒出图。
- 当前默认 profile 出图偏彩色电影感动漫；同 seed 校准显示 `manga-ink` 风格块能出多格黑白漫画页，自然语言也能出高质量单页。漫画项目默认应切到 `manga-ink`，封面/插画可保留 `cinematic-anime`。
- MOSS 普通 tag 可用、画师标签和权重语法无效（用户实测）。
- GitHub 远程：`https://github.com/AAAQ-ljt/mioss.git`（HTTPS 凭证可用；SSH 22 端口被挡）。M0-M2 已推送，提交 `2daf3dd`。
- 本机 push 若被系统代理干扰，用：`NO_PROXY=github.com HTTP_PROXY= HTTPS_PROXY= git -c http.sslBackend=schannel push origin main`。
- 旧项目 `NovelAI-Tag-local-v1.5.0/` 只读，不参与新项目运行。

待定：

- 漫画底模/profile：先用现有 MOSS 融合模型校准，再决定是否补二次元底模/LoRA。
- 负权重策略：首轮跑完后确认 `-1` 是否也进负面。
