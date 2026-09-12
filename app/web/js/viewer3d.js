// viewer3d.js — Three.js 骨架级 3D 查看器（点 + 连线）
// 视觉依据 03-标准规范：背景 #F5F5F7；点 #0071E3；选中 #FF9500；连线 rgba(0,0,0,0.22)
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const PICK_RADIUS_PX = 12; // 点选命中半径（屏幕像素）

export function createViewer(container, data, options = {}) {
  const onPick = options.onPick || (() => {});
  const points = data.points || [];
  const links = data.links || [];

  // ---------- 数据准备 ----------
  const nameToIdx = new Map();
  points.forEach((p, i) => nameToIdx.set(p.name, i));

  const posArr = new Float32Array(points.length * 3);
  const minV = [Infinity, Infinity, Infinity];
  const maxV = [-Infinity, -Infinity, -Infinity];
  points.forEach((p, i) => {
    posArr[i * 3] = p.x; posArr[i * 3 + 1] = p.y; posArr[i * 3 + 2] = p.z;
    minV[0] = Math.min(minV[0], p.x); maxV[0] = Math.max(maxV[0], p.x);
    minV[1] = Math.min(minV[1], p.y); maxV[1] = Math.max(maxV[1], p.y);
    minV[2] = Math.min(minV[2], p.z); maxV[2] = Math.max(maxV[2], p.z);
  });
  if (points.length === 0) { minV.fill(0); maxV.fill(1); }
  // 全量跨度（含离群点，供远裁剪面使用）
  const fullSize = Math.max(maxV[0] - minV[0], maxV[1] - minV[1], maxV[2] - minV[2]) || 1;

  // ---------- 取景边界（稳健版） ----------
  // 背景：真实图纸常含极端离群对象（如缩放异常的块引用），若按全量 bbox 取景，
  // 主体结构会被压缩到亚像素级而无法查看。这里用 1%~99% 分位数界定"主群体"
  // 作为初始取景框；离群点仍全量渲染（远裁剪面按全量跨度设置），可通过缩放查看。
  const ROBUST_MIN_COUNT = 200; // 小图（<200 点）直接按全量取景，不做分位修正
  const ROBUST_Q = 0.01;
  const ROBUST_PAD = 0.12;      // 分位框外扩 12%，避免边缘点贴边

  function percentile(sorted, q) {
    const pos = (sorted.length - 1) * q;
    const lo = Math.floor(pos), hi = Math.ceil(pos);
    return lo === hi ? sorted[lo] : sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  }

  let center, size;
  if (points.length >= ROBUST_MIN_COUNT) {
    const axes = [0, 1, 2].map((k) => points.map((p) => [p.x, p.y, p.z][k]).sort((a, b) => a - b));
    const lo = axes.map((s) => percentile(s, ROBUST_Q));
    const hi = axes.map((s) => percentile(s, 1 - ROBUST_Q));
    const vLo = [], vHi = [];
    for (let k = 0; k < 3; k++) {
      const span = hi[k] - lo[k] || 1;
      vLo.push(lo[k] - span * ROBUST_PAD);
      vHi.push(hi[k] + span * ROBUST_PAD);
    }
    center = new THREE.Vector3((vLo[0] + vHi[0]) / 2, (vLo[1] + vHi[1]) / 2, (vLo[2] + vHi[2]) / 2);
    size = Math.max(vHi[0] - vLo[0], vHi[1] - vLo[1], vHi[2] - vLo[2]) || 1;
  } else {
    center = new THREE.Vector3(
      (minV[0] + maxV[0]) / 2, (minV[1] + maxV[1]) / 2, (minV[2] + maxV[2]) / 2);
    size = fullSize;
  }

  const linePos = [];
  links.forEach((l) => {
    const a = nameToIdx.get(l.from);
    const b = nameToIdx.get(l.to);
    if (a == null || b == null) return;
    linePos.push(posArr[a * 3], posArr[a * 3 + 1], posArr[a * 3 + 2],
                 posArr[b * 3], posArr[b * 3 + 1], posArr[b * 3 + 2]);
  });

  // ---------- 场景 / 相机 / 渲染器 ----------
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xF5F5F7);

  const camera = new THREE.PerspectiveCamera(45, 1, size / 1000, fullSize * 200);
  const dist = size * 1.5;
  camera.up.set(0, 0, 1); // CAD 习惯：Z 轴向上
  camera.position.set(center.x + dist * 0.72, center.y - dist * 0.72, center.z + dist * 0.62);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  container.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.copy(center);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.update();

  // ---------- 圆点纹理 ----------
  function makeDotTexture() {
    const cv = document.createElement('canvas');
    cv.width = cv.height = 64;
    const ctx = cv.getContext('2d');
    ctx.clearRect(0, 0, 64, 64);
    ctx.beginPath();
    ctx.arc(32, 32, 26, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }
  const dotTex = makeDotTexture();

  // ---------- 点 ----------
  const pointsGeo = new THREE.BufferGeometry();
  pointsGeo.setAttribute('position', new THREE.BufferAttribute(posArr, 3));
  const pointsMat = new THREE.PointsMaterial({
    size: 7, sizeAttenuation: false, map: dotTex,
    transparent: true, alphaTest: 0.4, color: 0x0071E3,
  });
  const pointsObj = new THREE.Points(pointsGeo, pointsMat);
  pointsObj.renderOrder = 2;
  scene.add(pointsObj);

  // ---------- 选中高亮 ----------
  const hlGeo = new THREE.BufferGeometry();
  hlGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3), 3));
  const hlMat = new THREE.PointsMaterial({
    size: 14, sizeAttenuation: false, map: dotTex,
    transparent: true, alphaTest: 0.2, color: 0xFF9500, depthTest: false,
  });
  const hlObj = new THREE.Points(hlGeo, hlMat);
  hlObj.renderOrder = 5;
  hlObj.visible = false;
  scene.add(hlObj);

  // ---------- 连线 ----------
  const lineGeo = new THREE.BufferGeometry();
  lineGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(linePos), 3));
  const lineMat = new THREE.LineBasicMaterial({ color: 0x1D1D1F, transparent: true, opacity: 0.22 });
  const linesObj = new THREE.LineSegments(lineGeo, lineMat);
  scene.add(linesObj);

  // ---------- 悬浮提示（内建 tooltip） ----------
  const tooltip = document.createElement('div');
  tooltip.className = 'viewer-tooltip';
  tooltip.hidden = true;
  container.appendChild(tooltip);

  // ---------- 拾取 ----------
  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let selectedIdx = null;

  function computeThreshold() {
    const distToCam = camera.position.distanceTo(controls.target);
    const vFov = THREE.MathUtils.degToRad(camera.fov);
    const worldPerPixel = 2 * Math.tan(vFov / 2) * distToCam / (renderer.domElement.clientHeight || 1);
    return worldPerPixel * PICK_RADIUS_PX;
  }

  function pickAt(clientX, clientY) {
    const rect = renderer.domElement.getBoundingClientRect();
    ndc.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    ndc.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.params.Points.threshold = computeThreshold();
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObject(pointsObj, false);
    return hits.length ? hits[0].index : null;
  }

  function select(idx) {
    selectedIdx = idx;
    if (idx == null) {
      hlObj.visible = false;
    } else {
      const p = points[idx];
      const attr = hlGeo.getAttribute('position');
      attr.setXYZ(0, p.x, p.y, p.z);
      attr.needsUpdate = true;
      hlObj.visible = true;
    }
    onPick(idx == null ? null : points[idx]);
  }

  // ---------- 事件 ----------
  const el = renderer.domElement;
  let downX = 0, downY = 0;
  const onPointerDown = (e) => { downX = e.clientX; downY = e.clientY; };
  const onPointerUp = (e) => {
    if (Math.hypot(e.clientX - downX, e.clientY - downY) > 5) return; // 拖拽不算点击
    select(pickAt(e.clientX, e.clientY));
  };
  let lastHover = 0;
  const onPointerMove = (e) => {
    const now = performance.now();
    if (now - lastHover < 60) return;
    lastHover = now;
    const idx = pickAt(e.clientX, e.clientY);
    el.style.cursor = idx != null ? 'pointer' : 'default';
    if (idx != null) {
      const rect = container.getBoundingClientRect();
      tooltip.hidden = false;
      tooltip.textContent = points[idx].name;
      tooltip.style.left = `${e.clientX - rect.left + 14}px`;
      tooltip.style.top = `${e.clientY - rect.top + 14}px`;
    } else {
      tooltip.hidden = true;
    }
  };
  const onPointerLeave = () => { tooltip.hidden = true; };
  el.addEventListener('pointerdown', onPointerDown);
  el.addEventListener('pointerup', onPointerUp);
  el.addEventListener('pointermove', onPointerMove);
  el.addEventListener('pointerleave', onPointerLeave);

  // ---------- 尺寸 ----------
  function resize() {
    const w = container.clientWidth || 640;
    const h = container.clientHeight || 420;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(container);
  resize();

  // ---------- 渲染循环 ----------
  let raf = 0;
  const tick = () => {
    controls.update();
    renderer.render(scene, camera);
    raf = requestAnimationFrame(tick);
  };
  tick();

  // ---------- 辅助 API ----------
  function fitView() {
    camera.position.set(center.x + dist * 0.72, center.y - dist * 0.72, center.z + dist * 0.62);
    controls.target.copy(center);
    controls.update();
  }
  function projectToScreen(i) {
    const p = points[i];
    const v = new THREE.Vector3(p.x, p.y, p.z).project(camera);
    const rect = el.getBoundingClientRect();
    return {
      x: rect.left + ((v.x + 1) / 2) * rect.width,
      y: rect.top + ((-v.y + 1) / 2) * rect.height,
    };
  }

  // ---------- 销毁 ----------
  let disposed = false;
  function dispose() {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(raf);
    ro.disconnect();
    el.removeEventListener('pointerdown', onPointerDown);
    el.removeEventListener('pointerup', onPointerUp);
    el.removeEventListener('pointermove', onPointerMove);
    el.removeEventListener('pointerleave', onPointerLeave);
    controls.dispose();
    pointsGeo.dispose(); pointsMat.dispose();
    lineGeo.dispose(); lineMat.dispose();
    hlGeo.dispose(); hlMat.dispose();
    dotTex.dispose();
    renderer.dispose();
    if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
    if (tooltip.parentNode) tooltip.parentNode.removeChild(tooltip);
  }

  return {
    dispose, fitView, select, selectByIndex: select, projectToScreen, pickAt,
    get pointCount() { return points.length; },
    get selectedIndex() { return selectedIdx; },
    // 调试/测试句柄（E2E 取证用，只读）
    get scene() { return scene; },
    get objects() { return { pointsObj, hlObj, linesObj }; },
  };
}
