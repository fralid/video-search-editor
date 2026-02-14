# Video Search & Editor (Standalone)

Поиск по транскриптам видео и вырезка фрагментов. Локальное приложение: FastAPI backend + React frontend.

## Требования

- **Python 3.10+** — [python.org](https://www.python.org)
- **Node.js (LTS)** и **npm** — [nodejs.org](https://nodejs.org)
- **FFmpeg** — в PATH или `ffmpeg.exe` в корне проекта (для вырезки клипов)
- **yt-dlp** — для скачивания с YouTube: положите `yt-dlp.exe` в папку `yt-dlp/` (см. ниже)
- **CUDA** (опционально) — для ускорения Whisper и эмбеддингов на GPU

## Установка

### 1. Backend

```bash
pip install -r standalone_requirements.txt
```

### 2. Frontend

```bash
cd frontend
npm install
cd ..
```

### 3. yt-dlp (для загрузки с YouTube)

- Скачайте [yt-dlp.exe](https://github.com/yt-dlp/yt-dlp/releases) и поместите в папку **`yt-dlp/`** в корне проекта.
- В этой же папке есть `update.bat` для обновления до nightly-сборки.

### 4. Данные

При первом запуске создаётся каталог **`standalone_data/`** в текущей рабочей директории:

- `standalone_data/videos/` — видеофайлы
- `standalone_data/clips/` — вырезанные клипы
- `standalone_data/chroma/` — векторный индекс (ChromaDB)
- `standalone_data/app.db` — SQLite + FTS5

В репозиторий эти данные не попадают (см. `.gitignore`). Кэш моделей (Hugging Face) и `node_modules/` тоже игнорируются.

## Запуск

**Windows:** запустите **`standalone_start.bat`**. Скрипт проверит Python и Node, при необходимости установит зависимости frontend, поднимет backend и frontend и откроет браузер.

**Вручную:**

```bash
# Терминал 1 — backend
python standalone_app.py

# Терминал 2 — frontend
cd frontend && npm run dev
```

- **Backend:** http://127.0.0.1:8000  
- **Frontend:** http://localhost:5173  
- **API docs:** http://127.0.0.1:8000/docs  

Прокси Vite в режиме разработки перенаправляет запросы `/api` и `/files` на backend.

## Порты

- **8000** — FastAPI (backend)
- **5173** — Vite dev server (frontend)

Убедитесь, что порты свободны. `standalone_start.bat` при необходимости завершает процессы, занимающие 8000 и 5173.

## Добавление видео

- **YouTube:** в интерфейсе «Добавить видео» вставьте ссылку и выберите качество (720p или Best). Нужен `yt-dlp.exe` в папке `yt-dlp/`.
- **Локальные файлы:** положите видео в `standalone_data/videos/` и нажмите «Сканировать папку» в библиотеке, либо укажите путь к файлу **на машине, где запущен backend** (режим «По пути на сервере»).

## Тесты

Для запуска базовых тестов API (health, list videos) нужен установленный pytest. Из корня проекта:

```bash
pip install pytest
python -m pytest tests/test_standalone_api.py -v
```

## Лицензия и репозиторий

Проект в репозитории на GitHub. Данные, кэш и бинарники в коммиты не включаются.
