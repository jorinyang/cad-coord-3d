"""转换层自测：用生成的测试 DWG 验证 convert_dwg_to_dxf 回退链。"""
from collections import Counter
from pathlib import Path

import ezdxf

from converter import convert_dwg_to_dxf

TESTDATA = Path(__file__).resolve().parent.parent / "testdata"


def main() -> None:
    src = TESTDATA / "conv_in2" / "test_input.dwg"
    assert src.exists(), f"缺少测试文件：{src}（先运行测试图生成步骤）"
    out = convert_dwg_to_dxf(src)
    print("converted ->", out)
    doc = ezdxf.readfile(out)
    ents = list(doc.modelspace())
    c = Counter(e.dxftype() for e in ents)
    print("entities:", dict(c))
    assert c.get("LINE") == 4, "LINE 数量不符（期望 4）"
    assert c.get("TEXT") == 4, "TEXT 数量不符（期望 4）"
    assert c.get("LWPOLYLINE") == 1, "LWPOLYLINE 数量不符（期望 1）"
    print("OK: converter selftest passed")


if __name__ == "__main__":
    main()
