// api.js — 后端解析服务客户端
import { API_BASE } from './config.js';

export class ApiError extends Error {
  constructor(message, code) {
    super(message);
    this.name = 'ApiError';
    this.code = code || 'UNKNOWN';
  }
}

/**
 * 上传图纸到解析服务。
 * @param {File} file
 * @param {{onProgress?: (ratio: number) => void}} opts
 * @returns {Promise<object>} 标准坐标数据（meta/points/links）
 */
export function parseFile(file, { onProgress } = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE}/api/parse`);
    xhr.timeout = 10 * 60 * 1000;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };

    xhr.onload = () => {
      let j = null;
      try { j = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300 && j && j.ok) {
        resolve(j.data);
      } else if (j && j.error) {
        reject(new ApiError(j.error.message, j.error.code));
      } else {
        reject(new ApiError(`请求失败（HTTP ${xhr.status}）`, `HTTP_${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new ApiError('网络错误：无法连接解析服务', 'NETWORK'));
    xhr.ontimeout = () => reject(new ApiError('请求超时（10 分钟）', 'TIMEOUT'));

    const fd = new FormData();
    fd.append('file', file, file.name);
    xhr.send(fd);
  });
}

async function callJson(url, options) {
  const res = await fetch(url, options);
  const j = await res.json().catch(() => null);
  if (res.ok && j && j.ok) return j.data;
  throw new ApiError((j && j.error && j.error.message) || `请求失败（HTTP ${res.status}）`,
    (j && j.error && j.error.code) || `HTTP_${res.status}`);
}

export function renameDrawing(id, name) {
  return callJson(`${API_BASE}/api/drawings/${encodeURIComponent(id)}`,
    { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
}

export function deleteDrawing(id) {
  return callJson(`${API_BASE}/api/drawings/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export function renamePoint(drawingId, pointId, name) {
  return callJson(
    `${API_BASE}/api/drawings/${encodeURIComponent(drawingId)}/points/${encodeURIComponent(pointId)}`,
    { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
}

export function deletePoint(drawingId, pointId) {
  return callJson(
    `${API_BASE}/api/drawings/${encodeURIComponent(drawingId)}/points/${encodeURIComponent(pointId)}`,
    { method: 'DELETE' });
}

export function deleteLink(drawingId, linkId) {
  return callJson(
    `${API_BASE}/api/drawings/${encodeURIComponent(drawingId)}/links/${encodeURIComponent(linkId)}`,
    { method: 'DELETE' });
}

export function createShare(drawingId) {
  return callJson(
    `${API_BASE}/api/drawings/${encodeURIComponent(drawingId)}/share`,
    { method: 'POST' });
}

export function revokeShare(token) {
  return callJson(
    `${API_BASE}/api/share/${encodeURIComponent(token)}`,
    { method: 'DELETE' });
}
