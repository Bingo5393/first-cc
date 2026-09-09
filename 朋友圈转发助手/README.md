# 朋友圈转发助手

监控指定好友的朋友圈动态，自动下载图文/视频并转发到自己朋友圈的 Python 程序。

## 功能

- 定时轮询监控目标好友的朋友圈
- 自动下载朋友圈图片 / 视频到本地
- 基于内容哈希去重，避免重复转发
- 转发文案支持前缀 / 后缀
- 频率限制（每小时 / 每天上限）+ 随机延迟，降低风控风险
- 时段控制（仅指定时段转发）
- 日志轮转、掉线心跳检测、异常通知（企业微信机器人）

## 技术栈与原理

- **获取朋友圈 / 下载媒体**：WeChatFerry（PC 微信 hook）
- **发布朋友圈**：PC 微信 UI 自动化（pywinauto），因为 WeChatFerry **不支持**发布朋友圈
- 存储去重：SQLite；日志：loguru；调度：schedule

## 目录结构

```
朋友圈转发助手/
├── main.py            # 主入口（调度、心跳、全局异常）
├── config.yaml        # 配置文件
├── requirements.txt   # 依赖
├── src/
│   ├── client.py      # WeChatFerry 封装 + UI 自动化发布
│   ├── monitor.py     # 拉取新动态 + 去重整合
│   ├── parser.py      # 朋友圈消息解析 + 媒体下载
│   ├── forwarder.py   # 转发执行 + 随机延迟
│   ├── rate_limiter.py# 滑动窗口限频
│   ├── storage.py     # SQLite 去重存储
│   ├── logger.py      # 日志配置
│   └── utils.py       # 配置/路径/哈希工具
├── tools/
│   ├── dump_pyq.py       # 调试：dump 朋友圈消息原始字段
│   └── calibrate_coords.py  # 调试：发圈坐标校准
├── data/
│   ├── media/         # 下载的图片/视频
│   └── forwarded.db   # 去重数据库（运行后生成）
└── logs/              # 日志（运行后生成）
```

## 安装

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 部署 WeChatFerry：

   - `pip install wcferry==39.6.0.0` 后自带 `wcf.exe` / `spy.dll` / `sdk.dll`，无需单独下载 DLL；
   - 安装与 wcferry 匹配的 **PC 微信老版本**（本项目锁定 `wcferry==39.6.0.0`，对应微信 `3.9.12.56`，微信需关闭自动更新，否则升回 4.x 会 hook 失效）；
   - 启动微信并扫码登录营销号，然后启动 wcf 服务。

## 配置

编辑 `config.yaml`，关键字段：

```yaml
monitor:
  targets: ["张三", "wxid_xxxx"]   # 要监控的好友（备注名/昵称/wxid）
  blacklist: []                    # 忽略名单
forward:
  prefix: ""                       # 转发前缀
  suffix: ""                       # 转发后缀
rate_limit:
  max_per_hour: 5
  max_per_day: 20
  random_delay_min: 3
  random_delay_max: 8
time_control:
  enable: false
  start_hour: 9
  end_hour: 22
schedule:
  poll_interval_minutes: 10
  time_window_minutes: 60
  pyq_wait_seconds: 3              # refresh 后等待朋友圈消息推送的秒数
wcf:
  host: ""                          # 留空=本地模式（自动注入微信）
  port: 10086
publish_coords:                     # PC 微信发圈坐标（需实测校准）
  moments_entry: [66, 122]
  camera: [906, 56]
  add_image: [120, 160]
  text_input: [520, 420]
  publish_btn: [860, 600]
```

> `monitor.targets` 填备注名 / 昵称 / wxid 均可，程序会自动映射到 wxid。

## 运行

```bash
python main.py                # 默认 config.yaml
python main.py --config xxx.yaml
```

## 调试工具（真机实测用）

在正式跑转发前，建议先用下面两个工具在真机上校准，把结果回填到 `parser.py` 和 `config.yaml`：

```bash
# 1. dump 朋友圈消息原始字段（校准 type/sender/多图/XML 解析）
python tools/dump_pyq.py --wait 8

# 2. 校准发圈坐标（生成 publish_coords）
python tools/calibrate_coords.py
```

- `dump_pyq.py`：刷新朋友圈后 dump 每条消息的 `type` / `sender` / `content` / `thumb` / `extra` / 完整 `xml`，结果同时写入 `logs/pyq_dump_*.txt`。用这些真实字段精确化 `parser.py` 里的启发式解析（目前 `type`、`sender`、多图 `extra` 分隔规则均为占位实现）。
- `calibrate_coords.py`：引导你把鼠标移到各点击目标、按 **F8** 记录，输出可直接粘贴的 `publish_coords`（需要先 `pip install pywin32`）。

## ⚠️ 注意事项

1. **封号风险**：自动化操作违反微信使用条款，仅建议在营销小号上使用，并控制转发频率。
2. **微信版本锁定**：WeChatFerry 依赖特定版本的 PC 微信，升级微信会导致 hook 失效。
3. **PC UI 自动化坐标需实测**：`src/client.py` 顶部 `PYQ_ENTRY` / `PYQ_CAMERA` 等发布坐标是占位值，需在真机上实测校准后才能正确发布。
4. **纯文字动态无法转发**：PC 微信发朋友圈必须带图，纯文字朋友圈会被跳过。
