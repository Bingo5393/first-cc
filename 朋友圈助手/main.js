// 微信朋友圈发布助手 —— 主进程
// 职责：创建窗口、文案库 JSON 存储、剪贴板复制、ADB 手机剪贴板
const { app, BrowserWindow, ipcMain, clipboard } = require('electron');
const path = require('path');
const fs = require('fs');
const { execFile } = require('child_process');

// ---------- 内置营销文案模板（只读，供用户一键套用） ----------
const SEED_TEMPLATES = [
  {
    id: 'tpl-001',
    name: '新品上线',
    category: '新品发布',
    content:
      '🎉 新品上线！\n\n【产品名称】正式和大家见面啦～\n\n✅ 核心卖点一\n✅ 核心卖点二\n✅ 核心卖点三\n\n限时尝鲜价，喜欢的宝子抓紧冲！\n\n#新品发布 #限时优惠',
  },
  {
    id: 'tpl-002',
    name: '限时促销',
    category: '活动促销',
    content:
      '🔥 限时狂欢！\n\n原价 XX 元，现在只要 XX 元！\n\n📅 活动时间：即日起至 X 月 X 日\n📍 仅限 XX 份，先到先得\n\n错过这波，再等一年！\n\n#限时优惠 #手慢无',
  },
  {
    id: 'tpl-003',
    name: '节日祝福营销',
    category: '节日营销',
    content:
      '🌕 节日快乐！\n\n在这个特别的日子，我们为你准备了专属好礼：\n\n🎁 福利一：XXX\n🎁 福利二：XXX\n🎁 福利三：XXX\n\n把祝福和优惠一起打包送给你～\n\n#节日快乐 #专属福利',
  },
  {
    id: 'tpl-004',
    name: '用户好评反馈',
    category: '用户反馈',
    content:
      '💬 今日份好评分享！\n\n「引用客户评价……」\n\n感谢每一位信任我们的朋友！\n\n好产品会说话，好口碑靠积累。\n\n期待下一次与你相遇～\n\n#客户好评 #口碑推荐',
  },
  {
    id: 'tpl-005',
    name: '日常种草分享',
    category: '日常分享',
    content:
      '✨ 最近的爱用物分享！\n\n【产品名称】真的绝绝子～\n\n💡 使用感受：XXX\n💡 效果反馈：XXX\n\n自用推荐，无广放心冲！\n\n#好物分享 #种草',
  },
  {
    id: 'tpl-006',
    name: '品牌故事',
    category: '品牌故事',
    content:
      '📖 关于我们的一点小事。\n\n从一个人、一个想法，到今天的每一步，\n都离不开大家的支持。\n\n我们始终相信：认真做产品，时间会给出答案。\n\n谢谢一路相伴的你。\n\n#品牌故事 #匠心',
  },
  {
    id: 'tpl-007',
    name: '引流裂变',
    category: '引流裂变',
    content:
      '🎁 福利来啦！\n\n转发本条朋友圈 + 点赞，\n即可到店 / 私信领取【XXX】一份！\n\n📌 活动规则：\n1️⃣ 转发并集满 X 个赞\n2️⃣ 截图私信我\n\n名额有限，冲鸭！\n\n#福利 #转发有礼',
  },
  {
    id: 'tpl-008',
    name: '倒计时预告',
    category: '活动预告',
    content:
      '⏰ 倒计时开始！\n\n还有 X 天，【大事件】即将开启！\n\n🔔 提前锁定，福利不错过\n🔔 敬请期待\n\n准备好你的小本本了吗？\n\n#倒计时 #敬请期待',
  },
];

// ---------- 存储工具 ----------
// 数据保存在 Electron 的 userData 目录，与系统账号隔离，卸载不丢
const storePath = () => path.join(app.getPath('userData'), 'store.json');

