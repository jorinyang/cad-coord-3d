"""
db_setup.py — Supabase 数据层初始化（cad_ 前缀表 + RLS + 权限）

通道：psycopg2 直连 pooler（主）/ Management API（备，--via-api）
用法：
    python db_setup.py --check     # 只读：连接测试 + 列出 public 现有表
    python db_setup.py             # 执行建表 DDL（幂等，逐条）
    python db_setup.py --verify    # REST 验证：anon 只读 / anon 写被拒 / service 写通

凭据来源：~/.ClawShell/.env.supabase
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV_PATH = Path.home() / ".ClawShell" / ".env.supabase"
PROXY = "http://127.0.0.1:7890"


def load_env(path: Path) -> dict[str, str]:
    d: dict[str, str] = {}
    if not path.exists():
        return d
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def pick(d: dict, *names: str) -> str | None:
    for n in names:
        if d.get(n):
            return d[n]
    for k, v in d.items():
        for n in names:
            if n.lower() in k.lower() and v:
                return v
    return None


# ---------- psycopg2 pooler 直连 ----------

def pg_connect(env: dict):
    import psycopg2

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


def pg_exec(conn, sql: str) -> list:
    """逐条执行（分号拆分），返回每条语句的结果行。"""
    stmts = [s.strip() for s in sql.split(";") if s.strip()]
    out = []
    with conn.cursor() as cur:
        for st in stmts:
            cur.execute(st)
            out.append(cur.fetchall() if cur.description else None)
    return out


# ---------- Management API（备选通道）----------

def _open(req: urllib.request.Request, timeout: int = 45):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except Exception:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": PROXY, "http": PROXY}))
        return opener.open(req, timeout=timeout)


def run_sql_api(ref: str, pat: str, sql: str):
    url = f"https://api.supabase.com/v1/projects/{ref}/database/query"
    req = urllib.request.Request(
        url,
        data=json.dumps({"query": sql}).encode("utf-8"),
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        method="POST",
    )
    with _open(req) as r:
        body = r.read().decode("utf-8")
        return json.loads(body) if body.strip() else None


# ---------- DDL ----------

DDL = """
create table if not exists public.cad_drawings (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  source_filename text,
  source_format text not null check (source_format in ('dwg', 'dxf')),
  status text not null default 'ready',
  point_count integer not null default 0,
  link_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table if not exists public.cad_points (
  id uuid primary key default gen_random_uuid(),
  drawing_id uuid not null references public.cad_drawings(id) on delete cascade,
  name text not null,
  x double precision not null,
  y double precision not null,
  z double precision not null default 0,
  seq integer not null default 0
);
create index if not exists cad_points_drawing_idx on public.cad_points (drawing_id);
create table if not exists public.cad_links (
  id uuid primary key default gen_random_uuid(),
  drawing_id uuid not null references public.cad_drawings(id) on delete cascade,
  from_point_id uuid not null references public.cad_points(id) on delete cascade,
  to_point_id uuid not null references public.cad_points(id) on delete cascade
);
create index if not exists cad_links_drawing_idx on public.cad_links (drawing_id);
create table if not exists public.cad_share_snapshots (
  token text primary key,
  drawing_id uuid references public.cad_drawings(id) on delete set null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);
alter table public.cad_drawings enable row level security;
alter table public.cad_points enable row level security;
alter table public.cad_links enable row level security;
alter table public.cad_share_snapshots enable row level security;
drop policy if exists "cad anon read" on public.cad_drawings;
create policy "cad anon read" on public.cad_drawings for select to anon using (true);
drop policy if exists "cad anon read" on public.cad_points;
create policy "cad anon read" on public.cad_points for select to anon using (true);
drop policy if exists "cad anon read" on public.cad_links;
create policy "cad anon read" on public.cad_links for select to anon using (true);
drop policy if exists "cad anon read" on public.cad_share_snapshots;
create policy "cad anon read" on public.cad_share_snapshots for select to anon using (true);
grant select on public.cad_drawings to anon;
grant select on public.cad_points to anon;
grant select on public.cad_links to anon;
grant select on public.cad_share_snapshots to anon;
grant all on public.cad_drawings to service_role;
grant all on public.cad_points to service_role;
grant all on public.cad_links to service_role;
grant all on public.cad_share_snapshots to service_role;
"""


# ---------- REST 验证 ----------

def _rest(url: str, key: str, method: str, path: str, body=None, prefer: str | None = None):
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    req = urllib.request.Request(f"{url}/rest/v1/{path}", method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    return _open(req)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只读检查")
    ap.add_argument("--verify", action="store_true", help="REST 读写验证")
    ap.add_argument("--via-api", action="store_true", help="用 Management API 通道执行 DDL")
    args = ap.parse_args()

    env = load_env(ENV_PATH)
    if not env:
        print(f"ERROR: 未找到凭据文件 {ENV_PATH}")
        return 1
    missing = [k for k in ("SUPABASE_DB_HOST", "SUPABASE_DB_USER", "SUPABASE_DB_PASSWORD",
                           "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SERVICE_KEY") if not env.get(k)]
    if missing:
        print("ERROR: 凭据缺失字段:", missing, "现有键:", sorted(env.keys()))
        return 1

    url = env["SUPABASE_URL"]
    # 新式 key 优先（本项目 legacy JWT 已失效，2026-09-12 实测 401）
    anon = env.get("SUPABASE_PUBLISHABLE_KEY") or env.get("SUPABASE_ANON_JWT")
    service = env.get("SUPABASE_SERVICE_KEY") or env.get("SUPABASE_SERVICE_JWT")

    if args.verify:
        with _rest(url, anon, "GET", "cad_drawings?select=id&limit=1") as r:
            print("[anon read] status", r.status, r.read().decode()[:120])
        try:
            _rest(url, anon, "POST", "cad_drawings", {"name": "rls-probe", "source_format": "dxf"})
            print("[anon write] UNEXPECTED: allowed (RLS NOT effective?)")
        except urllib.error.HTTPError as e:
            print("[anon write] rejected OK:", e.code, e.read().decode()[:160])
        with _rest(url, service, "POST", "cad_drawings",
                   {"name": "f5-probe", "source_format": "dxf", "point_count": 0, "link_count": 0},
                   prefer="return=representation") as r:
            row = json.loads(r.read().decode())[0]
        print("[service write] OK id=", row["id"])
        with _rest(url, service, "DELETE", f"cad_drawings?id=eq.{row['id']}") as r:
            print("[service delete] status", r.status)
        return 0

    if args.check:
        conn = pg_connect(env)
        print(f"[pg] connected: {env['SUPABASE_DB_HOST']}:{env.get('SUPABASE_DB_PORT')} as {env['SUPABASE_DB_USER']}")
        rows = pg_exec(conn, "select tablename from pg_tables where schemaname='public' order by 1;")
        print("== existing public tables ==")
        for (t,) in (rows[0] or []):
            print("  -", t)
        rows2 = pg_exec(conn, "select tablename from pg_tables where schemaname='public' and tablename like 'cad_%' order by 1;")
        print("== cad_ tables ==", [t for (t,) in (rows2[0] or [])] or "(none)")
        conn.close()
        return 0

    # apply DDL
    if args.via_api:
        ref = env["SUPABASE_PROJECT_REF"]
        pat = env["SUPABASE_PAT"]
        print("[api] applying DDL via Management API …")
        res = run_sql_api(ref, pat, DDL)
        print("result:", json.dumps(res)[:200] if res else "ok")
        return 0

    conn = pg_connect(env)
    print(f"[pg] connected: {env['SUPABASE_DB_HOST']}:{env.get('SUPABASE_DB_PORT')}")
    stmts = [s.strip() for s in DDL.split(";") if s.strip()]
    fails = 0
    with conn.cursor() as cur:
        for i, st in enumerate(stmts, 1):
            head = " ".join(st.split())[:78]
            try:
                cur.execute(st)
                print(f"  [{i:>2}/{len(stmts)}] OK   {head}")
            except Exception as e:
                fails += 1
                print(f"  [{i:>2}/{len(stmts)}] FAIL {head}\n        -> {type(e).__name__}: {e}")
    rows = pg_exec(conn, "select tablename from pg_tables where schemaname='public' and tablename like 'cad_%' order by 1;")
    print("== cad_ tables now ==")
    for (t,) in (rows[0] or []):
        print("  -", t)
    conn.close()
    print("DDL done, failures:", fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
