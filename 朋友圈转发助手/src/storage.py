# -*- coding: utf-8 -*-
# 去重存储：SQLite 数据库
# 表 forwarded 记录已转发过的内容哈希，避免重复转发同一条朋友圈。

import os
import hashlib
import sqlite3
import threading
from datetime import datetime

from src import utils

# 数据库文件：data/forwarded.db
DB_PATH = utils.get_abs_path('data/forwarded.db')

# 用锁串行化数据库操作，避免并发写冲突
_lock = threading.Lock()


def _connect():
    """建立数据库连接（自动创建父目录）。"""
    utils.ensure_dir(os.path.dirname(DB_PATH))
    return sqlite3.connect(DB_PATH)


def init_db():
    """初始化数据库：创建 forwarded 表（幂等）。"""
    with _lock:
        conn = _connect()
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS forwarded (
                content_hash TEXT PRIMARY KEY,  -- 内容哈希（去重键）
                forward_time TEXT NOT NULL,     -- 转发时间（ISO 格式）
                source_user  TEXT               -- 来源好友（wxid / 名称）
            )
            '''
        )
        conn.commit()
        conn.close()


def is_duplicate(content_hash):
    """判断某内容哈希是否已转发过。"""
    with _lock:
        conn = _connect()
        row = conn.execute(
            'SELECT 1 FROM forwarded WHERE content_hash = ?', (content_hash,)
        ).fetchone()
        conn.close()
        return row is not None


def save_record(content_hash, source_user):
    """记录一条已转发内容（幂等：哈希相同则忽略）。"""
    with _lock:
        conn = _connect()
        conn.execute(
            'INSERT OR IGNORE INTO forwarded (content_hash, forward_time, source_user) VALUES (?, ?, ?)',
            (content_hash, datetime.now().isoformat(), source_user or ''),
        )
        conn.commit()
        conn.close()


def compute_content_hash(text, media_paths):
    """计算「文本 + 媒体文件内容」的组合哈希，作为去重键。

    media_paths 为本地文件路径列表；文件不存在时退化为用路径字符串参与哈希。
    """
    h = hashlib.sha256()
    h.update((text or '').encode('utf-8'))
    for p in sorted(media_paths or []):
        if os.path.exists(p):
            with open(p, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    h.update(chunk)
        else:
            h.update(p.encode('utf-8'))
    return h.hexdigest()
