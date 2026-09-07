# -*- coding: utf-8 -*-
# 朋友圈消息解析 + 媒体下载
#
# 将 WeChatFerry 收到的朋友圈消息（WxMsg）解析为结构化的 Moment，
# 并负责把图片/视频下载到本地。

import os
import re
import time
from dataclasses import dataclass, field

from loguru import logger


@dataclass
class Moment:
    """一条朋友圈动态的结构化表示。"""
    user: str                    # 发布者 wxid
    content: str                 # 文本内容
    media_type: str              # 'text' | 'image' | 'video'
    media_refs: list = field(default_factory=list)   # 媒体引用，元素为 (kind, ref)
    media_paths: list = field(default_factory=list)  # 下载后的本地文件路径
    timestamp: int = 0           # 时间戳（秒）
    msg_id: int = 0              # 原始消息 id（下载媒体时需要）
    content_hash: str = ''       # 内容哈希（去重键，由 monitor 填充）


# 朋友圈消息在 xml 中常见的关键字（用于启发式识别）
_PYQ_MARKERS = ('pyq', 'sns', 'timeline', '朋友圈')


def is_moment_msg(msg):
    """判断一条 WxMsg 是否为朋友圈消息（启发式）。

    因 WeChatFerry 未提供专门类型标记，这里用 xml / content 特征判断。
    TODO: 实测后根据真实 type / xml 特征精确化。
    """
    xml = (getattr(msg, 'xml', '') or '').lower()
    content = (getattr(msg, 'content', '') or '')
    # 命中朋友圈关键字，或同时具备文本与媒体引用（且非普通聊天文本）
    if any(m in xml for m in _PYQ_MARKERS):
        return True
    if getattr(msg, 'thumb', '') or getattr(msg, 'extra', ''):
        return True
    return False


def _extract_text(msg):
    """从消息里提取文本：优先 content 字段，其次从 xml 兜底。"""
    content = (getattr(msg, 'content', '') or '').strip()
    if content:
        return content
    xml = getattr(msg, 'xml', '') or ''
    if not xml:
        return ''
    # 从 xml 常见文本节点兜底提取
    for tag in ('des', 'title', 'content', 'text'):
        m = re.search(r'<%s[^>]*>(.*?)</%s>' % (tag, tag), xml, re.S)
        if m:
            txt = m.group(1).strip()
            if txt:
                return txt
    return ''


def _extract_media_refs(msg):
    """从消息里提取媒体引用列表，元素为 (kind, ref)。

    kind: 'image' 用 extra 下载；'video' 用 thumb 下载。
    TODO: 朋友圈多图场景下，extra/thumb 可能是分隔的多条引用，需实测确定分隔规则。
    """
    refs = []
    extra = getattr(msg, 'extra', '') or ''
    thumb = getattr(msg, 'thumb', '') or ''
    if extra:
        refs.append(('image', extra))
    elif thumb:
        # thumb 指向视频封面（.mp4）时视为视频，否则视为图片缩略图
        if thumb.lower().endswith('.mp4'):
            refs.append(('video', thumb))
        else:
            refs.append(('image', thumb))
    return refs


def parse_moment(msg):
    """把一条朋友圈消息解析为 Moment 对象。"""
    refs = _extract_media_refs(msg)
    if any(k == 'video' for k, _ in refs):
        media_type = 'video'
    elif refs:
        media_type = 'image'
    else:
        media_type = 'text'

    return Moment(
        user=getattr(msg, 'sender', '') or '',
        content=_extract_text(msg),
        media_type=media_type,
        media_refs=refs,
        timestamp=int(getattr(msg, 'ts', 0) or time.time()),
        msg_id=int(getattr(msg, 'id', 0) or 0),
    )


def download_media(client, moment, save_dir):
    """下载 Moment 的图片/视频到 save_dir，填充 moment.media_paths。

    返回成功下载的本地路径列表。
    """
    os.makedirs(save_dir, exist_ok=True)
    paths = []
    for kind, ref in moment.media_refs:
        try:
            if kind == 'video':
                p = client.download_video(moment.msg_id, ref, save_dir)
            else:
                p = client.download_image(moment.msg_id, ref, save_dir)
            if p and os.path.exists(p):
                paths.append(p)
                logger.info(f'媒体下载成功：{p}')
            else:
                logger.warning(f'媒体下载失败（{kind} ref={ref}）')
        except Exception as e:
            logger.error(f'媒体下载异常：{e}')
    moment.media_paths = paths
    return paths
