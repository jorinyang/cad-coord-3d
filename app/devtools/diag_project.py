# -*- coding: utf-8 -*-
"""投影分布诊断：3846 个点的屏幕投影落点统计（本地 8789 tab）。

判据：若所有点投影都在画布内且铺开 → 渲染问题；若聚团/在画布外 → 相机/缩放问题。
用法：python app/devtools/diag_project.py
"""
import sys

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

c = CDP(port=9225)
t, sid = c.attach_page("127.0.0.1:8789")
if not sid:
    print("no tab at 8789")
    sys.exit(1)

print("viewer-wrap rect :", c.js(
    "JSON.stringify((() => { const r = document.querySelector('.viewer-wrap').getBoundingClientRect();"
    " return {l: Math.round(r.left), t: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height)}; })())", sid))
print("canvas rect      :", c.js(
    "JSON.stringify((() => { const el = document.querySelector('.viewer-wrap canvas');"
    " if (!el) return null; const r = el.getBoundingClientRect();"
    " return {l: Math.round(r.left), t: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height)}; })())", sid))
print()
print("投影统计 :", c.js(
    "(() => { const r = window.__cadViewer; const n = r.pointCount;"
    " const cvs = document.querySelector('.viewer-wrap canvas'); const rect = cvs.getBoundingClientRect();"
    " let inside = 0, minx = 1e18, maxx = -1e18, miny = 1e18, maxy = -1e18;"
    " const sx = [], sy = [];"
    " for (let i = 0; i < n; i++) { const s = r.projectToScreen(i);"
    "  if (s.x >= rect.left && s.x <= rect.right && s.y >= rect.top && s.y <= rect.bottom) inside++;"
    "  minx = Math.min(minx, s.x); maxx = Math.max(maxx, s.x);"
    "  miny = Math.min(miny, s.y); maxy = Math.max(maxy, s.y); sx.push(s.x); sy.push(s.y); }"
    " sx.sort((a,b)=>a-b); sy.sort((a,b)=>a-b);"
    " const p50 = [sx[Math.floor(n*0.5)], sy[Math.floor(n*0.5)]];"
    " const p10 = [sx[Math.floor(n*0.1)], sy[Math.floor(n*0.1)]];"
    " const p90 = [sx[Math.floor(n*0.9)], sy[Math.floor(n*0.9)]];"
    " return JSON.stringify({n, inside,"
    "  minx: Math.round(minx), maxx: Math.round(maxx), miny: Math.round(miny), maxy: Math.round(maxy),"
    "  p10: p10.map(Math.round), p50: p50.map(Math.round), p90: p90.map(Math.round)}); })()", sid))

print()
print("世界坐标分位 :", c.js(
    "(() => { const a = window.__cadViewer.objects.pointsObj.geometry.attributes.position.array;"
    " const xs = [], ys = [], zs = [];"
    " for (let i = 0; i < a.length; i += 3) { xs.push(a[i]); ys.push(a[i + 1]); zs.push(a[i + 2]); }"
    " const q = (arr, p) => { const s = arr.slice().sort((x, y) => x - y); return s[Math.floor(s.length * p)]; };"
    " return JSON.stringify({x: [0, 0.01, 0.05, 0.5, 0.95, 0.99, 1].map(p => Math.round(q(xs, p))),"
    "  y: [0, 0.01, 0.05, 0.5, 0.95, 0.99, 1].map(p => Math.round(q(ys, p))),"
    "  z: [0, 0.5, 1].map(p => Math.round(q(zs, p)))}); })()", sid))
