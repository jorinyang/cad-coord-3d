"""
converter.py — DWG → DXF 转换层

转换链（回退顺序）：LibreDWG (dwg2dxf) → ODA File Converter → 明确报错（含手动转换指引）。
设计依据：03-标准规范 模式 5（转换回退链）。
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CONVERT_TIMEOUT = 300  # 单文件转换超时（秒）
ODA_OUTPUT_VERSION = "ACAD2018"  # DXF 输出版本（现代通用，ezdxf 全支持）
ODA_OUTPUT_TYPE = "DXF"


class ConversionError(RuntimeError):
    """DWG 转换失败（消息含下一步指引）。"""


def _find_oda() -> Path | None:
    """定位 ODA File Converter 可执行文件。"""
    env = os.environ.get("ODA_CONVERTER_PATH")
    if env and Path(env).exists():
        return Path(env)
    if os.name == "nt":
        candidates: list[str] = []
        for root in (r"C:\Program Files\ODA", r"C:\Program Files (x86)\ODA"):
            candidates += glob.glob(root + r"\ODAFileConverter *\ODAFileConverter.exe")
        if candidates:
            return Path(max(candidates, key=os.path.getmtime))
    else:
        exe = shutil.which("ODAFileConverter")
        if exe:
            return Path(exe)
        apps = sorted(
            glob.glob("/opt/oda/ODAFileConverter*.AppImage")
            + glob.glob(str(Path.home() / "ODAFileConverter*.AppImage"))
        )
        if apps:
            return Path(apps[0])
    return None


def _find_libredwg() -> Path | None:
    exe = shutil.which("dwg2dxf")
    return Path(exe) if exe else None


def _convert_with_oda(oda: Path, src: Path, workdir: Path) -> Path:
    """用 ODA File Converter 转换（目录进、目录出）。"""
    in_dir = workdir / "in"
    out_dir = workdir / "out"
    in_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, in_dir / src.name)
    env = dict(os.environ)
    if os.name != "nt":
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
    cmd = [str(oda), str(in_dir), str(out_dir), ODA_OUTPUT_VERSION, ODA_OUTPUT_TYPE, "0", "1", "*.dwg"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CONVERT_TIMEOUT, env=env)
    except subprocess.TimeoutExpired as e:
        raise ConversionError(f"ODA 转换超时（>{CONVERT_TIMEOUT}s）：{src.name}") from e
    out_file = out_dir / (src.stem + ".dxf")
    if not out_file.exists():
        detail = (proc.stderr or proc.stdout or "").strip()[:300]
        raise ConversionError(f"ODA 转换未产出文件：{src.name} rc={proc.returncode} {detail}")
    return out_file


def _convert_with_libredwg(exe: Path, src: Path, workdir: Path) -> Path:
    """用 LibreDWG dwg2dxf 转换。"""
    out_file = workdir / (src.stem + ".dxf")
    cmd = [str(exe), "-o", str(out_file), str(src)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CONVERT_TIMEOUT)
    except subprocess.TimeoutExpired as e:
        raise ConversionError(f"LibreDWG 转换超时（>{CONVERT_TIMEOUT}s）：{src.name}") from e
    if not out_file.exists():
        detail = (proc.stderr or proc.stdout or "").strip()[:300]
        raise ConversionError(f"LibreDWG 转换未产出文件：{src.name} rc={proc.returncode} {detail}")
    return out_file


def convert_dwg_to_dxf(src: str | Path, workdir: str | Path | None = None) -> Path:
    """把 .dwg 转为 .dxf，返回输出文件路径。

    回退链：LibreDWG → ODA → ConversionError（含手动转换指引）。
    """
    src = Path(src)
    if not src.exists():
        raise ConversionError(f"源文件不存在：{src}")
    tmp = Path(tempfile.mkdtemp(prefix="dwg2dxf_", dir=str(workdir) if workdir else None))
    errors: list[str] = []

    libredwg = _find_libredwg()
    if libredwg:
        try:
            return _convert_with_libredwg(libredwg, src, tmp)
        except ConversionError as e:
            errors.append(f"LibreDWG: {e}")

    oda = _find_oda()
    if oda:
        try:
            return _convert_with_oda(oda, src, tmp)
        except ConversionError as e:
            errors.append(f"ODA: {e}")

    if not libredwg and not oda:
        errors.append("未找到任何转换器（LibreDWG dwg2dxf / ODA File Converter）")
    raise ConversionError(
        "DWG 转换失败：" + "；".join(errors) + "。建议：在本机 CAD 中把图纸另存为 DXF 后上传。"
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: python converter.py <file.dwg>")
        raise SystemExit(2)
    out = convert_dwg_to_dxf(sys.argv[1])
    print("converted ->", out)