function loadStore() {
  const file = storePath();
  try {
    const raw = fs.readFileSync(file, 'utf-8');
    const data = JSON.parse(raw);
    return {
      sentences: Array.isArray(data.sentences) ? data.sentences : [],
    };
  } catch (err) {
    // 首次运行或文件损坏时，返回空文案
    return { sentences: [] };
  }
}

function saveStore(data) {
  const file = storePath();
  // 确保目录存在
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2), 'utf-8');
}

// 生成唯一 ID
function genId() {
  return Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
}

// ---------- IPC：文案库 ----------
ipcMain.handle('store:load', () => {
  const { sentences } = loadStore();
  return {
    sentences,
    templates: SEED_TEMPLATES,
    dataPath: storePath(),
  };
});

ipcMain.handle('sentence:add', (event, data) => {
  const store = loadStore();
  const now = new Date().toISOString();
  const sentence = {
    id: genId(),
    content: String(data.content || '').trim(),
    category: String(data.category || '').trim(),
    tags: Array.isArray(data.tags) ? data.tags : [],
    createdAt: now,
    updatedAt: now,
    lastCopiedAt: null,
  };
  // 内容为空则拒绝
  if (!sentence.content) {
    return { ok: false, error: '文案内容不能为空' };
  }
  store.sentences.unshift(sentence);
  saveStore(store);
  return { ok: true, sentence };
});

ipcMain.handle('sentence:update', (event, data) => {
  const store = loadStore();
  const idx = store.sentences.findIndex((s) => s.id === data.id);
  if (idx === -1) {
    return { ok: false, error: '未找到该文案，可能已被删除' };
  }
  const now = new Date().toISOString();
  const updated = {
    ...store.sentences[idx],
    content: String(data.content || '').trim(),
    category: String(data.category || '').trim(),
    tags: Array.isArray(data.tags) ? data.tags : [],
    updatedAt: now,
  };
  if (!updated.content) {
    return { ok: false, error: '文案内容不能为空' };
  }
  store.sentences[idx] = updated;
  saveStore(store);
  return { ok: true, sentence: updated };
});

ipcMain.handle('sentence:delete', (event, id) => {
  const store = loadStore();
  const before = store.sentences.length;
  store.sentences = store.sentences.filter((s) => s.id !== id);
  if (store.sentences.length === before) {
    return { ok: false, error: '未找到要删除的文案' };
  }
  saveStore(store);
  return { ok: true };
});

// 记录「最近复制时间」（不修改内容，只刷新时间戳）
function touchCopied(id) {
  const store = loadStore();
  const idx = store.sentences.findIndex((s) => s.id === id);
  if (idx === -1) return;
  store.sentences[idx].lastCopiedAt = new Date().toISOString();
  saveStore(store);
}

// ---------- IPC：电脑剪贴板 ----------
ipcMain.handle('clipboard:copy', (event, text, sentenceId) => {
  const content = String(text || '');
  if (!content) {
    return { ok: false, error: '没有可复制的内容' };
  }
  clipboard.writeText(content);
  if (sentenceId) touchCopied(sentenceId);
  return { ok: true };
});

// ---------- IPC：ADB 手机剪贴板（第二阶段自动化后端为 uiautomator2，这里先做「尽力而为」） ----------

// 执行一个命令，返回 { ok, stdout, stderr }；可自定义超时（毫秒）
function run(cmd, args, timeout = 15000) {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout }, (err, stdout, stderr) => {
      if (err) {
        resolve({ ok: false, stdout: stdout || '', stderr: stderr || err.message });
      } else {
        resolve({ ok: true, stdout: stdout || '', stderr: stderr || '' });
      }
    });
  });
}

