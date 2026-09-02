'use strict';

/* ---------- 常量与状态 ---------- */

const MODES = ['work', 'shortBreak', 'longBreak'];
const MODE_LABELS = { work: '专注', shortBreak: '短休息', longBreak: '长休息' };
const STORAGE_KEY = 'pomodoro-settings';
const THEME_KEY = 'pomodoro-theme';

const DEFAULT_SETTINGS = {
  work: 25,
  shortBreak: 5,
  longBreak: 15,
  longBreakInterval: 4,
};

let settings = loadSettings();
let durations = settingsToSeconds(settings);

let currentMode = 'work';
let totalSeconds = durations.work;
let remainingSeconds = totalSeconds;
let isRunning = false;
let endTime = null;
let intervalId = null;
let completedPomodoros = 0;

/* ---------- DOM 引用 ---------- */

const timeEl = document.getElementById('time');
const modeLabelEl = document.getElementById('mode-label');
const ringEl = document.getElementById('ring-progress');
const startPauseBtn = document.getElementById('start-pause');
const resetBtn = document.getElementById('reset');
const dotsEl = document.getElementById('dots');
const modeTabs = document.querySelectorAll('.mode-tab');

const themeToggleBtn = document.getElementById('theme-toggle');
const settingsOverlay = document.getElementById('settings-overlay');
const settingsBtn = document.getElementById('settings-btn');
const closeSettingsBtn = document.getElementById('close-settings');
const saveSettingsBtn = document.getElementById('save-settings');
const resetDefaultsBtn = document.getElementById('reset-defaults');
const inputWork = document.getElementById('set-work');
const inputShort = document.getElementById('set-short');
const inputLong = document.getElementById('set-long');
const inputInterval = document.getElementById('set-interval');

const RING_RADIUS = 132;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;
ringEl.style.strokeDasharray = `${RING_CIRCUMFERENCE}`;

/* ---------- 工具函数 ---------- */

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch (e) {
    /* 忽略损坏的存储 */
  }
  return { ...DEFAULT_SETTINGS };
}

function settingsToSeconds(s) {
  return {
    work: s.work * 60,
    shortBreak: s.shortBreak * 60,
    longBreak: s.longBreak * 60,
  };
}

function formatTime(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function setMode(mode) {
  currentMode = mode;
  totalSeconds = durations[mode];
  remainingSeconds = totalSeconds;
  stopTicking();
  updateBodyMode();
  updateTabs();
  updateDisplay();
}

function switchModeAfterComplete() {
  if (currentMode === 'work') {
    completedPomodoros += 1;
    updateDots();
    const next =
      completedPomodoros % settings.longBreakInterval === 0
        ? 'longBreak'
        : 'shortBreak';
    setMode(next);
  } else {
    setMode('work');
  }
}

/* ---------- 计时核心 ---------- */

function start() {
  if (isRunning) return;
  isRunning = true;
  endTime = Date.now() + remainingSeconds * 1000;
  intervalId = setInterval(tick, 200);
  startPauseBtn.textContent = '暂停';
  tick();
}

function pause() {
  if (!isRunning) return;
  isRunning = false;
  stopTicking();
  remainingSeconds = Math.max(0, Math.ceil((endTime - Date.now()) / 1000));
  startPauseBtn.textContent = '继续';
  updateDisplay();
}

function reset() {
  isRunning = false;
  stopTicking();
  remainingSeconds = totalSeconds;
  startPauseBtn.textContent = '开始';
  updateDisplay();
}

function stopTicking() {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
  }
}

function tick() {
  const remainingMs = endTime - Date.now();
  if (remainingMs <= 0) {
    complete();
    return;
  }
  remainingSeconds = Math.ceil(remainingMs / 1000);
  updateDisplay();
}

function complete() {
  isRunning = false;
  stopTicking();
  startPauseBtn.textContent = '开始';
  notify();
  switchModeAfterComplete();
}

/* ---------- 显示更新 ---------- */

function updateDisplay() {
  timeEl.textContent = formatTime(remainingSeconds);

  const elapsed = totalSeconds - remainingSeconds;
  const progress = totalSeconds > 0 ? elapsed / totalSeconds : 0;
  const offset = RING_CIRCUMFERENCE * (1 - progress);
  ringEl.style.strokeDashoffset = `${offset}`;

  modeLabelEl.textContent = MODE_LABELS[currentMode];
}

function updateBodyMode() {
  document.body.dataset.mode = currentMode;
}

function updateTabs() {
  modeTabs.forEach((tab) => {
    tab.classList.toggle('active', tab.dataset.mode === currentMode);
  });
}

