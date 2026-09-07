# 朋友圈助手

微信朋友圈自动发布助手 —— 安卓手机 + 先助手后自动。

## 当前进度

✅ 第一阶段「文案助手」已完成，可运行：

- 文案库：新建 / 编辑 / 删除 / 分类 / 标签 / 搜索 / 复制历史
- 内置 8 条营销文案模板，一键套用
- 一键复制到电脑剪贴板
- 复制到手机剪贴板（ADB + uiautomator2，尽力而为）

## 运行

```bash
npm install   # 首次安装
npm start
```

> 若 Electron 二进制下载失败（`fetch failed`），用国内镜像重下：
> `cd node_modules/electron && ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/" node install.js`

## 待办（第二阶段）

- [ ] 自动发布：ADB + uiautomator2 自动打开微信朋友圈 → 粘贴 → 发布
- [ ] 图片管理

## 方案文档

见 [朋友圈发布助手-项目方案.md](./朋友圈发布助手-项目方案.md)
