# CAD 坐标拆解与 3D 还原 · 标准规范

| 项 | 内容 |
| --- | --- |
| 代号 | cad-coord-3d |
| 日期 | 2026-09-11 |
| 上游 | 02-CAD坐标拆解与3D还原_结构设计（已确认） |
| 状态 | 已确认（2026-09-11） |

---

## 一、命名约定

| 概念 | 命名 | 规则 |
| --- | --- | --- |
| 项目代号 | cad-coord-3d | kebab-case |
| 前端模块文件 | library.js / viewer-3d.js / api-client.js | 小写短横线，一个模块一件事 |
| JS 变量 / 函数 | camelCase（loadDrawing / renderViewer） | — |
| JS 常量 | UPPER_SNAKE（PICK_THRESHOLD_PX） | — |
| CSS 类 | kebab-case（.drawing-card） | 设计令牌 --color-* / --space-* |
| Python 模块 | snake_case（converter.py / coord_parser.py） | — |
| Python 类 | PascalCase（DwgConverter / CoordParser） | — |
| API 路径 | /api/drawings/{id}/share | 复数名词 + kebab，REST 语义 |
| 数据表 | cad_drawings / cad_points / cad_links / cad_share_snapshots | cad_ 前缀 + 复数 snake_case |
| 表字段 | snake_case（drawing_id / from_point_id） | 不缩写（x / y / z 除外，领域标准） |
| 坐标点自动名 | P0001 起 4 位递增（P0001→P9999→P10000 自然涨位） | 图纸内唯一；图纸原有名称优先 |
| 分享 token | URL-safe 随机，≥16 字符 | 不可枚举 |
| 环境变量 | SUPABASE_URL / SUPABASE_SERVICE_KEY / CONVERTER_* | 复用既有命名风格 |

## 二、格式规范

- **编码**：UTF-8（无 BOM）；**行尾**：LF。特例：CSV 导出带 UTF-8 BOM（Excel 中文兼容）
- **前端**：原生 ES Modules，无构建链；入口 index.html；三方库 vendor 本地化（Three.js 锁版本，版本号记录于 vendor 目录）
- **API 响应信封**：
  - 成功：`{"ok": true, "data": ...}`
  - 失败：`{"ok": false, "error": {"code": "...", "message": "..."}}`
  - 错误码enum：CONVERT_FAILED / PARSE_FAILED / FILE_TOO_LARGE / NOT_FOUND / BAD_REQUEST
- **坐标数据 JSON**（解析输出 / 快照 payload 统一形状，与用户字段定义对齐）：
```json
{
  "meta": {"name": "样例图", "source_format": "dwg|dxf", "point_count": 128, "link_count": 96},
  "points": [{"name": "P0001", "x": 0.0, "y": 0.0, "z": 0.0}],
  "links":  [{"from": "P0001", "to": "P0002"}]
}
```
  - 交换格式中链接用**坐标名称**（贴合「产生链接的坐标名称」字段）；数据库内部用 id 引用
- **时间**：存储 ISO 8601 UTC；界面显示本地化（YYYY-MM-DD HH:mm）
- **数值显示**：坐标保留 3 位小数；导出 CSV 保留原始精度
- **导出文件命名**：`{图纸名}-坐标数据-{YYYYMMDD}.csv`（同规则 xlsx / json）

## 三、界面风格基线（设计令牌 · Apple 风）

白底极简基调，以下令牌为唯一真相源：

| 令牌 | 值 | 用途 |
| --- | --- | --- |
| --bg-page | #FFFFFF | 页面底 |
| --bg-subtle | #F5F5F7 | 3D 场景底、卡片底 |
| --text-primary | #1D1D1F | 主文本 |
| --text-secondary | #86868B | 次要文本 |
| --border | rgba(0,0,0,0.08) | 分隔线、卡片描边 |
| --accent | #0071E3 | 按钮 / 链接 / 选中 |
| --danger | #FF3B30 | 删除类操作 |
| --radius | 12px 卡片 / 8px 控件 | 圆角 |
| --shadow | 0 2px 12px rgba(0,0,0,0.06) | 卡片阴影 |
| --font | -apple-system, "SF Pro SC", "Segoe UI", "Microsoft YaHei", sans-serif | 系统字体栈 |

3D 场景：背景 #F5F5F7；点 #0071E3（选中态 #FF9500）；连线 rgba(0,0,0,0.25)；坐标轴淡化。
交互原则：hover 即提示、点选锁定详情（覆盖层展示，不压缩布局）、删改必确认、操作有 toast 反馈。

## 四、复用模式

