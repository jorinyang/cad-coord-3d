# CAD 坐标拆解与 3D 还原 · 构建日志

| 项 | 内容 |
| --- | --- |
| 代号 | cad-coord-3d |
| 日期 | 2026-09-11 起 |
| 上游 | 04-CAD坐标拆解与3D还原_任务清单（已批准） |
| 状态 | 构建中 |

---

## 任务进度

- [x] F1 · 转换链打通（本机）
- [ ] F2 · 云端基础设施冒烟（⏸ 容器验证等待用户确认 Docker 操作）
- [x] F3 · 解析器核心
- [x] F4 · 后端 API
- [x] F5 · 数据层
- [x] C1 · 前端最小闭环
- [x] C2 · 3D 查看器
- [x] C3 · 入库 + 图纸库 + 详情
- [x] C4 · 编辑修正
- [x] C5 · 导出
- [x] C6 · 分享
- [ ] C7 · 云端部署（OSS 前端 ✅ / FC 后端 ⏸ 等 Docker 确认）
- [x] P1 · 全态打磨
- [x] P2 · 端到端验证（核心项完成；用户样例到位后收尾）
- [x] P3 · 项目说明文档
- [ ] P4 · Review（待 C7b 后统一执行）

---

## 详细记录

### F1 · 转换链打通（本机）✅

