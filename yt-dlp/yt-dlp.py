import gradio as gr
import subprocess
import os
import time

# Доступные источники cookies (Firefox первый — он не имеет проблемы с DPAPI)
COOKIE_SOURCES = [
    "Firefox (рекомендуется)",
    "Chrome",
    "Edge",
    "Brave",
    "Opera",
    "Файл cookies (вручную)",
    "Без cookies",
]

# Маппинг названий на аргументы yt-dlp
BROWSER_MAP = {
    "Firefox (рекомендуется)": "firefox",
    "Chrome": "chrome",
    "Edge": "edge",
    "Brave": "brave",
    "Opera": "opera",
}

# Браузеры на движке Chromium, подверженные ошибке DPAPI
DPAPI_HINT = (
    "\n\n⚠ Подсказка: Chrome/Edge/Brave 127+ на Windows шифруют cookies через DPAPI, "
    "и yt-dlp не может их расшифровать.\n"
    "Решения:\n"
    "  1. Используйте Firefox (рекомендуется) — у него нет этой проблемы\n"
    "  2. Полностью закройте браузер перед загрузкой (включая фоновые процессы)\n"
    "  3. Используйте «Файл cookies (вручную)» — экспортируйте cookies расширением"
)
CHROMIUM_BROWSERS = {"Chrome", "Edge", "Brave", "Opera"}



# Режимы качества
QUALITY_BEST = "Лучшее качество (перекодировка NVENC)"
QUALITY_FAST = "Быстрая загрузка 720p (без перекодировки)"

QUALITY_MODES = [QUALITY_BEST, QUALITY_FAST]


def _build_command(url: str, cookie_source: str, quality_mode: str):
    """Собирает команду yt-dlp для загрузки одного видео."""
    work_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(work_dir, "save"), exist_ok=True)

    yt_dlp_path = os.path.join(work_dir, "yt-dlp.exe")

    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )

    command = [
        yt_dlp_path,
        "--js-runtimes", f"node:{os.path.join(work_dir, 'node.exe')}",
        "--no-playlist",
        "--newline",
        "--user-agent", user_agent,
        "--referer", "https://www.youtube.com/",
    ]

    if quality_mode == QUALITY_FAST:
        # ──── Быстрый режим: 720p, без перекодировки ────
        # Берём готовый mp4 до 720p — чтобы не нужен был мерж/перекодировка
        # Фоллбэк: если нет mp4, берём любое видео до 720p + аудио
        command.extend([
            "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best",
            "--remux-video", "mp4",  # простой ремукс (копирование потоков, без перекодировки)
            "-o", "save/%(title)s.mp4",
        ])
    else:
        # ──── Лучшее качество: макс. разрешение + перекодировка NVENC ────
        postproc_args = (
            "-c:v h264_nvenc -preset p4 -rc:v vbr -cq 19 -b:v 0 "
            "-c:a aac -b:a 128k -movflags +faststart -pix_fmt yuv420p"
        )
        command.extend([
            "-f", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "--recode-video", "mp4",
            "--postprocessor-args", f"ffmpeg:{postproc_args}",
            "-o", "save/%(title)s.mp4",
        ])

    # Добавляем аргументы cookies в зависимости от выбора пользователя
    if cookie_source in BROWSER_MAP:
        browser_name = BROWSER_MAP[cookie_source]
        command.extend(["--cookies-from-browser", browser_name])
    elif cookie_source == "Файл cookies (вручную)":
        cookies_path = os.path.join(work_dir, "www.youtube.com_cookies.txt")
        if not os.path.exists(cookies_path):
            return None, work_dir, (
                f"Ошибка: файл cookies не найден!\n"
                f"Ожидаемый путь: {cookies_path}\n"
                f"Поместите файл cookies в папку с программой или выберите браузер."
            )
        command.extend(["--cookies", cookies_path])

    command.append(url)
    return command, work_dir, None


def _detect_stage(line: str) -> str:
    """Определяет текущий этап по строке вывода yt-dlp."""
    lower = line.lower()
    if "extracting cookies" in lower or "[cookies]" in lower:
        return "🍪 Извлечение cookies"
    if "[download] destination" in lower:
        if "video" in lower or ".f" in lower:
            return "📥 Загрузка видео"
        if "audio" in lower:
            return "📥 Загрузка аудио"
        return "📥 Загрузка"
    if "[merger]" in lower or "merging formats" in lower:
        return "🔗 Объединение видео и аудио"
    if "[videoconvertor]" in lower or "converting video" in lower or "[ffmpeg]" in lower:
        return "⚙️ Перекодировка (NVENC)"
    if "deleting original file" in lower:
        return "🧹 Очистка временных файлов"
    if "has already been downloaded" in lower:
        return "✅ Файл уже был скачан ранее"
    return ""


