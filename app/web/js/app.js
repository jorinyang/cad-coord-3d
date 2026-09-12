// app.js — 入口与哈希路由（视图可返回卸载函数或 Promise<卸载函数>）
import { renderLibrary } from './views/library.js';
import { renderUpload } from './views/upload.js';
import { renderDetail } from './views/detail.js';
import { renderShare } from './views/share.js';

let unmount = null;
let navToken = 0;

function navigate() {
  const myToken = ++navToken;

  // 清理上一个视图
  if (typeof unmount === 'function') {
    try { unmount(); } catch { /* ignore */ }
  }
  unmount = null;

  const app = document.getElementById('app');
  app.innerHTML = '';
  const hash = location.hash || '#/';

  let ret;
  if (hash.startsWith('#/share/')) {
    ret = renderShare(app, { token: decodeURIComponent(hash.slice('#/share/'.length)) });
  } else if (hash.startsWith('#/detail/')) {
    ret = renderDetail(app, { id: decodeURIComponent(hash.slice('#/detail/'.length)) });
  } else if (hash === '#/upload') {
    ret = renderUpload(app);
  } else {
    ret = renderLibrary(app);
  }

  const accept = (fn) => {
    if (myToken === navToken) {
      unmount = typeof fn === 'function' ? fn : null;
    } else if (typeof fn === 'function') {
      fn(); // 过期视图的卸载函数立刻执行
    }
  };
  if (ret && typeof ret.then === 'function') {
    ret.then(accept).catch(() => accept(null));
  } else {
    accept(ret);
  }
}

window.addEventListener('hashchange', navigate);
navigate();