function updateDots() {
  const interval = settings.longBreakInterval;
  const inCycle = completedPomodoros % interval === 0 && completedPomodoros > 0
    ? interval
    : completedPomodoros % interval;
  dotsEl.innerHTML = '';
  for (let i = 0; i < interval; i++) {
    const dot = document.createElement('span');
    dot.className = 'dot' + (i < inCycle ? ' filled' : '');
    dotsEl.appendChild(dot);
  }
}

/* ---------- 通知与提示音 ---------- */

function notify() {
  const title =
    currentMode === 'work' ? '番茄完成，休息一下吧！' : '休息结束，开始专注吧！';
  try {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(title, { silent: true });
    } else if ('Notification' in window && Notification.permission !== 'denied') {
      Notification.requestPermission().then((p) => {
        if (p === 'granted') new Notification(title, { silent: true });
      });
    }
  } catch (e) {
    /* 通知失败不影响计时 */
  }
  playBeep();
}

function playBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const play = (freq, start, duration) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0, ctx.currentTime + start);
      gain.gain.linearRampToValueAtTime(0.25, ctx.currentTime + start + 0.02);
      gain.gain.linearRampToValueAtTime(0, ctx.currentTime + start + duration);
      osc.connect(gain).connect(ctx.destination);
      osc.start(ctx.currentTime + start);
      osc.stop(ctx.currentTime + start + duration);
    };
    play(880, 0, 0.25);
    play(660, 0.28, 0.25);
  } catch (e) {
    /* 无声环境下忽略 */
  }
}

/* ---------- 设置面板 ---------- */

function openSettings() {
  inputWork.value = settings.work;
  inputShort.value = settings.shortBreak;
  inputLong.value = settings.longBreak;
  inputInterval.value = settings.longBreakInterval;
  settingsOverlay.classList.remove('hidden');
}

function closeSettings() {
  settingsOverlay.classList.add('hidden');
}

function readSettingsInputs() {
  const clamp = (v, min, max, fallback) => {
    const n = parseInt(v, 10);
    if (Number.isNaN(n)) return fallback;
    return Math.min(max, Math.max(min, n));
  };
  return {
    work: clamp(inputWork.value, 1, 120, DEFAULT_SETTINGS.work),
    shortBreak: clamp(inputShort.value, 1, 60, DEFAULT_SETTINGS.shortBreak),
    longBreak: clamp(inputLong.value, 1, 120, DEFAULT_SETTINGS.longBreak),
    longBreakInterval: clamp(
      inputInterval.value,
      1,
      12,
      DEFAULT_SETTINGS.longBreakInterval
    ),
  };
}

function saveSettings() {
  settings = readSettingsInputs();
  durations = settingsToSeconds(settings);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  updateDots();
  // 若当前计时处于未开始状态，则按新时长刷新显示
  if (!isRunning && remainingSeconds === totalSeconds) {
    setMode(currentMode);
  } else if (!isRunning) {
    totalSeconds = durations[currentMode];
    remainingSeconds = totalSeconds;
    updateDisplay();
  }
  closeSettings();
}

function resetDefaults() {
  settings = { ...DEFAULT_SETTINGS };
  durations = settingsToSeconds(settings);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  inputWork.value = settings.work;
  inputShort.value = settings.shortBreak;
  inputLong.value = settings.longBreak;
  inputInterval.value = settings.longBreakInterval;
  updateDots();
  if (!isRunning) setMode(currentMode);
}

/* ---------- 事件绑定 ---------- */

startPauseBtn.addEventListener('click', () => {
  if (isRunning) pause();
  else start();
});

resetBtn.addEventListener('click', reset);

modeTabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    if (tab.dataset.mode !== currentMode) setMode(tab.dataset.mode);
  });
});

settingsBtn.addEventListener('click', openSettings);
closeSettingsBtn.addEventListener('click', closeSettings);
themeToggleBtn.addEventListener('click', () => {
  const next =
    document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem(THEME_KEY, next);
});
saveSettingsBtn.addEventListener('click', saveSettings);
resetDefaultsBtn.addEventListener('click', resetDefaults);

settingsOverlay.addEventListener('click', (e) => {
  if (e.target === settingsOverlay) closeSettings();
});

document.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && settingsOverlay.classList.contains('hidden')) {
    // 空格仅在设置面板未打开时触发开始/暂停
    e.preventDefault();
    if (isRunning) pause();
    else start();
  }
  if (e.code === 'Escape') closeSettings();
});

/* ---------- 初始化 ---------- */

if (localStorage.getItem(THEME_KEY) === 'dark') {
  document.documentElement.dataset.theme = 'dark';
}

updateBodyMode();
updateTabs();
updateDots();
updateDisplay();
