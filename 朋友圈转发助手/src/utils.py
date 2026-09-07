# -*- coding: utf-8 -*-
# 工具函数：配置加载、路径处理、文件哈希

import os
import hashlib

import yaml

# 项目根目录（src 的上一级）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 默认配置：用户配置文件缺失字段时，用它兜底
DEFAULT_CONFIG = {
    'monitor': {'targets': [], 'blacklist': []},
    'forward': {'prefix': '', 'suffix': ''},
    'rate_limit': {'max_per_hour': 5, 'max_per_day': 20,
                   'random_delay_min': 3, 'random_delay_max': 8},
    'time_control': {'enable': False, 'start_hour': 9, 'end_hour': 22},
    'schedule': {'poll_interval_minutes': 10, 'time_window_minutes': 60},
    'wcf': {'host': '127.0.0.1', 'port': 10086},
    'notify': {'enable': False, 'webhook_url': ''},
}


def _deep_merge(base, override):
    """递归合并两个 dict，override 优先（用于把用户配置叠加到默认配置上）。"""
    result = dict(base)
    for key, value in (override or {}).items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path):
    """加载 YAML 配置，并与默认配置合并后返回。

    文件不存在时返回纯默认配置（并附带 warn 标记），由调用方决定是否继续。
    """
    if not os.path.exists(path):
        return dict(DEFAULT_CONFIG), False
    with open(path, 'r', encoding='utf-8') as f:
        user_cfg = yaml.safe_load(f) or {}
    return _deep_merge(DEFAULT_CONFIG, user_cfg), True


def get_abs_path(relative):
    """把相对项目根目录的路径转成绝对路径。已是绝对路径则原样返回。"""
    if os.path.isabs(relative):
        return relative
    return os.path.join(PROJECT_ROOT, relative)


def ensure_dir(path):
    """确保目录存在（不存在则创建）。"""
    os.makedirs(path, exist_ok=True)
    return path


def compute_file_hash(path, algo='sha256'):
    """计算单个文件内容的哈希（默认 SHA256），返回十六进制字符串。"""
    h = hashlib.new(algo)
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()
