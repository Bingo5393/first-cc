# -*- coding: utf-8 -*-
"""
桌面实时翻译助手
==================
功能说明：
    1. 后台监控剪贴板：使用 Ctrl+C 复制英文文本后，程序自动检测到。
    2. 自动弹窗显示：在屏幕右下角弹出置顶、半透明的悬浮窗，显示翻译好的中文，
       显示 5 秒后自动淡出消失。
    3. 翻译接口：使用免费、无需密钥的 MyMemory 翻译接口（mt=1 启用机器翻译）。
    4. 操作简单：双击本文件即可后台运行，系统托盘提供「翻译历史」「暂停监控」「退出」按钮。

依赖安装（首次使用前执行一次）：
    pip install requests pyperclip pystray Pillow

提示：
    若想去掉运行时的黑色控制台窗口，可将本文件改名为 translator.pyw，
    或使用命令：pythonw translator.py
"""

import queue
import re
import sys
import threading
import time
import tkinter as tk

import pyperclip
import pystray
import requests
from PIL import Image, ImageDraw

# ---------------- 全局配置 ----------------
CHECK_INTERVAL_MS = 500       # 剪贴板轮询间隔（毫秒）
POPUP_SHOW_MS = 5000          # 悬浮窗显示时长（毫秒）
FADE_STEP_MS = 30             # 淡出动画每步间隔（毫秒）
FADE_ALPHA_STEP = 0.05        # 淡出动画每步透明度递减量
POPUP_ALPHA = 0.88            # 悬浮窗初始透明度（0 ~ 1）
POPUP_MAX_WIDTH = 900         # 悬浮窗最大宽度（像素，随字号放大）
HISTORY_MAX = 200             # 翻译历史最多保留条数

# 退出标志：托盘点击「退出」后置位，主循环检测到后退出
exit_event = threading.Event()

# 暂停标志：置位表示暂停监控，此时复制文本不再翻译
paused = threading.Event()

# 线程安全的队列：翻译线程把结果放入，主线程取出后更新界面
result_queue = queue.Queue()

# 线程安全的队列：用于把「打开历史窗口」等界面操作投递给主线程
ui_queue = queue.Queue()

# 翻译历史列表，每项为 (时间, 原文, 译文)，仅主线程读写
history = []

# 历史窗口及其文本控件的引用（单例，避免重复打开）
history_window = None
history_text = None

# 记录上一次剪贴板文本，用于去重
last_text = ""

# 当前正在显示的悬浮窗列表（用于多个弹窗上下堆叠，避免互相遮挡）
active_popups = []

# MyMemory 免费翻译接口地址
MYMEMORY_URL = "https://api.mymemory.translated.net/get"


def translate(text):
    """调用 MyMemory 免费接口（mt=1 启用机器翻译），把英文翻译成中文。"""
    resp = requests.get(
        MYMEMORY_URL,
        params={"q": text, "langpair": "en|zh-CN", "mt": "1"},
        timeout=15,
    )
    if resp.status_code == 429:
        raise RuntimeError("翻译请求过于频繁，请稍后再试")
    if resp.status_code != 200:
        raise RuntimeError(f"翻译接口返回错误状态码 {resp.status_code}")

    data = resp.json()
    translated = (data.get("responseData", {}).get("translatedText") or "").strip()
    # 去除结果中可能夹带的 HTML 标签
    translated = re.sub(r"<[^>]+>", "", translated).strip()

    if translated and translated != text.strip():
        return translated

    # 若 translatedText 无效（为空或原样返回原文），从翻译记忆 matches 里取候选
    for m in data.get("matches", []):
        candidate = re.sub(r"<[^>]+>", "", (m.get("translation") or "")).strip()
        if candidate and candidate != text.strip():
            return candidate

    raise RuntimeError("未获取到有效的翻译结果")


def log(msg):
    """打印中文日志，方便在控制台观察运行状态。

    注意：使用 pythonw（无控制台）运行时 sys.stdout 为 None，
    直接 print 会抛异常导致程序崩溃，因此先做判断。
    """
    if sys.stdout is None:
        return
    print(f"[翻译助手] {msg}")


def should_translate(text):
    """
    判断文本是否需要翻译。
    规则：非空、长度合理、包含英文字母、且中文字符占比不超过英文字母。
    """
    t = (text or "").strip()
    if not t:
        return False
    if len(t) > 3000:
        return False                          # 过长文本（大段复制）跳过，避免请求超时
    if not re.search(r"[A-Za-z]", t):
        return False                          # 不含英文字母，无需翻译
    cn_count = len(re.findall(r"[一-鿿]", t))
    en_count = len(re.findall(r"[A-Za-z]", t))
    if cn_count > en_count:
        return False                          # 中文占多数，跳过
    return True


