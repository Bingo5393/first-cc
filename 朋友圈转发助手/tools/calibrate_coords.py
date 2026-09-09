# -*- coding: utf-8 -*-
# 发圈坐标校准工具
#
# 用途：在真机上确定 PC 微信「发朋友圈」各步骤的点击坐标（相对微信主窗口
#       客户区左上角），生成 config.yaml 的 publish_coords 配置。
#
# 依赖：pywin32（发布朋友圈也依赖它）。未安装时：pip install pywin32
#
# 用法：
#   python tools/calibrate_coords.py
#
# 流程：
#   1. 先把微信主窗口调整到你「实际运行时」的大小（建议最大化或固定尺寸）；
#   2. 程序逐点提示「把鼠标移到 XX 中心，按 F8 记录」；
#   3. 全部记录完后输出可直接粘贴进 config.yaml 的 YAML 片段。
#
# 说明：用 F8 全局按键记录，你全程不用把鼠标移回终端窗口。

import os
import sys
import time

# 让 tools/ 下的脚本能 import 到项目根目录的 src 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

from src import logger as logger_mod

# 需要校准的坐标点（顺序与 config.yaml 的 publish_coords 一致）
POINTS = [
    ('moments_entry', '左侧导航栏「朋友圈」图标'),
    ('camera', '朋友圈页右上角「相机」图标（发图文）'),
    ('add_image', '发圈窗口「添加图片」区域（点开后选图）'),
    ('text_input', '发圈窗口的文字输入框'),
    ('publish_btn', '「发表」按钮'),
]

# 记录键：F8 的虚拟键码
VK_RECORD = 0x77


def find_wx_window():
    """定位微信主窗口，返回 (hwnd, 客户区宽, 客户区高)。失败返回 (0, 0, 0)。"""
    try:
        import win32gui
    except ImportError:
        logger.error('未安装 pywin32，请先执行：pip install pywin32')
        return 0, 0, 0

    # 微信主窗口类名（旧版 3.9）；标题以「微信」开头（可能带未读数，如「微信(3)」）
    hwnd = win32gui.FindWindow('WeChatMainWndForPC', None)
    if hwnd:
        rect = win32gui.GetClientRect(hwnd)
        return hwnd, rect[2], rect[3]

    # 兜底：枚举所有顶层窗口，找标题以「微信」开头的
    candidates = []

    def _cb(h, _):
        try:
            if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h).startswith('微信'):
                candidates.append(h)
        except Exception:
            pass

    win32gui.EnumWindows(_cb, None)
    if candidates:
        hwnd = candidates[0]
        rect = win32gui.GetClientRect(hwnd)
        return hwnd, rect[2], rect[3]

    logger.error('未找到微信主窗口，请确认 PC 微信已启动')
    return 0, 0, 0


def wait_for_key(win32api, vk):
    """轮询等待某个虚拟键被「按下再松开」一次（检测完整一次击键沿）。"""
    # 等待按键处于释放状态（避免上一次残留）
    while win32api.GetAsyncKeyState(vk) & 0x8000:
        time.sleep(0.05)
    # 等待按下
    while not (win32api.GetAsyncKeyState(vk) & 0x8000):
        time.sleep(0.05)
    # 等待松开
    while win32api.GetAsyncKeyState(vk) & 0x8000:
        time.sleep(0.05)


def main():
    logger_mod.setup_logger()

    hwnd, w, h = find_wx_window()
    if not hwnd:
        sys.exit(1)

    try:
        import win32api
        import win32gui
    except ImportError:
        logger.error('未安装 pywin32，请先执行：pip install pywin32')
        sys.exit(1)

    # 客户区左上角的屏幕坐标（后续坐标以它为原点）
    ox, oy = win32gui.ClientToScreen(hwnd, (0, 0))
    logger.info(f'已定位微信主窗口，客户区尺寸 = {w} x {h}（坐标都相对客户区左上角）')
    logger.info('提示：请保持窗口大小不变，把鼠标移到目标点后按 F8 记录。')

    coords = {}
    for key, desc in POINTS:
        logger.info(f'请把鼠标移到【{desc}】的中心，然后按 F8 …')
        wait_for_key(win32api, VK_RECORD)
        x, y = win32api.GetCursorPos()
        rx, ry = x - ox, y - oy
        # 越界提示
        if rx < 0 or ry < 0 or rx > w or ry > h:
            logger.warning(f'  该点 ({rx}, {ry}) 落在客户区 ({w}x{h}) 之外，请确认窗口未被遮挡或移动')
        coords[key] = [rx, ry]
        logger.info(f'  已记录 {key} = [{rx}, {ry}]')
        time.sleep(0.2)

    # 输出 YAML 片段
    print('\n' + '=' * 52)
    print('请把下面这段粘贴进 config.yaml 的 publish_coords：')
    print('=' * 52)
    print('publish_coords:')
    for key, _ in POINTS:
        print(f'  {key}: {coords[key]}')
    print('=' * 52)


if __name__ == '__main__':
    main()
