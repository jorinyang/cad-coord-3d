"""
store.py — Supabase 数据写入层（服务端专用，psycopg2 直连 pooler）

读路径：前端经 Supabase REST（只读）；本模块只负责写。
凭据：环境变量优先（FC 部署时注入），否则读 ~/.ClawShell/.env.supabase。
表结构：见 db_setup.py（cad_drawings / cad_points / cad_links / cad_share_snapshots）。
"""
from __future__ import annotations

import os
import secrets
import uuid
from pathlib import Path

ENV_PATH = Path.home() / ".ClawShell" / ".env.supabase"


def load_env() -> dict[str, str]:
    d: dict[str, str] = {k: v for k, v in os.environ.items() if k.startswith("SUPABASE_")}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            d.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return d


def _connect():
    import psycopg2

    env = load_env()
    conn = psycopg2.connect(
        host=env["SUPABASE_DB_HOST"],
        port=int(env.get("SUPABASE_DB_PORT", "6543")),
        user=env["SUPABASE_DB_USER"],
        password=env["SUPABASE_DB_PASSWORD"],
        dbname="postgres",
        sslmode="require",
        connect_timeout=15,
    )
    conn.autocommit = True
    return conn


def save_drawing(*, name: str, source_format: str, source_filename: str,
                 points: list[dict], links: list[dict]) -> str:
    """写入一张图纸（drawing + points + links），返回 drawing_id。"""
    from psycopg2.extras import execute_values

    drawing_id = str(uuid.uuid4())
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into cad_drawings (id, name, source_filename, source_format, status,"
                " point_count, link_count) values (%s, %s, %s, %s, %s, %s, %s)",
                (drawing_id, name, source_filename, source_format, "ready",
                 len(points), len(links)))

            name2id: dict[str, str] = {}
            rows = []
            for i, p in enumerate(points):
                pid = str(uuid.uuid4())
                name2id[p["name"]] = pid
                rows.append((pid, drawing_id, p["name"], p["x"], p["y"], p["z"], i))
            if rows:
                execute_values(
                    cur,
                    "insert into cad_points (id, drawing_id, name, x, y, z, seq) values %s",
                    rows, page_size=1000)

            lrows = []
            for lk in links:
                a = name2id.get(lk["from"])
                b = name2id.get(lk["to"])
                if a and b:
                    lrows.append((str(uuid.uuid4()), drawing_id, a, b))
            if lrows:
                execute_values(
                    cur,
                    "insert into cad_links (id, drawing_id, from_point_id, to_point_id) values %s",
                    lrows, page_size=1000)
        return drawing_id
    finally:
        conn.close()


def rename_drawing(drawing_id: str, name: str) -> bool:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("update cad_drawings set name=%s, updated_at=now() where id=%s",
                        (name, drawing_id))
            return cur.rowcount > 0
    finally:
        conn.close()


def delete_drawing(drawing_id: str) -> bool:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("delete from cad_drawings where id=%s", (drawing_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


def rename_point(drawing_id: str, point_id: str, name: str) -> str:
    """改名坐标点（同图内唯一）。返回 ok / not_found / conflict。"""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("select 1 from cad_points where id=%s and drawing_id=%s", (point_id, drawing_id))
            if not cur.fetchone():
                return "not_found"
            cur.execute("select 1 from cad_points where drawing_id=%s and name=%s and id<>%s",
                        (drawing_id, name, point_id))
            if cur.fetchone():
                return "conflict"
            cur.execute("update cad_points set name=%s where id=%s", (name, point_id))
        return "ok"
    finally:
        conn.close()


def _recount(cur, drawing_id: str) -> dict:
    cur.execute("select count(*) from cad_points where drawing_id=%s", (drawing_id,))
    pc = cur.fetchone()[0]
    cur.execute("select count(*) from cad_links where drawing_id=%s", (drawing_id,))
    lc = cur.fetchone()[0]
    return {"point_count": pc, "link_count": lc}


def _apply_counts(cur, drawing_id: str) -> dict:
    counts = _recount(cur, drawing_id)
    cur.execute("update cad_drawings set point_count=%s, link_count=%s, updated_at=now() where id=%s",
                (counts["point_count"], counts["link_count"], drawing_id))
    return counts


def delete_point(drawing_id: str, point_id: str):
    """删除坐标点（关联连线级联删除）。返回新计数；未找到返回 None。"""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("delete from cad_points where id=%s and drawing_id=%s", (point_id, drawing_id))
            if cur.rowcount == 0:
                return None
            return _apply_counts(cur, drawing_id)
    finally:
        conn.close()


def delete_link(drawing_id: str, link_id: str):
    """删除一条连接。返回新计数；未找到返回 None。"""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("delete from cad_links where id=%s and drawing_id=%s", (link_id, drawing_id))
            if cur.rowcount == 0:
                return None
            return _apply_counts(cur, drawing_id)
    finally:
        conn.close()


def load_drawing_payload(drawing_id: str):
    """读取图纸完整数据（标准坐标 JSON 形状）；不存在返回 None。"""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("select name, source_format, point_count, link_count from cad_drawings where id=%s",
                        (drawing_id,))
            row = cur.fetchone()
            if not row:
                return None
            meta = {"name": row[0], "source_format": row[1],
                    "point_count": row[2], "link_count": row[3]}
            cur.execute("select name, x, y, z from cad_points where drawing_id=%s order by seq asc",
                        (drawing_id,))
            points = [{"name": r[0], "x": r[1], "y": r[2], "z": r[3]} for r in cur.fetchall()]
            cur.execute(
                "select p1.name, p2.name from cad_links l "
                "join cad_points p1 on p1.id = l.from_point_id "
                "join cad_points p2 on p2.id = l.to_point_id "
                "where l.drawing_id = %s", (drawing_id,))
            links = [{"from": r[0], "to": r[1]} for r in cur.fetchall()]
            return {"meta": meta, "points": points, "links": links}
    finally:
        conn.close()


def create_share(drawing_id: str, payload: dict) -> str:
    """创建分享快照（同图仅保留一个：先删旧再插入）。返回 token。"""
    import json as _json

    token = secrets.token_urlsafe(16)
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("delete from cad_share_snapshots where drawing_id=%s", (drawing_id,))
            cur.execute(
                "insert into cad_share_snapshots (token, drawing_id, payload) values (%s, %s, %s::jsonb)",
                (token, drawing_id, _json.dumps(payload, ensure_ascii=False)))
        return token
    finally:
        conn.close()


def delete_share(token: str) -> bool:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("delete from cad_share_snapshots where token=%s", (token,))
            return cur.rowcount > 0
    finally:
        conn.close()
