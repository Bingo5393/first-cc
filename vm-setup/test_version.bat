@echo off
rem 在 ARM64WOWONAMD64 兼容层下运行诊断脚本，模拟微信进程的兼容层环境
set "__COMPAT_LAYER=~ ARM64WOWONAMD64"
python E:\first-cc\vm-setup\test_version.py
pause
