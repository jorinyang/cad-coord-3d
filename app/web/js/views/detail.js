// views/detail.js — 图纸详情（3D + 可编辑数据：点名修改 / 删点 / 删边）
import { getDrawing } from '../sb.js';
import { renameDrawing, deleteDrawing, renamePoint, deletePoint, deleteLink, createShare, revokeShare } from '../api.js';
import { createViewer } from '../viewer3d.js';
import { escapeHtml, toast, confirmDialog, promptDialog } from '../ui.js';
import { exportCsv, exportXlsx, exportJson, exportBaseName } from '../exporters.js';

window.__createViewer = createViewer; // 测试/调试钩子

const PT_LIMIT = 100; // 表格显示行数上限（大图）
const LK_LIMIT = 100;

let viewer = null;
let ctx = null; // { id, body, data }

function disposeViewer() {
  if (viewer) { viewer.dispose(); viewer = null; }
}

function fmt(v) {
  return (typeof v === 'number' ? v.toFixed(3) : String(v));
}

export async function renderDetail(root, params) {
  disposeViewer();
  cleanupDocClick();
  ctx = null;
  const id = params.id;

  root.innerHTML = `
    <div class="detail-head"><a class="back-link" href="#/">← 图纸库</a></div>
    <div id="detail-body"><p class="muted" style="padding:40px 0">加载中…</p></div>`;

  const body = root.querySelector('#detail-body');
  let data;
  try {
    data = await getDrawing(id);
  } catch (e) {
    body.innerHTML = `<div class="error-area">加载失败：${escapeHtml(e.message)}</div>`;
    return unmountHook;
  }
  if (!data) {
    body.innerHTML = `<div class="error-area">图纸不存在或已被删除</div>`;
    return unmountHook;
  }

  ctx = { id, body, data };
  renderFull();
  return unmountHook;
}

function unmountHook() {
  disposeViewer();
  cleanupDocClick();
}

function statsText() {
  const d = ctx.data.drawing;
  const dateText = (d.created_at || '').slice(0, 16).replace('T', ' ');
  return `${ctx.data.points.length} 点 · ${ctx.data.links.length} 线 · `
    + `${escapeHtml((d.source_format || '').toUpperCase())} · ${dateText}`;
}

function renderFull() {
  const { body, data } = ctx;
  const d = data.drawing;

  body.innerHTML = `
    <div class="detail-title-row">
      <h2 class="page-title" id="d-title" style="margin-bottom:0">${escapeHtml(d.name)}</h2>
      <div class="detail-actions">
        <div class="dropdown">
          <button class="btn btn-secondary" id="btn-export">导出 ▾</button>
          <div class="dropdown-menu" id="export-menu" hidden>
            <button data-fmt="csv">CSV</button>
            <button data-fmt="xlsx">Excel</button>
            <button data-fmt="json">JSON</button>
          </div>
        </div>
        <button class="btn btn-secondary" id="btn-share">分享</button>
        <button class="btn btn-secondary" id="btn-rename">重命名</button>
        <button class="btn btn-secondary btn-danger-text" id="btn-delete">删除</button>
      </div>
    </div>
    <p class="muted small" id="d-stats" style="margin:6px 0 4px">${statsText()}</p>
    <div class="viewer-wrap">
      <div class="viewer-canvas-host" id="viewer-host"></div>
      <div class="pick-info" id="pick-info" hidden>
        <div class="pi-name" id="pi-name"></div>
        <div class="pi-coords" id="pi-coords"></div>
      </div>
      <div class="viewer-hint">拖拽旋转 · 滚轮缩放 · 点击坐标点查看详情</div>
    </div>
    <div id="tables-area"></div>`;

  body.querySelector('#btn-rename').addEventListener('click', onRenameDrawing);
  body.querySelector('#btn-delete').addEventListener('click', onDeleteDrawing);
  body.querySelector('#btn-share').addEventListener('click', onShare);
  body.querySelector('#tables-area').addEventListener('click', onTableClick);
  bindExportMenu();

  renderTables();
  rebuildViewer();
}

function rebuildViewer() {
  const host = ctx.body.querySelector('#viewer-host');
  if (!host) return;
  disposeViewer();
  const pickInfo = ctx.body.querySelector('#pick-info');
  const piName = ctx.body.querySelector('#pi-name');
  const piCoords = ctx.body.querySelector('#pi-coords');
  viewer = createViewer(host, { points: ctx.data.points, links: ctx.data.links }, {
    onPick: (pt) => {
      if (pt) {
        pickInfo.hidden = false;
        piName.textContent = pt.name;
        piCoords.innerHTML = `X ${fmt(pt.x)}&ensp;·&ensp;Y ${fmt(pt.y)}&ensp;·&ensp;Z ${fmt(pt.z)}`;
      } else {
        pickInfo.hidden = true;
      }
    },
  });
  window.__cadViewer = viewer;
}

