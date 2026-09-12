// sb.js — Supabase 只读数据客户端（REST + publishable key）
// 前端零写权限：所有写操作走后端 API（api.js）
import { SUPABASE_URL, SUPABASE_ANON_KEY } from './config.js';

const HEADERS = { apikey: SUPABASE_ANON_KEY, Authorization: `Bearer ${SUPABASE_ANON_KEY}` };
const PAGE = 1000;

async function sbGetAll(table, query = '', pageSize = PAGE) {
  const out = [];
  let offset = 0;
  for (;;) {
    const sep = query.includes('?') ? '&' : '?';
    const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}${query}${sep}limit=${pageSize}&offset=${offset}`, {
      headers: HEADERS,
    });
    if (!res.ok) {
      let msg = `数据读取失败（HTTP ${res.status}）`;
      try {
        const j = await res.json();
        if (j && j.message) msg = j.message;
      } catch { /* ignore */ }
      throw new Error(msg);
    }
    const rows = await res.json();
    out.push(...rows);
    if (rows.length < pageSize) break;
    offset += pageSize;
  }
  return out;
}

export function listDrawings() {
  return sbGetAll('cad_drawings',
    '?select=id,name,source_format,point_count,link_count,created_at&order=created_at.desc,id.asc');
}

export async function getDrawing(id) {
  const enc = encodeURIComponent(id);
  const rows = await sbGetAll('cad_drawings', `?id=eq.${enc}&select=*`);
  if (!rows.length) return null;
  const drawing = rows[0];
  const points = await sbGetAll('cad_points', `?drawing_id=eq.${enc}&select=id,name,x,y,z&order=seq.asc`);
  const links = await sbGetAll('cad_links', `?drawing_id=eq.${enc}&select=id,from_point_id,to_point_id`);
  const id2name = new Map(points.map((p) => [p.id, p.name]));
  return {
    drawing,
    meta: {
      name: drawing.name,
      source_format: drawing.source_format,
      point_count: drawing.point_count,
      link_count: drawing.link_count,
    },
    points: points.map((p) => ({ id: p.id, name: p.name, x: p.x, y: p.y, z: p.z })),
    links: links
      .map((l) => ({ id: l.id, from: id2name.get(l.from_point_id), to: id2name.get(l.to_point_id) }))
      .filter((l) => l.from && l.to),
  };
}

export async function getShare(token) {
  const enc = encodeURIComponent(token);
  const rows = await sbGetAll('cad_share_snapshots', `?token=eq.${enc}&select=payload`);
  return rows.length ? rows[0].payload : null;
}
