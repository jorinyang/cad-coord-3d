# -*- coding: utf-8 -*-
"""bug 侦查 2：导出菜单行为取证（overflow 链 + 交互测试 + 可靠重截图）。

依赖：headless 9225、前端 8789。
"""
import base64
import sys
import time

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

PORT = 9225
FRONT = "http://127.0.0.1:8789/"
OUT = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\devtools\screenshots"
DID = "004bb6e6-4464-4a5c-9eb3-71113640d525"

HOOK = ("window.__errs=[];"
        "window.addEventListener('error',function(e){window.__errs.push(String(e.message||e))});"
        "window.addEventListener('unhandledrejection',function(e){window.__errs.push('rej:'+String(e.reason))});")


def two_frames(c, sid):
    c.js("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(1))))", sid)
    time.sleep(0.25)


def shot(c, sid, name):
    two_frames(c, sid)
    r = c.cmd("Page.captureScreenshot", {"format": "png"}, session_id=sid)
    data = base64.b64decode(r["result"]["data"])
    open(OUT + "\\" + name, "wb").write(data)
    print("shot:", name, len(data), "bytes")


def state(c, sid):
    return c.js("""(() => {
      const m = document.querySelector('#export-menu');
      if (!m) return 'no-menu';
      const r = m.getBoundingClientRect();
      return JSON.stringify({hidden: m.hidden, display: getComputedStyle(m).display,
                             x: Math.round(r.x), y: Math.round(r.y),
                             w: Math.round(r.width), h: Math.round(r.height),
                             visible: cr_visible(m)});
      function cr_visible(el) {
        let e = el;
        while (e && e !== document.documentElement) {
          const cs = getComputedStyle(e);
          if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0)
            return 'hidden-by:' + (e.className || e.tagName);
          if (cs.overflow !== 'visible') {
            const rr = e.getBoundingClientRect(); const er = el.getBoundingClientRect();
            if (er.bottom > rr.bottom + 0.5 || er.right > rr.right + 0.5 ||
                er.top < rr.top - 0.5 || er.left < rr.left - 0.5)
              return 'clipped-by:' + (e.className || e.tagName) + ' ov=' + cs.overflow;
          }
          e = e.parentElement;
        }
        return 'ok';
      }
    })()""", sid)


def main() -> int:
    c = CDP(port=PORT)
    t, sid = c.attach_page("127.0.0.1:8789")
    if not sid:
        print("cannot attach"); return 1
    c.cmd("Page.addScriptToEvaluateOnNewDocument", {"source": HOOK}, session_id=sid)
    c.cmd("Emulation.setDeviceMetricsOverride",
          {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, session_id=sid)
    c.goto(FRONT + "#/detail/" + DID, sid)
    for _ in range(80):
        if c.js("!!window.__cadViewer", sid):
            break
        time.sleep(0.5)
    time.sleep(1.5)
    c.js("window.scrollTo(0,0)", sid); time.sleep(0.3)

    # 0) 祖先 overflow 链
    chain = c.js("""(() => {
      let el = document.querySelector('#export-menu');
      const out = [];
      while (el && el !== document.body) {
        const cs = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        out.push({cls: String(el.className || el.tagName), overflow: cs.overflow,
                  x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)});
        el = el.parentElement;
      }
      return JSON.stringify(out, null, 1);
    })()""", sid)
    print("== ancestor chain (menu -> body) =="); print(chain)

    # 1) 初始状态
    print("\n1) initial:", state(c, sid))
    shot(c, sid, "scan4_closedB.png")

    # 2) 打开
    c.js("document.querySelector('#btn-export').click()", sid)
    time.sleep(1.0)
    print("2) after open:", state(c, sid))
    shot(c, sid, "scan5_openB.png")

    # 3) 点外部关闭
    c.js("document.body.click()", sid); time.sleep(0.6)
    print("3) after outside click:", state(c, sid))

    # 4) 打开 → 再点按钮（toggle 关闭）
    c.js("document.querySelector('#btn-export').click()", sid); time.sleep(0.4)
    h1 = state(c, sid)
    c.js("document.querySelector('#btn-export').click()", sid); time.sleep(0.4)
    h2 = state(c, sid)
    print("4) toggle: after open:", h1)
    print("   toggle: after 2nd click:", h2)

    # 5) 菜单项结构 + 事件冒烟（不执行真实下载，只读结构）
    c.js("document.querySelector('#btn-export').click()", sid); time.sleep(0.4)
    items = c.js("""(() => {
      const menu = document.querySelector('#export-menu');
      return JSON.stringify({
        visible: !menu.hidden,
        items: Array.from(menu.querySelectorAll('button')).map(b => b.textContent),
        menuRect: (() => { const r = menu.getBoundingClientRect();
          return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}; })()
      });
    })()""", sid)
    print("\n5) structure:", items)

    # 6) 最终截图（菜单保持打开，供像素 diff）
    shot(c, sid, "scan6_openFinal.png")

    print("\nerrs:", c.js("window.__errs", sid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
