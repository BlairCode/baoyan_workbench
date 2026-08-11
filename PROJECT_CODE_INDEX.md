# 推免准备系统代码定位手册

> 更新日期：2026-08-11  
> 用途：快速定位项目入口、页面、接口、数据表、函数和样式。本文覆盖项目源码与工程文件；`保研准备/`、`data/`、`处理文件/` 中的个人资料和运行数据只说明目录职责，不逐份解析其内容。

## 1. 系统执行链路

```text
start.bat / python app.py
  → baoyan_app.server.main()
  → baoyan_app.bootstrap.bootstrap() 初始化数据库与基础数据
  → ThreadingHTTPServer 提供静态页面和 JSON API
  → background_material_sync() 后台清理并同步资料索引
  → web/index.html
  → web/js/main.js
  → dashboard / contact / resources / table 页面模块
```

后端使用 Python 标准库 HTTP 服务与 SQLite；前端使用原生 ES Modules、HTML 和 CSS，无前端构建步骤。

## 2. 根目录文件

### `app.py`

- Python 启动入口，仅导入并调用 `baoyan_app.server.main()`。
- 日常启动、调试服务入口时首先查看此文件和 `baoyan_app/server.py`。

### `start.bat`

- Windows 快速启动脚本，执行 `python app.py`。

### `README.md`

- 面向使用者的项目说明，包含功能、截图、启动方式、端口配置、推荐流程、目录结构、技术栈和许可证。

### `PROJECT_CODE_INDEX.md`

- 本文件。按目录和文件记录代码职责、主要函数、类与修改入口。

### `.gitignore`

- Git 忽略规则，排除数据库、备份、运行缓存、个人资料与临时产物。

### `LICENSE`

- MIT 开源许可证正文。


## 3. 后端包 `baoyan_app/`

### `baoyan_app/__init__.py`

- Python 包标识与包级说明；公开模块名 `server`。

### `baoyan_app/config.py`

- 集中定义项目根目录、资料目录、数据目录、Web 目录和 SQLite 路径。
- 定义监听地址 `HOST`、端口 `PORT`、上传大小限制。
- `DEFAULT_SETTINGS`：品牌名、工作台名、头像、首页文字、主题、学校配色和 GitHub 地址的默认值。
- 修改资料根目录、端口默认值和设置默认值时定位到这里。

### `baoyan_app/bootstrap.py`

- `bootstrap()`：执行轻量启动初始化，包括建表、迁移院校旧状态、修复排序、写入默认待办和默认面试题。
- 文件资料扫描不在这里阻塞启动，而由 `server.background_material_sync()` 后台执行。

### `baoyan_app/db.py`

- `connect()`：创建数据目录、连接 `data/app.db` 并启用字典式行访问。
- `ensure_column()`：为旧数据库补加缺失列。
- `init_db()`：创建 `materials`、`programs`、`professors`、`tasks`、`questions`、`settings` 六张表，执行增量字段迁移并写入默认设置。
- `seed_tasks()`：仅在待办表为空时写入默认待办。
- `seed_questions()`：仅在面试题表为空时写入默认题目。
- 修改数据库结构、默认值或迁移逻辑时定位到这里。

### `baoyan_app/taxonomy.py`

- 保存所有业务枚举和统计集合：资料分类、院校类型、院校阶段、院校状态、导师状态、待办优先级/状态、面试题分类。
- `PROGRAM_STATUSES`：院校编辑器状态下拉框，包含“优营放弃”。
- `PROGRAM_STATUS_RANK`：院校状态排序权重。
- `PROGRAM_APPLIED_STATUSES`、`PROGRAM_ADMITTED_STATUSES`、`PROGRAM_EXCELLENT_STATUSES`、`PROGRAM_NEGATIVE_STATUSES`：总览统计口径。
- `normalize_category()`：兼容旧资料分类名。
- `default_stage_for_category()`：根据资料分类给出默认阶段。
- `program_status_rank()`：读取状态排序权重。
- 增删业务状态时应同时检查本文件、`web/js/status-colors.js` 和统计页面。

### `baoyan_app/repositories.py`

- `TABLES`：五类可编辑数据表的允许字段、搜索字段和默认排序，是通用 CRUD 的白名单。
- `list_table()`：列表与关键词查询，支持受限 `limit` 参数。
- `create_row()`、`update_row()`、`delete_row()`：通用新增、更新、删除。
- `move_program()`、`move_professor()`：院校/导师上移、下移或移动到指定位置。
- `move_ordered_row()`、`move_row_to_position()`、`resequence_table()`：通用显示顺序维护。
- `normalize_program_results()`：将旧 `result` 和旧状态迁移到当前状态模型。
- `ensure_program_display_order()`：修复院校和导师序号。
- `app_options()`：向前端返回编辑器下拉选项和导师/院校关联选项。
- `backup_db()`：复制 SQLite 文件到 `data/backups/`。

