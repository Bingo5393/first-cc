@echo off
rem 微信 3.9.12.56 32位 兼容性启动（绕过"版本过低"登录限制）
rem 请把下面的路径改成你的微信实际安装路径
set "__COMPAT_LAYER=~ ARM64WOWONAMD64"
start "" "C:\Program Files (x86)\Tencent\WeChat\WeChat.exe"