function pointRow(p) {
  return `<tr>
    <td class="cell-name" data-pid="${p.id}" title="点击重命名">${escapeHtml(p.name)}</td>
    <td>${p.x}</td><td>${p.y}</td><td>${p.z}</td>
    <td class="td-op"><button class="row-del" data-del-pid="${p.id}" title="删除该坐标点">✕</button></td>
  </tr>`;
}

function linkRow(l) {
  return `<tr>
    <td>${escapeHtml(l.from)}</td><td>${escapeHtml(l.to)}</td>
    <td class="td-op"><button class="row-del" data-del-lid="${l.id}" title="删除该连接">✕</button></td>
  </tr>`;
}

function renderTables() {
  const area = ctx.body.querySelector('#tables-area');
  const pts = ctx.data.points;
  const links = ctx.data.links;
  area.innerHTML = `
    <h4>坐标数据（前 ${Math.min(pts.length, PT_LIMIT)} 行 / 共 ${pts.length} 行）
      <span class="edit-hint">点击名称可修改 · ✕ 删除</span></h4>
    <table class="table editable">
      <thead><tr><th>名称</th><th>X</th><th>Y</th><th>Z</th><th class="th-ops"></th></tr></thead>
      <tbody>${pts.slice(0, PT_LIMIT).map(pointRow).join('')}</tbody>
    </table>
    <h4>连接关系（前 ${Math.min(links.length, LK_LIMIT)} 条 / 共 ${links.length} 条）</h4>
    <table class="table editable">
      <thead><tr><th>起点</th><th>终点</th><th class="th-ops"></th></tr></thead>
      <tbody>${links.slice(0, LK_LIMIT).map(linkRow).join('')}</tbody>
    </table>`;
}

function refreshAll() {
  const scrollY = window.scrollY;
  renderTables();
  rebuildViewer();
  const stats = ctx.body.querySelector('#d-stats');
  if (stats) stats.textContent = statsText();
  window.scrollTo(0, scrollY);
}

let docClickHandler = null;

function bindExportMenu() {
  const btn = ctx.body.querySelector('#btn-export');
  const menu = ctx.body.querySelector('#export-menu');
  btn.addEventListener('click', (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; });
  menu.addEventListener('click', (e) => {
    const fmt = e.target && e.target.getAttribute && e.target.getAttribute('data-fmt');
    if (!fmt) return;
    menu.hidden = true;
    doExport(fmt);
  });
  cleanupDocClick();
  docClickHandler = () => { menu.hidden = true; };
  document.addEventListener('click', docClickHandler);
}

function cleanupDocClick() {
  if (docClickHandler) {
    document.removeEventListener('click', docClickHandler);
    docClickHandler = null;
  }
}

function doExport(fmt) {
  const base = exportBaseName(ctx.data.drawing.name);
  try {
    if (fmt === 'csv') exportCsv(ctx.data, base);
    else if (fmt === 'xlsx') exportXlsx(ctx.data, base);
    else if (fmt === 'json') exportJson(ctx.data, base);
    toast(`已导出 ${fmt.toUpperCase()}`);
  } catch (e) {
    toast(`导出失败：${e.message}`, 'error');
  }
}

async function onShare() {
  try {
    const r = await createShare(ctx.id);
    const link = `${location.origin}${location.pathname}#/share/${r.token}`;
    showShareDialog(link);
  } catch (e) {
    toast(e.message || '分享失败', 'error');
  }
}