### `baoyan_app/materials.py`

- 负责资料扫描、分类、索引、资源浏览、上传、打开和删除，是资源页的主要后端。
- `IGNORED_DIRECTORY_NAMES`、`IGNORED_FILE_SUFFIXES`：扫描排除项；当前排除 `node_modules`、`.pnpm-store`、`.next`、缓存和虚拟环境等非资料目录。
- `is_ignored_material_path()`：判断路径是否属于排除目录。
- `purge_ignored_material_rows()`：从 SQLite 索引清理已误收录的依赖/构建文件记录，不删除磁盘文件。
- `clean_professor_name()`：从套磁信文件名提取导师名。
- `known_professor_names()`：读取已有导师名用于文件关联。
- `infer_related_professor()`：根据文件名和资料类型推断导师。
- `classify_material()`：根据目录、文件名和扩展名推断分类、阶段、资料类型与关联对象。
- `scan_materials()`：递归同步实际资料到数据库，更新新增/变化/缺失计数，并跳过生成目录。
- `sanitize_material_paths()`：把越界或已不存在的活动索引标为缺失。
- `seed_professors_from_letters()`、`ensure_professors_from_letter_materials()`：从套磁信资料补建导师记录。
- `normalize_existing_materials()`、`cleanup_generated_records()`：兼容和清理历史资料/导师数据。
- `get_material()`、`material_actions()`：读取单条资料并生成可预览操作信息。
- `resource_groups()`：旧版全量分组接口，保留兼容用途。
- `resource_directory()`：资源页当前使用的逐层目录接口；普通浏览只返回当前层，搜索最多返回 300 条。
- `delete_material_file()`：删除真实文件并把索引标为缺失。
- `parse_upload()`、`upload_material()`：解析 multipart 上传并保存到 `保研准备/网页添加/`。

### `baoyan_app/contact.py`

- `is_auto_professor_record()`：识别由文件自动生成、尚未完善的导师记录。
- `professor_key()`：规范导师姓名，用于合并和去重。
- `profile_score()`：计算导师资料完整度。
- `merge_professor()`：合并同名导师资料，优先保留完整信息。
- `contact_workspace()`：组装套磁页所需的导师、套磁信、相关文件和未归类资源。
- `resequence_active_professors()`：重排未归档导师顺序。

### `baoyan_app/analytics.py`

- `_count()`：通用 SQL 数量查询。
- `_logical_professors()`：读取并合并逻辑导师记录，避免自动记录造成统计重复。
- `_status_breakdown()`、`_count_statuses()`：状态聚合工具。
- `summary()`：生成总览页的院校、套磁、待办、资料数量、比例、状态分布和近期内容。

### `baoyan_app/settings.py`

- `avatar_path()`：寻找当前头像文件。
- `read_settings()`：读取允许的设置键、解析学校颜色 JSON 并生成头像 URL。
- `update_settings()`：校验并保存工作台设置与学校配色。
- `save_avatar()`：校验大小/格式并保存头像。
- `avatar_response()`：返回头像二进制和 MIME 类型。
- 设置中不再提供 email；导师业务邮箱仍由 `professors.email` 保存。

### `baoyan_app/server.py`

- `send_json()`：发送 UTF-8 JSON 响应。
- `read_body()`：读取 JSON 请求体。
- `Handler`：HTTP 请求处理类。
  - `log_message()`：输出简短 API 日志，隐藏成功的静态资源请求。
  - `handle_one_request()`：记录单次请求起始时间。
  - `do_GET()`：总览、套磁工作区、逐层资源、选项、设置、通用列表、文件预览和静态文件。
  - `do_POST()`：扫描、上传、备份、头像、打开目录、排序和通用新增。
  - `do_PATCH()`：设置与通用记录更新。
  - `do_DELETE()`：真实文件和数据记录删除。
  - `serve_static()`、`serve_material()`、`serve_avatar()`：静态资源/资料/头像响应。
  - `open_material()`、`open_path()`：调用系统默认程序或文件管理器。
- `main()`：轻量初始化、打印启动摘要、启动后台同步和多线程 HTTP 服务。
- `background_material_sync()`：后台清理旧索引、扫描资料并输出同步摘要。

### `baoyan_app/utils.py`

- `now_text()`：生成当前本地时间文本。
- `rows_to_dicts()`：SQLite 行转字典列表。
- `is_safe_path()`：限制路径必须位于项目根目录内，是文件操作安全边界。
- `relative_text()`：生成相对资料路径。
- `folder_level()`：从资料文件夹路径截取指定层级。