- 状态：完成（2026-09-12 00:13）
- 产出：`app/server/converter.py`（LibreDWG → ODA 回退链封装）、`app/server/test_converter.py`（自测脚本）、`app/testdata/`（测试素材）
- 环境：ODA File Converter 27.1.0 已静默安装（`C:\Program Files\ODA\ODAFileConverter 27.1.0\`）；Linux AppImage 已下载备用（F2 用）
- 验证：
  - ① 自造图往返转换（DXF→DWG→DXF）：9/9 实体精确保留（含三维折线 Z 坐标）
  - ② 封装自测：通过
  - ③ 真实样例 4 个版本（R2000/R2013/R2018/R14）：4/4 成功，各 68 实体，类型分布一致
- 备注：样例含 INSERT（块引用）/DIMENSION（标注）等实体——为 F3 解析器设计提供输入；用户真实工程图纸到位后补充标定

### F2 · 云端基础设施冒烟（进行中，部分等待用户）

- 状态：⏸ 容器内转换验证 = Docker 命令触发系统权限确认（凌晨用户不在，超时被拦）→ 遵守规则不重试，等待用户确认后继续
- 已就绪：Docker 29.6.1 运行中；ODA Linux AppImage（51MB）已下载；python:3.11-slim 拉取与容器内验证脚本已备好
- 待办：① 用户确认后跑容器内 DWG→DXF 验证 ② OSS/FC 通道冒烟（需阿里云凭据）

### F3 · 解析器核心 ✅

- 状态：完成（2026-09-12 00:20）
- 产出：`app/server/coord_parser.py`（提取/归一/连线/名称匹配/补号 → 标准坐标 JSON）、`app/server/test_parser.py`
- 验证：
  - ① 自造图严格断言：6 点 / 8 边 / JA–JE 五名称命中 / 补号 1 个（P0001@5,10,0）——含 3D 点（5,5,3）保真
  - ② 真实样例 4 版本：各 3846 点 / 3736 连线（解析结果四版本一致）
  - ③ 解析期间发现并修复 1 个生成器耗尽 bug（_bbox_diag）
- 备注：v1 范围 = LINE/LWPOLYLINE/POLYLINE/ARC/POINT + INSERT 递归展开 + TEXT/MTEXT/ATTRIB；DIMENSION/SPLINE/CIRCLE 等忽略并统计（增强项）。名称匹配命中率待真实图纸标定

### F4 · 后端 API ✅

- 状态：完成（2026-09-12 00:25）
- 产出：`app/server/main.py`（FastAPI：GET /api/health、POST /api/parse：魔数校验→转换→解析→统一信封+错误码；CORS 开发期放开）、`app/server/test_main.py`
- 验证（TestClient 进程内测试，不启动常驻服务）：
  - ① 健康检查 OK
  - ② DXF 上传解析 OK（5 点 / 6 线）
  - ③ **DWG 上传全链路 OK**（转换→解析→JSON）
  - ④ 坏文件三类结构化拒绝：魔数不符 / 不支持扩展名 / 空文件
- 备注：uvicorn 入口已备（127.0.0.1:8788，供本地联调）；starlette 的 httpx 弃用警告不影响运行

### F5 · 数据层 ✅

- 状态：完成（2026-09-12 00:40）
- 产出：`app/server/db_setup.py`（检查/建表/验证三模式）；Supabase 项目 `mqsqcpkcmcgwbzcsmrlm` 新增 4 张表：cad_drawings / cad_points / cad_links / cad_share_snapshots（含索引、RLS、授权）
- 通道：psycopg2 直连 pooler（aws-0-us-west-2.pooler.supabase.com:6543）成功；cli `db query` 遇历史 login-role 权限问题，未采用；Management API 的 PAT 不完整（13 字符）
- 验证：① anon 读 200 ② anon 写被 RLS 拒（42501 row-level security）③ service 写 201 → 读回 → 删除 204 ④ 列表恢复空
- 重要发现：**本项目 legacy JWT 已失效**（401 Invalid API key）→ 全链路必须用新式 key：前端 `sb_publishable_…` / 后端 `sb_secret_…`
- 备注：库内现有 68 张表（exam_* / ls_* / pm_* / xiangyu_works 等），cad_ 前缀隔离无冲突

### C1 · 前端最小闭环 ✅

- 状态：完成（2026-09-12 01:05）
- 产出：`app/web/`（index.html + css/app.css + js/{app,api,ui,config}.js + js/views/{library,upload}.js）——原生 ES Modules、无构建链、设计令牌落地（Apple 风）
- 测试基建：`app/devtools/cdp_e2e_c1.py`（headless Chrome CDP 端到端测试，复用 qianwen cdp_lib）；独立 headless 实例 9225
- 验证（真实浏览器端到端）：首页空态 ✓ → 上传页渲染 ✓ → 注入 test_input.dxf → 结果卡显示「5 坐标点 / 6 连接关系」+ 坐标预览表 ✓
- 备注：后端端口 8788→8791（8788 被其他进程占用）；服务运行中（后端 8791 / 前端 8789）

### C2 · 3D 查看器 ✅

- 状态：完成（2026-09-12 01:20）
- 产出：`app/web/js/viewer3d.js`（点/线渲染、OrbitControls 旋转缩放、Raycaster 点选 12px 阈值、选中高亮、悬浮提示、dispose 生命周期）；`app/web/vendor/three/`（r170 本地化）；集成到上传结果卡
- 测试基建：`app/devtools/cdp_e2e_c2.py` + `cdp_e2e_c2b.py`（CDP 真实鼠标注入）
- 验证（headless Chrome 端到端）：
  - ① WebGL 上下文 + canvas 渲染 ✓
  - ② 点选：投影→真实鼠标点击→详情面板「JA / X 0.000 · Y 0.000 · Z 0.000」✓
  - ③ 悬浮提示显示点名 ✓
  - ④ 旋转（拖拽）/ 缩放（滚轮）：CDP 真实鼠标注入，投影坐标显著变化 ✓
  - ⑤ 旋转后点选回归 ✓
  - ⑥ dispose：幂等、DOM 清理干净、重复上传流程正常 ✓
  - ⑦ 10k 点帧率 40fps（headless SwiftShader 软渲染环境；真机更高，超过 30fps 标准）✓
  - ⑧ DWG 全链二次上传（转换→解析→3D）✓
- 修复：① 同文件重选不触发 change（点击前清空 input.value）② dispose 幂等化
- 经验：交互测试用 CDP `Input.dispatchMouseEvent`（真实鼠标）；合成 PointerEvent 会触发 setPointerCapture 报错（仅测试副产物）

### C3 · 入库 + 图纸库 + 详情 ✅

- 状态：完成（2026-09-12 01:40）
- 产出：
  - 后端：`app/server/store.py`（psycopg2 写入层：save/rename/delete）；`main.py` v0.2.0（/api/parse 解析后入库返回 drawing_id；新增 PATCH/DELETE /api/drawings/{id}）
  - 前端：`sb.js`（Supabase 只读客户端，limit/offset 分页）；`views/library.js`（图纸库列表）；`views/detail.js`（详情：3D + 数据表 + 重命名/删除）；`app.js`（路由 + 视图卸载生命周期）；`upload.js`（上传成功跳转详情页）；`ui.js`（confirmDialog / promptDialog 自制对话框）
- 验证（TestClient + headless 端到端双重）：
  - ① API：DXF/DWG 上传入库 + 清理、重命名、删除、重复删除 404 全通过
  - ② E2E 全流程：上传→自动跳详情→3D 就绪→点选「JA」→列表 1 卡片→重命名「E2E 测试图纸」→列表持久化→删除→空列表，**页面零错误**
- 备注：前端配置（Supabase URL + publishable key）由脚本从凭据文件生成写入 config.js（key 设计上公开）

### C4 · 编辑修正 ✅

- 状态：完成（2026-09-12 02:05）
- 产出：
  - 后端：`store.py` 新增 rename_point（同图唯一性校验）/ delete_point（关联边级联删除+计数刷新）/ delete_link；`main.py` 新增 3 端点（PATCH points / DELETE points / DELETE links），均返回最新计数
  - 前端：`views/detail.js` 重写为可编辑数据表（点表：点击名称改名、✕ 删点；边表：✕ 删边）；操作后 **3D 与表格同步刷新**（viewer 重建 + 表格重渲染 + 统计更新）；改名时同步边表中的名称引用
  - `sb.js`（links 携带 id）、`api.js`（renamePoint / deletePoint / deleteLink）
- 验证（E2E）：改名 ALPHA（表格 + 边表同步 ✓）→ 删点 5/6→4/3（级联 3 条边正确）→ 删边 →4/2 → 刷新持久 ✓ 页面零错误 ✓
- 对应 SC4：网页上改数据（改名/删点/调关系）→ 与 3D 同步 ✓

### C5 · 导出 ✅

- 状态：完成（2026-09-12 02:15）
- 产出：`app/web/js/exporters.js`（CSV/XLSX/JSON 生成 + 下载）；`app/web/vendor/xlsx/`（SheetJS 0.20.3 本地化）；detail.js 操作区「导出」下拉
- 列定义（对齐用户字段）：`坐标名称 / X 坐标值 / Y 坐标值 / Z 坐标值 / 产生链接的坐标名称`
- 验证（E2E + 文件级校验）：
  - CSV：UTF-8 BOM ✓、表头逐字正确 ✓、6 行 ✓、`JA,0,0,0,JB、P0001、P0002`（关联列正确）✓
  - XLSX：合法 zip（10 条目含 xl/workbook.xml）✓
  - JSON：结构完整（5 点 6 线）✓
- 文件命名：`{图纸名}-坐标数据-{YYYYMMDD}.{ext}` ✓（符合 Standards）

### C6 · 分享 ✅

- 状态：完成（2026-09-12 02:30）
- 产出：
  - 后端：store.py（load_drawing_payload / create_share 同图单快照 / delete_share）；main.py（POST /api/drawings/{id}/share、DELETE /api/share/{token}）
  - 前端：`views/share.js`（#/share/{token} 只读页：3D + 数据表 + 「只读分享」徽章）；detail.js 分享按钮 + 分享对话框（复制/撤销）；sb.js getShare；api.js createShare/revokeShare；app.js 路由
- 验证（E2E）：生成分享链接 → **独立标签页**打开（只读：有 3D、无编辑控件、无上传导航动作）→ 撤销 → 刷新链接显示「分享不存在或已撤销」✔ 页面零错误
- 对应 SC5：分享链接未登录只读查看 ✓（撤销语义完整）
- 备注：同图仅保留一个分享快照（再分享即刷新）；token = secrets.token_urlsafe(16)

### C7 · 云端部署（进行中：前端 ✅ / 后端 ⏸）

- **C7a 前端 OSS 部署 ✅（2026-09-12 02:50）**
  - 产出：`app/deploy/upload_oss.py`（web → OSS 同步脚本，含 Content-Type 映射 + no-store）
  - 目标：`oss://clawshell-vault/web-spa/cad-coord-3d/`（16 文件 / 2.3MB 全部上传）
  - 线上地址：**`https://gzzhike.cn/web-spa/cad-coord-3d/index.html`**
  - 验证（绕代理直连 + headless 线上整页）：title ✓、列表读取云端数据（1 卡片「示例图纸」）✓、详情 3D 渲染 ✓、零错误 ✓
  - 备注：config.js 的 API_BASE 暂指本地 8791（上传/编辑功能待 FC 上线后更新重推）；浏览/3D/导出/分享已线上可用
