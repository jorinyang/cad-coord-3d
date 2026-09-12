# -*- coding: utf-8 -*-
"""生成「空间网架结构演示」DXF —— 64 节点 / 171 连线，全程 XYZ 三维。

结构：4×4×4 节点网格（间距 1000mm，总尺寸 3m³）
- X/Y/Z 三向轴向杆件：每向 48 根 → 144
- 单元体对角线斜撑：3×3×3 = 27 根
- 每节点配 TEXT 名称「P{i}{j}{k}」（1-based；P111 = 原点，P444 = 对角顶点）

输出：app/testdata/space_frame_64.dxf
用法：python app/devtools/make_demo_frame.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import ezdxf

N = 4
STEP = 1000.0
ROOT = Path(__file__).resolve().parent.parent          # app/
OUT = ROOT / "testdata" / "space_frame_64.dxf"
sys.path.insert(0, str(ROOT / "server"))


def build_dxf(path: Path) -> None:
    doc = ezdxf.new("R2010")
    doc.layers.add("FRAME", color=7)
    doc.layers.add("LABEL", color=1)
    msp = doc.modelspace()

    def P(i: int, j: int, k: int):
        return (i * STEP, j * STEP, k * STEP)

    n_axis = 0
    for i in range(N):
        for j in range(N):
            for k in range(N):
                if i < N - 1:
                    msp.add_line(P(i, j, k), P(i + 1, j, k), dxfattribs={"layer": "FRAME"}); n_axis += 1
                if j < N - 1:
                    msp.add_line(P(i, j, k), P(i, j + 1, k), dxfattribs={"layer": "FRAME"}); n_axis += 1
                if k < N - 1:
                    msp.add_line(P(i, j, k), P(i, j, k + 1), dxfattribs={"layer": "FRAME"}); n_axis += 1

    n_diag = 0
    for i in range(N - 1):
        for j in range(N - 1):
            for k in range(N - 1):
                msp.add_line(P(i, j, k), P(i + 1, j + 1, k + 1), dxfattribs={"layer": "FRAME"}); n_diag += 1

    for i in range(N):
        for j in range(N):
            for k in range(N):
                t = msp.add_text(f"P{i + 1}{j + 1}{k + 1}", height=80, dxfattribs={"layer": "LABEL"})
                t.dxf.insert = P(i, j, k)

    doc.saveas(path)
    print(f"[gen] saved {path}")
    print(f"[gen] axis_lines={n_axis} diagonal_lines={n_diag} total_lines={n_axis + n_diag} texts={N ** 3}")


def verify(path: Path) -> int:
    from coord_parser import parse_dxf

    data = parse_dxf(path, name="空间网架结构演示（64节点）")
    m = data["meta"]
    pts = data["points"]
    print(f"[verify] points={m['point_count']} links={m['link_count']} skipped={m['skipped_entities']}")

    names = [p["name"] for p in pts]
    check = {
        "点数=64": m["point_count"] == 64,
        "线数=171": m["link_count"] == 171,
        "P111 在名称中": "P111" in names,
        "P444 在名称中": "P444" in names,
        "无自动编号残留": not any(re.fullmatch(r"P\d{4}", n) for n in names),
    }
    xs = sorted({p["x"] for p in pts})
    ys = sorted({p["y"] for p in pts})
    zs = sorted({p["z"] for p in pts})
    check["三轴展开(x/y/z 各 4 层)"] = (len(xs), len(ys), len(zs)) == (4, 4, 4)

    ok = True
    for k, v in check.items():
        print(f"[verify] {'PASS' if v else 'FAIL'} {k}")
        ok = ok and v

    sample = {p["name"]: (p["x"], p["y"], p["z"]) for p in pts}
    print("[verify] P111 =", sample.get("P111"), " P234 =", sample.get("P234"), " P444 =", sample.get("P444"))
    return 0 if ok else 1


if __name__ == "__main__":
    build_dxf(OUT)
    sys.exit(verify(OUT))