def create_tray_image():
    """生成系统托盘图标（蓝色背景 + 白色圆形，避免依赖外部图片文件）。"""
    img = Image.new("RGB", (64, 64), "#2563eb")
    draw = ImageDraw.Draw(img)
    draw.ellipse((10, 10, 54, 54), fill="#ffffff")
    return img


def on_exit(icon, item):
    """托盘「退出」按钮的回调：停止图标并通知主循环退出。"""
    log("用户点击退出，程序即将关闭")
    exit_event.set()
    icon.stop()


def on_toggle_pause(icon, item):
    """托盘「暂停/恢复监控」按钮的回调：切换暂停状态并更新菜单文字。"""
    if paused.is_set():
        paused.clear()
        log("监控已恢复，复制英文文本将继续翻译")
    else:
        paused.set()
        log("监控已暂停，复制文本将不再翻译")
    # 同步更新菜单项文字，反映当前状态
    item.text = "恢复监控" if paused.is_set() else "暂停监控"
    try:
        icon.update_menu()
    except Exception as exc:
        log(f"更新托盘菜单失败：{exc}")


def on_show_history(icon, item):
    """托盘「翻译历史」按钮的回调：请求主线程打开历史窗口。"""
    ui_queue.put("show_history")


def show_popup(root, text):
    """在屏幕右下角显示一个置顶、半透明的悬浮窗。"""
    win = tk.Toplevel(root)
    win.overrideredirect(True)                 # 去掉系统边框，只显示内容
    win.attributes("-topmost", True)           # 置顶显示
    try:
        win.attributes("-alpha", POPUP_ALPHA)  # 设置半透明（部分平台可能不支持）
    except tk.TclError:
        pass

    # 文本标签：白色背景 + 黑色文字，字号放大 3 倍，超宽自动换行
    label = tk.Label(
        win,
        text=text,
        bg="#ffffff",
        fg="#000000",
        font=("Microsoft YaHei", 33),
        wraplength=POPUP_MAX_WIDTH - 40,
        justify="left",
        padx=20,
        pady=16,
    )
    label.pack()

    # 计算位置：右下角，并根据已有弹窗数量向上偏移，避免重叠
    win.update_idletasks()
    w = win.winfo_width()
    h = win.winfo_height()
    offset = sum(p.winfo_height() + 12 for p in active_popups if p.winfo_exists())
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = sw - w - 20
    y = sh - h - 20 - offset
    win.geometry(f"+{x}+{y}")

    active_popups.append(win)
    # 显示时长结束后开始淡出
    win.after(POPUP_SHOW_MS, lambda: fade_out(win, POPUP_ALPHA))


def fade_out(win, alpha):
    """逐帧降低悬浮窗透明度，实现淡出效果，最后销毁窗口。"""
    if not win.winfo_exists():
        return
    alpha -= FADE_ALPHA_STEP
    if alpha <= 0:
        destroy_popup(win)
        return
    try:
        win.attributes("-alpha", alpha)
    except tk.TclError:
        return
    win.after(FADE_STEP_MS, lambda: fade_out(win, alpha))


def destroy_popup(win):
    """销毁悬浮窗并从活动列表移除。"""
    if win in active_popups:
        active_popups.remove(win)
    try:
        win.destroy()
    except tk.TclError:
        pass


def translate_and_show(text):
    """后台线程执行翻译，成功后把结果放入队列，由主线程显示。"""
    try:
        result = translate(text)
        if not result:
            raise RuntimeError("翻译结果为空")
        log(f"翻译完成：{result[:40]}...")
    except Exception as exc:
        log(f"翻译失败：{exc}")                # 失败仅记录日志，不弹窗打扰
        return
    result_queue.put((text, result))


def drain_result_queue(root):
    """把队列中的翻译结果取出，记录历史并在主线程中显示悬浮窗。"""
    try:
        while True:
            source, result = result_queue.get_nowait()
            append_history(source, result)
            show_popup(root, result)
    except queue.Empty:
        pass


def drain_ui_queue(root):
    """把队列中的界面操作取出并执行（目前仅用于打开历史窗口）。"""
    try:
        while True:
            action = ui_queue.get_nowait()
            if action == "show_history":
                show_history_window(root)
    except queue.Empty:
        pass