## 4. 前端 `web/`

### `web/index.html`

- 单页应用 HTML 壳：侧栏、顶栏、搜索框、Toast、主内容容器、通用编辑弹窗、文件弹窗和设置弹窗。
- 设置项（品牌、头像、首页文字、主题）和脚本/样式入口都在这里。

### `web/style.css`

- 全站样式和主题变量。
- 文件开头 `:root`：默认“晴空薄荷”配色；后续 `body[data-theme=...]`：其他可选主题。
- 主要样式区依次包括：布局/侧栏/顶栏、面板/表格、院校列表、徽章/按钮、套磁表格与学校配色、逐层资源浏览、文件图标、总览数据卡与饼图、弹窗和响应式布局。
- `.badge` 使用 `--status-color`、`--status-border`、`--status-bg`，颜色由 `status-colors.js` 注入。
- `.resource-folder-*`、`.resource-breadcrumbs`：资源页逐层文件夹 UI。

### `web/app.js`

- 兼容入口，仅导入 `web/js/main.js`。

## 5. 前端核心模块 `web/js/`

### `web/js/main.js`

- 前端总入口和页面路由。
- `setPage()`：切换页面并清空当前搜索词。
- `render()`：根据 `state.page` 调用对应页面渲染器。
- `bindCommonActions()`：统一绑定跳转、打开文件/文件夹、删除和资料编辑。
- `scanMaterials()`：触发资料扫描并显示计数。
- `backupData()`：触发数据库备份。
- 文件末尾绑定侧栏按钮、搜索防抖和全局自定义事件，然后加载设置并首次渲染。

### `web/js/api.js`

- `api()`：JSON Fetch 封装，统一响应解析与错误处理。
- `uploadForm()`：multipart 表单上传封装。

### `web/js/state.js`

- `state`：当前页面、搜索词、缓存数据、资源路径、选项和设置等前端共享状态。
- `pages`：侧栏六个页面的 ID、中文标题和图标文字。

### `web/js/schemas.js`

- `schemas`：院校、导师、资料、待办、面试题的列定义和编辑表单字段定义。
- 字段的 `optionKey` 对应后端 `/api/options` 返回值；修改编辑器字段通常要同时检查 `repositories.TABLES`。

### `web/js/status-colors.js`

- `STATUS_COLORS`：院校、导师、待办等状态的固定语义配色表。
- `statusColor()`：返回指定状态颜色，未知状态使用稳定的备用色序列。
- `statusStyle()`：生成徽章使用的文字、边框和浅背景 CSS 变量。

### `web/js/ui.js`

- 通用界面组件和弹窗逻辑。
- `toast()`：显示短提示。
- `loadSettings()`、`applySettings()`：读取并应用品牌、头像和主题。
- `renderNav()`：渲染侧栏导航。
- `renderBadge()`：按固定语义色渲染状态徽章。
- `renderSimpleList()`：通用简表。
- `openPapersDialog()`、`professorAssignSelect()`、`bindAssignActions()`：相关文件弹窗及导师归类。
- `ensureOptions()`：按需加载表单选项。
- `openEditor()`、`renderField()`、`collectForm()`：通用新增/编辑弹窗。
- `renderEditorOrderActions()`、`moveEditorRow()`：编辑器中的置顶/置底。
- `normalizeMaterialPayload()`：保存前规范资料分类与关联字段。
- `openSettings()`、`updateAvatarPreview()`、`saveSettings()`：设置弹窗和头像预览/上传。
- `shortDirection()`：压缩长研究方向文本用于表格显示。

### `web/js/files.js`

- `fileIcon()`：按扩展名生成 SVG 文件图标。
- `fileButtons()`：生成打开和预览按钮。
- `renderFileList()`、`renderFileItem()`：文件列表和单条文件 UI。
- `openMaterial()`：调用系统默认程序打开文件。
- `openFolderPath()`：调用本机文件管理器打开目录。
- `deleteFile()`：二次确认后删除真实文件。

### `web/js/utils.js`

- `$()`：`document.querySelector` 简写。
- `escapeHtml()`：对插入模板的文本做 HTML 转义。
- `fileSize()`：格式化文件大小。
- `percent()`：安全计算百分比。
- `shortText()`：截断长文本。

## 6. 页面模块 `web/js/pages/`

### `web/js/pages/dashboard.js`

- `renderDashboard()`：请求 `/api/summary`，渲染指标卡、文件搜索、院校/套磁状态饼图和首页文字。
- `metricCard()`：单个指标卡。
- `piePanel()`、`pieChart()`：状态占比面板和饼图；颜色来自 `status-colors.js`。
- 全局文件搜索最多请求 100 条，避免大结果集拖慢页面。

