# -*- coding: utf-8 -*-
# 日志：loguru，按天轮转、保留 7 天，同时输出到控制台和文件。

import os
import sys

from loguru import logger

from src import utils

# 日志格式（含时间、级别、模块、行号、消息）
_FMT = ('<green>{time:YYYY-MM-DD HH:mm:ss}</green> | '
        '<level>{level: <8}</level> | '
        '<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>')


def setup_logger():
    """配置日志并返回 logger（幂等，重复调用不重复添加 handler）。"""
    # 移除默认 handler，避免重复输出
    logger.remove()

    # 控制台输出
    logger.add(sys.stdout, level='INFO', format=_FMT)

    # 文件输出：按天轮转，保留 7 天
    log_dir = utils.ensure_dir(utils.get_abs_path('logs'))
    logger.add(
        os.path.join(log_dir, 'app.log'),
        level='DEBUG',
        format=_FMT,
        rotation='00:00',        # 每天零点轮转
        retention='7 days',      # 保留 7 天
        encoding='utf-8',
        enqueue=True,            # 多线程安全
    )
    return logger