def download_videos(urls_text: str, cookie_source: str, quality_mode: str):
    """Генератор — стримит вывод построчно в Gradio."""
    url_list = [line.strip() for line in urls_text.splitlines() if line.strip()]
    if not url_list:
        yield "Нет введённых URL."
        return

    mode_label = "⚡ 720p быстро" if quality_mode == QUALITY_FAST else "🎬 Лучшее качество"
    total = len(url_list)
    log_lines = [f"Режим: {mode_label}\n"]

    for idx, url in enumerate(url_list, 1):
        header = f"{'='*50}\n[{idx}/{total}] {url}\n{'='*50}"
        log_lines.append(header)
        yield "\n".join(log_lines)

        result = _build_command(url, cookie_source, quality_mode)
        command, work_dir, error = result
        if command is None:
            log_lines.append(error)
            yield "\n".join(log_lines)
            continue

        current_stage = ""
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=work_dir,
                bufsize=1,
            )

            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue

                # Определяем этап
                new_stage = _detect_stage(line)
                if new_stage and new_stage != current_stage:
                    current_stage = new_stage
                    log_lines.append(f"\n{current_stage}")
                    yield "\n".join(log_lines)

                # Строки прогресса ([download]  45.2% ...) обновляем на месте
                if "[download]" in line and "%" in line:
                    # Заменяем последнюю строку прогресса, если она есть
                    if log_lines and "[download]" in log_lines[-1] and "%" in log_lines[-1]:
                        log_lines[-1] = line
                    else:
                        log_lines.append(line)
                    yield "\n".join(log_lines)
                elif "[download] 100%" in line.lower():
                    log_lines.append(line)
                    yield "\n".join(log_lines)
                # Важные информационные строки
                elif any(kw in line.lower() for kw in [
                    "[merger]", "[ffmpeg]", "[videoconvertor]",
                    "destination", "already", "deleting", "error", "warning"
                ]):
                    log_lines.append(line)
                    yield "\n".join(log_lines)

            proc.wait()

            if proc.returncode == 0:
                log_lines.append(f"✅ Готово: {url}")
            else:
                error_msg = f"❌ Ошибка (код {proc.returncode}): {url}"
                log_lines.append(error_msg)
                if cookie_source in CHROMIUM_BROWSERS:
                    # Проверяем, была ли ошибка DPAPI
                    full_log = "\n".join(log_lines)
                    if "DPAPI" in full_log:
                        log_lines.append(DPAPI_HINT)

        except Exception as e:
            log_lines.append(f"❌ Исключение для {url}: {e}")

        log_lines.append("")
        yield "\n".join(log_lines)

    log_lines.append(f"\n{'='*50}\n🏁 Все задачи завершены ({total} видео)\n{'='*50}")
    yield "\n".join(log_lines)


with gr.Blocks(title="yt-dlp by fralid") as iface:
    gr.Markdown("# yt-dlp by fralid")
    gr.Markdown(
        "Cookies берутся автоматически из браузера — "
        "больше не нужно вручную обновлять файл!\n\n"
        "**Рекомендуется Firefox** — Chrome 127+ на Windows блокирует доступ к cookies (DPAPI)."
    )

    with gr.Row():
        cookie_dropdown = gr.Dropdown(
            choices=COOKIE_SOURCES,
            value="Firefox (рекомендуется)",
            label="Источник cookies",
            info="Firefox рекомендуется — у Chrome/Edge есть проблема с DPAPI на Windows",
        )
        quality_radio = gr.Radio(
            choices=QUALITY_MODES,
            value=QUALITY_BEST,
            label="Режим загрузки",
            info="Быстрый: 720p без перекодировки | Лучший: макс. качество + NVENC",
        )

    urls_input = gr.Textbox(
        label="Введите URL видео (по одному на строке)",
        lines=10,
        placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...",
    )

    download_btn = gr.Button("Скачать", variant="primary")
    output_text = gr.Textbox(label="Результат", lines=15, interactive=False)

    # Обработчик нажатия — кнопка блокируется на время загрузки
    def on_click_start():
        return gr.update(interactive=False, value="⏳ Загрузка...")

    def on_click_end():
        return gr.update(interactive=True, value="Скачать")

    click_event = download_btn.click(
        fn=on_click_start,
        outputs=download_btn,
    ).then(
        fn=download_videos,
        inputs=[urls_input, cookie_dropdown, quality_radio],
        outputs=output_text,
    ).then(
        fn=on_click_end,
        outputs=download_btn,
    )

if __name__ == "__main__":
    iface.launch(inbrowser=True)
    input("Сервер запущен. Нажмите Enter для завершения работы...")