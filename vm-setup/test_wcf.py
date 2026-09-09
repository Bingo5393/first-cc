# -*- coding: utf-8 -*-
# 最小连通性测试：验证 patch 后 spy.dll 能否正常注入微信
import sys

print("1. import wcferry", flush=True)
from wcferry import Wcf

print("2. 初始化 Wcf(block=False)...", flush=True)
wcf = Wcf(host=None, port=10086, block=False)
print("3. Wcf 初始化完成", flush=True)

login = wcf.is_login()
print("4. is_login =", login, flush=True)
if login:
    print("5. self_wxid =", wcf.get_self_wxid(), flush=True)

print("=== 测试完成 ===", flush=True)
