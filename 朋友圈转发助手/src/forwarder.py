# -*- coding: utf-8 -*-
# 转发执行：拼装转发文案 → 发布 → 记录结果，并加入随机延迟防风控。

import random
import time

from loguru import logger

from src import storage


def build_forward_text(moment, config):
    """拼装转发文案：prefix + 原文 + suffix。"""
    prefix = config['forward']['prefix'] or ''
    suffix = config['forward']['suffix'] or ''
    return prefix + (moment.content or '') + suffix


def random_delay(config):
    """随机延迟 3~8 秒（仿人操作间隔，降低风控风险）。"""
    lo = config['rate_limit']['random_delay_min']
    hi = config['rate_limit']['random_delay_max']
    delay = random.uniform(lo, hi)
    logger.info(f'随机延迟 {delay:.1f} 秒…')
    time.sleep(delay)


def forward_moment(client, moment, config):
    """转发一条动态。返回 (ok, err_msg)。"""
    # 边界：PC 微信发朋友圈必须带图，纯文本动态无法转发
    if not moment.media_paths:
        logger.warning(f'动态无图片/视频（纯文本），PC 微信无法发纯文字朋友圈，跳过：{moment.user}')
        return False, '无媒体内容，PC 微信不支持发纯文字朋友圈'

    text = build_forward_text(moment, config)
    random_delay(config)

    ok, err = client.publish_moment(text, moment.media_paths)
    if ok:
        storage.save_record(moment.content_hash, moment.user)
        logger.info(f'转发成功：{moment.user}（{len(moment.media_paths)} 个媒体）')
    else:
        logger.error(f'转发失败：{moment.user} - {err}')
    return ok, err
