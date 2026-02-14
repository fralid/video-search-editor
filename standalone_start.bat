@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

title Video Search ^& Editor - Standalone

echo ==================================================
echo   Video Search ^& Editor (Standalone)
echo ==================================================
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден!
    echo Скачайте Python 3.10+ с https://python.org
    pause
    exit /b 1
)

REM Проверка Node.js
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js не найден!
    echo Скачайте Node.js LTS с https://nodejs.org
    pause
    exit /b 1
)

REM Проверка npm
where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm не найден!
    pause
    exit /b 1
)

echo [OK] Python и Node.js найдены
echo.

REM Установка npm зависимостей если нужно
if not exist "frontend\node_modules" (
    echo Установка зависимостей frontend...
    cd frontend
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed
        pause
        exit /b 1
    )
    cd ..
    echo [OK] Зависимости установлены
    echo.
)

REM Очистка старых процессов (если есть)
echo Проверка портов...
netstat -ano | findstr ":8000" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Порт 8000 занят. Останавливаю старый процесс...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do taskkill /F /PID %%a >nul 2>&1
    timeout /t 2 /nobreak >nul
)

netstat -ano | findstr ":5173" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Порт 5173 занят. Останавливаю старый процесс...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173"') do taskkill /F /PID %%a >nul 2>&1
    timeout /t 2 /nobreak >nul
)

echo.

REM Запуск Backend (в фоне, без проверки кода возврата start)
echo [1/2] Запуск Backend (FastAPI)...
start "Backend - Video Search" /MIN cmd /k "python standalone_app.py"
timeout /t 3 /nobreak >nul

REM Ждём пока backend стартанёт (проверяем порт 8000)
echo Ожидание готовности backend (до 60 секунд)...
set BACKEND_READY=0
for /L %%i in (1,1,60) do (
    timeout /t 1 /nobreak >nul
    
    REM Проверяем порт
    netstat -ano | findstr ":8000" >nul 2>&1
    if not errorlevel 1 (
        REM Порт открыт, даём ещё секунду на инициализацию
        timeout /t 2 /nobreak >nul
        set BACKEND_READY=1
        goto :backend_ready
    )
    if %%i==10 echo   Жду... (попытка %%i/60)
    if %%i==30 echo   Жду... (попытка %%i/60)
)

:backend_ready
if %BACKEND_READY%==0 (
    echo [ERROR] Backend не запустился за 60 секунд
    echo Проверьте окно "Backend - Video Search" для ошибок
    pause
    exit /b 1
)
echo [OK] Backend готов на http://127.0.0.1:8000
echo.

REM Запуск Frontend
echo [2/2] Запуск Frontend (Vite)...
cd frontend
start "Frontend - Video Search" /MIN cmd /k "npm run dev"
cd ..
timeout /t 3 /nobreak >nul

REM Ждём пока frontend стартанёт (проверяем порт 5173)
echo Ожидание готовности frontend...
set FRONTEND_READY=0
for /L %%i in (1,1,60) do (
    timeout /t 1 /nobreak >nul
    netstat -ano | findstr ":5173" >nul 2>&1
    if not errorlevel 1 (
        set FRONTEND_READY=1
        goto :frontend_ready
    )
    echo   Попытка %%i/60... порт не открыт
)

:frontend_ready
if %FRONTEND_READY%==0 (
    echo [WARNING] Frontend не запустился за 60 секунд
    echo Проверьте окно "Frontend - Video Search" для ошибок
    echo Может быть другой порт (Vite автоматически выбирает свободный)
) else (
    echo [OK] Frontend готов на http://localhost:5173
)

echo.
echo ==================================================
echo   Приложение запущено!
echo ==================================================
echo   Backend:  http://127.0.0.1:8000 (Local)
echo   Frontend: http://localhost:5173 (Local) / http://IP-ADDRESS:5173 (Network)
echo ==================================================
echo.

REM Открываем браузер
timeout /t 2 /nobreak >nul
start http://localhost:5173

echo Окна Backend и Frontend запущены в фоне.
echo Для остановки закройте их или нажмите Ctrl+C здесь.
echo.
pause
