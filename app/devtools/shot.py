# -*- coding: utf-8 -*-
"""截图工具：对 9225 实例中当前的 8789 页面截图（默认动作：切到结果区再截）。"""
import base64
import sys
import time

sys.path.insert(0, r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\qianwen-case-studio")
from cdp_lib import CDP  # noqa: E402

OUT = r"C:\Users\Aorus\Desktop\Knowledge\Work\Output\cad-coord-3d\app\devtools\screenshots\c1_result.png"


def main() -> int:
    c = CDP(port=9225)
    t, sid = c.attach_page("127.0.0.1:8789")
    if not sid:
        print("no page"); return 1
    c.cmd("Emulation.setDeviceMetricsOverride",
          {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False}, session_id=sid)
    time.sleep(1.0)
    r = c.cmd("Page.captureScreenshot", {"format": "png"}, session_id=sid)
    if "result" not in r:
        print("screenshot failed:", r); return 1
    data = base64.b64decode(r["result"]["data"])
    with open(OUT, "wb") as f:
        f.write(data)
    print("saved:", OUT, len(data), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
