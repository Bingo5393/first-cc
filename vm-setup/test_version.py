# -*- coding: utf-8 -*-
# 诊断脚本：模拟 spy.dll 读取微信文件版本号的行为，判断 ARM64WOWONAMD64
# 兼容层到底破坏了哪个 API（GetModuleFileNameW 还是 GetFileVersionInfoW）。
#
# 用法：
#   直接运行        -> 无兼容层对照（应该能读到 3.9.12.56）
#   test_version.bat -> 设置 __COMPAT_LAYER 后运行（模拟微信进程的兼容层环境）

import os
import sys
import ctypes
from ctypes import wintypes

path = r"C:\Program Files (x86)\Tencent\WeChat\[3.9.12.56]\WeChatWin.dll"
print("=== 环境 ===")
print("__COMPAT_LAYER =", repr(os.environ.get("__COMPAT_LAYER", "(未设置)")))
print("目标文件:", path)
print("文件存在:", os.path.exists(path))
print()

# ---------- 方法 1：win32api（pywin32 封装） ----------
print("=== 方法1：win32api.GetFileVersionInfo ===")
try:
    import win32api
    info = win32api.GetFileVersionInfo(path, '\\')
    ms = info['FileVersionMS']
    ls = info['FileVersionLS']
    ver = "%d.%d.%d.%d" % (win32api.HIWORD(ms), win32api.LOWORD(ms),
                           win32api.HIWORD(ls), win32api.LOWORD(ls))
    print("FileVersion =", ver)
except Exception as e:
    print("读取失败:", repr(e))
print()

# ---------- 方法 2：ctypes 直接调 GetFileVersionInfoW（与 spy.dll 同款 API） ----------
print("=== 方法2：ctypes GetFileVersionInfoW（同 spy.dll） ===")
ver_dll = ctypes.WinDLL("version", use_last_error=True)

size = ver_dll.GetFileVersionInfoSizeW(path, None)
print("GetFileVersionInfoSizeW 返回:", size)
if size:
    buf = ctypes.create_string_buffer(size)
    ok = ver_dll.GetFileVersionInfoW(path, 0, size, buf)
    print("GetFileVersionInfoW 返回:", ok)
    if ok:
        p = ctypes.c_void_p()
        plen = wintypes.UINT()
        ok2 = ver_dll.VerQueryValueW(buf, "\\", ctypes.byref(p), ctypes.byref(plen))
        print("VerQueryValueW 返回:", ok2)
        if ok2:
            # 解析 VS_FIXEDFILEINFO 里的版本号
            import struct
            fixed = struct.unpack_from("13I", p.value)  # 读前 13 个 DWORD
            # dwFileVersionMS=第2个，dwFileVersionLS=第3个（索引1、2）
            ms = fixed[1]
            ls = fixed[2]
            ver = "%d.%d.%d.%d" % ((ms >> 16) & 0xFFFF, ms & 0xFFFF,
                                   (ls >> 16) & 0xFFFF, ls & 0xFFFF)
            print("解析出的 FileVersion =", ver)
print()

# ---------- 方法 3：模拟 GetModuleFileNameW 取模块路径 ----------
print("=== 方法3：GetModuleFileNameW 取当前进程模块路径 ===")
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
buf = ctypes.create_unicode_buffer(1024)
n = k32.GetModuleFileNameW(None, buf, 1024)
print("当前进程主模块路径:", buf.value if n else "(失败)")
print()
print("=== 结论 ===")
print("如果方法2在兼容层下读不到版本（size=0 或 ok=0），说明兼容层破坏 GetFileVersionInfoW。")
print("如果方法2正常但微信里 spy 仍失败，问题在 GetModuleFileNameW 返回的路径。")