### `web/js/pages/contact.js`

- `renderContact()`：请求 `/api/contact-workspace`，应用学校/状态/关键词筛选并渲染套磁表格。
- `SCHOOL_COLOR_PALETTE`、`SCHOOL_COLOR_PRESETS`：学校默认和官方预设颜色，与状态色相互独立。
- `renderSchoolColorDialog()`、`bindSchoolColorSettings()`、`saveSchoolColor()`：学校颜色设置。
- `renderContactFilters()`：学校和状态筛选器。
- `renderProfessorRow()`：导师行、学校色条/标签和固定状态色徽章。
- `defaultSchoolColor()`、`officialSchoolPreset()`、`schoolColorFor()`：学校颜色解析。
- `normalizeHex()`、`hexToRgba()`：颜色输入校验与透明背景转换。
- `renderUnassigned()`：未归类套磁资料提示。
- `bindProfessorActions()`：编辑、相关文件、移动、归档、删除和建档。
- `bindContactFilters()`：筛选器事件。
- `createProfessorRecord()`、`moveProfessor()`、`archiveProfessor()`、`deleteProfessor()`：导师写操作。

### `web/js/pages/resources.js`

- `renderResources()`：请求 `/api/resources`；无搜索词时只加载 `state.resourcePath` 当前层，有搜索词时返回受限搜索结果。
- `renderDirectory()`：渲染面包屑、直接子文件夹和当前层文件。
- `renderSearchResults()`：渲染最多 200 条搜索结果及截断提示。
- `showPageError()`：把目录加载错误转成 Toast。
- `uploadFile()`：上传文件并触发刷新。

### `web/js/pages/table.js`

- `renderTablePage()`：通用列表页面入口，院校页额外提供状态筛选。
- `renderProgramFilters()`：院校状态筛选器。
- `renderTable()`：普通数据表；院校分派给紧凑列表。
- `renderPrograms()`：院校页面布局，状态使用 `renderBadge()` 固定配色。
- `programActions()`：院校排序和相关文件按钮。
- `programMeta()`、`compactLine()`、`programProgress()`、`shortValue()`：院校信息压缩展示。
- `formatCell()`：普通表格字段格式化。
- `bindTableActions()`：新增/编辑/删除/移动/相关文件事件。
- `bindProgramFilters()`：院校筛选事件。
- `openProgramFiles()`：查询并弹出院校关联资料。

## 7. 非源码目录与文件

### `data/`

- `app.db`：SQLite 运行数据库，包含资料索引、院校、导师、待办、面试题和设置；不应手工用文本编辑器修改。
- `avatar.jpg`：当前上传头像，扩展名可能随上传格式改变。
- `backups/`：通过“备份数据”生成的数据库副本。

### `保研准备/`

- 用户实际资料库，是资料扫描和资源页浏览根目录。
- 当前一级目录包括夏令营、套磁信、证明、网页添加、论文、项目等。
- 本目录内容属于个人资料，不是本系统源码；删除资源页文件会删除这里的真实文件。

### `处理文件/`

- 文档处理工作区。

### `imgs/`

- README 使用的页面截图。

## 8. 常见修改定位

| 想修改的功能 | 首要文件 | 同步检查 |
| --- | --- | --- |
| 默认配色或主题 | `web/style.css` | `web/index.html` 主题选项 |
| 状态名称/统计口径 | `baoyan_app/taxonomy.py` | `web/js/status-colors.js`、`baoyan_app/analytics.py` |
| 状态徽章颜色 | `web/js/status-colors.js` | `web/js/ui.js`、页面是否使用 `renderBadge()` |
| 院校字段 | `web/js/schemas.js` | `baoyan_app/repositories.py`、`baoyan_app/db.py` |
| 导师字段 | `web/js/schemas.js` | `baoyan_app/repositories.py`、`baoyan_app/db.py`、`baoyan_app/contact.py` |
| 资源扫描规则 | `baoyan_app/materials.py` | `baoyan_app/server.py` 后台同步日志 |
| 资源页层级浏览 | `web/js/pages/resources.js` | `baoyan_app/materials.py:resource_directory()` |
| 总览指标 | `baoyan_app/analytics.py` | `web/js/pages/dashboard.js` |
| API 路由或日志 | `baoyan_app/server.py` | `web/js/api.js` |
| 设置字段 | `web/index.html`、`web/js/ui.js` | `baoyan_app/config.py`、`baoyan_app/settings.py`、`baoyan_app/db.py` |
| 数据库表/迁移 | `baoyan_app/db.py` | `baoyan_app/repositories.py` |

