// views/share.js — 只读分享页（#/share/{token}）
import { getShare } from '../sb.js';
import { createViewer } from '../viewer3d.js';
import { escapeHtml } from '../ui.js';

let viewer = null;

function unmount() {
  if (viewer) { viewer.dispose(); viewer = null; }
}

function fmt(v) {
  return (typeof v === 'number' ? v.toFixed(3) : String(v));
}

export async function renderShare(root, params) {
  unmount();
  const token = params.token;

  root.innerHTML = `<div id="share-body"><p class="muted" style="padding:40px 0">加载中…</p></div>`;
  const body = root.querySelector('#share-body');

  let payload;
  try {
    payload = await getShare(token);
  } catch (e) {
    body.innerHTML = `<div class="error-area">加载失败：${escapeHtml(e.message)}</div>`;
    return unmount;
  }
  if (!payload) {
    body.innerHTML = `
      <section class="empty-state">
        <h2>分享不存在或已撤销</h2>
        <p>该分享链接可能已被撤销，或从未存在</p>
      </section>`;
    return unmount;
  }

  renderFull(body, payload);
  return unmount;
}

function renderFull(body, payload) {
  const m = payload.meta || {};
  const pts = payload.points || [];
  const previewRows = pts.slice(0, 100).map((p) => `
    <tr><td>${escapeHtml(p.name)}</td><td>${p.x}</td><td>${p.y}</td><td>${p.z}</td></tr>`).join('');

  body.innerHTML = `
    <div class="share-head">
      <h2 class="page-title" style="margin-bottom:0">${escapeHtml(m.name || '图纸分享')}</h2>
      <span class="share-badge">只读分享</span>
    </div>
    <p class="muted small" style="margin:6px 0 4px">
      ${m.point_count ?? pts.length} 点 · ${m.link_count ?? (payload.links || []).length} 线
      · ${escapeHtml((m.source_format || '').toUpperCase())}
    </p>
    <div class="viewer-wrap">
      <div class="viewer-canvas-host" id="viewer-host"></div>
      <div class="pick-info" id="pick-info" hidden>
        <div class="pi-name" id="pi-name"></div>
        <div class="pi-coords" id="pi-coords"></div>
      </div>
      <div class="viewer-hint">拖拽旋转 · 滚轮缩放 · 点击坐标点查看详情</div>
    </div>
    <h4>坐标数据（前 ${Math.min(pts.length, 100)} 行 / 共 ${pts.length} 行）</h4>
    <table class="table">
      <thead><tr><th>名称</th><th>X</th><th>Y</th><th>Z</th></tr></thead>
      <tbody>${previewRows}</tbody>
    </table>`;

  const host = body.querySelector('#viewer-host');
  const pickInfo = body.querySelector('#pick-info');
  const piName = body.querySelector('#pi-name');
  const piCoords = body.querySelector('#pi-coords');
  viewer = createViewer(host, { points: payload.points, links: payload.links }, {
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
