# 当前系统直装微信 3.9.x 脚本 —— 卸载 4.x、装 3.9.x、关自动更新、装 Python 依赖
#
# 在你当前这台电脑上运行（不需要虚拟机）。
#
# 用法（以管理员身份运行 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File .\setup_wechat.ps1 -WeChatInstaller "F:\iso\WeChatSetup-3.9.12.56.exe"
#
# 参数：
#   -WeChatInstaller  微信 3.9.12.56 安装包完整路径（可选；不传则跳过自动安装）

param(
    [string]$WeChatInstaller = ''
)

$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string]$m)
    Write-Host "`n===== $m =====" -ForegroundColor Cyan
}

# ---------- 1. 检查管理员权限 ----------
Write-Step '检查管理员权限'
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host '错误：请以管理员身份运行 PowerShell。' -ForegroundColor Red
    exit 1
}

# ---------- 2. 检测当前微信版本 ----------
Write-Step '检测当前微信版本'
$ver = $null
foreach ($p in @(
        'C:\Program Files (x86)\Tencent\Weixin\Weixin.exe',
        'C:\Program Files (x86)\Tencent\WeChat\WeChat.exe',
        'C:\Program Files\Tencent\Weixin\Weixin.exe',
        'C:\Program Files\Tencent\WeChat\WeChat.exe'
    )) {
    if (Test-Path $p) {
        $ver = (Get-Item $p).VersionInfo.ProductVersion
        Write-Host "检测到微信：$p  版本 $ver"
        break
    }
}

if ($ver -and $ver -match '^4\.') {
    Write-Host '当前是微信 4.x，与 WeChatFerry 不兼容，必须先卸载。' -ForegroundColor Yellow
    Write-Host '请手动卸载：设置 → 应用 → 已安装的应用 → 找到「微信」→ 卸载。'
    Write-Host '（卸载时选「保留聊天记录」也无妨，但 3.9.x 大概率读不了 4.x 的本地记录）'
    Read-Host '卸载完成后按回车继续…'
} elseif ($ver -and $ver -match '^3\.9\.') {
    Write-Host '当前已是微信 3.9.x，无需卸载。'
} else {
    Write-Host '未检测到已安装的微信。'
}

# ---------- 3. 安装微信 3.9.x ----------
Write-Step '安装微信 3.9.x'
if ($WeChatInstaller -and (Test-Path $WeChatInstaller)) {
    Write-Host "正在静默安装：$WeChatInstaller"
    Start-Process -FilePath $WeChatInstaller -ArgumentList '/S' -Wait
    Write-Host '微信安装完成。'
} else {
    Write-Host '未提供安装包（-WeChatInstaller 参数），跳过。请手动双击安装包完成安装。' -ForegroundColor Yellow
}

# ---------- 4. 关闭自动更新 + 扫码登录（关键，手动） ----------
Write-Step '关闭自动更新 + 扫码登录（需手动）'
Write-Host '请完成以下操作：'
Write-Host '  1) 启动微信，扫码登录你的营销号'
Write-Host '  2) 左下角「设置」→「通用设置」→ 取消勾选「有更新时自动升级」'
Write-Host '  3) 顺便取消「开机时自动启动微信」'
Write-Host '  4) 登录后从右下角托盘退出微信（确保 hook 前是干净状态）'
Read-Host '完成后按回车继续…'

# ---------- 5. 安装 Python 依赖 ----------
Write-Step '安装 Python 依赖'
python -m pip install --upgrade pip
python -m pip install pywinauto pywin32 loguru schedule PyYAML requests Pillow

# ---------- 6. 验证 ----------
Write-Step '验证环境'
python -c "import wcferry; print('wcferry 版本：', wcferry.__version__)"
python -c "import pywinauto, win32api; print('pywinauto / pywin32 已就绪')"

Write-Host "`n环境搭建完成！" -ForegroundColor Green
Write-Host '下一步：cd 到「朋友圈转发助手」目录，先跑 python tools/dump_pyq.py 做真机校准。'
