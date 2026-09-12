// ui.js — 基础反馈组件
let toastTimer = null;

export function toast(msg, type = 'info') {
  let el = document.getElementById('toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast';
    document.body.appendChild(el);
  }
  el.className = `toast ${type}`;
  el.textContent = msg;
  // 强制重绘以重启动画
  void el.offsetWidth;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}

export function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function formatBytes(n) {
  if (!Number.isFinite(n)) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function confirmDialog(message, { danger = false } = {}) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'dialog-overlay';
    overlay.innerHTML = `
      <div class="dialog">
        <p class="dialog-msg">${escapeHtml(message)}</p>
        <div class="dialog-actions">
          <button class="btn btn-secondary" data-a="cancel">取消</button>
          <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" data-a="ok">确定</button>
        </div>
      </div>`;
    const close = (val) => { overlay.remove(); resolve(val); };
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close(false);
      const a = e.target && e.target.getAttribute && e.target.getAttribute('data-a');
      if (a === 'ok') close(true);
      if (a === 'cancel') close(false);
    });
    document.body.appendChild(overlay);
  });
}

export function promptDialog(message, defaultValue = '') {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'dialog-overlay';
    overlay.innerHTML = `
      <div class="dialog">
        <p class="dialog-msg">${escapeHtml(message)}</p>
        <input class="dialog-input" type="text" value="${escapeHtml(defaultValue)}">
        <div class="dialog-actions">
          <button class="btn btn-secondary" data-a="cancel">取消</button>
          <button class="btn btn-primary" data-a="ok">确定</button>
        </div>
      </div>`;
    const input = overlay.querySelector('.dialog-input');
    const close = (val) => { overlay.remove(); resolve(val); };
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close(null);
      const a = e.target && e.target.getAttribute && e.target.getAttribute('data-a');
      if (a === 'ok') close(input.value.trim() || null);
      if (a === 'cancel') close(null);
    });
    overlay.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') close(input.value.trim() || null);
      if (e.key === 'Escape') close(null);
    });
    document.body.appendChild(overlay);
    input.focus();
    input.select();
  });
}
