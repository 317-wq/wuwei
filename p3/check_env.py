# -*- coding: utf-8 -*-
"""环境自检：确认当前解释器里两个框架都装好了、浏览器也能启动。

IDE（Pylance / PyCharm）报 “无法解析导入” 只说明它选中的解释器和这里跑的不是同一个，
跟代码能不能运行没关系。先跑这个脚本看实际情况：

    python check_env.py
"""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _line(title: str, value: str) -> None:
    print(f"{title:<26}{value}")


def _check_package(dist_name: str, import_name: str) -> bool:
    """同时看两件事：包是否装在这个解释器里、能不能真的 import。"""
    try:
        dist_version = version(dist_name)
    except PackageNotFoundError:
        _line(import_name, "未安装（当前解释器里没有这个包）")
        return False
    try:
        module = __import__(import_name)
    except Exception as exc:  # noqa: BLE001
        _line(import_name, f"{dist_version} 但导入失败：{exc}")
        return False
    _line(import_name, f"{dist_version}  <- {Path(module.__file__).parent}")
    return True


def main() -> int:
    ok = True
    print("=" * 76)
    _line("Python 解释器", sys.executable)
    _line("Python 版本", sys.version.split()[0])
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    _line("虚拟环境", "是（" + sys.prefix + "）" if in_venv else "否（直接用全局解释器）")

    print("-" * 76)
    ok &= _check_package("DrissionPage", "DrissionPage")
    ok &= _check_package("playwright", "playwright")

    print("-" * 76)
    # Playwright 用的 Chromium 是否存在（对应：python -m playwright install chromium）
    browsers = Path.home() / "AppData" / "Local" / "ms-playwright"
    chromium = sorted(browsers.glob("chromium-*")) if browsers.exists() else []
    if chromium:
        _line("Playwright Chromium", chromium[-1].name)
    else:
        _line("Playwright Chromium", "未找到 -> python -m playwright install chromium")
        ok = False

    # DrissionPage 接管的是本机 Chrome / Edge
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    chrome = next((p for p in candidates if p.exists()), None)
    _line("本机 Chrome / Edge", str(chrome) if chrome else "未找到，DrissionPage 要手动 set_browser_path")
    ok = ok and chrome is not None

    print("-" * 76)
    # “能 import” 不等于 “能跑”，两边各真起一次浏览器
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content("<h1>ok</h1>")
            text = page.inner_text("h1")
            browser.close()
        _line("Playwright 启动测试", f"通过（读到 {text}）")
    except Exception as exc:  # noqa: BLE001
        _line("Playwright 启动测试", f"失败：{exc}")
        ok = False

    try:
        from DrissionPage import ChromiumOptions, ChromiumPage

        page = ChromiumPage(ChromiumOptions().auto_port().headless())
        try:
            page.get("data:text/html,<h1>ok</h1>")
            text = page.ele("css:h1").text
        finally:
            page.quit()
        _line("DrissionPage 启动测试", f"通过（读到 {text}）")
    except Exception as exc:  # noqa: BLE001
        _line("DrissionPage 启动测试", f"失败：{exc}")
        ok = False

    print("=" * 76)
    if ok:
        print("环境可用 ✅  直接 python run_all.py 即可")
    else:
        print("环境有缺失 ❌  先 pip install -r requirements.txt，再 python -m playwright install chromium")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
