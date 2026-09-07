# -*- coding: utf-8 -*-
# 朋友圈转发助手 —— 主入口
#
# 用法：
#   python main.py                  # 使用默认 config.yaml
#   python main.py --config xxx.yaml
#
# 功能：定时轮询监控目标的朋友圈，去重后自动转发到自己朋友圈。

import argparse
import sys
import time
import traceback
from datetime import datetime

import schedule
from loguru import logger

from src import (client, forwarder, logger as logger_mod, monitor,
                 rate_limiter, storage, utils)


def parse_args():
    """解析命令行参数。"""
    p = argparse.ArgumentParser(description='朋友圈转发助手')
    p.add_argument('--config', default='config.yaml', help='配置文件路径')
    return p.parse_args()


def is_in_time_window(config):
    """时段控制：当前是否在允许转发的时段内。"""
    tc = config['time_control']
    if not tc.get('enable'):
        return True
    hour = datetime.now().hour
    return tc['start_hour'] <= hour < tc['end_hour']


def notify(config, msg):
    """发送通知（企业微信机器人 webhook，可选）。"""
    if not config['notify'].get('enable'):
        return
    url = config['notify'].get('webhook_url')
    if not url:
        return
    try:
        import requests
        requests.post(url, json={
            'msgtype': 'text',
            'text': {'content': f'[朋友圈转发助手] {msg}'},
        }, timeout=5)
    except Exception as e:
        logger.warning(f'通知发送失败：{e}')


def run_once(wx, config, limiter):
    """单次轮询：拉取新动态 → 去重 → 逐条转发。"""
    if not is_in_time_window(config):
        logger.info('当前不在允许转发的时段内，跳过')
        return

    moments = monitor.fetch_new_moments(wx, config)
    if not moments:
        return

    for moment in moments:
        if not limiter.allow():
            logger.warning('已达到频率上限（每小时/每天），停止本轮转发')
            notify(config, '达到频率上限，已停止本轮转发')
            break
        ok, err = forwarder.forward_moment(wx, moment, config)
        if not ok:
            notify(config, f'转发失败：{moment.user} - {err}')


def main():
    args = parse_args()

    # 1. 初始化日志（先于其它模块，确保日志可用）
    logger_mod.setup_logger()

    # 2. 加载配置
    config, existed = utils.load_config(args.config)
    if not existed:
        logger.warning(f'配置文件不存在：{args.config}，使用默认配置运行')

    # 3. 初始化数据库
    storage.init_db()

    # 4. 初始化微信客户端（WeChatFerry）
    try:
        wx = client.WxClient(
            config['wcf']['host'],
            config['wcf']['port'],
            config.get('publish_coords'),  # 发圈坐标，可空（用默认占位值）
        )
    except Exception as e:
        logger.error(f'初始化 WeChatFerry 客户端失败：{e}')
        logger.error('请确认：1) PC 微信已启动并登录；2) wcf 服务/DLL 已就绪')
        notify(config, f'初始化失败：{e}')
        sys.exit(1)

    # 5. 登录检测
    if not wx.login_check():
        logger.error('微信未登录，请先在 PC 微信扫码登录后重试')
        notify(config, '微信未登录，请先扫码登录')
        sys.exit(1)
    logger.info(f'微信已登录，wxid={wx.get_self_wxid()}')

    # 6. 开启朋友圈消息接收
    wx.enable_moments_receiving()
    logger.info('已开启朋友圈消息接收')

    # 7. 初始化限频器
    limiter = rate_limiter.RateLimiter(
        config['rate_limit']['max_per_hour'],
        config['rate_limit']['max_per_day'],
    )

    # 8. 定时调度
    interval = config['schedule']['poll_interval_minutes']
    schedule.every(interval).minutes.do(run_once, wx, config, limiter)
    logger.info(f'启动定时轮询：每 {interval} 分钟执行一次')

    # 9. 主循环：处理定时任务 + 心跳检测
    last_heartbeat = time.time()
    HEARTBEAT_INTERVAL = 300  # 心跳间隔（秒）
    while True:
        try:
            schedule.run_pending()

            # 心跳检测：每 5 分钟检查一次登录状态
            if time.time() - last_heartbeat >= HEARTBEAT_INTERVAL:
                last_heartbeat = time.time()
                if not wx.keep_alive():
                    logger.error('心跳检测：微信已掉线')
                    notify(config, '微信已掉线，请检查')
                    # 掉线后停止调度，避免空转（可手动重启程序）
                    break

            time.sleep(1)
        except KeyboardInterrupt:
            logger.info('收到退出信号，程序结束')
            break
        except Exception as e:
            # 全局异常捕获：记录日志并通知，继续运行避免崩溃
            logger.error(f'主循环异常：{e}\n{traceback.format_exc()}')
            notify(config, f'主循环异常：{e}')
            time.sleep(5)


if __name__ == '__main__':
    main()