### 模式 1 · API 端点
- **何时使用**：后端新增任何接口
- **模板**：FastAPI router + Pydantic 模型校验 + service 调用 + 统一错误信封
- **参考**：结构设计（02）第二节端点表

### 模式 2 · 前端视图模块
- **何时使用**：新增页面 / 视图
- **模板**：`export async function render(container, params) {}` + 路由注册 + 卸载清理
- **参考**：视图清单（library / upload / detail / share）

### 模式 3 · 数据读写
- **何时使用**：任何数据操作
- **模板**：读 = 前端 Supabase 客户端（anon，只读）；写 = fetch 后端 API
- **铁律**：前端零写权限

### 模式 4 · 3D 查看器生命周期
- **何时使用**：挂载 / 销毁 3D
- **模板**：`createViewer(container, data) → { dispose() }`；切换图纸必 dispose（防 WebGL 上下文泄漏）

### 模式 5 · 转换回退链
- **何时使用**：DWG 处理
- **模板**：`LibreDWG → ODA → 明确报错（含手动转换指引）`，逐级 try/catch，失败信息带下一步建议

### 模式 6 · 解析器实体提取
- **何时使用**：解析层扩展
- **模板**：实体分发表 `{LINE: ..., LWPOLYLINE: ..., POLYLINE: ..., POINT: ...}`；几何提取与名称匹配分离为两个函数

### 模式 7 · 反馈组件
- **何时使用**：用户操作反馈
- **模板**：`toast(msg, type)` / `confirmDialog(msg)` / `setLoading(btn, on)` 统一实现，全站复用

## 五、质量基线（DoD）

### 每任务 DoD（Build 逐项对照）
| # | 检查项 | 通过标准 |
| --- | --- | --- |
| 1 | 运行证据 | 附实际执行输出 / 截图 / URL；禁止未运行代码 |
| 2 | SC 对照 | 指明覆盖哪条成功标准（SC1–SC6） |
| 3 | 错误路径 | 至少构造 1 个失败场景，验证提示与兜底 |
| 4 | 规范合规 | 对照本文第一、二、三节 |
| 5 | 记录 | 写入 BUILD_LOG（产出 / 验证 / 问题） |

### 项目级质量门（交付前）
| # | 项 | 标准 |
| --- | --- | --- |
| 1 | 全链路 | SC1–SC6 逐条验证通过，换设备数据仍在 |
| 2 | 3D 性能 | 10k 点级场景旋转 ≥ 30fps（桌面 Chrome 基准） |
| 3 | 点选精度 | 12px 命中半径内可选中 |
| 4 | 解析质量 | 样例图抽验 ≥ 3 处（点数 / 线数 / 名称对照） |
| 5 | 上传上限 | ≤ 100MB；超限明确提示 |
| 6 | 分享 | 无登录可看；撤销后立即失效 |
| 7 | 浏览器 | Chrome / Edge 最新版通过 |

> 数值为初始基线；样例实测后如需校准，记录于 Build 日志。

## 六、反模式（禁止）

| # | 反模式 | 原因 |
| --- | --- | --- |
| 1 | 前端直接写数据库 | 破坏读写分治，安全边界崩塌 |
| 2 | 修改 CAD 原图数据 | 违反只读解析原则（Brief 核心原则 ①） |
| 3 | 代码硬编码凭据 | key 只走环境变量 / 配置；service key 禁入前端 |
| 4 | 转换跳级 / 静默跳级 | 必须逐级回退，跳级掩盖兼容性问题 |
| 5 | 引入构建链 / 大框架（React / Vue / Webpack） | 保持无构建 ES Modules；部署 = 传文件 |
| 6 | 静默失败 | 错误必须用户可见 + 留痕 |
| 7 | 新旧并存 | 更新实现时删旧版；改一处须查全局引用 |
| 8 | 文件名带版本号 | 版本记于文档内部（既有文档规范） |
| 9 | 破坏性操作无确认 | 删图纸 / 删点 / 撤销分享必须二次确认 |

## 七、安全基线

- **权限模型**：anon = 只读；service key 仅存在于后端环境
- **分享 token**：随机 ≥ 16 字符，不可枚举
- **上传校验**：仅接受 .dwg / .dxf（扩展名 + 文件头双重校验）；解析在服务端独立目录，临时文件即用即清
- **错误信息**：对用户友好、对日志详细；不向客户端泄露服务器路径 / 堆栈

## 八、文档规范

- 工作流文档：编号体系 00 → 06；文件名不带版本号；版本记于头部
- 修改纪律：核心决策变更 → 活文档记录 → 同步全部受影响文档（全量 review）
- Build 日志：按 answer 模板（任务 / 产出 / 验证 / 问题）
