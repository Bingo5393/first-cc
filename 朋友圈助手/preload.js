// 微信朋友圈发布助手 —— 预加载脚本
// 通过 contextBridge 向渲染进程暴露安全的 IPC 接口
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  // 加载全部数据（文案 + 内置模板 + 数据路径）
  load: () => ipcRenderer.invoke('store:load'),

  // 文案增删改
  addSentence: (data) => ipcRenderer.invoke('sentence:add', data),
  updateSentence: (data) => ipcRenderer.invoke('sentence:update', data),
  deleteSentence: (id) => ipcRenderer.invoke('sentence:delete', id),

  // 复制到电脑剪贴板；若传 sentenceId 则同步记录复制时间
  copy: (text, sentenceId) => ipcRenderer.invoke('clipboard:copy', text, sentenceId),

  // 手机剪贴板（ADB + uiautomator2，尽力而为）
  copyToPhone: (text, sentenceId) => ipcRenderer.invoke('phone:copy', text, sentenceId),
  checkAdb: () => ipcRenderer.invoke('phone:check'),

  // 自动发布到朋友圈（分身微信）
  publishToMoments: (text) => ipcRenderer.invoke('publish:post', text),
});
