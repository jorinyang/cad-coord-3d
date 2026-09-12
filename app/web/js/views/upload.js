// views/upload.js — 上传与解析流（成功后跳转详情页）
import { parseFile, ApiError } from '../api.js';
import { formatBytes, toast } from '../ui.js';

const ACCEPT = ['.dwg', '.dxf'];
const MAX_SIZE = 100 * 1024 * 1024;

export function renderUpload(root) {
  root.innerHTML = `
    <section>
      <h2 class="page-title">上传图纸</h2>
      <div class="card">
        <div class="dropzone" id="dropzone">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M4 20h16"/>
          </svg>
          <p class="dz-title">拖拽图纸到这里，或 <span class="link">点击选择文件</span></p>
          <p class="dz-hint">支持 .dwg / .dxf · 单文件 ≤ 100MB</p>
          <input type="file" id="file-input" accept=".dwg,.dxf" hidden>
        </div>
        <div class="progress-area" id="progress-area" hidden>
          <div class="file-line" id="file-line"></div>
          <div class="progress"><div class="progress-bar" id="progress-bar"></div></div>
          <div class="status-line" id="status-line"></div>
        </div>
        <div class="error-area" id="error-area" hidden></div>
      </div>
    </section>`;

  const dz = root.querySelector('#dropzone');
  const input = root.querySelector('#file-input');
  const progressArea = root.querySelector('#progress-area');
  const progressBar = root.querySelector('#progress-bar');
  const statusLine = root.querySelector('#status-line');
  const fileLine = root.querySelector('#file-line');
  const errArea = root.querySelector('#error-area');

  dz.addEventListener('click', () => { input.value = ''; input.click(); });
  input.addEventListener('change', () => input.files[0] && handleFile(input.files[0]));
  ['dragover', 'dragenter'].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add('active'); }));
  ['dragleave', 'drop'].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove('active'); }));
  dz.addEventListener('drop', (e) => {
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  });

  function showError(msg) {
    errArea.hidden = false;
    errArea.textContent = msg;
  }
  function hideError() { errArea.hidden = true; errArea.textContent = ''; }

  function setProgress(pct, indeterminate = false) {
    progressBar.classList.toggle('indeterminate', indeterminate);
    if (indeterminate) progressBar.style.width = '';
    else progressBar.style.width = `${pct}%`;
  }

  async function handleFile(file) {
    const name = file.name || '';
    const dot = name.lastIndexOf('.');
    const ext = dot >= 0 ? name.slice(dot).toLowerCase() : '';
    if (!ACCEPT.includes(ext)) {
      showError(`不支持的文件类型：${ext || '(无扩展名)'}（仅支持 .dwg / .dxf）`);
      toast('文件类型不支持', 'error');
      return;
    }
    if (file.size > MAX_SIZE) {
      showError(`文件超过 100MB 上限（当前 ${formatBytes(file.size)}）`);
      toast('文件过大', 'error');
      return;
    }

    hideError();
    progressArea.hidden = false;
    dz.classList.add('disabled');
    fileLine.textContent = `${name}（${formatBytes(file.size)}）`;
    setProgress(0);
    statusLine.textContent = '上传中…';

    try {
      const data = await parseFile(file, {
        onProgress: (ratio) => {
          setProgress(Math.round(ratio * 100));
          if (ratio >= 1) {
            setProgress(0, true);
            statusLine.textContent = '解析中…（.dwg 需先转换，视图纸大小可能需要几秒到几十秒）';
          }
        },
      });
      statusLine.textContent = '解析完成，正在打开…';
      toast('解析完成');
      location.hash = `#/detail/${encodeURIComponent(data.drawing_id)}`;
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : String(err);
      showError(msg);
      progressArea.hidden = true;
      toast('解析失败', 'error');
    } finally {
      dz.classList.remove('disabled');
    }
  }
}
