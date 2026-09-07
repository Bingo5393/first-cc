# -*- coding: utf-8 -*-
# WeChatFerry 客户端封装 + PC 微信 UI 自动化发布
#
# 职责：
#   1. 封装 WeChatFerry（Wcf），提供登录检测、好友列表、朋友圈获取、媒体下载；
#   2. 封装 PC 微信「发朋友圈」的 UI 自动化（因为 WeChatFerry 无发布朋友圈接口）。

import time

from loguru import logger

from wcferry import Wcf


# ---------- PC 微信发朋友圈：窗口标题 / 坐标 ----------
# 说明：PC 微信是 Duilib 自绘 UI，pywinauto 通常只能定位到主窗口，
# 内部控件需靠「相对主窗口左上角的坐标」点击。以下坐标是占位值，
# TODO: 需在真机上实测校准（微信 3.9.x 默认窗口大小）。
WX_WINDOW_TITLE = '微信'            # 主窗口标题（用于定位窗口）

# 坐标统一为 (x, y)，相对微信主窗口客户区左上角
PYQ_ENTRY = (66, 122)       # 左侧导航栏「朋友圈」图标
PYQ_CAMERA = (906, 56)      # 朋友圈页右上角「相机」图标（点击 = 发图文）
PYQ_ADD_IMG = (120, 160)    # 发朋友圈窗口「添加图片」区域（点 + 加图）
PYQ_TEXT_INPUT = (520, 420) # 文字输入框
PYQ_PUBLISH_BTN = (860, 600)  # 「发表」按钮


class WxClient:
    """封装 WeChatFerry，提供朋友圈转发所需的高层接口。"""

    def __init__(self, host='127.0.0.1', port=10086):
        self.host = host
        self.port = port
        # 初始化 WeChatFerry 客户端（会注入/连接 wcf 服务）
        self.wcf = Wcf(host=host, port=port)

    # ---------- 连接 / 登录 ----------
    def login_check(self):
        """检测微信是否在线。"""
        try:
            return bool(self.wcf.is_login())
        except Exception as e:
            logger.error(f'检测登录状态失败：{e}')
            return False

    def get_self_wxid(self):
        """获取当前登录的微信 wxid。"""
        return self.wcf.get_self_wxid()

    # ---------- 好友 ----------
    def get_friends_list(self):
        """获取好友列表（返回 RpcContact 对象列表，含 wxid/name/remark 等）。"""
        return self.wcf.get_contacts()

    # ---------- 朋友圈获取 ----------
    def enable_moments_receiving(self):
        """开启朋友圈消息接收（pyq=True）。"""
        return self.wcf.enable_receiving_msg(pyq=True)

    def refresh_moments(self):
        """触发刷新朋友圈，返回状态码（1 成功）。"""
        return self.wcf.refresh_pyq()

    def fetch_pending_msgs(self):
        """非阻塞地取出当前积压的微信消息（含朋友圈消息）。"""
        msgs = []
        try:
            while self.wcf.is_receiving_msg():
                msg = self.wcf.get_msg(block=False)
                if msg is None:
                    break
                msgs.append(msg)
        except Exception as e:
            logger.warning(f'读取消息队列异常：{e}')
        return msgs

    # ---------- 媒体下载 ----------
    def download_image(self, msg_id, extra, save_dir):
        """下载朋友圈图片，返回本地路径（失败返回空串）。"""
        return self.wcf.download_image(msg_id, extra, save_dir)

    def download_video(self, msg_id, thumb, save_dir):
        """下载朋友圈视频，返回本地路径（失败返回空串）。"""
        return self.wcf.download_video(msg_id, thumb, save_dir)

    # ---------- 心跳 / 保活（Phase 6） ----------
    def keep_alive(self):
        """心跳检测：返回当前是否仍在线。"""
        return self.login_check()

    # ---------- 发布朋友圈（PC UI 自动化，Phase 4） ----------
    def publish_moment(self, text, media_paths):
        """通过 PC 微信 UI 自动化发布朋友圈。

        返回 (ok: bool, err_msg: str)。
        因微信是自绘 UI，采用「定位主窗口 + 相对坐标点击」方案。
        """
        try:
            import pywinauto
        except ImportError:
            return False, '未安装 pywinauto，请执行：pip install pywinauto'

        try:
            # 1. 定位并激活微信主窗口
            app = pywinauto.Application(backend='win32').connect(title=WX_WINDOW_TITLE)
            win = app.window(title=WX_WINDOW_TITLE)
            win.set_focus()

            # 2. 进入朋友圈 → 点相机发起图文
            self._click(win, *PYQ_ENTRY)
            time.sleep(1.5)
            self._click(win, *PYQ_CAMERA)
            time.sleep(2.0)

            # 3. 添加图片（PC 微信发朋友圈必须带图）
            for media in media_paths:
                self._click(win, *PYQ_ADD_IMG)
                time.sleep(1.0)
                # TODO: 这里需要把本地图片路径填入文件选择框（可用 pywinauto 的 Edit 控件或直接粘贴路径）
                self._type_file_path(media)

            # 4. 输入文字
            self._click(win, *PYQ_TEXT_INPUT)
            self._type_text(text)

            # 5. 点发表
            self._click(win, *PYQ_PUBLISH_BTN)
            time.sleep(2.0)
            return True, ''
        except Exception as e:
            logger.error(f'UI 自动化发布失败：{e}')
            return False, f'UI 自动化发布失败：{e}'

    # ---------- UI 自动化辅助 ----------
    def _click(self, win, x, y):
        """相对窗口客户区坐标点击。"""
        win.click_input(coords=(x, y))

    def _type_text(self, text):
        """输入文本（中文需用剪贴板粘贴）。"""
        import pywinauto
        from pywinauto import clipboard
        clipboard.set_text(text)          # 先写剪贴板（支持中文）
        pywinauto.keyboard.send_keys('^v')  # Ctrl+V 粘贴

    def _type_file_path(self, path):
        """在文件选择框输入路径并回车（用于添加图片）。"""
        import pywinauto
        pywinauto.keyboard.send_keys(path, with_spaces=True)
        pywinauto.keyboard.send_keys('{ENTER}')
