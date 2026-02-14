@echo off
setlocal

:: === Настройка ===
:: Путь к исполняемому файлу yt-dlp
set "YTDLP_PATH=%~dp0yt-dlp.exe"
:: URL последней версии
set "YTDLP_LATEST_URL=https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp.exe"

:: === Проверка наличия yt-dlp.exe ===
if not exist "%YTDLP_PATH%" (
    echo yt-dlp.exe не найден в текущей папке: %~dp0
    echo Скачиваем новую версию...
) else (
    echo Найден yt-dlp: %YTDLP_PATH%
    echo Обновление yt-dlp до последней версии...
)

:: === Загрузка последней версии ===
curl -L "%YTDLP_LATEST_URL%" -o "%YTDLP_PATH%"
if errorlevel 1 (
    echo [Ошибка] Не удалось загрузить yt-dlp. Проверьте соединение с интернетом.
    exit /b 1
)

:: === Проверка обновления ===
echo Успешно обновлено до версии:
"%YTDLP_PATH%" --version

echo.
pause
endlocal