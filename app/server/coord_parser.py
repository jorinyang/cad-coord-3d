"""
coord_parser.py — CAD 图纸坐标解析核心

流程：DXF → 实体提取 → 顶点归一（容差去重）→ 连线构建 → 名称匹配（就近、一对一）
     → 缺名补号（P0001…）→ 标准坐标 JSON（03-标准规范 第二节）。

v1 提取范围：
- 几何：LINE / LWPOLYLINE / POLYLINE / ARC（端点成边）/ POINT；INSERT 递归展开（深度 ≤ 5）
- 名称：TEXT / MTEXT / INSERT 属性（ATTRIB）
- 忽略并统计：DIMENSION / HATCH / CIRCLE / SPLINE / ELLIPSE / REGION 等
"""
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import ezdxf

MAX_INSERT_DEPTH = 5
NAME_MATCH_RATIO = 0.01  # 名称匹配阈值 = 包围盒对角线 × 1%（实测校准）
MERGE_TOL_RATIO = 1e-7   # 顶点归并容差 = 包围盒对角线 × 1e-7（下限 1e-9）
AUTO_NAME_FMT = "P{:04d}"
ROUND_DIGITS = 6

_MTEXT_FMT = re.compile(r"\\[A-Za-z][^;\\]*;")


@dataclass
class Segment:
    a: tuple[float, float, float]
    b: tuple[float, float, float]


@dataclass
class TextItem:
    text: str
    pos: tuple[float, float, float]


@dataclass
class Extraction:
    segments: list[Segment] = field(default_factory=list)
    points: list[tuple[float, float, float]] = field(default_factory=list)
    texts: list[TextItem] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)

    def skip(self, t: str) -> None:
        self.skipped[t] = self.skipped.get(t, 0) + 1


def _v3(v) -> tuple[float, float, float]:
    try:
        return (float(v[0]), float(v[1]), float(v[2]))
    except (IndexError, TypeError):
        return (float(v[0]), float(v[1]), 0.0)


def _clean_text(s: str | None) -> str:
    s = s or ""
    s = _MTEXT_FMT.sub("", s)          # 清 MTEXT 格式码 \fArial|b0; 等
    s = s.replace("\\P", " ").replace("\\p", " ")
    s = s.replace("{", "").replace("}", "").strip()
    return s


def _polyline_segments(ext: Extraction, pts: list[tuple[float, float, float]], closed: bool) -> None:
    for i in range(len(pts) - 1):
        ext.segments.append(Segment(pts[i], pts[i + 1]))
    if closed and len(pts) > 2:
        ext.segments.append(Segment(pts[-1], pts[0]))


def _extract(doc) -> Extraction:
    ext = Extraction()

    def handle(e, depth: int = 0) -> None:
        t = e.dxftype()
        if t == "INSERT":
            if depth >= MAX_INSERT_DEPTH:
                ext.skip("INSERT(depth-limit)")
                return
            for a in (getattr(e, "attribs", None) or []):
                try:
                    ext.texts.append(TextItem(_clean_text(a.dxf.text), _v3(a.dxf.insert)))
                except Exception:
                    pass
            try:
                subs = list(e.virtual_entities())
            except Exception:
                ext.skip("INSERT(virtual-fail)")
                return
            for s in subs:
                handle(s, depth + 1)
            return
        if t == "LINE":
            ext.segments.append(Segment(_v3(e.dxf.start), _v3(e.dxf.end)))
        elif t == "LWPOLYLINE":
            z = float(getattr(e.dxf, "elevation", 0.0) or 0.0)
            pts = [(float(p[0]), float(p[1]), z) for p in e.get_points("xy")]
            _polyline_segments(ext, pts, bool(e.closed))
        elif t == "POLYLINE":
            try:
                pts = [_v3(p) for p in e.points()]
            except Exception:
                pts = []
            try:
                closed = bool(e.is_closed)
            except Exception:
                closed = False
            _polyline_segments(ext, pts, closed)
        elif t == "POINT":
            ext.points.append(_v3(e.dxf.location))
        elif t == "ARC":
            ext.segments.append(Segment(_v3(e.start_point), _v3(e.end_point)))
        elif t == "TEXT":
            try:
                pos = _v3(e.dxf.insert)
            except Exception:
                pos = (0.0, 0.0, 0.0)
            ext.texts.append(TextItem(_clean_text(e.dxf.text), pos))
        elif t == "MTEXT":
            try:
                pos = _v3(e.dxf.insert)
            except Exception:
                pos = (0.0, 0.0, 0.0)
            ext.texts.append(TextItem(_clean_text(e.text), pos))
        else:
            ext.skip(t)

    for e in doc.modelspace():
        handle(e)
    return ext


