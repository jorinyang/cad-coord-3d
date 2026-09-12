// views/library.js — 图纸库（列表 + 上传入口）
import { listDrawings } from '../sb.js';
import { escapeHtml } from '../ui.js';

export async function renderLibrary(root) {
  root.innerHTML = `
    <div class="lib-head">
      <h2 class="page-title" style="margin-bottom:0">图纸库</h2>
      <a class="btn btn-primary" href="#/upload">上传图纸</a>
    </div>
    <div id="lib-body" style="margin-top:22px"><p class="muted">加载中…</p></div>`;

  const body = root.querySelector('#lib-body');
  let rows;
  try {
    rows = await listDrawings();
  } catch (e) {
    body.innerHTML = `<div class="error-area">图纸列表加载失败：${escapeHtml(e.message)}<br>
      请确认网络连接与数据配置</div>`;
    return;
  }

  if (!rows.length) {
    body.innerHTML = `
      <section class="empty-state">
        <svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 7l4.5-4.5h9L21 7v13.5H3z"/>
          <path d="M3 7h18"/><path d="M8 12l3 3 5-6"/>
        </svg>
        <h2>还没有图纸</h2>
        <p>上传 .dwg 或 .dxf 图纸，自动拆解为坐标点与连接关系</p>
        <a class="btn btn-primary" href="#/upload">上传图纸</a>
      </section>`;
    return;
  }

  body.innerHTML = `<div class="drawing-list">${rows.map(cardHtml).join('')}</div>`;
}

function cardHtml(d) {
  const date = (d.created_at || '').slice(0, 16).replace('T', ' ');
  const fmt = (d.source_format || '').toUpperCase();
  return `
    <a class="drawing-card" href="#/detail/${encodeURIComponent(d.id)}">
      <div class="dc-name">${escapeHtml(d.name)}</div>
      <div class="dc-meta">${d.point_count} 点 · ${d.link_count} 线 · ${escapeHtml(fmt)} · ${date}</div>
    </a>`;
}