- **C7b 后端 FC 部署 ⏸**：
  - 阻塞项：① Docker 操作等待用户确认（容器内转换验证 + 镜像构建）② FC 权限待验证（ossutilconfig 的 AK 是否含 FC 权限）
  - 技能情报：alicloud-fc-deploy（ACS3 签名 + WSGI handler）；DWG 转换（ODA）必须走容器方案
  - 备选情报：FC 代码包路线（zip）不适用（ODA 二进制 + Qt 依赖超限）

### P1 · 全态打磨 ✅

- 状态：完成（2026-09-12 03:00）
- 覆盖：空态（库 / 上传 / 分享失效）、加载态（库 / 详情）、错误态（上传 / 解析 / 网络 / 加载失败）、动效（toast / dialog 入场 / 卡片悬浮）、favicon.svg + meta 描述
- 响应式：桌面优先（内容容器 860px），基础自适应

### P2 · 端到端验证（核心项完成）

- 解析质量抽验（质量门第 4 项）：源 LINE 端点 10/10 命中；links 覆盖源线数；顶层文字命中 2/3（未命中者为长说明文本，非点名）；bbox 合理 ✓
- 线上分享全流程 ✓：线上版生成分享 → 独立页只读访问（3D 渲染 + 「只读分享」徽章）
  - 分享链接（保留供体验）：`https://gzzhike.cn/web-spa/cad-coord-3d/index.html#/share/EKFT0gyTQ_sW9_wTT_Waiw`
