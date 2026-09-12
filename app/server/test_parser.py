"""解析器自测：① 自造图严格断言 ② 真实样例统计观察。"""
from pathlib import Path

import ezdxf

from coord_parser import parse_doc, parse_dxf

TESTDATA = Path(__file__).resolve().parent.parent / "testdata"


def _make_synthetic():
    """确定结构的测试图：方形 + 3D 折线 + 平面多段线 + 顶点标注文字。

    期望：6 个顶点、8 条边、5 个名称命中（JA–JE）、1 个自动补号点（5,10,0）。
    """
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    sq = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
    for i in range(4):
        msp.add_line(sq[i], sq[(i + 1) % 4])
    msp.add_line((0, 0, 0), (5, 5, 3))
    msp.add_line((5, 5, 3), (10, 0, 0))
    msp.add_lwpolyline([(0, 10), (5, 10), (10, 10)])
    for nm, pos in [("JA", (0, 0, 0)), ("JB", (10, 0, 0)), ("JC", (0, 10, 0)),
                    ("JD", (10, 10, 0)), ("JE", (5, 5, 3))]:
        msp.add_text(nm, height=1.5).set_placement(pos)
    return doc


def test_synthetic() -> None:
    data = parse_doc(_make_synthetic(), name="synthetic")
    m = data["meta"]
    assert m["point_count"] == 6, f"point_count={m['point_count']} (expect 6)"
    assert m["link_count"] == 8, f"link_count={m['link_count']} (expect 8)"
    by_name = {p["name"]: p for p in data["points"]}

    def near(nm, xyz):
        p = by_name[nm]
        assert (abs(p["x"] - xyz[0]) < 1e-6 and abs(p["y"] - xyz[1]) < 1e-6
                and abs(p["z"] - xyz[2]) < 1e-6), f"{nm}={p} != {xyz}"

    near("JA", (0, 0, 0))
    near("JB", (10, 0, 0))
    near("JC", (0, 10, 0))
    near("JD", (10, 10, 0))
    near("JE", (5, 5, 3))
    auto = [p for p in data["points"] if p["name"].startswith("P")]
    assert len(auto) == 1, f"auto-named={[p['name'] for p in auto]} (expect 1)"
    assert (auto[0]["x"], auto[0]["y"], auto[0]["z"]) == (5.0, 10.0, 0.0), auto[0]
    names = [p["name"] for p in data["points"]]
    print(f"[synthetic] OK  points={m['point_count']} links={m['link_count']} names={names}")


def test_samples() -> None:
    for f in sorted((TESTDATA / "converted").glob("*.dxf")):
        data = parse_dxf(f, name=f.stem)
        m = data["meta"]
        print(f"[sample] {f.name}: points={m['point_count']} links={m['link_count']} "
              f"skipped={m['skipped_entities']}")


if __name__ == "__main__":
    test_synthetic()
    test_samples()
    print("OK: parser selftest passed")
