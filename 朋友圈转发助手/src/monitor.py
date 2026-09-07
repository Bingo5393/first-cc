# -*- coding: utf-8 -*-
# 监控：拉取监控目标的最新朋友圈动态，去重后产出待转发的 Moment 列表。

from datetime import datetime, timedelta

from loguru import logger

from src import parser, storage, utils


def fetch_new_moments(client, config):
    """拉取监控目标的新朋友圈动态。

    流程：刷新朋友圈 → 取消息 → 过滤（朋友圈/目标用户/黑名单/时间窗口）
         → 下载媒体 → 计算哈希去重 → 返回待转发列表。
    """
    targets = config['monitor']['targets'] or []
    blacklist = set(config['monitor']['blacklist'] or [])
    window_minutes = config['schedule']['time_window_minutes']

    if not targets:
        logger.warning('配置未设置监控目标（monitor.targets），跳过本次拉取')
        return []

    # 1. 触发刷新朋友圈（让微信推送最新动态）
    client.refresh_moments()

    # 2. 取出积压消息
    msgs = client.fetch_pending_msgs()
    if not msgs:
        logger.info('本次未收到朋友圈消息')
        return []

    # 3. 过滤条件：时间窗口
    cutoff = datetime.now() - timedelta(minutes=window_minutes)
    media_dir = utils.ensure_dir(utils.get_abs_path('data/media'))

    results = []
    for msg in msgs:
        # 只处理朋友圈消息
        if not parser.is_moment_msg(msg):
            continue

        moment = parser.parse_moment(msg)

        # 只处理监控目标，且排除黑名单
        if moment.user not in targets:
            continue
        if moment.user in blacklist:
            logger.debug(f'好友 {moment.user} 在黑名单中，跳过')
            continue

        # 只处理时间窗口内的新动态
        if datetime.fromtimestamp(moment.timestamp) < cutoff:
            logger.debug(f'动态太旧（{moment.timestamp}），跳过')
            continue

        # 下载媒体
        parser.download_media(client, moment, media_dir)

        # 计算哈希并去重
        moment.content_hash = storage.compute_content_hash(
            moment.content, moment.media_paths
        )
        if storage.is_duplicate(moment.content_hash):
            logger.info(f'已转发过，跳过：{moment.user}「{moment.content[:20]}」')
            continue

        logger.info(f'发现新动态：{moment.user} | {moment.media_type} | {moment.content[:30]}')
        results.append(moment)

    return results
