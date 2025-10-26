#!/usr/bin/env python3
import subprocess
import sys

def install_playwright_browsers():
    """Установка браузеров для Playwright"""
    print("Установка браузеров Playwright...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        print("✅ Браузеры успешно установлены")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки браузеров: {e}")
        sys.exit(1)

if __name__ == "__main__":
    install_playwright_browsers()