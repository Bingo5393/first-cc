# -*- coding: utf-8 -*-
# 朋友圈消息字段 dump 工具
#
# 用途：在真机（虚拟机装微信 3.9.x + WeChatFerry）上运行，刷新朋友圈并 dump
#       收到的朋友圈消息的全部原始字段，用于校准 src/parser.py 里的解析逻辑
#       （type 判断、sender 取值、多图 extra 分隔规则、xml 兜底字段等）。
#
# 用法：
#   python tools/dump_pyq.py                 # 默认 config.yaml，等待 6 秒
#   python tools/dump_pyq.py --wait 10       # 消息推送慢时调大等待秒数
#   python tools/dump_pyq.py --max 20        # 最多 dump 20 条
#
# 输出：控制台 + logs/pyq_dump_<时间戳>.txt（XML 较长，建议看文件）

import argparse
import os
import sys
from datetime import datetime

# 让 tools/ 下的脚本能 import 到项目根目录的 src 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

from src import client as client_mod
from src import logger as logger_mod
from src import utils


def fmt_msg(msg):
    """把一条 WxMsg 格式化为多行文本，完整保留原始字段供分析。"""
    ts = getattr(msg, 'ts', 0) or 0
    ts_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else '无'
    lines = [
        '=' * 72,
        f'类型 type     : {getattr(msg, "type", "?")} (十六进制 0x{getattr(msg, "type", 0):x})',
        f'消息 id       : {getattr(msg, "id", "?")}',
        f'时间戳 ts     : {ts} -> {ts_str}',
        f'签名 sign     : {getattr(msg, "sign", "")}',
        f'发送者 sender : {getattr(msg, "sender", "")}',
        f'群 id roomid  : {getattr(msg, "roomid", "")}',
        f'是否自己发    : {msg.from_self()}',
        f'是否群消息    : {msg.from_group()}',
        f'文本 content  : {getattr(msg, "content", "")}',
        f'缩略图 thumb  : {getattr(msg, "thumb", "")}',
        f'媒体 extra    : {getattr(msg, "extra", "")}',
        '完整 XML      :',
        getattr(msg, 'xml', '') or '(空)',
    ]
    return '\n'.join(lines)


def parse_args():
    p = argparse.ArgumentParser(description='朋友圈消息字段 dump 工具')
    p.add_argument('--config', default='config.yaml', help='配置文件路径')
    p.add_argument('--wait', type=float, default=6.0, help='刷新后等待消息推送的秒数')
    p.add_argument('--max', type=int, default=20, help='最多 dump 的消息条数')
    return p.parse_args()


def main():
    args = parse_args()
    logger_mod.setup_logger()

    config, _ = utils.load_config(args.config)

    # 连接微信（block=False，未登录时走下面的友好提示）
    wx = client_mod.WxClient(
        config['wcf']['host'], config['wcf']['port'],
        config.get('publish_coords'),
    )

    if not wx.login_check():
        logger.error('微信未登录，请先在 PC 微信扫码登录后重试')
        sys.exit(1)
    logger.info(f'微信已登录，wxid={wx.get_self_wxid()}')

    # 打印消息类型对照表（帮助理解 type 数值含义）
    try:
        types = wx.wcf.get_msg_types()
        logger.info('消息类型对照表：{}'.format(types))
    except Exception as e:
        logger.warning(f'获取消息类型对照表失败：{e}')

    # 开启朋友圈接收 + 刷新
    wx.enable_moments_receiving()
    logger.info('已开启朋友圈接收，触发刷新…')
    wx.refresh_moments()

    # 等待消息异步推送后收集
    logger.info(f'等待 {args.wait} 秒收集朋友圈消息…')
    msgs = wx.fetch_pending_msgs(wait_seconds=args.wait)
    logger.info(f'共收到 {len(msgs)} 条消息')

    if not msgs:
        logger.warning('未收到任何消息。可能原因：')
        logger.warning('  1) 朋友圈没有新动态；2) 等待时间太短（用 --wait 调大）；')
        logger.warning('  3) 微信版本与 wcferry 不兼容（需锁定 3.9.x）。')
        return

    # 格式化输出并写文件
    body = '\n\n'.join(fmt_msg(m) for m in msgs[:args.max])
    out_path = os.path.join(
        utils.ensure_dir(utils.get_abs_path('logs')),
        f'pyq_dump_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt',
    )
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(body + '\n')

    # 控制台也打印（XML 很长时以文件为准）
    print('\n' + body + '\n')
    logger.info(f'完整结果已保存到：{out_path}')

    logger.info('接下来请对照这些字段，把结论反馈回来校准 parser.py：')
    logger.info('  * type 的数值 -> 用于精确化 is_moment_msg 的朋友圈类型判断')
    logger.info('  * sender 是否为发布者 wxid -> 用于 parse_moment 的 user 取值')
    logger.info('  * extra 是否含分隔符（多图） -> 用于 _extract_media_refs 拆分')
    logger.info('  * xml 里的 userName/nickName/content 节点 -> 用于兜底解析')


if __name__ == '__main__':
    main()
