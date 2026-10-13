@echo off
chcp 65001 >nul
rem llama-cpp-monitor 生产一键启动（issue #23，spec #22）
rem 编码约定：本文件保持 UTF-8 无 BOM，靠第 2 行 chcp 65001 对齐控制台代码页。
rem 行尾约定：本文件必须为 CRLF（Windows 批处理硬性要求；LF 会被 cmd 误读成碎命令，
rem           表现为 'rlevel'/'墠鍙板崟绐楀彛' 之类的乱码报错，且 conda activate 行会被破坏）。
rem           编辑器保存时勿转成 LF。勿存为 GBK（与仓库其他 UTF-8 文件不一致）。

rem ---------- 参数：--build 强制重建前端 ----------
set FORCE_BUILD=0
if /i "%~1"=="--build" set FORCE_BUILD=1

rem ---------- Python 环境（不依赖 conda activate，直接指向 env 的 Scripts，避免落到系统 Python） ----------
set "PYENV=H:\conda_envs\llamacpp-monitor"
if not exist "%PYENV%\Scripts\uvicorn.exe" (
    echo [错误] 未找到 conda 环境 llamacpp-monitor（%PYENV%），请先创建该环境并安装 requirements.txt。
    exit /b 1
)
set "PATH=%PYENV%\Scripts;%PYENV%;%PATH%"

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

rem ---------- 启动后端（前台单进程，关窗即停、端口随进程释放） ----------
rem 不加 --reload：reload 会另起一个 worker 子进程真正占住 5000，关窗只杀前台父进程，
rem worker 残留成孤儿导致端口释放不掉。开发期要热重载，请另开窗口手动跑：
rem   uvicorn backend.main:app --host 127.0.0.1 --port 5000 --reload --reload-dir backend
echo [启动] uvicorn backend.main:app --host 127.0.0.1 --port 5000
uvicorn backend.main:app --host 127.0.0.1 --port 5000