def append_history(source, result):
    """把一条翻译记录追加到历史列表，并刷新历史窗口。"""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    history.append((stamp, source, result))
    # 限制历史条数，防止无限增长占用内存
    if len(history) > HISTORY_MAX:
        del history[: len(history) - HISTORY_MAX]
    refresh_history_view()


def clear_history():
    """清空翻译历史并刷新历史窗口。"""
    history.clear()
    refresh_history_view()
    log("翻译历史已清空")


def refresh_history_view():
    """刷新历史窗口的文本内容（若窗口已打开）。"""
    global history_text
    if history_text is None:
        return
    if not history:
        content = "（暂无翻译历史）"
    else:
        lines = []
        # 最新的记录显示在最上面
        for stamp, source, result in reversed(history):
            lines.append(f"[{stamp}] {source}")
            lines.append(f"    → {result}")
            lines.append("-" * 44)
        content = "\n".join(lines)
    history_text.config(state="normal")
    history_text.delete("1.0", "end")
    history_text.insert("1.0", content)
    history_text.config(state="disabled")


def close_history_window(win):
    """关闭历史窗口并清空相关引用。"""
    global history_window, history_text
    try:
        win.destroy()
    except tk.TclError:
        pass
    history_window = None
    history_text = None


def show_history_window(root):
    """打开（或前置）翻译历史窗口。"""
    global history_window, history_text
    # 若窗口已存在，直接前置并刷新，避免重复打开
    if history_window is not None and history_window.winfo_exists():
        history_window.deiconify()
        history_window.lift()
        refresh_history_view()
        return

    win = tk.Toplevel(root)
    win.title("翻译历史")
    win.geometry("460x380")
    history_window = win

    # 顶部操作栏：标题 + 清空按钮
    bar = tk.Frame(win)
    bar.pack(fill="x", padx=10, pady=(10, 6))
    tk.Label(bar, text="翻译历史", font=("Microsoft YaHei", 12, "bold")).pack(side="left")
    tk.Button(bar, text="清空历史", command=clear_history).pack(side="right")

    # 带滚动条的只读文本框，用于展示历史记录
    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    scroll = tk.Scrollbar(frame)
    scroll.pack(side="right", fill="y")
    text_widget = tk.Text(
        frame,
        wrap="word",
        font=("Microsoft YaHei", 10),
        yscrollcommand=scroll.set,
        state="disabled",
    )
    text_widget.pack(side="left", fill="both", expand=True)
    scroll.config(command=text_widget.yview)
    history_text = text_widget

    refresh_history_view()

    # 关闭窗口时清空引用
    win.protocol("WM_DELETE_WINDOW", lambda: close_history_window(win))


def check_clipboard(root):
    """周期性检查剪贴板，发现新的英文文本则启动翻译线程。"""
    global last_text

    # 先处理待执行的界面操作和已完成的翻译结果
    drain_ui_queue(root)
    drain_result_queue(root)

    try:
        text = pyperclip.paste()
    except Exception as exc:
        log(f"读取剪贴板失败：{exc}")
        text = None

    if not paused.is_set() and text and text != last_text and should_translate(text):
        last_text = text
        log(f"检测到英文文本，开始翻译：{text[:40]}...")
        threading.Thread(target=translate_and_show, args=(text,), daemon=True).start()

    # 检测到退出标志则结束主循环
    if exit_event.is_set():
        root.quit()
        return

    root.after(CHECK_INTERVAL_MS, lambda: check_clipboard(root))


def main():
    """程序入口：创建主窗口、启动托盘线程与剪贴板轮询。"""
    # 创建并隐藏主窗口（仅用于承载主循环）
    root = tk.Tk()
    root.withdraw()

    # 启动系统托盘（在独立线程中运行，避免阻塞主循环）
    icon = pystray.Icon(
        "translator",
        create_tray_image(),
        "实时翻译助手",
        menu=pystray.Menu(
            pystray.MenuItem("翻译历史", on_show_history),
            pystray.MenuItem("暂停监控", on_toggle_pause),
            pystray.MenuItem("退出", on_exit),
        ),
    )
    threading.Thread(target=icon.run, daemon=True).start()

    log("实时翻译助手已启动，复制英文文本即可自动翻译")
    log("在系统托盘图标上点击右键，选择「退出」即可关闭")

    # 开始剪贴板轮询，并进入 tkinter 主循环
    root.after(0, lambda: check_clipboard(root))
    root.mainloop()


if __name__ == "__main__":
    main()