- SC 覆盖现状：SC1 / SC2 / SC4 / SC5 / SC6 已验证；SC3 本地全链 ✓ + 线上浏览 ✓（线上上传后端待 C7b）
- 收尾项：用户真实图纸到位后补充最终标定

### P3 · 项目说明文档 ✅

- 状态：完成（2026-09-12 03:05）
- 产出：`app/README.md`（架构图 / 目录 / 本地启动 / OSS 部署 / 凭据 / FAQ（转换引擎与阈值调整）/ 测试入口 / 数据模型）

### P4 · Review（预审完成，终版待 C7b）

- 状态：预审完成（2026-09-12 03:15）；产出：`06-CAD坐标拆解与3D还原_审查报告.md`
- 对照审查：完整性 9/10、一致性 ✅、标准合规 ✅、依赖闭合 🟡（FC）、受众适配 ✅
- 质量门 7 项：6 项通过，1 项部分（SC3 线上上传待 C7b）
- 反模式 9 条：零违反
- 蓝军摘要：Tiger ×2（真实图纸名称匹配 / FC 延宕）；Elephant ×1（Supabase 容量）
- 综合评分：87/100（预审）

---

## 修复记录（用户报 bug，2026-09-12）

### Bug 1：导出菜单"无法缩进"（无法收起）

- **根因**：`.dropdown-menu` 的 `display: flex`（作者样式）覆盖了 HTML `hidden` 属性的 UA 规则（`[hidden] { display: none }`），`hidden` 完全失效 → 菜单永远展开。
- **证据**：菜单开/关两态截图 **0 像素差异**；`elementsFromPoint` 命中 `dropdown-menu`（菜单一直盖在 3D 视图上方）；DOM 层级/交互排查确认。
- **修复**：`app.css` 增加 `.dropdown-menu[hidden] { display: none; }`。
- **隐患普查**：全项目 6 处 `hidden` 用法逐一核对（pick-info / viewer-tooltip / progress-area / error-area / file-input / export-menu）——仅 export-menu 一处受影响。

### Bug 2：3D 图一根"无连接端点的线"

- **根因**：viewer3d.js 自加的 AxesHelper（坐标轴）中，**Z 轴**从原点竖直伸出、不连接任何点/线（X/Y 轴恰与图纸边共线，故不显眼）。数据层 6 条线全部正常连接，无解析错误。
- **证据**：场景对象拆解（AxesHelper 6 顶点）+ "base vs 轴-off" 像素对照（643px 三色轴像素）+ REST 数据全量核对。
- **修复**：移除 AxesHelper（含 dispose 清理与调试句柄引用，改用 `scene`/`objects` 只读句柄供测试）。