// 检测 adb 是否可用、设备是否在线
ipcMain.handle('phone:check', async () => {
  const adb = await run('adb', ['version']);
  if (!adb.ok) {
    return { ok: false, adb: false, device: false, error: '未检测到 adb，请先安装 ADB 并加入 PATH' };
  }
  const version = (adb.stdout.split('\n')[0] || '').trim();
  const devices = await run('adb', ['devices']);
  // 从 "List of devices attached" 后解析出 device 状态
  const lines = (devices.stdout || '').split('\n').slice(1).map((l) => l.trim()).filter(Boolean);
  const online = lines.some((l) => l.endsWith('\tdevice'));
  return {
    ok: online,
    adb: true,
    device: online,
    version,
    error: online ? '' : '未发现已连接的安卓设备（请确认已开启 USB 调试 / 无线调试）',
  };
});

// 复制到手机剪贴板：通过 Python + uiautomator2 的 set_clipboard
ipcMain.handle('phone:copy', async (event, text, sentenceId) => {
  const content = String(text || '');
  if (!content) {
    return { ok: false, error: '没有可复制的内容' };
  }

  // 1. 先确认 adb 与设备
  const check = await run('adb', ['devices']);
  const hasDevice = (check.stdout || '')
    .split('\n')
    .slice(1)
    .some((l) => l.trim().endsWith('\tdevice'));
  if (!hasDevice) {
    return { ok: false, error: '未连接安卓设备，请先开启 USB 调试 / 无线调试并通过 ADB 连接' };
  }

  // 2. 通过 uiautomator2 写入剪贴板（脚本内不做任何界面操作，仅写剪贴板，安全）
  const py = [
    'import sys, uiautomator2 as u2',
    'd = u2.connect()',
    "d.set_clipboard(sys.argv[1])",
    "print('OK')",
  ].join(';');
  const res = await run('python', ['-c', py, content]);
  if (res.ok && /OK/.test(res.stdout)) {
    if (sentenceId) touchCopied(sentenceId);
    return { ok: true };
  }
  const hint = res.stderr || res.stdout || '';
  const msg = /No module named/.test(hint)
    ? '未安装 uiautomator2，请先在电脑执行：pip install uiautomator2（以及 python -m uiautomator2 init）'
    : '手机剪贴板写入失败，请确认已安装 Python 与 uiautomator2';
  return { ok: false, error: msg, detail: hint };
});

// ---------- IPC：自动发布到朋友圈（第二阶段，分身微信专用） ----------
ipcMain.handle('publish:post', async (event, text) => {
  const content = String(text || '');
  if (!content) {
    return { ok: false, error: '没有可发布的文案' };
  }

  // 1. 先确认 adb 与设备
  const check = await run('adb', ['devices']);
  const hasDevice = (check.stdout || '')
    .split('\n')
    .slice(1)
    .some((l) => l.trim().endsWith('\tdevice'));
  if (!hasDevice) {
    return { ok: false, error: '未连接安卓设备，请先开启 USB 调试 / 无线调试并通过 ADB 连接' };
  }

  // 2. 调用 publish.py 执行自动发圈（涉及多步 UI 操作，放宽超时到 90 秒）
  const pyPath = path.join(__dirname, 'publish.py');
  const res = await run('python', [pyPath, content], 90000);
  const raw = (res.stdout || '').trim();

  // 3. 解析脚本返回的单行 JSON
  try {
    const result = JSON.parse(raw);
    if (result && result.ok) {
      return { ok: true };
    }
    return { ok: false, error: (result && result.error) || '发布失败', detail: res.stderr || '' };
  } catch (e) {
    const hint = res.stderr || res.stdout || '';
    const msg = /No module named/.test(hint)
      ? '未安装 uiautomator2，请先在电脑执行：pip install uiautomator2（以及 python -m uiautomator2 init）'
      : '发布脚本执行异常，请确认已安装 Python 与 uiautomator2';
    return { ok: false, error: msg, detail: hint };
  }
});

// ---------- 窗口 ----------
function createWindow() {
  const win = new BrowserWindow({
    width: 1080,
    height: 720,
    minWidth: 860,
    minHeight: 560,
    autoHideMenuBar: true,
    title: '朋友圈助手',
    backgroundColor: '#f5f6f7',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  win.loadFile('index.html');
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
