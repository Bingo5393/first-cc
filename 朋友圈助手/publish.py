# -*- coding: utf-8 -*-
# 朋友圈助手 —— 自动发「纯文字」朋友圈（华为分身微信专用）
#
# 背景：用户的营销号微信运行在华为「应用分身」（u128 空间）里，
# uiautomator2 的 dump_hierarchy / text 定位读不到分身空间的 UI，
# 因此本脚本改用「adb 坐标操作 + dumpsys 焦点检测」的方式控制。
#
# 用法：python publish.py "要发布的文案内容"
# 输出：单行 JSON —— {"ok": true} 或 {"ok": false, "error": "中文错误信息"}
#
# 依赖：uiautomator2（pip install uiautomator2 && python -m uiautomator2 init）

import sys
import time
import json

import uiautomator2 as u2

# ---------- 关键坐标（基于 1212x2616 分辨率、华为 nova12 + 微信分身） ----------
# 注意：这些坐标依赖屏幕分辨率和微信版本，微信升级后可能需要重新实测。
TAB_DISCOVER = (757, 2560)   # 底部「发现」tab
ENTRY_MOMENTS = (606, 560)   # 发现页「朋友圈」入口（取行中心，避免点偏）
CAMERA_ICON = (1150, 220)    # 朋友圈右上角相机图标（长按 = 发纯文字）
INPUT_BOX = (600, 500)       # 纯文字编辑页的输入框区域
PASTE_BTN = (250, 435)       # 长按输入框后「粘贴」菜单项
PUBLISH_BTN = (1140, 196)    # 编辑页右上角「发表」按钮
ALLOW_BTN = (902, 2055)      # 权限请求框的「允许」按钮

WECHAT_PKG = 'com.tencent.mm'
WECHAT_MAIN = 'com.tencent.mm/.ui.LauncherUI'
TWIN_USER = '128'            # 分身应用所在的用户空间


class PublishError(Exception):
    """业务错误：脚本会捕获并输出给调用方。"""


def sh(cmd):
    """执行一条 adb shell 命令，返回输出文本。"""
    return (d.shell(cmd).output or '')


def focus_text():
    """读取当前焦点窗口，用于判断所处页面。"""
    return sh('dumpsys window')


def is_chooser():
    """是否处于华为的权限/选择对话框（HwChooserActivity）。"""
    return 'HwChooserActivity' in focus_text()


def is_locked():
    """是否处于锁屏/熄屏显示状态。"""
    # 屏幕未点亮即视为锁屏
    try:
        if not d.info.get('screenOn'):
            return True
    except Exception:
        pass
    # 屏幕已亮，但锁屏界面仍在显示（isKeyguardShowing=true）
    return 'isKeyguardShowing=true' in focus_text()


def tap(x, y):
    d.shell('input tap {} {}'.format(int(x), int(y)))


def long_press(x, y, ms=1000):
    # 长按 = 起点与终点相同的 swipe
    d.shell('input swipe {} {} {} {} {}'.format(int(x), int(y), int(x), int(y), int(ms)))


def sleep(ms):
    time.sleep(ms / 1000.0)


def main(text):
    # ---------- 1. 唤醒屏幕并确认已解锁 ----------
    d.screen_on()
    sleep(1500)
    if is_locked():
        raise PublishError('手机处于锁屏状态，请先手动解锁并保持屏幕常亮（可开启开发者选项里的「充电时保持唤醒」）')

    # ---------- 2. 冷启动分身微信 ----------
    # force-stop 清掉微信页面栈，确保重启后落在主界面（否则可能停在「听一听」等全屏页）
    sh('am force-stop --user {u} {p}'.format(u=TWIN_USER, p=WECHAT_PKG))
    sleep(1500)
    sh('am start --user {u} -n {a}'.format(u=TWIN_USER, a=WECHAT_MAIN))
    sleep(4000)

    # ---------- 3. 处理启动后的权限请求框（存储 / 定位 / 电话等） ----------
    # 华为分身微信在 force-stop 后会重新弹权限框，需逐个点「允许」。
    # 用焦点检测判断是否有权限框，避免无框时盲点误触微信界面。
    for _ in range(8):
        if is_chooser():
            tap(*ALLOW_BTN)
            sleep(1500)
        else:
            break
    if is_chooser():
        raise PublishError('微信权限请求框未能自动关闭，请手动点「允许」后重试')
    # 等微信页面稳定（权限框关闭后可能有短暂过渡态）
    sleep(1500)
    # 检测落点：若停在「听一听」全屏页则明确提示（后续坐标导航依赖底部 tab 栏）
    if 'TingFlutterActivity' in focus_text():
        raise PublishError('微信停在了「听一听」页面，请手动退出到主界面（聊天列表）后重试')

    # ---------- 4. 写入剪贴板（uiautomator2 的剪贴板可跨分身空间读取） ----------
    d.set_clipboard(text)
    sleep(500)

    # ---------- 5. 导航：发现 → 朋友圈 → 长按相机进入纯文字编辑页 ----------
    tap(*TAB_DISCOVER)
    sleep(2200)
    tap(*ENTRY_MOMENTS)
    sleep(2600)
    long_press(*CAMERA_ICON, 1500)   # 长按相机 = 发纯文字（点按 = 发图文）
    sleep(2600)

    # ---------- 6. 点击输入框 → 长按弹出粘贴菜单 → 点「粘贴」 ----------
    tap(*INPUT_BOX)
    sleep(800)
    long_press(*INPUT_BOX, 800)
    sleep(1000)
    tap(*PASTE_BTN)
    sleep(1200)

    # ---------- 7. 点「发表」 ----------
    tap(*PUBLISH_BTN)
    sleep(3000)

    # 完成（如需更强校验可在此处截图比对，当前 MVP 不做）


if __name__ == '__main__':
    # 自动连接当前 ADB 设备（无多设备时无需写死 serial）
    d = u2.connect()
    text = sys.argv[1] if len(sys.argv) > 1 else ''
    if not text.strip():
        print(json.dumps({'ok': False, 'error': '文案内容不能为空'}, ensure_ascii=False))
        sys.exit(0)
    try:
        main(text)
        print(json.dumps({'ok': True}, ensure_ascii=False))
    except PublishError as e:
        print(json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({'ok': False, 'error': '发布失败：{}'.format(e)}, ensure_ascii=False))
