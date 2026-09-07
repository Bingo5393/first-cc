// 微信朋友圈发布助手 —— 渲染进程逻辑
(function () {
  'use strict';

  // ---------- 状态 ----------
  const state = {
    sentences: [],
    templates: [],
    dataPath: '',
    filterCategory: '全部', // 当前分类筛选
    search: '',             // 当前搜索关键词
    editingId: null,        // 正在编辑的文案 id，null 表示新建
  };

  // ---------- DOM 引用 ----------
  const $ = (id) => document.getElementById(id);
  const el = {
    adbStatus: $('adbStatus'),
    btnNew: $('btnNew'),
    searchInput: $('searchInput'),
    categoryChips: $('categoryChips'),
    listCount: $('listCount'),
    sentenceList: $('sentenceList'),
    editorTitle: $('editorTitle'),
    contentInput: $('contentInput'),
    categoryInput: $('categoryInput'),
    tagsInput: $('tagsInput'),
    btnCopy: $('btnCopy'),
    btnCopyPhone: $('btnCopyPhone'),
    btnPublish: $('btnPublish'),
    btnSave: $('btnSave'),
    btnDelete: $('btnDelete'),
    templateList: $('templateList'),
    dataPath: $('dataPath'),
    toast: $('toast'),
  };

  // ---------- 工具 ----------
  function fmtTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const p = (n) => String(n).padStart(2, '0');
    return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }

  let toastTimer = null;
  function toast(msg) {
    el.toast.textContent = msg;
    el.toast.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.toast.classList.add('hidden'), 2600);
  }

  // 设置手机连接状态
  function setAdbStatus(kind, text) {
    el.adbStatus.className = 'status ' + kind;
    el.adbStatus.textContent = text;
  }

  // ---------- 渲染 ----------
  function getCategories() {
    const set = new Set();
    state.sentences.forEach((s) => {
      if (s.category) set.add(s.category);
    });
    return Array.from(set);
  }

  function renderChips() {
    const cats = getCategories();
    const chips = ['全部', ...cats];
    el.categoryChips.innerHTML = '';
    chips.forEach((c) => {
      const chip = document.createElement('span');
      chip.className = 'chip' + (c === state.filterCategory ? ' active' : '');
      chip.textContent = c;
      chip.addEventListener('click', () => {
        state.filterCategory = c;
        renderChips();
        renderList();
      });
      el.categoryChips.appendChild(chip);
    });
  }

  function filteredSentences() {
    const kw = state.search.trim().toLowerCase();
    return state.sentences.filter((s) => {
      // 分类筛选
      if (state.filterCategory !== '全部' && s.category !== state.filterCategory) return false;
      // 关键词搜索（内容 / 分类 / 标签）
      if (kw) {
        const hay = (s.content + ' ' + s.category + ' ' + (s.tags || []).join(' ')).toLowerCase();
        if (!hay.includes(kw)) return false;
      }
      return true;
    });
  }

  function renderList() {
    const list = filteredSentences();
    el.listCount.textContent = list.length ? `${list.length} 条` : '';
    el.sentenceList.innerHTML = '';

    if (!list.length) {
      const empty = document.createElement('div');
      empty.className = 'empty';
      empty.textContent = state.sentences.length ? '没有匹配的文案' : '还没有文案，点右上角「新建文案」开始吧';
      el.sentenceList.appendChild(empty);
      return;
    }

    list.forEach((s) => {
      const li = document.createElement('li');
      li.className = 'list-item' + (s.id === state.editingId ? ' active' : '');

      const preview = document.createElement('div');
      preview.className = 'item-preview';
      preview.textContent = s.content;

      const meta = document.createElement('div');
      meta.className = 'item-meta';
      if (s.category) {
        const cat = document.createElement('span');
        cat.className = 'item-cat';
        cat.textContent = s.category;
        meta.appendChild(cat);
      }
      (s.tags || []).forEach((t) => {
        const tag = document.createElement('span');
        tag.className = 'item-tag';
        tag.textContent = '#' + t;
        meta.appendChild(tag);
      });
      if (s.lastCopiedAt) {
        const copied = document.createElement('span');
        copied.className = 'item-copied';
        copied.textContent = '复制于 ' + fmtTime(s.lastCopiedAt);
        meta.appendChild(copied);
      }

      li.appendChild(preview);
      li.appendChild(meta);
      li.addEventListener('click', () => startEdit(s.id));
      el.sentenceList.appendChild(li);
    });
  }

  function renderTemplates() {
    el.templateList.innerHTML = '';
    state.templates.forEach((t) => {
      const li = document.createElement('li');
      li.className = 'template-item';

      const name = document.createElement('div');
      name.className = 'template-name';
      name.textContent = t.name;

      const cat = document.createElement('div');
      cat.className = 'template-cat';
      cat.textContent = t.category;

      const preview = document.createElement('div');
      preview.className = 'template-preview';
      preview.textContent = t.content;

      li.appendChild(name);
      li.appendChild(cat);
      li.appendChild(preview);
      li.title = '点击套用该模板';
      li.addEventListener('click', () => applyTemplate(t));
      el.templateList.appendChild(li);
    });
  }

  function renderEditor() {
    if (state.editingId) {
      const s = state.sentences.find((x) => x.id === state.editingId);
      if (s) {
        el.editorTitle.textContent = '编辑文案';
        el.contentInput.value = s.content;
        el.categoryInput.value = s.category || '';
        el.tagsInput.value = (s.tags || []).join(', ');
        el.btnDelete.disabled = false;
        return;
      }
    }
    // 新建状态
    el.editorTitle.textContent = '新建文案';
    el.contentInput.value = '';
    el.categoryInput.value = '';
    el.tagsInput.value = '';
    el.btnDelete.disabled = true;
  }

  function renderAll() {
    renderChips();
    renderList();
    renderTemplates();
    renderEditor();
  }

  // ---------- 编辑动作 ----------
  function startEdit(id) {
    state.editingId = id;
    renderList();
    renderEditor();
    el.contentInput.focus();
  }

  function startNew() {
    state.editingId = null;
    renderList();
    renderEditor();
    el.contentInput.focus();
  }

  // 解析标签输入框为数组
  function parseTags() {
    return el.tagsInput.value
      .split(/[,，、]/)
      .map((t) => t.trim())
      .filter(Boolean);
  }

  async function save() {
    const content = el.contentInput.value.trim();
    if (!content) {
      toast('⚠️ 文案内容不能为空');
      el.contentInput.focus();
      return;
    }
    const payload = {
      content,
      category: el.categoryInput.value.trim(),
      tags: parseTags(),
    };

    if (state.editingId) {
      const res = await window.api.updateSentence({ ...payload, id: state.editingId });
      if (!res.ok) return toast('⚠️ ' + (res.error || '保存失败'));
      const idx = state.sentences.findIndex((s) => s.id === state.editingId);
      if (idx !== -1) state.sentences[idx] = res.sentence;
      toast('✅ 已保存');
    } else {
      const res = await window.api.addSentence(payload);
      if (!res.ok) return toast('⚠️ ' + (res.error || '保存失败'));
      state.sentences.unshift(res.sentence);
      state.editingId = res.sentence.id;
      toast('✅ 已新建并保存');
    }
    renderAll();
  }

  async function remove() {
    if (!state.editingId) return;
    const s = state.sentences.find((x) => x.id === state.editingId);
    const ok = confirm(`确定删除这条文案吗？\n\n${(s && s.content || '').slice(0, 60)}`);
    if (!ok) return;
    const res = await window.api.deleteSentence(state.editingId);
    if (!res.ok) return toast('⚠️ ' + (res.error || '删除失败'));
    state.sentences = state.sentences.filter((x) => x.id !== state.editingId);
    state.editingId = null;
    toast('🗑️ 已删除');
    renderAll();
  }

  // 应用模板到编辑器
  function applyTemplate(t) {
    el.contentInput.value = t.content;
    if (t.category && !el.categoryInput.value) el.categoryInput.value = t.category;
    el.editorTitle.textContent = '编辑文案（来自模板：' + t.name + '）';
    el.contentInput.focus();
    toast('📋 已套用模板「' + t.name + '」');
  }

  // ---------- 复制 ----------
  async function copyToPC() {
    const text = el.contentInput.value;
    if (!text.trim()) return toast('⚠️ 没有可复制的内容');
    const res = await window.api.copy(text, state.editingId || undefined);
    if (!res.ok) return toast('⚠️ ' + (res.error || '复制失败'));
    // 更新内存中的复制时间并刷新列表
    if (state.editingId) {
      const s = state.sentences.find((x) => x.id === state.editingId);
      if (s) s.lastCopiedAt = new Date().toISOString();
      renderList();
    }
    toast('📋 已复制到电脑剪贴板，可去微信粘贴');
  }

  async function copyToPhone() {
    const text = el.contentInput.value;
    if (!text.trim()) return toast('⚠️ 没有可复制的内容');
    el.btnCopyPhone.disabled = true;
    try {
      const res = await window.api.copyToPhone(text, state.editingId || undefined);
      if (!res.ok) {
        toast('⚠️ ' + (res.error || '复制到手机失败'));
        return;
      }
      if (state.editingId) {
        const s = state.sentences.find((x) => x.id === state.editingId);
        if (s) s.lastCopiedAt = new Date().toISOString();
        renderList();
      }
      toast('📱 已复制到手机剪贴板');
    } finally {
      el.btnCopyPhone.disabled = false;
    }
  }

  // 自动发布到朋友圈（分身微信）
  async function publish() {
    const text = el.contentInput.value;
    if (!text.trim()) return toast('⚠️ 文案内容不能为空');
    // 发布涉及多步 UI 操作、耗时较长，禁用按钮防重复点击
    el.btnPublish.disabled = true;
    el.btnPublish.textContent = '⏳ 发布中…';
    try {
      const res = await window.api.publishToMoments(text);
      if (!res.ok) {
        toast('⚠️ ' + (res.error || '发布失败'));
        return;
      }
      toast('✅ 已发布到朋友圈');
    } finally {
      el.btnPublish.disabled = false;
      el.btnPublish.textContent = '📱 自动发布';
    }
  }

  // ---------- 手机连接检测 ----------
  async function checkPhone() {
    try {
      const res = await window.api.checkAdb();
      if (!res.adb) {
        setAdbStatus('status-bad', '未检测到 ADB');
      } else if (!res.device) {
        setAdbStatus('status-bad', '未连接手机');
      } else {
        setAdbStatus('status-ok', '手机已连接');
      }
    } catch (e) {
      setAdbStatus('status-bad', '检测失败');
    }
  }

  // ---------- 初始化 ----------
  async function init() {
    const data = await window.api.load();
    state.sentences = data.sentences;
    state.templates = data.templates;
    state.dataPath = data.dataPath;
    el.dataPath.textContent = '数据文件：' + data.dataPath;
    renderAll();
    checkPhone();
  }

  // ---------- 事件绑定 ----------
  el.btnNew.addEventListener('click', startNew);
  el.btnSave.addEventListener('click', save);
  el.btnDelete.addEventListener('click', remove);
  el.btnCopy.addEventListener('click', copyToPC);
  el.btnCopyPhone.addEventListener('click', copyToPhone);
  el.btnPublish.addEventListener('click', publish);

  // 搜索（防抖）
  let searchTimer = null;
  el.searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.search = el.searchInput.value;
      renderList();
    }, 180);
  });

  // 键盘快捷键：Ctrl/Cmd + S 保存
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
      e.preventDefault();
      save();
    }
  });

  init();
})();
