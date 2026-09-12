# -*- coding: utf-8 -*-
"""扫描转换产物 DXF，定位极端坐标（离群点）的来源实体。"""
import sys
from pathlib import Path

import ezdxf

DXF = Path(r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\testdata\verify_conv\example_2018.dxf")
LIM = 100_000  # 极端阈值（主群体在 ±1 万内）


def pts_of(e):
    t = e.dxftype()
    out = []
    try:
        if t == "LINE":
            out = [e.dxf.start, e.dxf.end]
        elif t == "LWPOLYLINE":
            out = [(p[0], p[1], e.dxf.elevation) for p in e.get_points()]
        elif t == "POLYLINE":
            out = [v.dxf.location for v in e.vertices]
        elif t == "INSERT":
            out = [e.dxf.insert]
        elif t == "POINT":
            out = [e.dxf.location]
    except Exception:
        pass
    return out


doc = ezdxf.readfile(DXF)
ms = doc.modelspace()

print("=== 模型空间极端坐标实体 ===")
hits = []
for e in ms:
    for p in pts_of(e):
        x, y, z = p[0], p[1], (p[2] if len(p) > 2 else 0)
        if abs(x) > LIM or abs(y) > LIM:
            hits.append((e.dxftype(), e.dxf.handle, round(x), round(y), round(z)))
            break
print(f"数量: {len(hits)}")
for h in hits[:40]:
    print(" ", h)

print()
print("=== 块定义内部极端坐标 ===")
bhits = []
for blk in doc.blocks:
    for e in blk:
        for p in pts_of(e):
            x, y, z = p[0], p[1], (p[2] if len(p) > 2 else 0)
            if abs(x) > LIM or abs(y) > LIM:
                bhits.append((blk.name, e.dxftype(), e.dxf.handle, round(x), round(y), round(z)))
                break
print(f"数量: {len(bhits)}")
for h in bhits[:40]:
    print(" ", h)

print()
print("=== 头部变量检查（EXTMIN/EXTMAX） ===")
try:
    print("EXTMIN:", doc.header.get("$EXTMIN"))
    print("EXTMAX:", doc.header.get("$EXTMAX"))
except Exception as e:
    print("header read failed:", e)