### 修复验证（全部通过）

| 项 | 结果 |
| --- | --- |
| `verify_fix.py`（本地） | **11/11 PASS**（菜单三态 + 元素层级 + 像素断言 + 场景断言） |
| 回归 C2b（旋转/缩放/点选） | PASS |
| 回归 C5（CSV/XLSX/JSON 导出 + 菜单） | PASS |
| `verify_online.py`（线上） | **6/6 PASS** |
| 修复后 3D 画面 | 轴色像素 0（R/G/Y）——纯数据视图 |
| 部署 | OSS 17 文件更新（2026-09-12） |

- 新增测试基建：`bugscan1-6.py`（侦查）、`verify_fix.py` / `verify_online.py`（修复验证）、`cmp_png.py` / `analyze4.py`（像素分析）

---

## 演示图纸新增（用户需求，2026-09-12）

**需求**：在图纸库中新增含 X/Y/Z 三轴展开、不少于 50 点的复杂演示图纸。

**交付**：**「空间网架结构演示（64节点）」**（drawing_id `70120562-9800-4bf5-8e76-16adec50e482`）
- 结构：4×4×4 节点网格，3m×3m×3m（间距 1000mm），X/Y/Z 三轴各 4 层完整展开
- 规模：**64 点 / 171 连线**（轴向杆件 144 = 三向各 48；单元体对角线斜撑 27）
- 命名：节点名称 `P{i}{j}{k}`（1-based；P111 = 原点、P444 = 对角顶点），由 TEXT 就近匹配全量提取（无自动编号残留）

**链路（沿用「所有写入走解析服务」架构）**
1. `app/devtools/make_demo_frame.py`：ezdxf 生成 `app/testdata/space_frame_64.dxf` + 自检 6 项 PASS
2. `app/devtools/upload_demo_frame.py`：`POST /api/parse` 上传 → 解析入库 → PATCH 改名
3. 数据层复核：cad_points 实际 **64 行** / cad_links 实际 **171 行**；名称全部 `P[1-4]###` 且唯一；三轴各 [0,1000,2000,3000]
4. 3D 验证 `app/devtools/verify_demo_frame.py`（本地 + 线上双跑，**全 PASS**）：
   - 场景构成 64 点 / 171 线；程序化选中 + 真实鼠标点击均正常
   - 点选自洽抽验：P111 → (0,0,0)；P214 → (1000,0,3000)
   - 画面 1445 蓝点像素、点域铺展 493×439（立体感 ✓）
   - 截图：`app/devtools/screenshots/demo_{local,online}_viewer.png`

---

## DWG → DXF 转换可行性验证（用户请求，2026-09-12）

**结论：可行。** 六层 20 项全 PASS、0 警告（脚本 `app/devtools/test_dwg_pipeline.py`，报告 `app/testdata/verify_conv/report.json`）。

| 层 | 内容 | 结果 |
| --- | --- | --- |
| A 转换 | 4 个真实 DWG（R14/R2000/R2013/R2018）→ DXF | 4/4 ✓ 0.3–0.6s/文件，产物 855–1372KB |
| B 有效性 | ezdxf 读产物 + 实体统计 | 4/4 ✓（AC1032，68 实体/图） |
| C 解析 | coord_parser 解析产物 | 4/4 ✓ 3846 点 / 3736 线 |
| D 一致性 | 四版本转换+解析结果**逐点比对** | 3/3 ✓ 点/线/名称完全一致（转换无损） |
| E 端到端 | POST /api/parse 上传 DWG（R2018）→ 转换+解析+入库 | ✓ 4.8s；id `07cf015e-1c0b-4da3-940e-c7b6ad7875d1`；云端复核 3846/3846 点、3736/3736 线 |
| F 异常 | 损坏 DWG / 文件不存在 | ✓ 502 CONVERT_FAILED +「另存为 DXF」指引；参数校验明确报错 |

