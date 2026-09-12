# -*- coding: utf-8 -*-
"""上传 space_frame_64.dxf → 解析入库 → 重命名为演示名称 → 打印验证信息。

前置：本地后端 8791 在跑；先执行 make_demo_frame.py 生成 DXF。
用法：python app/devtools/upload_demo_frame.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

API = "http://127.0.0.1:8791"
ROOT = Path(__file__).resolve().parent.parent
DXF = ROOT / "testdata" / "space_frame_64.dxf"
NAME = "空间网架结构演示（64节点）"


def main() -> int:
    if not DXF.exists():
        print(f"[error] 找不到 {DXF}，请先运行 make_demo_frame.py")
        return 1

    with DXF.open("rb") as f:
        r = httpx.post(f"{API}/api/parse", files={"file": (DXF.name, f, "application/dxf")}, timeout=120)
    r.raise_for_status()
    body = r.json()
    assert body.get("ok"), body
    d = body["data"]
    did = d["drawing_id"]
    m = d["meta"]
    print(f"[upload] drawing_id={did}")
    print(f"[upload] points={m['point_count']} links={m['link_count']} skipped={m['skipped_entities']}")

    r2 = httpx.patch(f"{API}/api/drawings/{did}", json={"name": NAME}, timeout=30)
    r2.raise_for_status()
    print(f"[rename] ok -> {r2.json()['data']['name']}")

    print(f"[done] id={did}")
    print(f"[next] 本地: http://127.0.0.1:8789/#/detail/{did}")
    print(f"[next] 线上: https://gzzhike.cn/web-spa/cad-coord-3d/index.html#/detail/{did}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
