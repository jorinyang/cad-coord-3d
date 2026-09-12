# -*- coding: utf-8 -*-
"""生成「榫卯格构演示」DXF —— 不规则多层格构，节点 >=500，每节点连接 >=3。

设计（模拟多零件榫卯拼装体的骨架）：
- 9 层不规则井字格架：每层网格规格不同、层中心随机漂移、格距/层高抖动
- 层内：X/Y 双向梁 + 随机单元斜撑（斜交构件，15%）
- 层间：立柱（四角强制 + 其余 35% 采样）→ 三维咬合
- 度数硬保证：生成后对任何连接数 <3 的节点补撑，最终 min degree >= 3（断言）
- 节点命名 M{层}-{序号}（2 位）

输出：app/testdata/mortise_frame.dxf
用法：python app/devtools/make_mortise_frame.py
"""
from __future__ import annotations

import math
import random
import re
import sys
from collections import Counter
from pathlib import Path

import ezdxf

SEED = 42
ROOT = Path(__file__).resolve().parent.parent          # app/
OUT = ROOT / "testdata" / "mortise_frame.dxf"
sys.path.insert(0, str(ROOT / "server"))

# 每层 (rows, cols)——不规则轮廓（中部最大，上下收敛）
SPEC = [(8, 8), (9, 9), (10, 9), (9, 10), (9, 9), (8, 9), (8, 8), (7, 8), (7, 7)]

STEP = 250.0     # 基准格距 mm
LAYER_H = 260.0  # 基准层高 mm


def norm(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def build_geometry(rng: random.Random):
    """返回 (points, names, edges, n_fix)。"""
    points: list[tuple[float, float, float]] = []
    names: list[str] = []
    edges: set[tuple[int, int]] = set()

    # ---------- 1) 各层格点（不规则：层中心漂移 + 格距抖动 + 位置抖动） ----------
    layers = []
    z = 0.0
    for li, (rows, cols) in enumerate(SPEC):
        z += LAYER_H * (1 + rng.uniform(-0.15, 0.15))
        cx = rng.uniform(-150, 150)
        cy = rng.uniform(-150, 150)
        xs = [0.0]
        for _ in range(cols - 1):
            xs.append(xs[-1] + STEP * (1 + rng.uniform(-0.18, 0.18)))
        ys = [0.0]
        for _ in range(rows - 1):
            ys.append(ys[-1] + STEP * (1 + rng.uniform(-0.18, 0.18)))
        grid = {}
        for r in range(rows):
            for c in range(cols):
                grid[(r, c)] = len(points)
                points.append((xs[c] + cx + rng.uniform(-40, 40),
                               ys[r] + cy + rng.uniform(-40, 40),
                               z))
                names.append(f"M{li + 1}-{r * cols + c + 1:02d}")
        layers.append({"rows": rows, "cols": cols, "grid": grid})

    # ---------- 2) 层内梁 + 随机斜撑 ----------
    for lay in layers:
        rows, cols, g = lay["rows"], lay["cols"], lay["grid"]
        for r in range(rows):
            for c in range(cols - 1):
                edges.add(norm(g[(r, c)], g[(r, c + 1)]))
        for r in range(rows - 1):
            for c in range(cols):
                edges.add(norm(g[(r, c)], g[(r + 1, c)]))
        for r in range(rows - 1):
            for c in range(cols - 1):
                if rng.random() < 0.15:
                    edges.add(norm(g[(r, c)], g[(r + 1, c + 1)]))

    # ---------- 3) 层间立柱（四角强制 + 35% 采样） ----------
    def nearest_in(lay, x: float, y: float):
        best, bd = None, float("inf")
        for gi in lay["grid"].values():
            px, py, _pz = points[gi]
            d = (px - x) ** 2 + (py - y) ** 2
            if d < bd:
                bd, best = d, gi
        return best

    for k in range(len(layers) - 1):
        a, b = layers[k], layers[k + 1]
        forced = {(0, 0), (0, a["cols"] - 1), (a["rows"] - 1, 0), (a["rows"] - 1, a["cols"] - 1)}
        for rc, gi in a["grid"].items():
            if rc in forced or rng.random() < 0.35:
                x, y, _z = points[gi]
                j = nearest_in(b, x, y)
                if j is not None and j != gi:
                    edges.add(norm(gi, j))

    # ---------- 4) 度数硬保证：<3 的节点补撑 ----------
    adj = Counter()
    for a, b in edges:
        adj[a] += 1
        adj[b] += 1
    n_fix = 0
    for i in range(len(points)):
        if adj[i] >= 3:
            continue
        xi, yi, zi = points[i]
        cands = []
        for j in range(len(points)):
            if j == i:
                continue
            xj, yj, zj = points[j]
            cands.append((math.dist((xi, yi, zi), (xj, yj, zj)), j))
        cands.sort()
        for d, j in cands:
            if adj[i] >= 3:
                break
            if d > 1200:          # 不拉诡异长边
                break
            e = norm(i, j)
            if e in edges:
                continue
            edges.add(e)
            adj[i] += 1
            adj[j] += 1
            n_fix += 1

    bad = [i for i in range(len(points)) if adj[i] < 3]
    if bad:
        raise RuntimeError(f"度数修复失败：{len(bad)} 个节点仍 <3（示例 {names[bad[0]]}）")

    return points, names, edges, n_fix


def build_dxf(path: Path, points, names, edges) -> None:
    doc = ezdxf.new("R2010")
    doc.layers.add("MORTISE", color=7)
    doc.layers.add("LABEL", color=1)
    msp = doc.modelspace()
    for a, b in edges:
        msp.add_line(points[a], points[b], dxfattribs={"layer": "MORTISE"})
    for i, nm in enumerate(names):
        t = msp.add_text(nm, height=60, dxfattribs={"layer": "LABEL"})
        t.dxf.insert = points[i]
    doc.saveas(path)
    print(f"[gen] points={len(points)} edges={len(edges)} -> {path}")


def verify(path: Path, min_pts: int = 500, min_deg: int = 3) -> int:
    from coord_parser import parse_dxf

    data = parse_dxf(path, name="榫卯格构演示")
    m = data["meta"]
    pts = data["points"]
    links = data["links"]
    deg = Counter()
    for l in links:
        deg[l["from"]] += 1
        deg[l["to"]] += 1
    degs = [deg.get(p["name"], 0) for p in pts]
    dmin, dmax = min(degs), max(degs)
    davg = sum(degs) / len(degs)

    check = {
        f"点数 >= {min_pts}": m["point_count"] >= min_pts,
        f"最小连接数 >= {min_deg}": dmin >= min_deg,
        "名称全部为 M#-## 格式": all(re.fullmatch(r"M\d-\d{2}", p["name"]) for p in pts),
        "三维结构（各层 z 不同）": len({round(p["z"], 1) for p in pts}) >= 5,
    }
    print(f"[verify] points={m['point_count']} links={m['link_count']} "
          f"deg min/avg/max = {dmin}/{davg:.2f}/{dmax} skipped={m['skipped_entities']}")
    print("[verify] 度数分布:", dict(sorted(Counter(degs).items())))
    ok = True
    for k, v in check.items():
        print(f"[verify] {'PASS' if v else 'FAIL'} {k}")
        ok = ok and v
    return 0 if ok else 1


if __name__ == "__main__":
    rng = random.Random(SEED)
    points, names, edges, n_fix = build_geometry(rng)
    build_dxf(OUT, points, names, edges)
    print(f"[gen] fix_edges={n_fix}")
    sys.exit(verify(OUT))
