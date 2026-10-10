@echo off
rem llama-cpp-monitor 后端一键启动（T9，ADR 端口约定：后端 5000）
rem conda 环境：llamacpp-monitor
call conda activate llamacpp-monitor
uvicorn backend.main:app --host 127.0.0.1 --port 5000
