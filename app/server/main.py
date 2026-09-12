"""
main.py — 解析服务 API（FastAPI）

端点：
- GET    /api/health                健康检查
- POST   /api/parse                 上传 DWG/DXF → 转换 → 解析 → 入库 → 返回坐标 JSON
- PATCH  /api/drawings/{id}         重命名图纸
- DELETE /api/drawings/{id}         删除图纸（连带点/边）

启动（本地开发）：python main.py  → http://127.0.0.1:8791
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import store
from converter import ConversionError, convert_dwg_to_dxf
from coord_parser import parse_dxf

SERVICE_VERSION = "0.2.0"
MAX_UPLOAD = 100 * 1024 * 1024  # 100MB

app = FastAPI(title="CAD 坐标拆解服务", version=SERVICE_VERSION)

# 开发期放开；C7 部署时收紧到前端域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def ok(data):
    return {"ok": True, "data": data}


def err(code: str, message: str, status: int = 400):
    return JSONResponse(status_code=status, content={"ok": False, "error": {"code": code, "message": message}})


def _magic_check(content: bytes, suffix: str) -> bool:
    """文件头校验：DWG 必须 AC10xx/AC12xx 魔数；DXF 检查文本 SECTION / 二进制标记。"""
    if suffix == ".dwg":
        return content[:4] in (b"AC10", b"AC12")
    head4k = content[:4096]
    if head4k.startswith(b"AutoCAD Binary DXF"):
        return True
    return b"SECTION" in head4k


@app.get("/api/health")
def health():
    return ok({"service": "cad-coord-parse", "version": SERVICE_VERSION})


@app.post("/api/parse")
async def parse(file: UploadFile = File(...)):
    name = file.filename or "unnamed"
    suffix = Path(name).suffix.lower()
    if suffix not in (".dwg", ".dxf"):
        return err("BAD_REQUEST", f"不支持的文件类型：{suffix or '(无扩展名)'}（仅支持 .dwg / .dxf）")

    content = await file.read()
    if not content:
        return err("BAD_REQUEST", "文件为空")
    if len(content) > MAX_UPLOAD:
        return err("FILE_TOO_LARGE", f"文件超过 {MAX_UPLOAD // 1024 // 1024}MB 上限")
    if not _magic_check(content, suffix):
        return err("BAD_REQUEST", "文件内容与扩展名不符（文件头校验失败），请确认文件类型")

    workdir = Path(tempfile.mkdtemp(prefix="parse_"))
    try:
        src = workdir / f"input{suffix}"
        src.write_bytes(content)

        if suffix == ".dwg":
            try:
                dxf_path = convert_dwg_to_dxf(src, workdir=workdir)
            except ConversionError as e:
                return err("CONVERT_FAILED", str(e), 502)
        else:
            dxf_path = src

        try:
            data = parse_dxf(dxf_path, name=Path(name).stem, source_format=suffix.lstrip("."))
        except Exception as e:
            return err("PARSE_FAILED", f"解析失败：{type(e).__name__}: {e}", 502)

        try:
            drawing_id = store.save_drawing(
                name=data["meta"]["name"],
                source_format=data["meta"]["source_format"],
                source_filename=name,
                points=data["points"],
                links=data["links"],
            )
        except Exception as e:
            return err("SAVE_FAILED", f"数据保存失败：{type(e).__name__}: {e}", 502)

        data["drawing_id"] = drawing_id
        return ok(data)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


class RenameBody(BaseModel):
    name: str = ""


@app.patch("/api/drawings/{drawing_id}")
def rename_drawing(drawing_id: str, body: RenameBody):
    new_name = (body.name or "").strip()
    if not new_name:
        return err("BAD_REQUEST", "名称不能为空")
    try:
        done = store.rename_drawing(drawing_id, new_name)
    except Exception as e:
        return err("INTERNAL", f"重命名失败：{type(e).__name__}: {e}", 500)
    if not done:
        return err("NOT_FOUND", "图纸不存在", 404)
    return ok({"id": drawing_id, "name": new_name})


@app.delete("/api/drawings/{drawing_id}")
def delete_drawing(drawing_id: str):
    try:
        done = store.delete_drawing(drawing_id)
    except Exception as e:
        return err("INTERNAL", f"删除失败：{type(e).__name__}: {e}", 500)
    if not done:
        return err("NOT_FOUND", "图纸不存在", 404)
    return ok({"id": drawing_id, "deleted": True})


class PointRenameBody(BaseModel):
    name: str = ""


@app.patch("/api/drawings/{drawing_id}/points/{point_id}")
def rename_point(drawing_id: str, point_id: str, body: PointRenameBody):
    name = (body.name or "").strip()
    if not name:
        return err("BAD_REQUEST", "名称不能为空")
    try:
        res = store.rename_point(drawing_id, point_id, name)
    except Exception as e:
        return err("INTERNAL", f"重命名失败：{type(e).__name__}: {e}", 500)
    if res == "not_found":
        return err("NOT_FOUND", "坐标点不存在", 404)
    if res == "conflict":
        return err("CONFLICT", f"名称「{name}」已存在", 409)
    return ok({"id": point_id, "name": name})


@app.delete("/api/drawings/{drawing_id}/points/{point_id}")
def delete_point(drawing_id: str, point_id: str):
    try:
        counts = store.delete_point(drawing_id, point_id)
    except Exception as e:
        return err("INTERNAL", f"删除失败：{type(e).__name__}: {e}", 500)
    if counts is None:
        return err("NOT_FOUND", "坐标点不存在", 404)
    return ok(counts)


@app.delete("/api/drawings/{drawing_id}/links/{link_id}")
def delete_link(drawing_id: str, link_id: str):
    try:
        counts = store.delete_link(drawing_id, link_id)
    except Exception as e:
        return err("INTERNAL", f"删除失败：{type(e).__name__}: {e}", 500)
    if counts is None:
        return err("NOT_FOUND", "连接不存在", 404)
    return ok(counts)


@app.post("/api/drawings/{drawing_id}/share")
def create_share(drawing_id: str):
    try:
        payload = store.load_drawing_payload(drawing_id)
    except Exception as e:
        return err("INTERNAL", f"分享失败：{type(e).__name__}: {e}", 500)
    if payload is None:
        return err("NOT_FOUND", "图纸不存在", 404)
    try:
        token = store.create_share(drawing_id, payload)
    except Exception as e:
        return err("INTERNAL", f"分享失败：{type(e).__name__}: {e}", 500)
    return ok({"token": token})


@app.delete("/api/share/{token}")
def delete_share(token: str):
    try:
        done = store.delete_share(token)
    except Exception as e:
        return err("INTERNAL", f"撤销失败：{type(e).__name__}: {e}", 500)
    if not done:
        return err("NOT_FOUND", "分享不存在或已撤销", 404)
    return ok({"token": token, "deleted": True})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8791)
