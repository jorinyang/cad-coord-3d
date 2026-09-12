"""API 自测（TestClient）：健康 / DXF / DWG 上传入库 / 坏文件 / 重命名 / 删除。

注意：上传会真实写入 Supabase，测试各用例结束后自动清理。
"""
from pathlib import Path

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
TESTDATA = Path(__file__).resolve().parent.parent / "testdata"


def _upload(path: Path):
    content = path.read_bytes()
    r = client.post("/api/parse", files={"file": (path.name, content, "application/octet-stream")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"], j
    return j["data"]


def test_health() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"], r.text
    print("[health] OK", r.json()["data"])


def test_parse_dxf() -> None:
    data = _upload(TESTDATA / "test_input.dxf")
    m = data["meta"]
    assert m["point_count"] == 5 and m["link_count"] == 6, m
    did = data["drawing_id"]
    assert did, "missing drawing_id"
    print(f"[parse dxf] OK points={m['point_count']} links={m['link_count']} id={did[:8]}…")
    r = client.delete(f"/api/drawings/{did}")
    assert r.json()["ok"], r.text
    print("[cleanup dxf] OK")


def test_parse_dwg() -> None:
    data = _upload(TESTDATA / "conv_in2" / "test_input.dwg")
    m = data["meta"]
    assert m["point_count"] == 5 and m["link_count"] == 6, m
    did = data["drawing_id"]
    print(f"[parse dwg] OK points={m['point_count']} links={m['link_count']} id={did[:8]}…")
    r = client.delete(f"/api/drawings/{did}")
    assert r.json()["ok"], r.text
    print("[cleanup dwg] OK")


def test_rename_and_delete() -> None:
    data = _upload(TESTDATA / "test_input.dxf")
    did = data["drawing_id"]

    r = client.patch(f"/api/drawings/{did}", json={"name": "重命名测试"})
    assert r.status_code == 200 and r.json()["ok"], r.text
    assert r.json()["data"]["name"] == "重命名测试"

    r = client.delete(f"/api/drawings/{did}")
    assert r.json()["ok"], r.text
    r = client.delete(f"/api/drawings/{did}")  # 已删除 → 404
    assert r.status_code == 404, r.text
    print("[rename/delete] OK (rename + delete + 404 on re-delete)")


def test_bad_files() -> None:
    r = client.post("/api/parse", files={"file": ("evil.dwg", b"MZ\x90\x00 not a dwg", "application/octet-stream")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "BAD_REQUEST", r.text
    r2 = client.post("/api/parse", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r2.status_code == 400 and r2.json()["error"]["code"] == "BAD_REQUEST", r2.text
    r3 = client.post("/api/parse", files={"file": ("a.dxf", b"", "application/octet-stream")})
    assert r3.status_code == 400, r3.text
    print("[bad files] OK all three rejected with structure")


if __name__ == "__main__":
    test_health()
    test_parse_dxf()
    test_parse_dwg()
    test_rename_and_delete()
    test_bad_files()
    print("OK: api selftest passed")
