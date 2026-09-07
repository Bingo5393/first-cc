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

   - 从 [WeChatFerry 官方仓库](https://github.com/lich0821/WeChatFerry) 下载对应版本的 `wcf` DLL；
   - 安装与 wcferry 匹配的 **PC 微信老版本**（本项目锁定 `wcferry==39.6.0.0`，对应微信 `3.9.6.0`，微信需关闭自动更新）；
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
wcf:
  host: "127.0.0.1"
  port: 10086
```

## 运行

```bash
python main.py                # 默认 config.yaml
python main.py --config xxx.yaml
```

## ⚠️ 注意事项

1. **封号风险**：自动化操作违反微信使用条款，仅建议在营销小号上使用，并控制转发频率。
2. **微信版本锁定**：WeChatFerry 依赖特定版本的 PC 微信，升级微信会导致 hook 失效。
3. **PC UI 自动化坐标需实测**：`src/client.py` 顶部 `PYQ_ENTRY` / `PYQ_CAMERA` 等发布坐标是占位值，需在真机上实测校准后才能正确发布。
4. **纯文字动态无法转发**：PC 微信发朋友圈必须带图，纯文字朋友圈会被跳过。
