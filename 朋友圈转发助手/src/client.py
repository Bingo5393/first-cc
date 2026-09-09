# -*- coding: utf-8 -*-
# WeChatFerry 客户端封装 + PC 微信 UI 自动化发布
#
# 职责：
#   1. 封装 WeChatFerry（Wcf），提供登录检测、好友列表、朋友圈获取、媒体下载；
#   2. 封装 PC 微信「发朋友圈」的 UI 自动化（因为 WeChatFerry 无发布朋友圈接口）。

import time
from queue import Empty

from loguru import logger

from wcferry import Wcf


# 微信主窗口标题（用于定位窗口）
WX_WINDOW_TITLE = '微信'

# 默认发圈坐标（相对微信主窗口客户区左上角），占位值，需实测校准。
# 用户可在 config.yaml 的 publish_coords 里覆盖，无需改代码。
DEFAULT_COORDS = {
    'moments_entry': (66, 122),      # 左侧导航「朋友圈」图标
    'camera': (906, 56),             # 朋友圈页右上角「相机」图标（发图文）
    'add_image': (120, 160),         # 发圈窗口「添加图片」区域
    'text_input': (520, 420),        # 文字输入框
    'publish_btn': (860, 600),       # 「发表」按钮
}


class WxClient:
    """封装 WeChatFerry，提供朋友圈转发所需的高层接口。"""

    def __init__(self, host='', port=10086, coords=None):
        # host 留空 = 本地模式（wcferry 自动运行 wcf.exe 注入微信）；填 IP = 连接远程 wcf 服务
        self.host = host or None
        self.port = port
        self.coords = coords or DEFAULT_COORDS
        self._contacts = None  # 好友列表缓存（别名映射用）
        # 初始化 WeChatFerry 客户端（本地模式会运行 wcf.exe 注入微信）
        # block=False：不在构造函数里阻塞等待登录，改由 login_check() 显式检测，
        # 否则微信未登录时这里会死循环卡住，走不到后面的友好提示。
        # debug=False：注入 release 版 spy.dll（本项目已 patch 其版本检查以适配兼容层），
        # 若用 debug=True 会注入 spy_debug.dll，那是另一个未 patch 的文件。
        self.wcf = Wcf(host=self.host, port=port, block=False, debug=False)

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

    # ---------- 好友 / 别名映射 ----------
    def get_friends_list(self):
        """获取好友列表（dict 列表，含 wxid/name/remark 等）。带缓存。"""
        if self._contacts is None:
            try:
                self._contacts = self.wcf.get_contacts() or []
            except Exception as e:
                logger.error(f'获取好友列表失败：{e}')
                self._contacts = []
        return self._contacts

    def resolve_targets(self, names):
        """把配置里的监控目标（备注名/昵称/wxid）解析为 wxid 列表。

        用户填「张三」即可匹配，无需手查 wxid；填 wxid 也直接兼容。
        """
        mapping = {}
        for c in self.get_friends_list():
            wxid = c.get('wxid') if isinstance(c, dict) else getattr(c, 'wxid', '')
            remark = c.get('remark') if isinstance(c, dict) else getattr(c, 'remark', '')
            name = c.get('name') if isinstance(c, dict) else getattr(c, 'name', '')
            if wxid:
                mapping[wxid] = wxid
            if remark:
                mapping[remark] = wxid
            if name:
                mapping[name] = wxid

        resolved = []
        for n in names:
            resolved.append(mapping.get(n, n))  # 找不到就原样（可能本身是 wxid）
        return resolved

    # ---------- 朋友圈获取 ----------
    def enable_moments_receiving(self):
        """开启朋友圈消息接收（pyq=True）。"""
        return self.wcf.enable_receiving_msg(pyq=True)

    def refresh_moments(self):
        """触发刷新朋友圈，返回状态码（1 成功）。"""
        return self.wcf.refresh_pyq()

    def fetch_pending_msgs(self, wait_seconds=0.0):
        """取出当前积压的微信消息（含朋友圈消息）。

        wait_seconds > 0：在该时间内阻塞等待消息到达（refresh_pyq 后消息是异步
        推送的，需要短暂等待才能取到刚刷新的动态）；
        wait_seconds = 0：只取当前队列里已有的消息，不等待。
        """
        msgs = []
        deadline = time.time() + max(wait_seconds, 0.0)
        try:
            while self.wcf.is_receiving_msg():
                if wait_seconds <= 0:
                    # 非阻塞模式：队列空即结束
                    try:
                        msg = self.wcf.get_msg(block=False)
                    except Empty:
                        break
                else:
                    # 阻塞模式：get_msg 队列空时最多阻塞 1 秒后抛 Empty，继续等到 deadline
                    if time.time() >= deadline:
                        break
                    try:
                        msg = self.wcf.get_msg(block=True)
                    except Empty:
                        continue
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

    # ---------- 心跳 / 保活 ----------
    def keep_alive(self):
        """心跳检测：返回当前是否仍在线。"""
        return self.login_check()

    # ---------- 发布朋友圈（PC UI 自动化） ----------
    def publish_moment(self, text, media_paths):
        """通过 PC 微信 UI 自动化发布朋友圈。返回 (ok, err_msg)。

        因微信是自绘 UI，采用「定位主窗口 + 相对坐标点击」方案。
        坐标来自 self.coords（可在 config.yaml 的 publish_coords 覆盖）。
        """
        try:
            import pywinauto
        except ImportError:
            return False, '未安装 pywinauto，请执行：pip install pywinauto'

        c = self.coords
        try:
            # 1. 定位并激活微信主窗口
            app = pywinauto.Application(backend='win32').connect(title=WX_WINDOW_TITLE)
            win = app.window(title=WX_WINDOW_TITLE)
            win.set_focus()

            # 2. 进入朋友圈 → 点相机发起图文
            self._click(win, *c['moments_entry'])
            time.sleep(1.5)
            self._click(win, *c['camera'])
            time.sleep(2.0)

            # 3. 添加图片（PC 微信发朋友圈必须带图）
            for media in media_paths:
                self._click(win, *c['add_image'])
                time.sleep(1.0)
                self._type_file_path(media)

            # 4. 输入文字
            self._click(win, *c['text_input'])
            self._type_text(text)

            # 5. 点发表
            self._click(win, *c['publish_btn'])
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
        clipboard.set_text(text)              # 先写剪贴板（支持中文）
        pywinauto.keyboard.send_keys('^v')    # Ctrl+V 粘贴

    def _type_file_path(self, path):
        """在文件选择框输入路径并回车（用于添加图片）。"""
        import pywinauto
        pywinauto.keyboard.send_keys(path, with_spaces=True)
        pywinauto.keyboard.send_keys('{ENTER}')