**环境说明**：本机 LibreDWG 未装 → 转换链**自动回退**至 ODA File Converter 27.1.0（`C:\Program Files\ODA\`），无需手工步骤。

**渲染链路验证**（`app/devtools/check_dwg_render.py`，本地+线上各 8 项全 PASS）：
- DWG 转换图（3846 点）3D 可渲染：点云顶点 3846 / 线顶点 7472 全部进 GPU、无 NaN、3846 个 distinct 点；点选交互正常（P0098 → (490.6, 4118.2, 0)）

**发现（数据特性，非转换缺陷）：示例工程图含"离群块"致初始视图被压缩**
- 定位：图中块引用 `bloko`（insert=(0,0,0)，scale=(3256.5, -1843.5, 3256.5)，rot=311°）——展开后几何延伸至 ±268 万；主图仅 x∈[-2451,9001] / y∈[-1583,3079]
- 独立佐证：转换产物 `$EXTMIN` = (-2680430, -1672547)——与原 DWG 一致（ODA 忠实转换）；4 版本转换逐点一致
- 影响：3D fitView 按全量 bbox（跨 340 万）取景 → 主图压缩至 <1px → 演示体验受限
- 诊断链：`diag_points.py`（顶点/NaN/尺寸对照实验：size 7→30）→ `diag_project.py`（投影分布：p10=p50=p90 同点）→ `diag_outliers.py` + DXF grep → 块引用缩放
- 建议（待用户决策）：fitView 稳健化——按分位数剔除尾部离群点计算初始 center/size，离群块保留、可缩放查看

---

## 修复：大图取景被离群对象撑爆（用户请求，2026-09-12）

**背景**：DWG 验证发现示例工程图含缩放异常的块引用（`bloko`，scale≈3256），展开几何延伸至 ±268 万坐标；3D 按全量 bbox 取景时主图被压缩到亚像素级。

**修复**（`app/web/js/viewer3d.js`）：
- 取景改用**稳健边界**：1%~99% 分位数界定主群体 + 12% 外扩；离群点仍全量渲染（远裁剪面保持全量跨度），可通过缩放查看
- 小图保护：<200 点直接按全量取景（零回归）

**验证**：
- 大图（3846 点）：蓝点像素 381 → 2772（7.3×），非背景 7572 → 12193，点域铺展 300×308 → 382×334
- 64 点演示图回归：完全一致（1445 蓝像素、P214 点选正确）
- 已部署 OSS，线上/本地双环境全 PASS

## 演示图纸新增：榫卯格构（647 节点，用户请求，2026-09-12）

**设计**（`app/devtools/make_mortise_frame.py`，种子 42 可复现）——模拟多零件榫卯拼装体骨架：
- 9 层不规则井字格架：层规格 8×8~10×9 变化、层中心漂移 ±150mm、格距/层高 ±15%~18% 抖动
- 层内 X/Y 双向梁 + 15% 单元斜撑；层间立柱（四角强制 + 35% 采样）
- 度数硬保证：生成后校验 + 自动补撑（本轮实际 0 补）；**断言 min degree ≥ 3**

**规模**：647 节点 / 1433 连线；度数 min/avg/max = 3/4.43/8（分布 3→108 / 4→252 / 5→200 / 6→76 / 7→10 / 8→1）

**验证**（`app/devtools/verify_mortise_frame.py`，本地+线上 19 项 × 2 全 PASS）：
- 数据层（Supabase 直查独立重算）：647 点 / 1433 线 / 端点全部有效 / min 连接数 ≥3
- 3D：渲染 647 点 2866 线顶点、点选 M3-41 / M5-06、11212 蓝像素、立体铺展 376×378
- 命名 `M{层}-{序号}`，全链路无自动编号

## 项目上传 GitHub（用户请求，2026-09-12）

- **仓库**：https://github.com/jorinyang/cad-coord-3d （public，127 文件）
- **Release**：v0.9.0（模块功能详列：解析服务 / 数据层 / 前端 / 演示数据 / 验证状态）
- **README**：仓库根新增项目主页（能力 / 架构图 / 快速开始 / 演示图纸 / 测试 / 构建文档索引）；app/README 凭据段改为环境变量说明
- **安全检查**：全仓凭据特征扫描 0 命中；`.gitignore` 排除 .venv / __pycache__ / supabase/.temp
- **环境问题定位**：本机环境变量残留 WSL 时代代理（`http_proxy / https_proxy` = `172.24.48.1:7890`）导致 gh/git 请求 EOF 中断；**清掉该变量后 GitHub 直连完全正常**（此前「push 被墙」的判断由此修正）

