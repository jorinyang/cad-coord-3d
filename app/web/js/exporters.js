// exporters.js — 导出（CSV / XLSX / JSON）
// 列定义对齐用户字段：坐标名称 / X 坐标值 / Y 坐标值 / Z 坐标值 / 产生链接的坐标名称
const HEADERS = ['坐标名称', 'X 坐标值', 'Y 坐标值', 'Z 坐标值', '产生链接的坐标名称'];

function buildAdjacency(links) {
  const adj = new Map();
  const ensure = (n) => {
    if (!adj.has(n)) adj.set(n, []);
    return adj.get(n);
  };
  for (const l of links) {
    ensure(l.from).push(l.to);
    ensure(l.to).push(l.from);
  }
  return adj;
}

export function buildRows(data) {
  const adj = buildAdjacency(data.links || []);
  return (data.points || []).map((p) => [
    p.name, p.x, p.y, p.z, (adj.get(p.name) || []).join('、'),
  ]);
}

export function buildCsv(data) {
  const rows = buildRows(data);
  const esc = (v) => {
    const s = String(v ?? '');
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [HEADERS.join(','), ...rows.map((r) => r.map(esc).join(','))];
  return `\ufeff${lines.join('\r\n')}`; // BOM（Excel 中文兼容）+ CRLF
}

export function buildJson(data) {
  return JSON.stringify({
    meta: { ...data.meta, exported_at: new Date().toISOString() },
    points: data.points,
    links: data.links,
  }, null, 1);
}

export function exportBaseName(drawingName) {
  const d = new Date();
  const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  const safe = String(drawingName || 'drawing').replace(/[\\/:*?"<>|]/g, '_');
  return `${safe}-坐标数据-${ymd}`;
}

export function exportCsv(data, baseName) {
  downloadBlob(new Blob([buildCsv(data)], { type: 'text/csv;charset=utf-8' }), `${baseName}.csv`);
}

export function exportJson(data, baseName) {
  downloadBlob(new Blob([buildJson(data)], { type: 'application/json;charset=utf-8' }), `${baseName}.json`);
}

export function exportXlsx(data, baseName) {
  const aoa = [HEADERS, ...buildRows(data)];
  const ws = XLSX.utils.aoa_to_sheet(aoa);
  ws['!cols'] = [{ wch: 16 }, { wch: 14 }, { wch: 14 }, { wch: 14 }, { wch: 34 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, '坐标数据');
  XLSX.writeFile(wb, `${baseName}.xlsx`);
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}
