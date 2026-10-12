@echo off
chcp 65001 >nul
rem llama-cpp-monitor 生产一键启动（issue #23，spec #22）
rem 编码约定：本文件保持 UTF-8 无 BOM，靠第 2 行 chcp 65001 对齐控制台代码页。
rem 勿存为 GBK（与仓库其他 UTF-8 文件不一致，编辑器一保存就复发乱码）。

rem ---------- 参数：--build 强制重建前端 ----------
set FORCE_BUILD=0
if /i "%~1"=="--build" set FORCE_BUILD=1

rem ---------- conda 环境 ----------
call conda activate llamacpp-monitor
if errorlevel 1 (
    echo [错误] conda 环境 llamacpp-monitor 激活失败，请确认已安装 conda 且该环境存在。
    exit /b 1
)

rem ---------- node/npm 自检 ----------
where node >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 node，请先安装 Node.js 并加入 PATH。
    exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 npm，请先安装 Node.js 并加入 PATH。
    exit /b 1
)

rem ---------- 前端依赖 ----------
if not exist "frontend\node_modules" (
    echo [提示] frontend\node_modules 缺失，执行 npm install ...
    pushd frontend
    call npm install
    if errorlevel 1 (
        popd
        echo [错误] npm install 失败，请检查网络或 npm 源。
        exit /b 1
    )
    popd
)

rem ---------- 前端构建（dist 缺失或 --build 时构建） ----------
if "%FORCE_BUILD%"=="1" goto :do_build
if exist "frontend\dist\index.html" goto :skip_build
:do_build
echo [提示] 构建前端（vue-tsc + vite build）...
pushd frontend
call npm run build
if errorlevel 1 (
    popd
    echo [错误] 前端构建失败，不启动后端（避免带旧 dist 运行）。
    exit /b 1
)
popd
:skip_build
echo [提示] frontend\dist 已存在，跳过构建（start.bat --build 可强制重建）。

rem ---------- 端口占用检测 ----------
netstat -ano | findstr :5000 >nul
if not errorlevel 1 (
    echo [错误] 端口 5000 已被占用，请先关闭上次的启动窗口。
    exit /b 1
)

rem ---------- 启动后端（前台单窗口，关窗即停；--reload 仅监听 backend/） ----------
echo [启动] uvicorn backend.main:app --host 127.0.0.1 --port 5000 --reload --reload-dir backend
uvicorn backend.main:app --host 127.0.0.1 --port 5000 --reload --reload-dir backend
