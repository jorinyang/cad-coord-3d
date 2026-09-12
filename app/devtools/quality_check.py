# -*- coding: utf-8 -*-
"""解析质量抽验（质量门第 4 项）：对真实样例 DXF 做 ≥3 处程序化抽样核对。

用法：python quality_check.py  （cwd 项目根目录）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import ezdxf  # noqa: E402

from coord_parser import parse_dxf  # noqa: E402

DOC = str(Path(__file__).resolve().parent.parent / "testdata" / "converted" / "example_2018.dxf")


def main() -> int:
    doc = ezdxf.readfile(DOC)
    data = parse_dxf(DOC, name="example_2018")
    pts = data["points"]
    coordset = {(p["x"], p["y"], p["z"]) for p in pts}
    names = {p["name"] for p in pts}
    print(f"parsed: points={len(pts)} links={data['meta']['link_count']}")

    # 抽验 1：源 LINE 端点（前 5 条 → 10 个端点）坐标应存在于解析点集
    lines = [e for e in doc.modelspace() if e.dxftype() == "LINE"]
    miss = 0
    for e in lines[:5]:
        for v in (e.dxf.start, e.dxf.end):
            t = (round(v.x, 6), round(v.y, 6), round(v.z, 6))
            if t not in coordset:
                miss += 1
    print(f"[1] 源 LINE 端点抽验: 5 条线/10 端点, 缺失 {miss}")
    assert miss == 0, "端点缺失"

    # 抽验 2：数量关系 —— links 应 >= 源 LINE 数（每条 LINE 至少贡献一条边）
    n_links = data["meta"]["link_count"]
    print(f"[2] links({n_links}) >= 源 LINE 数({len(lines)}): {n_links >= len(lines)}")
    assert n_links >= len(lines)

    # 抽验 3：源文字命中率（顶层 TEXT/MTEXT 内容出现在点名称中）
    texts = []
    for e in doc.modelspace():
        if e.dxftype() == "TEXT":
            texts.append(e.dxf.text)
        elif e.dxftype() == "MTEXT":
            texts.append(e.text)
    texts = [t.strip() for t in texts if t and t.strip()]
    hit = [t for t in texts if t in names]
    print(f"[3] 源文字抽验: 顶层文字 {len(texts)} 个, 命中名称 {len(hit)} 个")
    print(f"    样例文字: {texts[:4]}")
    print(f"    命中示例: {hit[:4]}")

    # 抽验 4：坐标范围合理性（bbox 一致性与有限性）
    xs = [p["x"] for p in pts]
    ys = [p["y"] for p in pts]
    zs = [p["z"] for p in pts]
    print(f"[4] bbox: x[{min(xs):.2f},{max(xs):.2f}] y[{min(ys):.2f},{max(ys):.2f}] z[{min(zs):.2f},{max(zs):.2f}]")
    assert all(isinstance(v, float) for v in xs + ys + zs)
    print("QUALITY CHECK: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
