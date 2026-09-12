# -*- coding: utf-8 -*-
"""DWG → DXF 转换可行性 · 完整验证（六层）。

A. 转换链调用：4 个真实 DWG 样例（R14/R2000/R2013/R2018）→ DXF 产物（converter.convert_dwg_to_dxf）
B. 产物有效性：ezdxf 读取 + 实体统计
C. 坐标解析：coord_parser.parse_dxf → 点数 / 线数 / 名称
D. 跨版本一致性：四版产物解析结果对比
E. 端到端 API：POST /api/parse 上传 DWG → 转换 + 解析 + 入库 → 云端复核
F. 异常路径：损坏 DWG / 不存在文件 → 明确报错（含手动指引）

前置：本地后端 8791 在跑（E/F 需要）。
用法：python app/devtools/test_dwg_pipeline.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d")
sys.path.insert(0, str(ROOT / "app" / "server"))

import ezdxf  # noqa: E402
import httpx  # noqa: E402

from converter import ConversionError, convert_dwg_to_dxf  # noqa: E402
from coord_parser import parse_dxf  # noqa: E402

SAMPLES = ROOT / "app" / "testdata" / "samples"
WC = ROOT / "app" / "testdata" / "verify_conv"
API = "http://127.0.0.1:8791"

fails: list[str] = []
warns: list[str] = []
report: dict = {"steps": [], "converted": {}}


def check(name: str, ok: bool, detail: str = ""):
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}" + (f"  — {detail}" if detail else ""))
    report["steps"].append({"name": name, "ok": bool(ok), "detail": detail})
    if not ok:
        fails.append(name)


def warn(name: str, detail: str = ""):
    print(f"[WARN] {name}" + (f"  — {detail}" if detail else ""))
    warns.append(name)


def sb_headers(cfg: str):
    url = re.search(r"https://[a-z0-9]+\.supabase\.co", cfg).group(0)
    key = re.search(r"(eyJ[A-Za-z0-9_.\-]{30,}|sb_publishable_[A-Za-z0-9_\-]+)", cfg).group(1)
    return url, key


def sb_count(url: str, key: str, path: str) -> int | None:
    req = urllib.request.Request(
        url + path,
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json",
                 "Prefer": "count=exact", "Range": "0-0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        cr = {k.lower(): v for k, v in dict(r.headers).items()}.get("content-range", "")
    return int(cr.split("/")[-1]) if "/" in cr else None


def main() -> int:
    if WC.exists():
        shutil.rmtree(WC)
    WC.mkdir(parents=True)
    samples = sorted(SAMPLES.glob("*.dwg"))
    print(f"=== 样例：{len(samples)} 个真实 DWG ===\n")

    parsed: dict[str, tuple] = {}

    # ---- A / B / C ----
    for s in samples:
        key = s.stem
        t0 = time.time()
        try:
            out = convert_dwg_to_dxf(s, workdir=WC)
        except ConversionError as e:
            check(f"A 转换 {s.name}", False, str(e)[:200])
            continue
        secs = time.time() - t0
        dest = WC / f"{key}.dxf"
        shutil.copy2(out, dest)
        shutil.rmtree(out.parent.parent, ignore_errors=True)
        check(f"A 转换 {s.name} → {key}.dxf", True, f"{secs:.1f}s / {dest.stat().st_size/1024:.0f}KB")

        try:
            doc = ezdxf.readfile(str(dest))
            ents = Counter(e.dxftype() for e in doc.modelspace())
            top = ", ".join(f"{k}×{v}" for k, v in ents.most_common(6))
            check(f"B 产物有效 {key}", True, f"DXF={doc.dxfversion}, {sum(ents.values())} 实体（{top}）")
        except Exception as e:
            check(f"B 产物有效 {key}", False, f"{type(e).__name__}: {e}")
            continue

        data = parse_dxf(dest, name=key, source_format="dwg")
        m = data["meta"]
        nsample = [p["name"] for p in data["points"][:3]]
        check(f"C 解析 {key}", m["point_count"] > 0,
              f"{m['point_count']} 点 / {m['link_count']} 线 / 跳过 {m['skipped_entities']}；名称样例 {nsample}")

        pts_sig = sorted((p["name"], float(p["x"]), float(p["y"]), float(p["z"])) for p in data["points"])
        links_sig = sorted((l["from"], l["to"]) for l in data["links"])
        parsed[key] = (pts_sig, links_sig)
        report["converted"][key] = {
            "source_bytes": s.stat().st_size, "dxf_bytes": dest.stat().st_size,
            "convert_secs": round(secs, 1), "entities": sum(ents.values()),
            "points": m["point_count"], "links": m["link_count"], "skipped": m["skipped_entities"]}

    # ---- D 跨版本一致性 ----
    if len(parsed) >= 2:
        keys = sorted(parsed)
        base = keys[0]
        bp, bl = parsed[base]
        for k in keys[1:]:
            pp, ll = parsed[k]
            if (pp == bp) and (ll == bl):
                check(f"D 一致性 {base} ≡ {k}", True, f"点/线/名称完全一致（{len(pp)} 点 / {len(ll)} 线）")
            else:
                warn(f"D 一致性 {base} ≠ {k}", f"点 {len(pp)}/{len(bp)}，线 {len(ll)}/{len(bl)}")

    # ---- E 端到端 API ----
    dwg = SAMPLES / "example_2018.dwg"
    t0 = time.time()
    try:
        with dwg.open("rb") as f:
            r = httpx.post(f"{API}/api/parse", files={"file": (dwg.name, f, "application/octet-stream")}, timeout=600)
        j = r.json()
        ok = r.status_code == 200 and j.get("ok")
        dt = time.time() - t0
        if ok:
            d = j["data"]
            did = d["drawing_id"]
            m = d["meta"]
            check("E 端到端上传 DWG（R2018）", True,
                  f"HTTP {r.status_code}，{dt:.1f}s，id={did}，{m['point_count']} 点 / {m['link_count']} 线")
            report["e2e"] = {"drawing_id": did, "secs": round(dt, 1),
                             "points": m["point_count"], "links": m["link_count"]}
            r2 = httpx.patch(f"{API}/api/drawings/{did}",
                             json={"name": "DWG转换验证 · example_2018"}, timeout=30)
            if r2.status_code == 200:
                print(f"   [rename] -> {r2.json()['data']['name']}")
            try:
                cfg = (ROOT / "app" / "web" / "js" / "config.js").read_text(encoding="utf-8")
                sb_url, sb_key = sb_headers(cfg)
                n_pts = sb_count(sb_url, sb_key, f"/rest/v1/cad_points?drawing_id=eq.{did}&select=id")
                n_lnk = sb_count(sb_url, sb_key, f"/rest/v1/cad_links?drawing_id=eq.{did}&select=id")
                check("E 云端复核（点/线实际行数）", n_pts == m["point_count"] and n_lnk == m["link_count"],
                      f"点 {n_pts}/{m['point_count']}，线 {n_lnk}/{m['link_count']}")
            except Exception as e:
                warn("E 云端复核失败", f"{type(e).__name__}: {e}")
        else:
            check("E 端到端上传 DWG（R2018）", False, f"HTTP {r.status_code} {str(j)[:200]}")
    except Exception as e:
        check("E 端到端上传 DWG（R2018）", False, f"{type(e).__name__}: {e}")

    # ---- F 异常路径 ----
    bad = WC / "bad_fake.dwg"
    bad.write_bytes(b"AC1015" + os.urandom(4096))
    try:
        t0 = time.time()
        r = httpx.post(f"{API}/api/parse",
                       files={"file": ("bad_fake.dwg", bad.read_bytes(), "application/octet-stream")},
                       timeout=340)
        j = r.json()
        ecode = (j.get("error") or {}).get("code")
        emsg = ((j.get("error") or {}).get("message") or "")
        check("F 损坏 DWG → 明确报错", r.status_code == 502 and ecode == "CONVERT_FAILED",
              f"HTTP {r.status_code}，{time.time()-t0:.1f}s，{emsg[:120]}")
        check("F 报错含手动转换指引", "另存为 DXF" in emsg,
              "含「另存为 DXF」指引" if "另存为 DXF" in emsg else emsg[-90:])
    except Exception as e:
        check("F 损坏 DWG → 明确报错", False, f"{type(e).__name__}: {e}")

    try:
        convert_dwg_to_dxf(WC / "not_exists.dwg")
        check("F 不存在文件 → 明确报错", False, "未抛错")
    except ConversionError as e:
        check("F 不存在文件 → 明确报错", True, str(e)[:70])

    # ---- 汇总 ----
    report["fails"] = fails
    report["warns"] = warns
    (WC / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print("=" * 60)
    if fails:
        print(f"RESULT: FAILURES ({len(fails)})")
        for f in fails:
            print(" -", f)
    else:
        print("RESULT: ALL PASS ✓" + (f"（{len(warns)} 个警告见上）" if warns else ""))
    print(f"report: {WC / 'report.json'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