function showShareDialog(link) {
  const token = link.split('#/share/')[1];
  const overlay = document.createElement('div');
  overlay.className = 'dialog-overlay';
  overlay.innerHTML = `
    <div class="dialog">
      <p class="dialog-msg">分享链接（只读）</p>
      <input class="dialog-input" readonly value="${escapeHtml(link)}">
      <p class="muted small" style="margin:-6px 0 14px">
        任何人打开此链接可查看 3D 与坐标数据（只读）；撤销后链接立即失效。
      </p>
      <div class="dialog-actions">
        <button class="btn btn-secondary" data-a="revoke">撤销分享</button>
        <button class="btn btn-secondary" data-a="copy">复制链接</button>
        <button class="btn btn-primary" data-a="close">完成</button>
      </div>
    </div>`;
  const input = overlay.querySelector('.dialog-input');
  try {
    if (navigator.clipboard) navigator.clipboard.writeText(link).catch(() => {});
  } catch { /* ignore */ }
  overlay.addEventListener('click', async (e) => {
    if (e.target === overlay) { overlay.remove(); return; }
    const a = e.target && e.target.getAttribute && e.target.getAttribute('data-a');
    if (a === 'close') { overlay.remove(); return; }
    if (a === 'copy') {
      try {
        await navigator.clipboard.writeText(link);
        toast('链接已复制');
      } catch {
        input.select();
        try { document.execCommand('copy'); toast('链接已复制'); } catch { /* ignore */ }
      }
      return;
    }
    if (a === 'revoke') {
      try {
        await revokeShare(token);
        toast('已撤销分享');
        overlay.remove();
      } catch (err) {
        toast(err.message || '撤销失败', 'error');
      }
    }
  });
  document.body.appendChild(overlay);
}

async function onTableClick(e) {
  const t = e.target;
  const pid = t.getAttribute && t.getAttribute('data-pid');
  const delPid = t.getAttribute && t.getAttribute('data-del-pid');
  const delLid = t.getAttribute && t.getAttribute('data-del-lid');
  if (pid) return editPointName(pid);
  if (delPid) return removePoint(delPid);
  if (delLid) return removeLink(delLid);
}

async function editPointName(pointId) {
  const p = ctx.data.points.find((x) => x.id === pointId);
  if (!p) return;
  const name = await promptDialog('重命名坐标点', p.name);
  if (!name || name === p.name) return;
  const oldName = p.name;
  try {
    const r = await renamePoint(ctx.id, pointId, name);
    p.name = r.name;
    ctx.data.links.forEach((l) => {
      if (l.from === oldName) l.from = r.name;
      if (l.to === oldName) l.to = r.name;
    });
    toast('已重命名');
    refreshAll();
  } catch (e) {
    toast(e.message || '重命名失败', 'error');
  }
}

async function removePoint(pointId) {
  const p = ctx.data.points.find((x) => x.id === pointId);
  if (!p) return;
  const linked = ctx.data.links.filter((l) => l.from === p.name || l.to === p.name).length;
  const yes = await confirmDialog(`删除坐标点「${p.name}」？\n将同时删除 ${linked} 条关联连接。`, { danger: true });
  if (!yes) return;
  try {
    const counts = await deletePoint(ctx.id, pointId);
    ctx.data.points = ctx.data.points.filter((x) => x.id !== pointId);
    ctx.data.links = ctx.data.links.filter((l) => l.from !== p.name && l.to !== p.name);
    toast(`已删除（剩余 ${counts.point_count} 点 / ${counts.link_count} 线）`);
    refreshAll();
  } catch (e) {
    toast(e.message || '删除失败', 'error');
  }
}

async function removeLink(linkId) {
  const l = ctx.data.links.find((x) => x.id === linkId);
  if (!l) return;
  const yes = await confirmDialog(`删除连接「${l.from} → ${l.to}」？`, { danger: true });
  if (!yes) return;
  try {
    const counts = await deleteLink(ctx.id, linkId);
    ctx.data.links = ctx.data.links.filter((x) => x.id !== linkId);
    toast(`已删除（剩余 ${counts.point_count} 点 / ${counts.link_count} 线）`);
    refreshAll();
  } catch (e) {
    toast(e.message || '删除失败', 'error');
  }
}

async function onRenameDrawing() {
  const d = ctx.data.drawing;
  const name = await promptDialog('重命名图纸', d.name);
  if (!name || name === d.name) return;
  try {
    const r = await renameDrawing(ctx.id, name);
    d.name = r.name;
    ctx.body.querySelector('#d-title').textContent = r.name;
    toast('重命名成功');
  } catch (e) {
    toast(e.message || '重命名失败', 'error');
  }
}

async function onDeleteDrawing() {
  const d = ctx.data.drawing;
  const yes = await confirmDialog(`确定删除「${d.name}」？\n图纸及其全部坐标数据将被永久删除。`, { danger: true });
  if (!yes) return;
  try {
    await deleteDrawing(ctx.id);
    toast('已删除');
    location.hash = '#/';
  } catch (e) {
    toast(e.message || '删除失败', 'error');
  }
}
