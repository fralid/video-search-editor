#!/usr/bin/env python3
"""
Standalone Video Search & Editor
FastAPI бэкенд + React фронтенд (оригинальный UI).
"""
import sys
import subprocess
import os

# Настройки CUDA для Windows (expandable_segments НЕ поддерживается на Windows)
# max_split_size_mb помогает избежать фрагментации памяти
if "PYTORCH_CUDA_ALLOC_CONF" not in os.environ:
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"


def check_deps() -> bool:
    print("Проверка зависимостей...")
    ok = True

    for name, pkg, hint in [
        ("torch", "torch", "pip install torch"),
        ("transformers", "transformers", "pip install transformers optimum accelerate"),
        ("sentence_transformers", "sentence-transformers", "pip install sentence-transformers"),
        ("chromadb", "chromadb", "pip install chromadb"),
        ("fastapi", "fastapi", "pip install fastapi uvicorn[standard]"),
        ("uvicorn", "uvicorn", "pip install uvicorn[standard]"),
    ]:
        try:
            mod = __import__(name)
            ver = getattr(mod, "__version__", "")
            print(f"  [OK] {pkg} {ver}")
        except ImportError:
            print(f"  [!!] {pkg} — {hint}")
            ok = False

    # GPU
    try:
        import torch
        if torch.cuda.is_available():
            print(f"  [OK] CUDA: {torch.cuda.get_device_name(0)}")
        else:
            print("  [--] CUDA не доступна (CPU mode)")
    except Exception:
        pass

    # FFmpeg
    try:
        r = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        print("  [OK] ffmpeg") if r.returncode == 0 else print("  [--] ffmpeg (ошибка)")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("  [--] ffmpeg не найден (вырезка недоступна)")

    print()
    return ok


def main():
    print("=" * 50)
    print("  Video Search & Editor (Standalone)")
    print("=" * 50)
    print()

    if not check_deps():
        print("Установите зависимости:")
        print("  pip install -r standalone_requirements.txt")
        input("\nEnter для выхода...")
        sys.exit(1)

    try:
        from standalone.db import init_db
        from standalone.config import VIDEO_DIR
        from standalone import watcher
    except Exception as e:
        print(f"[ERROR] Ошибка импорта модулей: {e}")
        import traceback
        traceback.print_exc()
        input("\nEnter для выхода...")
        sys.exit(1)

    try:
        init_db()
    except Exception as e:
        print(f"[ERROR] Ошибка инициализации БД: {e}")
        import traceback
        traceback.print_exc()
        input("\nEnter для выхода...")
        sys.exit(1)

    # Автообработка отключена — обработка только через UI
    # print(f"Автообработка: {VIDEO_DIR.absolute()}")
    # watcher.start()

    # Получаем локальный IP для доступа по сети
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    # Запуск FastAPI на порту 8000
    print()
    print("=" * 50)
    print(f"  Backend:  http://127.0.0.1:8000 (Local)")
    print(f"            http://{local_ip}:8000 (Network)")
    print(f"  Frontend: http://127.0.0.1:5173 (Local)")
    print(f"            http://{local_ip}:5173 (Network)")
    print("=" * 50)
    print()

    try:
        import uvicorn
        from standalone.api import app
    except Exception as e:
        print(f"[ERROR] Ошибка импорта FastAPI: {e}")
        import traceback
        traceback.print_exc()
        input("\nEnter для выхода...")
        sys.exit(1)

    try:
        # 0.0.0.0 позволяет доступ по сети
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except KeyboardInterrupt:
        watcher.stop()
        print("\nОстановлено.")
    except Exception as e:
        watcher.stop()
        print(f"\n[ERROR] Ошибка запуска сервера: {e}")
        import traceback
        traceback.print_exc()
        input("\nEnter для выхода...")
        sys.exit(1)


if __name__ == "__main__":
    main()
