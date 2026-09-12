#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""upload_oss.py — 将 app/web 部署到 OSS（clawshell-vault / web-spa/cad-coord-3d/）。

用法：
    python upload_oss.py --list     # 列出目标前缀现有对象
    python upload_oss.py            # 上传全部文件（Cache-Control: no-store）

凭据：~/.ossutilconfig
"""
from __future__ import annotations

import sys
from pathlib import Path

import oss2

SRC = Path(__file__).resolve().parent.parent / "web"
PREFIX = "web-spa/cad-coord-3d/"
BUCKET_NAME = "clawshell-vault"

CT_MAP = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def load_config() -> dict:
    cfg = {}
    path = Path.home() / ".ossutilconfig"
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("[") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip()
    return cfg


def main() -> int:
    cfg = load_config()
    auth = oss2.Auth(cfg["accessKeyID"], cfg["accessKeySecret"])
    bucket = oss2.Bucket(auth, cfg["endpoint"], BUCKET_NAME)

    if "--list" in sys.argv:
        print(f"== existing objects under {PREFIX} ==")
        n = 0
        for obj in oss2.ObjectIterator(bucket, prefix=PREFIX):
            print("  ", obj.key, obj.size)
            n += 1
        print(f"total: {n}")
        return 0

    files = sorted(f for f in SRC.rglob("*") if f.is_file())
    total = sum(f.stat().st_size for f in files)
    print(f"== uploading {len(files)} files ({total // 1024} KB) → oss://{BUCKET_NAME}/{PREFIX}")
    for f in files:
        rel = f.relative_to(SRC).as_posix()
        key = PREFIX + rel
        ct = CT_MAP.get(f.suffix.lower(), "application/octet-stream")
        bucket.put_object_from_file(key, str(f), headers={
            "Content-Type": ct,
            "Cache-Control": "no-store",
        })
        print(f"  ↑ {key}  ({f.stat().st_size} B)")
    print("== done ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
