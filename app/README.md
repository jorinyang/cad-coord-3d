# CAD 坐标拆解与 3D 还原（cad-coord-3d）

上传 .dwg / .dxf 图纸 → 自动拆解为「坐标点 + 连接关系」→ 云端留存 → 3D 演示还原。

## 架构

```
前端 SPA（阿里云 OSS 静态托管）
  ├─ 只读直连 Supabase（图纸库 / 详情 / 分享快照）
  └─ 上传 / 编辑 → 解析服务（FastAPI）
                     ├─ 转换链：LibreDWG → ODA File Converter（回退）
                     ├─ 解析：ezdxf（顶点归一 / 连线构建 / 名称就近匹配 / 缺名补号）
                     └─ 写库：psycopg2 → Supabase（service key）
```

- 前端零写权限：读走 Supabase REST（publishable key），写只经后端 service key。
- 分享 = 快照：生成独立只读链接，可随时撤销。

## 目录

```
app/
├── web/          前端（原生 ES Modules，无构建链；Three.js / SheetJS 本地 vendor）
├── server/       解析服务（FastAPI + ezdxf）
├── deploy/       OSS 上传脚本（upload_oss.py）
├── devtools/     E2E 测试脚本（headless Chrome CDP）+ 质量抽验
└── testdata/     测试素材（自造图 + 公开样例 + 转换产物）
```

## 本地启动

```bash
cd app/server && ../.venv/Scripts/python.exe main.py     # 后端 → 127.0.0.1:8791
cd app/web    && ../.venv/Scripts/python.exe -m http.server 8789   # 前端 → 127.0.0.1:8789
# 浏览器打开 http://127.0.0.1:8789/
```

## 部署（OSS）

```bash
python app/deploy/upload_oss.py          # 同步 app/web → oss://clawshell-vault/web-spa/cad-coord-3d/
python app/deploy/upload_oss.py --list   # 查看线上对象
```

线上地址：`https://gzzhike.cn/web-spa/cad-coord-3d/index.html`
（目录短地址会返回根页 Error Document——对外一律使用完整文件名 URL）

## 凭据

| 用途 | 位置 |
| --- | --- |
| Supabase（DB / REST / 服务端写） | `~/.ClawShell/.env.supabase` |
| OSS | `~/.ossutilconfig` |

⚠️ 本项目 Supabase 项目必须使用**新式 key**：前端 `SUPABASE_PUBLISHABLE_KEY`（sb_publishable_*），后端 `SUPABASE_SERVICE_KEY`（sb_secret_*）。legacy JWT（eyJ…）已失效（401）。

## 常见调整（FAQ）

| 想要 | 改哪 |
| --- | --- |
| 换 DWG 转换引擎 / 指定 ODA 路径 | `server/converter.py`（回退链：LibreDWG → ODA）；环境变量 `ODA_CONVERTER_PATH` |
| 名称匹配距离阈值 | `server/coord_parser.py` → `NAME_MATCH_RATIO`（默认包围盒对角线 1%） |
| 顶点归并容差 | `server/coord_parser.py` → `MERGE_TOL_RATIO`（默认 1e-7，下限 1e-9） |
| 解析实体范围 | `server/coord_parser.py` → `_extract()`（当前：LINE / LWPOLYLINE / POLYLINE / ARC / POINT + INSERT 递归展开 + TEXT / MTEXT / ATTRIB；其余忽略并统计） |
| 上传大小上限 | `server/main.py` → `MAX_UPLOAD`（默认 100MB） |
| 端口 | 后端 `main.py`（8791）；前端静态服务（8789） |
| 分享快照 | 同图仅保留一个（再次分享即刷新旧链接） |

## 测试

```bash
cd app/server
python test_converter.py     # 转换链自测
python test_parser.py        # 解析器断言（自造图 + 样例统计）
python test_main.py          # API 自测（含入库/重命名/删除，测试后自动清理）

# E2E（需 9225 端口 headless Chrome + 后端/前端在跑）
python app/devtools/cdp_e2e_c3.py    # 上传→详情→列表→重命名→删除 全流程
python app/devtools/cdp_e2e_c4.py    # 编辑修正
python app/devtools/cdp_e2e_c5.py    # 导出（下载文件内容校验）
python app/devtools/cdp_e2e_c6.py    # 分享
python app/devtools/verify_fix.py    # 菜单/3D 修复验证（像素级断言）
python app/devtools/verify_online.py # 线上部署验证（gzzhike.cn）
python app/devtools/verify_demo_frame.py local|online  # 演示图纸 3D 验证（64节点）
python app/devtools/test_dwg_pipeline.py  # DWG→DXF 转换六层验证（A-F）
python app/devtools/check_dwg_render.py local|online  # DWG 转换图 3D 渲染检查
python app/devtools/quality_check.py # 解析质量抽验
```

## 数据模型（Supabase）

| 表 | 用途 |
| --- | --- |
| `cad_drawings` | 图纸元数据（名称/格式/点数/线数/时间） |
| `cad_points` | 坐标点（name / x / y / z / seq） |
| `cad_links` | 连接关系（from_point_id → to_point_id） |
| `cad_share_snapshots` | 分享快照（token + payload jsonb） |

RLS：`anon` 只读；写入仅后端 service key（绕过 RLS）。