def _bbox_diag(coords: list[tuple[float, float, float]]) -> float:
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    zs = [p[2] for p in coords]
    return math.dist((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def _dedup_points(coords: list[tuple[float, float, float]], tol: float):
    """网格哈希顶点归并；返回（代表点列表, 每个输入坐标 → 代表点索引）。"""
    cell = tol
    reps: list[tuple[float, float, float]] = []
    buckets: dict[tuple[int, int, int], list[int]] = {}
    index_map: list[int] = []
    for p in coords:
        k = (math.floor(p[0] / cell), math.floor(p[1] / cell), math.floor(p[2] / cell))
        found = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for ri in buckets.get((k[0] + dx, k[1] + dy, k[2] + dz), ()):
                        q = reps[ri]
                        if abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol and abs(p[2] - q[2]) <= tol:
                            found = ri
                            break
                    if found is not None:
                        break
                if found is not None:
                    break
            if found is not None:
                break
        if found is None:
            reps.append(p)
            found = len(reps) - 1
            buckets.setdefault(k, []).append(found)
        index_map.append(found)
    return reps, index_map


def _match_names(points, texts: list[TextItem], threshold: float) -> dict[int, str]:
    """就近一对一分配：每个文字至多命名一个点，每个点至多获一个名。"""
    if threshold <= 0 or not points or not texts:
        return {}
    cell = threshold
    grid: dict[tuple[int, int, int], list[int]] = {}
    for pi, p in enumerate(points):
        k = (math.floor(p[0] / cell), math.floor(p[1] / cell), math.floor(p[2] / cell))
        grid.setdefault(k, []).append(pi)
    pairs: list[tuple[float, int, int]] = []
    for ti, t in enumerate(texts):
        k = (math.floor(t.pos[0] / cell), math.floor(t.pos[1] / cell), math.floor(t.pos[2] / cell))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for pi in grid.get((k[0] + dx, k[1] + dy, k[2] + dz), ()):
                        d = math.dist(t.pos, points[pi])
                        if d <= threshold:
                            pairs.append((d, ti, pi))
    pairs.sort(key=lambda x: x[0])
    got_text: set[int] = set()
    got_point: set[int] = set()
    result: dict[int, str] = {}
    for _d, ti, pi in pairs:
        if ti in got_text or pi in got_point:
            continue
        got_text.add(ti)
        got_point.add(pi)
        result[pi] = texts[ti].text
    return result


def parse_doc(doc, name: str, source_format: str = "dxf",
              name_match_ratio: float = NAME_MATCH_RATIO) -> dict:
    """解析已打开的 DXF 文档 → 标准坐标 JSON（dict）。"""
    ext = _extract(doc)
    coords: list[tuple[float, float, float]] = []
    for s in ext.segments:
        coords.append(s.a)
        coords.append(s.b)
    coords.extend(ext.points)

    if not coords:
        return {"meta": {"name": name, "source_format": source_format, "point_count": 0,
                         "link_count": 0, "skipped_entities": ext.skipped},
                "points": [], "links": []}

    diag = _bbox_diag(coords)
    tol = max(diag * MERGE_TOL_RATIO, 1e-9)
    merged, index_map = _dedup_points(coords, tol)

    edges: set[tuple[int, int]] = set()
    for si in range(len(ext.segments)):
        ia, ib = index_map[2 * si], index_map[2 * si + 1]
        if ia != ib:
            edges.add((min(ia, ib), max(ia, ib)))

    threshold = diag * name_match_ratio
    assigned = _match_names(merged, ext.texts, threshold)

    used: set[str] = set()

    def uniq(nm: str) -> str:
        if nm not in used:
            used.add(nm)
            return nm
        i = 2
        while f"{nm}_{i}" in used:
            i += 1
        nm2 = f"{nm}_{i}"
        used.add(nm2)
        return nm2

    out_points = []
    auto = 0
    for pi, p in enumerate(merged):
        nm = assigned.get(pi)
        if not nm:
            auto += 1
            nm = uniq(AUTO_NAME_FMT.format(auto))
        else:
            nm = uniq(nm)
        out_points.append({"name": nm, "x": round(p[0], ROUND_DIGITS),
                           "y": round(p[1], ROUND_DIGITS), "z": round(p[2], ROUND_DIGITS)})

    out_links = [{"from": out_points[i]["name"], "to": out_points[j]["name"]}
                 for (i, j) in sorted(edges)]

    meta = {"name": name, "source_format": source_format,
            "point_count": len(out_points), "link_count": len(out_links),
            "merge_tol": tol, "name_match_ratio": name_match_ratio,
            "skipped_entities": ext.skipped}
    return {"meta": meta, "points": out_points, "links": out_links}


def parse_dxf(path: str | Path, *, name: str | None = None, source_format: str = "dxf",
              name_match_ratio: float = NAME_MATCH_RATIO) -> dict:
    """读取 DXF 文件并解析（结构错误时自动进入修复模式）。"""
    path = Path(path)
    try:
        doc = ezdxf.readfile(path)
    except ezdxf.DXFStructureError:
        from ezdxf import recover

        doc, _auditor = recover.readfile(path)
    return parse_doc(doc, name=name or path.stem, source_format=source_format,
                     name_match_ratio=name_match_ratio)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="CAD 图纸坐标解析")
    ap.add_argument("dxf", help="输入 DXF 文件")
    ap.add_argument("-o", "--out", default=None, help="输出 JSON 路径（默认同名 .coord.json）")
    ap.add_argument("--name", default=None, help="图纸名称")
    args = ap.parse_args()
    data = parse_dxf(args.dxf, name=args.name)
    out = Path(args.out) if args.out else Path(args.dxf).with_suffix(".coord.json")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    m = data["meta"]
    print(f"saved {out}")
    print(f"points={m['point_count']} links={m['link_count']} skipped={m['skipped_entities']}")
