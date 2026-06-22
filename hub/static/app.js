/**
 * AITrainScripts Hub — 前端逻辑
 */

const PAGE_META = {
  workflow: {
    title: 'LoRA 工作流',
    subtitle: '转换/缩放 → 输出 → 批量重命名，一键完成数据准备',
  },
  video: {
    title: '豆包视频',
    subtitle: 'Seedance 1.5-pro 文/图/音视频参考生成视频（火山方舟 API，默认 480p）',
  },
  convert: {
    title: '格式转换',
    subtitle: '多格式转 PNG；按目标像素总面积智能缩放（非固定输出宽高）',
  },
  toIco: {
    title: '转 ICO',
    subtitle: 'PNG/JPG/WebP 等批量转为 Windows 多尺寸 .ico 图标',
  },
  compress: {
    title: '图片压缩',
    subtitle: '将图片压缩到指定 KB/MB 以内（质量优先，必要时缩小尺寸）',
  },
  formatConvert: {
    title: '格式互转',
    subtitle: 'PNG/JPEG/WebP/BMP/GIF/TIFF 互转，保持原始分辨率',
  },
  resizeCanvas: {
    title: '画布填充',
    subtitle: '等比缩放后居中放入指定宽高的透明画布',
  },
  crop2k: {
    title: '区域裁剪',
    subtitle: '2560×1440 PNG 固定区域裁剪，保持目录结构',
  },
  filter2k: {
    title: '尺寸筛选',
    subtitle: '仅保留指定宽高，删除其余文件（请先预览）',
  },
  rename: {
    title: '批量重命名',
    subtitle: '前缀编号或纯序号，默认仅预览',
  },
  mp4ToMp3: {
    title: 'MP4 转 MP3',
    subtitle: '批量从视频中提取 MP3 音频（需 ffmpeg）',
  },
};

const PAGE_TO_SECTION = {
  rename: 'image',
  workflow: 'image',
  convert: 'image',
  resizeCanvas: 'image',
  crop2k: 'image',
  filter2k: 'image',
  video: 'av',
  mp4ToMp3: 'av',
};

const NAV_SECTIONS_KEY = 'hub-nav-sections-v1';

let activePage = 'workflow';
let browseTargetInput = null;
let browseCurrentPath = null;
let browseMode = 'dir';
let renameMode = 'numbered';
let filterPreviewDone = false;
let busy = false;

// --- 表单参数持久化（localStorage）---

const FORM_STORAGE_KEY = 'hub-form-v1';
const LAST_PAGE_KEY = 'hub-last-page';
const SHARED_PATHS_KEY = 'hub-shared-paths';

function readSharedPaths() {
  try {
    return JSON.parse(localStorage.getItem(SHARED_PATHS_KEY)) || {};
  } catch {
    return {};
  }
}

function writeSharedPaths(paths) {
  localStorage.setItem(SHARED_PATHS_KEY, JSON.stringify(paths));
}

/** 从各模块表单字段同步「常用输入/输出目录」，便于跨页面复用。 */
function syncSharedPaths(pageKey, data) {
  if (!data) return;
  const shared = readSharedPaths();
  const input =
    data.source || data.target || data.input || data.dir || data.folder;
  if (input && String(input).trim()) shared.input = String(input).trim();
  const output = data.output;
  if (output && String(output).trim()) shared.output = String(output).trim();
  writeSharedPaths(shared);
}

function withSharedPaths(data, inputKeys, outputKey) {
  const shared = readSharedPaths();
  const out = { ...data };
  for (const key of inputKeys) {
    if (!out[key] && shared.input) out[key] = shared.input;
  }
  if (outputKey && !out[outputKey] && shared.output) out[outputKey] = shared.output;
  return out;
}

function readFormStore() {
  try {
    return JSON.parse(localStorage.getItem(FORM_STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

function writeFormStore(store) {
  localStorage.setItem(FORM_STORAGE_KEY, JSON.stringify(store));
}

function fieldVal(id) {
  const el = document.getElementById(id);
  if (!el) return undefined;
  if (el.type === 'checkbox') return el.checked;
  return el.value;
}

function setField(id, value) {
  const el = document.getElementById(id);
  if (!el || value === undefined) return;
  if (el.type === 'checkbox') el.checked = Boolean(value);
  else el.value = value;
}

function applyWfRenameMode(mode) {
  wfRenameMode = mode || 'numbered';
  document.querySelectorAll('.wf-rename-tab').forEach((t) => {
    t.classList.toggle('active', t.dataset.wfRename === wfRenameMode);
  });
  document.getElementById('wf-numbered-fields')?.classList.toggle('hidden', wfRenameMode !== 'numbered');
  document.getElementById('wf-sequential-fields')?.classList.toggle('hidden', wfRenameMode !== 'sequential');
}

function applyRenameMode(mode) {
  renameMode = mode || 'numbered';
  document.querySelectorAll('.rename-tab').forEach((t) => {
    t.classList.toggle('active', t.dataset.renameMode === renameMode);
  });
  document.getElementById('rename-numbered-fields')?.classList.toggle('hidden', renameMode !== 'numbered');
  document.getElementById('rename-sequential-fields')?.classList.toggle('hidden', renameMode !== 'sequential');
}

function collectWorkflowForm() {
  return {
    source: fieldVal('wf-source'),
    output: fieldVal('wf-output'),
    width: fieldVal('wf-width'),
    height: fieldVal('wf-height'),
    mode: document.querySelector('input[name="wf-mode"]:checked')?.value || 'area_64',
    recursive: fieldVal('wf-recursive'),
    renameMode: wfRenameMode,
    prefix: fieldVal('wf-prefix'),
    start_num: fieldVal('wf-start-num'),
    digits: fieldVal('wf-digits'),
    start_index: fieldVal('wf-start-index'),
    sync_captions: fieldVal('wf-sync-captions'),
  };
}

function restoreWorkflowForm(data) {
  data = withSharedPaths(data || {}, ['source'], 'output');
  if (!data) return;
  setField('wf-source', data.source);
  setField('wf-output', data.output);
  setField('wf-width', data.width);
  setField('wf-height', data.height);
  setField('wf-recursive', data.recursive);
  setField('wf-prefix', data.prefix);
  setField('wf-start-num', data.start_num);
  setField('wf-digits', data.digits);
  setField('wf-start-index', data.start_index);
  setField('wf-sync-captions', data.sync_captions);
  if (data.mode) {
    const radio = document.querySelector(`input[name="wf-mode"][value="${data.mode}"]`);
    if (radio) radio.checked = true;
  }
  applyWfRenameMode(data.renameMode);
}

function collectVideoForm() {
  return {
    prompt: fieldVal('video-prompt'),
    model: fieldVal('video-model'),
    ratio: fieldVal('video-ratio'),
    resolution: fieldVal('video-resolution'),
    duration: fieldVal('video-duration'),
    generate_audio: fieldVal('video-generate-audio'),
    watermark: fieldVal('video-watermark'),
    output: fieldVal('video-output'),
    references: collectVideoRefs(),
  };
}

function restoreVideoForm(data) {
  if (!data) return;
  setField('video-prompt', data.prompt);
  setField('video-model', data.model);
  setField('video-ratio', data.ratio);
  setField('video-resolution', data.resolution);
  setField('video-output', data.output);
  setField('video-generate-audio', data.generate_audio);
  setField('video-watermark', data.watermark);
  restoreVideoRefs(data.references);
  if (data.duration != null) {
    setField('video-duration', data.duration);
  }
  syncVideoOptions();
}

function collectConvertForm() {
  return {
    target: fieldVal('convert-target'),
    output: fieldVal('convert-output'),
    w: fieldVal('convert-w'),
    h: fieldVal('convert-h'),
    recursive: fieldVal('convert-recursive'),
    rename: fieldVal('convert-rename'),
  };
}

function restoreConvertForm(data) {
  data = withSharedPaths(data || {}, ['target'], 'output');
  if (!data) return;
  setField('convert-target', data.target);
  setField('convert-output', data.output);
  setField('convert-w', data.w);
  setField('convert-h', data.h);
  setField('convert-recursive', data.recursive);
  setField('convert-rename', data.rename);
}

function collectResizeForm() {
  return {
    input: fieldVal('resize-input'),
    output: fieldVal('resize-output'),
    w: fieldVal('resize-w'),
    h: fieldVal('resize-h'),
    recursive: fieldVal('resize-recursive'),
  };
}

function restoreResizeForm(data) {
  data = withSharedPaths(data || {}, ['input'], 'output');
  if (!data) return;
  setField('resize-input', data.input);
  setField('resize-output', data.output);
  setField('resize-w', data.w);
  setField('resize-h', data.h);
  setField('resize-recursive', data.recursive);
}

function collectCropForm() {
  return {
    input: fieldVal('crop-input'),
    output: fieldVal('crop-output'),
  };
}

function restoreCropForm(data) {
  data = withSharedPaths(data || {}, ['input'], 'output');
  if (!data) return;
  setField('crop-input', data.input);
  setField('crop-output', data.output);
}

function collectFilterForm() {
  return {
    dir: fieldVal('filter-dir'),
    w: fieldVal('filter-w'),
    h: fieldVal('filter-h'),
  };
}

function restoreFilterForm(data) {
  data = withSharedPaths(data || {}, ['dir'], null);
  if (!data) return;
  setField('filter-dir', data.dir);
  setField('filter-w', data.w);
  setField('filter-h', data.h);
}

function collectRenameForm() {
  return {
    mode: renameMode,
    folder: fieldVal('rename-folder'),
    prefix: fieldVal('rename-prefix'),
    start_num: fieldVal('rename-start-num'),
    digits: fieldVal('rename-digits'),
    start_index: fieldVal('rename-start-index'),
    dry_run: fieldVal('rename-dry-run'),
  };
}

function restoreRenameForm(data) {
  data = withSharedPaths(data || {}, ['folder'], null);
  if (!data) return;
  setField('rename-folder', data.folder);
  setField('rename-prefix', data.prefix);
  setField('rename-start-num', data.start_num);
  setField('rename-digits', data.digits);
  setField('rename-start-index', data.start_index);
  setField('rename-dry-run', data.dry_run);
  applyRenameMode(data.mode);
}

function collectMp4Form() {
  return {
    input: fieldVal('mp3-input'),
    output: fieldVal('mp3-output'),
    recursive: fieldVal('mp3-recursive'),
    overwrite: fieldVal('mp3-overwrite'),
  };
}

function restoreMp4Form(data) {
  data = withSharedPaths(data || {}, ['input'], 'output');
  if (!data) return;
  setField('mp3-input', data.input);
  setField('mp3-output', data.output);
  setField('mp3-recursive', data.recursive);
  setField('mp3-overwrite', data.overwrite);
}

const FORM_COLLECTORS = {
  workflow: collectWorkflowForm,
  video: collectVideoForm,
  convert: collectConvertForm,
  resizeCanvas: collectResizeForm,
  crop2k: collectCropForm,
  filter2k: collectFilterForm,
  rename: collectRenameForm,
  mp4ToMp3: collectMp4Form,
};

const FORM_RESTORERS = {
  workflow: restoreWorkflowForm,
  video: restoreVideoForm,
  convert: restoreConvertForm,
  resizeCanvas: restoreResizeForm,
  crop2k: restoreCropForm,
  filter2k: restoreFilterForm,
  rename: restoreRenameForm,
  mp4ToMp3: restoreMp4Form,
};

function saveFormState(pageKey) {
  const collect = FORM_COLLECTORS[pageKey];
  if (!collect) return;
  const data = collect();
  const store = readFormStore();
  store[pageKey] = data;
  writeFormStore(store);
  syncSharedPaths(pageKey, data);
}

function restoreAllFormState() {
  const store = readFormStore();
  for (const [key, restore] of Object.entries(FORM_RESTORERS)) {
    restore(store[key]);
  }
}

function bindFormAutoSave(pageKey, panelId) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  let timer;
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(() => saveFormState(pageKey), 400);
  };
  panel.addEventListener('input', schedule);
  panel.addEventListener('change', schedule);
}

function bindAllFormAutoSave() {
  bindFormAutoSave('workflow', 'page-workflow');
  bindFormAutoSave('video', 'page-video');
  bindFormAutoSave('convert', 'page-convert');
  bindFormAutoSave('resizeCanvas', 'page-resizeCanvas');
  bindFormAutoSave('crop2k', 'page-crop2k');
  bindFormAutoSave('filter2k', 'page-filter2k');
  bindFormAutoSave('rename', 'page-rename');
  bindFormAutoSave('mp4ToMp3', 'page-mp4ToMp3');
}

// --- Theme ---

function applyTheme(mode) {
  const root = document.documentElement;
  if (mode === 'system') {
    const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.classList.toggle('dark', dark);
  } else {
    root.classList.toggle('dark', mode === 'dark');
  }
  localStorage.setItem('theme', mode);
}

function initTheme() {
  const saved = localStorage.getItem('theme') || 'system';
  const select = document.getElementById('theme-select');
  select.value = saved;
  applyTheme(saved);
  select.addEventListener('change', () => applyTheme(select.value));
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (localStorage.getItem('theme') === 'system') applyTheme('system');
  });
}

// --- Navigation ---

function readNavSections() {
  try {
    return JSON.parse(localStorage.getItem(NAV_SECTIONS_KEY)) || {};
  } catch {
    return {};
  }
}

function writeNavSections(state) {
  localStorage.setItem(NAV_SECTIONS_KEY, JSON.stringify(state));
}

function setSectionCollapsed(sectionId, collapsed) {
  const section = document.querySelector(`.nav-section[data-section="${sectionId}"]`);
  if (!section) return;
  section.classList.toggle('collapsed', collapsed);
  const toggle = section.querySelector('.nav-section-toggle');
  if (toggle) toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
}

function expandNavSection(sectionId) {
  const state = readNavSections();
  state[sectionId] = false;
  writeNavSections(state);
  setSectionCollapsed(sectionId, false);
}

function initNavSections() {
  const state = readNavSections();
  document.querySelectorAll('.nav-section').forEach((section) => {
    const id = section.dataset.section;
    const collapsed = Boolean(state[id]);
    setSectionCollapsed(id, collapsed);
  });
}

function showPage(page) {
  activePage = page;
  localStorage.setItem(LAST_PAGE_KEY, page);
  document.querySelectorAll('.page-panel').forEach((el) => el.classList.add('hidden'));
  const panel = document.getElementById(`page-${page}`);
  if (panel) panel.classList.remove('hidden');

  document.querySelectorAll('.nav-item').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.page === page);
  });

  const sectionId = PAGE_TO_SECTION[page];
  if (sectionId) expandNavSection(sectionId);

  const meta = PAGE_META[page] || PAGE_META.workflow;
  document.getElementById('page-title').textContent = meta.title;
  document.getElementById('page-subtitle').textContent = meta.subtitle;

  if (page === 'video') {
    refreshVideoQueue();
    startVideoQueuePolling();
  } else {
    stopVideoQueuePolling();
  }
}

// --- API ---

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

const JOB_TYPE_LABELS = {
  'video-generate': '豆包视频',
  workflow: 'LoRA 工作流',
  convert: '格式转换',
  'resize-canvas': '画布填充',
  'crop-2k': '区域裁剪',
  'filter-2k': '尺寸筛选',
  rename: '批量重命名',
  'mp4-to-mp3': 'MP4 转 MP3',
};

const JOB_STATUS_LABELS = {
  pending: '排队中',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
};

const ENDPOINT_JOB_TYPE = {
  '/api/jobs/video-generate': 'video-generate',
  '/api/jobs/workflow': 'workflow',
  '/api/jobs/convert': 'convert',
  '/api/jobs/resize-canvas': 'resize-canvas',
  '/api/jobs/crop-2k': 'crop-2k',
  '/api/jobs/filter-2k': 'filter-2k',
  '/api/jobs/rename': 'rename',
  '/api/jobs/mp4-to-mp3': 'mp4-to-mp3',
};

function formatElapsed(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const mins = Math.floor(s / 60);
  const secs = s % 60;
  return mins > 0 ? `${mins} 分 ${secs} 秒` : `${secs} 秒`;
}

function setLogPanelState(state) {
  const panel = document.getElementById('log-panel');
  const bar = document.getElementById('log-progress-wrap');
  if (!panel) return;
  panel.classList.remove('log-running', 'log-success', 'log-error');
  if (state === 'running') {
    panel.classList.add('log-running');
    bar?.classList.remove('hidden');
  } else if (state === 'success') {
    panel.classList.add('log-success');
    bar?.classList.add('hidden');
  } else if (state === 'error') {
    panel.classList.add('log-error');
    bar?.classList.add('hidden');
  } else {
    bar?.classList.add('hidden');
  }
}

function appendLog(summary, lines, { running = false, success = false, error = false } = {}) {
  document.getElementById('log-summary').textContent = summary;
  const body = document.getElementById('log-body');
  body.textContent = lines.join('\n') || '（无详情）';
  body.scrollTop = body.scrollHeight;
  if (running) setLogPanelState('running');
  else if (success) setLogPanelState('success');
  else if (error) setLogPanelState('error');
  else setLogPanelState('idle');

  if (running) {
    document.getElementById('log-panel')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function buildProgressLines(job, elapsedSec) {
  const lines = [...(job.progress_lines || [])];
  const latest = job.progress_message;

  if (lines.length === 0) {
    if (job.status === 'pending') {
      lines.push('[等待] 任务已提交，等待后台线程启动…');
    } else if (job.type === 'video-generate') {
      if (elapsedSec < 20) {
        lines.push('[提示] 正在连接火山方舟 API…');
      } else if (elapsedSec < 90) {
        lines.push('[提示] 视频生成通常需 1–5 分钟，请耐心等待');
      } else {
        lines.push(`[提示] 仍在处理中，已等待 ${formatElapsed(elapsedSec)}，请勿关闭页面`);
      }
    } else {
      lines.push(`[提示] 后台处理中，已等待 ${formatElapsed(elapsedSec)}…`);
    }
  } else if (latest && lines.every((line) => !line.includes(latest))) {
    lines.push(`[最新] ${latest}`);
  }

  const now = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  lines.push(`[心跳] ${now} · 任务仍在线，持续轮询中…`);
  return lines;
}

function updateJobProgressUI(job, startedMs) {
  const elapsedSec = (Date.now() - startedMs) / 1000;
  const typeLabel = JOB_TYPE_LABELS[job.type] || job.type || '任务';
  const statusLabel = JOB_STATUS_LABELS[job.status] || job.status;
  const summary = `${typeLabel} · ${statusLabel} · 已用时 ${formatElapsed(elapsedSec)}`;
  appendLog(summary, buildProgressLines(job, elapsedSec), { running: true });
}

async function pollJob(jobId, { jobType } = {}) {
  const maxAttempts = 3600;
  const startedMs = Date.now();
  const pollMs = jobType === 'video-generate' ? 2000 : 1000;

  for (let i = 0; i < maxAttempts; i++) {
    const job = await api(`/api/jobs/${jobId}`);
    if (job.status === 'completed' || job.status === 'failed') {
      return job;
    }
    updateJobProgressUI(job, startedMs);
    await new Promise((r) => setTimeout(r, pollMs));
  }
  throw new Error('任务超时（超过 1 小时）');
}

function setBusy(isBusy) {
  busy = isBusy;
  document.querySelectorAll('.btn-primary, .btn-secondary, .btn-danger').forEach((btn) => {
    if (!btn.id?.startsWith('log-')) btn.disabled = isBusy;
  });
  if (!isBusy) {
    const deleteBtn = document.getElementById('btn-filter-delete');
    const backupCheck = document.getElementById('filter-backup-check');
    if (deleteBtn && backupCheck) deleteBtn.disabled = !backupCheck.checked;
  }
}

function formatJobResult(job) {
  const progress = job.progress_lines || [];
  if (job.status === 'failed') {
    return {
      summary: `失败：${job.error}`,
      lines: [...progress, job.error || '未知错误'],
      error: true,
    };
  }
  const r = job.result;
  if (!r) {
    return { summary: '完成（无结果数据）', lines: progress, success: true };
  }
  const summary = `${r.message} · 处理 ${r.processed} · 跳过 ${r.skipped}`;
  const lines = [
    ...(r.details || progress),
    ...(r.errors || []).map((e) => `错误: ${e}`),
  ];
  return { summary, lines, success: r.ok !== false };
}

async function runJob(endpoint, body, formKey) {
  if (formKey) saveFormState(formKey);
  setBusy(true);
  const jobType = ENDPOINT_JOB_TYPE[endpoint] || 'task';
  const typeLabel = JOB_TYPE_LABELS[jobType] || '任务';
  appendLog(`${typeLabel} · 正在提交…`, ['[步骤] 创建后台任务并排队'], { running: true });
  try {
    const { job_id } = await api(endpoint, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    appendLog(
      `${typeLabel} · 已提交`,
      [`[步骤] 任务 ID: ${job_id}`, '[步骤] 开始轮询进度…'],
      { running: true },
    );
    const job = await pollJob(job_id, { jobType });
    const { summary, lines, success, error } = formatJobResult(job);
    appendLog(summary, lines, { success, error: error || !success });
    return job;
  } catch (e) {
    appendLog(`出错 · ${typeLabel}`, [String(e.message || e)], { error: true });
    throw e;
  } finally {
    setBusy(false);
  }
}

// --- Health ---

async function loadHealth() {
  const el = document.getElementById('health-dots');
  try {
    const data = await api('/api/health');
    const deps = data.dependencies || {};
    const labels = {
      pillow: 'Pillow',
      pillow_heif: 'HEIF',
      natsort: 'natsort',
      ffmpeg: 'ffmpeg',
      ark_api_key: 'ARK Key',
    };
    el.innerHTML = Object.entries(labels)
      .map(([key, label]) => {
        const ok = deps[key];
        return `<span class="health-dot ${ok ? 'ok' : 'fail'}" title="${label}"></span>`;
      })
      .join('');
  } catch {
    el.textContent = 'API 离线';
  }
}

// --- Browse modal ---

async function openBrowse(inputEl, mode = 'dir') {
  browseTargetInput = inputEl;
  browseMode = mode;
  const start = inputEl.value.trim() || null;
  const title = document.getElementById('browse-title');
  const selectBtn = document.getElementById('browse-select');
  const hint = document.getElementById('browse-hint');
  if (mode === 'media') {
    title.textContent = '选择媒体文件';
    selectBtn.classList.add('hidden');
    hint.classList.remove('hidden');
    hint.textContent = '点击文件夹进入，点击文件即可选中';
  } else {
    title.textContent = '选择文件夹';
    selectBtn.classList.remove('hidden');
    hint.classList.add('hidden');
  }
  await loadBrowseList(start);
  document.getElementById('browse-modal').classList.remove('hidden');
}

async function loadBrowseList(path) {
  const q = path ? `?path=${encodeURIComponent(path)}` : '';
  const endpoint = browseMode === 'media' ? '/api/browse/media' : '/api/browse';
  const data = await api(`${endpoint}${q}`);
  browseCurrentPath = data.current;
  document.getElementById('browse-current').textContent = data.current;
  const list = document.getElementById('browse-list');
  list.innerHTML = '';
  for (const entry of data.entries) {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.type = 'button';
    if (entry.is_dir) {
      btn.textContent = entry.name === '..' ? '⬆️ ..' : `📁 ${entry.name}`;
    } else {
      btn.textContent = `📄 ${entry.name}`;
    }
    btn.addEventListener('click', () => {
      if (entry.is_dir) {
        loadBrowseList(entry.path);
        return;
      }
      if (browseMode === 'media' && browseTargetInput) {
        browseTargetInput.value = entry.path;
        const row = browseTargetInput.closest('.video-ref-row');
        if (row) {
          updateVideoRefHint(row, entry.path, entry.name);
          validateVideoRefPath(row);
        }
        closeBrowse();
        syncVideoOptions();
        maybePreferAdaptiveRatio();
        return;
      }
      loadBrowseList(entry.path);
    });
    li.appendChild(btn);
    list.appendChild(li);
  }
}

function closeBrowse() {
  document.getElementById('browse-modal').classList.add('hidden');
  browseTargetInput = null;
  browseMode = 'dir';
}

function confirmBrowse() {
  if (browseTargetInput && browseCurrentPath) {
    browseTargetInput.value = browseCurrentPath;
  }
  closeBrowse();
}

async function uploadVideoRefFile(row, file) {
  const typeSel = row.querySelector('.ref-type');
  const refType = typeSel.value;
  const hint = row.querySelector('.ref-hint');
  const urlInput = row.querySelector('.ref-url');
  hint.textContent = `上传中: ${file.name}…`;

  const form = new FormData();
  form.append('file', file);
  form.append('ref_type', refType);

  const res = await fetch('/api/video/stage-media', { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  const data = await res.json();
  urlInput.value = data.path;
  if (data.detected_type && data.detected_type !== refType) {
    typeSel.value = data.detected_type;
    fillRefRoleOptions(
      row.querySelector('.ref-role'),
      data.detected_type,
      defaultRefRole(data.detected_type),
    );
  }
  updateVideoRefHint(row, data.path, data.name, data.size);
  syncVideoOptions();
  maybePreferAdaptiveRatio();
}

const VIDEO_REF_ROLES = {
  image_url: [
    { value: 'reference_image', label: '参考图', title: '作为人物、风格或构图参考' },
    { value: 'first_frame', label: '首帧', title: '生成视频的第一帧画面' },
    { value: 'last_frame', label: '尾帧', title: '生成视频的最后一帧画面' },
  ],
  video_url: [
    { value: 'reference_video', label: '参考视频', title: '参考镜头运动、场景或动作' },
  ],
  audio_url: [
    { value: 'reference_audio', label: '参考音频', title: '参考背景音乐或对白节奏' },
  ],
};

function defaultRefRole(refType) {
  return VIDEO_REF_ROLES[refType]?.[0]?.value || 'reference_image';
}

function fillRefRoleOptions(roleSel, refType, selected) {
  const roles = VIDEO_REF_ROLES[refType] || VIDEO_REF_ROLES.image_url;
  const pick = roles.some((r) => r.value === selected) ? selected : roles[0].value;
  roleSel.innerHTML = roles
    .map(
      (r) =>
        `<option value="${r.value}" title="${r.title}">${r.label}</option>`,
    )
    .join('');
  roleSel.value = pick;
}

function updateVideoRefHint(row, path, name, size, status) {
  const hint = row.querySelector('.ref-hint');
  const sizeText = size != null ? ` (${(size / 1024).toFixed(0)} KB)` : '';
  const display = name || path.split('/').pop() || path;
  hint.classList.remove('text-red-500', 'text-emerald-600', 'dark:text-emerald-400');
  if (status === 'error') {
    hint.classList.add('text-red-500');
    hint.textContent = path;
    return;
  }
  if (status === 'ok') {
    hint.classList.add('text-emerald-600', 'dark:text-emerald-400');
  }
  hint.textContent = status === 'ok'
    ? `已就绪: ${display}${sizeText}`
    : `已选: ${display}${sizeText}`;
}

async function validateVideoRefPath(row) {
  const urlInput = row.querySelector('.ref-url');
  const refType = row.querySelector('.ref-type').value;
  const raw = urlInput.value.trim();
  if (!raw) {
    row.querySelector('.ref-hint').textContent = '';
    return true;
  }
  if (raw.startsWith('http://') || raw.startsWith('https://') || raw.startsWith('data:')) {
    updateVideoRefHint(row, raw, raw.split('/').pop() || '远程链接');
    return true;
  }

  const hint = row.querySelector('.ref-hint');
  hint.textContent = '正在校验路径…';
  hint.classList.remove('text-red-500', 'text-emerald-600', 'dark:text-emerald-400');
  try {
    const q = new URLSearchParams({ path: raw, ref_type: refType });
    const data = await api(`/api/video/check-media?${q}`);
    updateVideoRefHint(row, data.path, data.name, data.size, 'ok');
    if (data.path && data.path !== raw) {
      urlInput.value = data.path;
    }
    return true;
  } catch (e) {
    updateVideoRefHint(row, String(e.message || e), null, null, 'error');
    return false;
  }
}

function bindVideoRefRow(row) {
  const typeSel = row.querySelector('.ref-type');
  const roleSel = row.querySelector('.ref-role');
  const urlInput = row.querySelector('.ref-url');
  const fileInput = row.querySelector('.ref-file');
  const drop = row.querySelector('.ref-drop');

  fillRefRoleOptions(roleSel, typeSel.value, defaultRefRole(typeSel.value));

  typeSel.addEventListener('change', () => {
    fillRefRoleOptions(roleSel, typeSel.value, defaultRefRole(typeSel.value));
    syncVideoOptions();
  });

  row.querySelector('.ref-remove').addEventListener('click', () => {
    row.remove();
    syncVideoRefsHeader();
    syncVideoOptions();
    saveFormState('video');
  });
  row.querySelector('.ref-browse').addEventListener('click', () => openBrowse(urlInput, 'media'));

  drop.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', async () => {
    const file = fileInput.files?.[0];
    fileInput.value = '';
    if (!file) return;
    try {
      await uploadVideoRefFile(row, file);
    } catch (e) {
      row.querySelector('.ref-hint').textContent = String(e.message || e);
    }
  });

  ['dragenter', 'dragover'].forEach((ev) => {
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      drop.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach((ev) => {
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      drop.classList.remove('dragover');
    });
  });
  drop.addEventListener('drop', async (e) => {
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    try {
      await uploadVideoRefFile(row, file);
    } catch (err) {
      row.querySelector('.ref-hint').textContent = String(err.message || err);
    }
  });

  urlInput.addEventListener('change', async () => {
    const v = urlInput.value.trim();
    if (v) await validateVideoRefPath(row);
    syncVideoOptions();
    maybePreferAdaptiveRatio();
  });
  urlInput.addEventListener('blur', async () => {
    if (urlInput.value.trim()) await validateVideoRefPath(row);
  });
}

// --- Page actions ---

function filterDimensions() {
  return {
    target_width: Number(document.getElementById('filter-w').value),
    target_height: Number(document.getElementById('filter-h').value),
  };
}

function createVideoRefRow(data) {
  const row = document.createElement('div');
  row.className = 'video-ref-row grid gap-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-700 sm:grid-cols-12';
  row.innerHTML = `
    <select class="input ref-type sm:col-span-2">
      <option value="image_url">图片</option>
      <option value="video_url">视频</option>
      <option value="audio_url">音频</option>
    </select>
    <div class="ref-source sm:col-span-6 space-y-1.5">
      <div class="ref-drop">拖放文件到此处，或点击选择</div>
      <input type="file" class="ref-file hidden" accept="image/*,video/*,audio/*" />
      <div class="flex gap-1">
        <input type="text" class="input ref-url min-w-0 flex-1" placeholder="本机绝对路径（可粘贴）或 https://..." />
        <button type="button" class="btn-secondary ref-browse shrink-0 text-xs">浏览</button>
      </div>
      <p class="ref-hint text-xs text-zinc-500"></p>
    </div>
    <select class="input ref-role sm:col-span-3" title="该素材在生成中的用途"></select>
    <button type="button" class="btn-secondary ref-remove sm:col-span-1 text-xs">删</button>
  `;
  bindVideoRefRow(row);
  if (data) {
    const typeSel = row.querySelector('.ref-type');
    const roleSel = row.querySelector('.ref-role');
    const urlInput = row.querySelector('.ref-url');
    if (data.type) typeSel.value = data.type;
    fillRefRoleOptions(roleSel, typeSel.value, data.role || defaultRefRole(typeSel.value));
    if (data.url) {
      urlInput.value = data.url;
      updateVideoRefHint(row, data.url);
    }
  }
  return row;
}

function restoreVideoRefs(refs) {
  const container = document.getElementById('video-refs');
  if (!container) return;
  container.innerHTML = '';
  for (const ref of refs || []) {
    container.appendChild(createVideoRefRow(ref));
  }
  syncVideoRefsHeader();
}

function syncVideoRefsHeader() {
  const header = document.getElementById('video-refs-header');
  const hasRefs = document.querySelectorAll('.video-ref-row').length > 0;
  header?.classList.toggle('hidden', !hasRefs);
}

function videoGenerationMode() {
  const rows = [...document.querySelectorAll('.video-ref-row')];
  if (rows.length === 0) return 't2v';
  const types = rows.map((row) => row.querySelector('.ref-type').value);
  if (types.some((t) => t === 'video_url' || t === 'audio_url')) return 'multimodal';
  if (types.some((t) => t === 'image_url')) return 'i2v';
  return 't2v';
}

function syncVideoRatioHint() {
  const sel = document.getElementById('video-ratio');
  const hint = document.getElementById('video-ratio-hint');
  if (!sel || !hint) return;

  const mode = videoGenerationMode();
  const ratio = sel.value;
  if (ratio === 'adaptive') {
    if (mode === 'i2v') {
      hint.textContent = '按参考图比例自动匹配 16:9 / 9:16 / 1:1 等最接近的标准画幅（推荐）';
    } else if (mode === 'multimodal') {
      hint.textContent = '按参考素材智能选比例（通常优先参考视频，其次图片）';
    } else {
      hint.textContent = '纯文生视频时，模型根据提示词选择合适画幅';
    }
  } else if (mode === 'i2v' || mode === 'multimodal') {
    hint.textContent = `固定 ${ratio}；与参考图比例不一致时，方舟会居中裁切以填满画幅`;
  } else {
    hint.textContent = `文生视频固定输出为 ${ratio}`;
  }
}

function syncVideoOptions() {
  syncVideoDurationOptions();
  syncVideoRatioHint();
}

function maybePreferAdaptiveRatio() {
  const sel = document.getElementById('video-ratio');
  if (!sel) return;
  const mode = videoGenerationMode();
  const hasImage = collectVideoRefs().some((r) => r.type === 'image_url' && r.url);
  if ((mode === 'i2v' || mode === 'multimodal') && hasImage && sel.value === '16:9') {
    sel.value = 'adaptive';
    syncVideoRatioHint();
  }
}

function syncVideoDurationOptions() {
  const input = document.getElementById('video-duration');
  const hint = document.getElementById('video-duration-hint');
  if (!input) return;

  const mode = videoGenerationMode();
  if (mode === 'i2v') {
    input.min = '5';
    input.max = '15';
    if (hint) {
      hint.textContent = '图生视频：API 仅接受 5 / 10 / 15 秒，可手动输入上述数值';
    }
  } else {
    input.min = '4';
    input.max = '15';
    if (hint) {
      hint.textContent = mode === 'multimodal'
        ? '多模态参考：支持 4–15 秒（整数）'
        : '纯文生视频：支持 4–15 秒（整数）';
    }
  }
}

function collectVideoRefs() {
  return [...document.querySelectorAll('.video-ref-row')].map((row) => ({
    type: row.querySelector('.ref-type').value,
    url: row.querySelector('.ref-url').value.trim(),
    role: row.querySelector('.ref-role').value,
  })).filter((r) => r.url);
}

async function ensureVideoRefsValid() {
  const rows = [...document.querySelectorAll('.video-ref-row')];
  let ok = true;
  for (const row of rows) {
    const url = row.querySelector('.ref-url').value.trim();
    if (!url) continue;
    if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) {
      continue;
    }
    const valid = await validateVideoRefPath(row);
    if (!valid) ok = false;
  }
  return ok;
}

// --- 视频批量队列 ---

let videoBatchItems = [];
let videoQueuePollTimer = null;

const QUEUE_STATUS_LABELS = {
  pending: '排队中',
  running: '生成中',
  completed: '已完成',
  failed: '失败',
};

async function stageImageForBatch(file) {
  const form = new FormData();
  form.append('file', file);
  form.append('ref_type', 'image_url');
  const res = await fetch('/api/video/stage-media', { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  const data = await res.json();
  return { path: data.path, name: data.name || file.name };
}

function renderVideoBatchList() {
  const list = document.getElementById('video-batch-list');
  const btn = document.getElementById('btn-video-batch');
  if (!list) return;
  if (videoBatchItems.length === 0) {
    list.innerHTML = '<li class="text-xs text-zinc-500">尚未添加图片</li>';
    if (btn) btn.textContent = '批量提交';
    return;
  }
  list.innerHTML = videoBatchItems
    .map(
      (item, i) =>
        `<li class="flex items-center justify-between gap-2 rounded border border-zinc-200 px-2 py-1 dark:border-zinc-700">
          <span class="truncate">${i + 1}. ${item.name}</span>
          <button type="button" class="text-xs text-red-500 hover:underline" data-batch-remove="${i}">移除</button>
        </li>`,
    )
    .join('');
  list.querySelectorAll('[data-batch-remove]').forEach((el) => {
    el.addEventListener('click', () => {
      videoBatchItems.splice(Number(el.dataset.batchRemove), 1);
      renderVideoBatchList();
    });
  });
  if (btn) btn.textContent = `批量提交（${videoBatchItems.length} 个）`;
}

async function addVideoBatchFiles(fileList) {
  const files = [...fileList].filter((f) => f.type.startsWith('image/'));
  if (!files.length) return;
  appendLog('上传参考图', [`正在上传 ${files.length} 张…`], { running: true });
  let ok = 0;
  for (const file of files) {
    try {
      videoBatchItems.push(await stageImageForBatch(file));
      ok += 1;
    } catch (e) {
      appendLog('上传失败', [`${file.name}: ${e.message || e}`], { error: true });
    }
  }
  renderVideoBatchList();
  if (ok) appendLog('已加入批量列表', [`${ok} 张参考图，填写提示词后点「批量提交」`], { success: true });
}

function collectVideoJobParams() {
  return {
    prompt: document.getElementById('video-prompt').value.trim(),
    model: document.getElementById('video-model').value.trim(),
    ratio: document.getElementById('video-ratio').value,
    resolution: document.getElementById('video-resolution').value,
    duration: Number(document.getElementById('video-duration').value),
    generate_audio: document.getElementById('video-generate-audio').checked,
    watermark: document.getElementById('video-watermark').checked,
    output_path: document.getElementById('video-output').value.trim() || null,
  };
}

function extractVideoUrlFromJob(job) {
  const details = job.result?.details || [];
  for (const line of details) {
    const match = line.match(/https:\/\/\S+/);
    if (match && (match[0].includes('.mp4') || match[0].includes('video'))) {
      return match[0].replace(/[）)]+$/, '');
    }
  }
  return null;
}

function queueStatusClass(status) {
  if (status === 'completed') return 'queue-status-done';
  if (status === 'failed') return 'queue-status-fail';
  if (status === 'running' || status === 'pending') return 'queue-status-running';
  return '';
}

async function refreshVideoQueue() {
  const list = document.getElementById('video-queue-list');
  if (!list) return;
  try {
    const data = await api('/api/jobs?job_type=video-generate&limit=40');
    const jobs = data.jobs || [];
    if (!jobs.length) {
      list.innerHTML = '<p class="text-xs text-zinc-500">暂无视频任务。使用批量提交或单个提交后在此查看。</p>';
      return;
    }
    list.innerHTML = jobs
      .map((job) => {
        const label = job.label || job.id;
        const statusText = QUEUE_STATUS_LABELS[job.status] || job.status;
        const batchTag = job.batch_id
          ? `<span class="text-xs text-zinc-400">批次 ${job.batch_id.slice(0, 8)} · </span>`
          : '';
        const progress = job.progress_message
          ? `<p class="mt-1 truncate text-xs text-zinc-500">${job.progress_message}</p>`
          : '';
        const saved = job.result?.outputs?.[0]
          ? `<p class="mt-1 text-xs text-emerald-600 dark:text-emerald-400">已保存: ${job.result.outputs[0]}</p>`
          : '';
        const url = extractVideoUrlFromJob(job);
        const link = url
          ? `<a class="mt-1 inline-block text-xs text-indigo-600 hover:underline dark:text-indigo-400" href="${url}" target="_blank" rel="noopener">打开在线视频</a>`
          : '';
        const err = job.error || job.result?.errors?.[0];
        const errLine = err
          ? `<p class="mt-1 text-xs text-red-500">${err}</p>`
          : job.result && job.result.ok === false
            ? `<p class="mt-1 text-xs text-red-500">${job.result.message || ''}</p>`
            : '';
        return `<div class="queue-row">
          <div class="${queueStatusClass(job.status)}">${batchTag}<strong>${label}</strong> · ${statusText}</div>
          ${progress}${saved}${link}${errLine}
        </div>`;
      })
      .join('');
  } catch (e) {
    list.innerHTML = `<p class="text-xs text-red-500">加载失败: ${e.message || e}</p>`;
  }
}

function startVideoQueuePolling() {
  stopVideoQueuePolling();
  videoQueuePollTimer = setInterval(refreshVideoQueue, 8000);
}

function stopVideoQueuePolling() {
  if (videoQueuePollTimer) {
    clearInterval(videoQueuePollTimer);
    videoQueuePollTimer = null;
  }
}

async function submitVideoBatch() {
  if (!videoBatchItems.length) {
    appendLog('批量提交', ['请先添加至少一张参考图到批量列表'], { error: true });
    return;
  }
  const params = collectVideoJobParams();
  if (!params.prompt) {
    appendLog('请填写提示词', [], { error: true });
    return;
  }
  saveFormState('video');

  const role = document.getElementById('video-batch-role')?.value || 'reference_image';
  const invalidPaths = [];
  for (const item of videoBatchItems) {
    if (item.path.startsWith('http://') || item.path.startsWith('https://')) continue;
    try {
      const q = new URLSearchParams({ path: item.path, ref_type: 'image_url' });
      await api(`/api/video/check-media?${q}`);
    } catch (e) {
      invalidPaths.push(`${item.name}: ${e.message || e}`);
    }
  }
  if (invalidPaths.length) {
    appendLog('批量参考图路径无效', invalidPaths, { error: true });
    return;
  }

  const body = {
    prompt: params.prompt,
    model: params.model,
    ratio: params.ratio,
    resolution: params.resolution,
    duration: params.duration,
    generate_audio: params.generate_audio,
    watermark: params.watermark,
    output_path: params.output_path,
    output_dir: null,
    items: videoBatchItems.map((item) => ({
      url: item.path,
      label: item.name,
      role,
    })),
  };

  setBusy(true);
  appendLog('批量提交中…', [`共 ${body.items.length} 个任务`], { running: true });
  try {
    const data = await api('/api/jobs/video-generate-batch', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    const lines = [
      data.message,
      `批次 ID: ${data.batch_id}`,
      ...data.jobs.map((j) => `· ${j.label} → ${j.job_id}`),
    ];
    appendLog(`已提交 ${data.total} 个任务`, lines, { success: true });
    videoBatchItems = [];
    renderVideoBatchList();
    await refreshVideoQueue();
    startVideoQueuePolling();
  } catch (e) {
    appendLog('批量提交失败', [String(e.message || e)], { error: true });
  } finally {
    setBusy(false);
  }
}

function initVideoBatch() {
  const drop = document.getElementById('video-batch-drop');
  const input = document.getElementById('video-batch-files');
  if (!drop || !input) return;

  drop.addEventListener('click', () => input.click());
  input.addEventListener('change', async () => {
    await addVideoBatchFiles(input.files || []);
    input.value = '';
  });
  ['dragenter', 'dragover'].forEach((ev) => {
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      drop.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach((ev) => {
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      drop.classList.remove('dragover');
    });
  });
  drop.addEventListener('drop', async (e) => {
    await addVideoBatchFiles(e.dataTransfer?.files || []);
  });

  document.getElementById('btn-video-batch')?.addEventListener('click', submitVideoBatch);
  document.getElementById('btn-video-batch-clear')?.addEventListener('click', () => {
    videoBatchItems = [];
    renderVideoBatchList();
  });
  document.getElementById('btn-video-batch-add-path')?.addEventListener('click', async () => {
    const input = document.getElementById('video-batch-path');
    const p = input?.value.trim();
    if (!p) return;
    try {
      const q = new URLSearchParams({ path: p, ref_type: 'image_url' });
      const data = await api(`/api/video/check-media?${q}`);
      videoBatchItems.push({ path: data.path, name: data.name || p.split('/').pop() || p });
      if (input) input.value = '';
      renderVideoBatchList();
    } catch (e) {
      appendLog('路径无效', [String(e.message || e)], { error: true });
    }
  });
  document.getElementById('btn-video-queue-refresh')?.addEventListener('click', refreshVideoQueue);
  renderVideoBatchList();
}

function initVideo() {
  document.getElementById('video-ratio')?.addEventListener('change', syncVideoRatioHint);

  document.getElementById('video-add-ref')?.addEventListener('click', () => {
    document.getElementById('video-refs').appendChild(createVideoRefRow());
    syncVideoRefsHeader();
    syncVideoOptions();
    saveFormState('video');
  });

  document.getElementById('btn-video')?.addEventListener('click', async () => {
    const prompt = document.getElementById('video-prompt').value.trim();
    if (!prompt) {
      appendLog('请填写提示词', []);
      return;
    }
    if (!(await ensureVideoRefsValid())) {
      appendLog('参考素材路径无效', ['请检查标红的本机路径是否存在，或改用拖放/浏览选择文件'], { error: true });
      return;
    }
    const output_path = document.getElementById('video-output').value.trim() || null;
    runJob('/api/jobs/video-generate', {
      prompt,
      references: collectVideoRefs(),
      model: document.getElementById('video-model').value.trim(),
      ratio: document.getElementById('video-ratio').value,
      resolution: document.getElementById('video-resolution').value,
      duration: Number(document.getElementById('video-duration').value),
      generate_audio: document.getElementById('video-generate-audio').checked,
      watermark: document.getElementById('video-watermark').checked,
      output_path,
    }, 'video');
  });
}

function initWorkflow() {
  document.querySelectorAll('.wf-rename-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      applyWfRenameMode(tab.dataset.wfRename);
      saveFormState('workflow');
    });
  });

  document.getElementById('btn-workflow').addEventListener('click', () => {
    const source_dir = document.getElementById('wf-source').value.trim();
    const output_dir = document.getElementById('wf-output').value.trim();
    if (!source_dir || !output_dir) {
      appendLog('请填写来源与输出目录', []);
      return;
    }
    const mode = document.querySelector('input[name="wf-mode"]:checked')?.value || 'area_64';
    const body = {
      source_dir,
      output_dir,
      target_width: Number(document.getElementById('wf-width').value),
      target_height: Number(document.getElementById('wf-height').value),
      resize_mode: mode,
      recursive: document.getElementById('wf-recursive').checked,
      rename_mode: wfRenameMode,
      prefix: document.getElementById('wf-prefix').value,
      start_num: Number(document.getElementById('wf-start-num').value),
      digits: Number(document.getElementById('wf-digits').value),
      start_index: Number(document.getElementById('wf-start-index').value),
      sync_captions: document.getElementById('wf-sync-captions').checked,
    };
    runJob('/api/jobs/workflow', body, 'workflow');
  });
}

function initConvert() {
  document.querySelector('[data-preset-convert="1024"]')?.addEventListener('click', () => {
    document.getElementById('convert-w').value = 1024;
    document.getElementById('convert-h').value = 1024;
  });

  document.getElementById('btn-convert').addEventListener('click', () => {
    const target_path = document.getElementById('convert-target').value.trim();
    const output_path = document.getElementById('convert-output').value.trim();
    if (!target_path || !output_path) {
      appendLog('请填写路径', ['图片来源与输出目录均必填']);
      return;
    }
    runJob('/api/jobs/convert', {
      target_path,
      output_path,
      base_width: Number(document.getElementById('convert-w').value),
      base_height: Number(document.getElementById('convert-h').value),
      recursive: document.getElementById('convert-recursive').checked,
      rename_output: document.getElementById('convert-rename').checked,
    }, 'convert');
  });
}

function initResize() {
  document.querySelector('[data-preset-resize="1024"]')?.addEventListener('click', () => {
    document.getElementById('resize-w').value = 1024;
    document.getElementById('resize-h').value = 1024;
  });

  document.getElementById('btn-resize').addEventListener('click', () => {
    const input_dir = document.getElementById('resize-input').value.trim();
    if (!input_dir) {
      appendLog('请填写输入目录', []);
      return;
    }
    const output_dir = document.getElementById('resize-output').value.trim() || null;
    runJob('/api/jobs/resize-canvas', {
      input_dir,
      output_dir,
      canvas_width: Number(document.getElementById('resize-w').value),
      canvas_height: Number(document.getElementById('resize-h').value),
      recursive: document.getElementById('resize-recursive').checked,
    }, 'resizeCanvas');
  });
}

function initCrop() {
  document.getElementById('btn-crop').addEventListener('click', () => {
    const input_root = document.getElementById('crop-input').value.trim();
    const output_root = document.getElementById('crop-output').value.trim();
    if (!input_root || !output_root) {
      appendLog('请填写输入与输出目录', []);
      return;
    }
    runJob('/api/jobs/crop-2k', { input_root, output_root }, 'crop2k');
  });
}

function initFilter() {
  const confirmBlock = document.getElementById('filter-confirm-block');
  const backupCheck = document.getElementById('filter-backup-check');
  const deleteBtn = document.getElementById('btn-filter-delete');

  document.querySelector('[data-preset-filter="2k"]')?.addEventListener('click', () => {
    document.getElementById('filter-w').value = 2560;
    document.getElementById('filter-h').value = 1440;
  });

  backupCheck.addEventListener('change', () => {
    deleteBtn.disabled = !backupCheck.checked;
  });

  document.getElementById('btn-filter-preview').addEventListener('click', async () => {
    const target_dir = document.getElementById('filter-dir').value.trim();
    if (!target_dir) {
      appendLog('请填写目标目录', []);
      return;
    }
    filterPreviewDone = false;
    confirmBlock.classList.add('hidden');
    backupCheck.checked = false;
    deleteBtn.disabled = true;

    const job = await runJob('/api/jobs/filter-2k', {
      target_dir,
      dry_run: true,
      ...filterDimensions(),
    }, 'filter2k');
    if (job.status === 'completed' && job.result) {
      filterPreviewDone = true;
      const n = (job.result.outputs || []).length;
      if (n > 0) {
        confirmBlock.classList.remove('hidden');
        appendLog(
          job.result.message,
          [
            ...(job.result.details || []).slice(0, 200),
            ...(job.result.details?.length > 200 ? ['…（详情已截断）'] : []),
          ]
        );
      }
    }
  });

  deleteBtn.addEventListener('click', () => {
    if (!filterPreviewDone || !backupCheck.checked) return;
    const target_dir = document.getElementById('filter-dir').value.trim();
    const dims = filterDimensions();
    if (
      !confirm(
        `最后确认：将永久删除非 ${dims.target_width}×${dims.target_height} 的图片，是否继续？`
      )
    ) {
      return;
    }
    runJob('/api/jobs/filter-2k', { target_dir, dry_run: false, ...dims }, 'filter2k').then(() => {
      confirmBlock.classList.add('hidden');
      filterPreviewDone = false;
    });
  });
}

function initAutoTag() {
  const presetSelect = document.getElementById('tag-caption-preset');
  const triggerInput = document.getElementById('tag-trigger');

  async function fillTagPreset(presetId) {
    try {
      const data = await api(`/api/caption/presets/${encodeURIComponent(presetId)}`);
      if (!triggerInput.value.trim() && data.trigger_word) {
        triggerInput.value = data.trigger_word;
      }
    } catch {
      /* 预设加载失败时保留用户输入 */
    }
  }

  api('/api/caption/presets')
    .then(async (data) => {
      presetSelect.innerHTML = '';
      for (const p of data.presets || []) {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        presetSelect.appendChild(opt);
      }
      if (!presetSelect.options.length) {
        const opt = document.createElement('option');
        opt.value = 'default';
        opt.textContent = 'default';
        presetSelect.appendChild(opt);
      }
      await fillTagPreset(presetSelect.value);
    })
    .catch(() => {
      presetSelect.innerHTML = '<option value="default">default</option>';
    });

  presetSelect.addEventListener('change', () => fillTagPreset(presetSelect.value));

  document.getElementById('btn-auto-tag').addEventListener('click', () => {
    const image_dir = document.getElementById('tag-dir').value.trim();
    if (!image_dir) {
      appendLog('请填写图片目录', []);
      return;
    }
    runJob('/api/jobs/auto-tag', {
      image_dir,
      repo_id: document.getElementById('tag-model').value,
      batch_size: 4,
      general_threshold: Number(document.getElementById('tag-general-thresh').value),
      character_threshold: Number(document.getElementById('tag-char-thresh').value),
      trigger_word: document.getElementById('tag-trigger').value.trim(),
      undesired_tags: document.getElementById('tag-undesired').value.trim(),
      caption_preset: presetSelect.value,
      auto_clean: document.getElementById('tag-auto-clean').checked,
      clean_preset: presetSelect.value,
      recursive: document.getElementById('tag-recursive').checked,
      remove_underscore: document.getElementById('tag-remove-underscore').checked,
      append_tags: document.getElementById('tag-append').checked,
    });
  });
}

function initCaptionClean() {
  const presetSelect = document.getElementById('clean-preset');
  const triggerInput = document.getElementById('clean-trigger');

  async function fillCleanPreset(presetId) {
    try {
      const data = await api(`/api/caption/presets/${encodeURIComponent(presetId)}`);
      if (!triggerInput.value.trim() && data.trigger_word) {
        triggerInput.placeholder = data.trigger_word || '留空则用预设';
      }
    } catch {
      /* ignore */
    }
  }

  api('/api/caption/presets')
    .then(async (data) => {
      presetSelect.innerHTML = '';
      for (const p of data.presets || []) {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        presetSelect.appendChild(opt);
      }
      if (!presetSelect.options.length) {
        const opt = document.createElement('option');
        opt.value = 'default';
        opt.textContent = 'default';
        presetSelect.appendChild(opt);
      }
      await fillCleanPreset(presetSelect.value);
    })
    .catch(() => {
      presetSelect.innerHTML = '<option value="default">default</option>';
    });

  presetSelect.addEventListener('change', () => fillCleanPreset(presetSelect.value));

  document.getElementById('btn-caption-clean').addEventListener('click', () => {
    const target_dir = document.getElementById('clean-dir').value.trim();
    if (!target_dir) {
      appendLog('请填写 Caption 目录', []);
      return;
    }
    runJob('/api/jobs/caption-clean', {
      target_dir,
      preset: presetSelect.value,
      recursive: document.getElementById('clean-recursive').checked,
      dry_run: document.getElementById('clean-dry-run').checked,
      trigger_word: document.getElementById('clean-trigger').value.trim(),
      strip_tags: document.getElementById('clean-strip').value.trim(),
      ensure_tags: document.getElementById('clean-ensure').value.trim(),
    });
  });
}

function initLoraTrain() {
  const select = document.getElementById('lora-preset');

  async function fillLoraFormFromPreset(presetId) {
    try {
      const { config } = await api(`/api/lora/presets/${encodeURIComponent(presetId)}`);
      const res = String(config.resolution || '1024,1024').split(',');
      document.getElementById('lora-train-dir').value = config.train_data_dir || '';
      document.getElementById('lora-base-model').value = config.pretrained_model_name_or_path || '';
      document.getElementById('lora-output-name').value = config.output_name || '';
      document.getElementById('lora-output-dir').value = config.output_dir || '';
      document.getElementById('lora-epochs').value = config.max_train_epochs ?? 10;
      document.getElementById('lora-batch-size').value = config.train_batch_size ?? 2;
      document.getElementById('lora-save-every').value = config.save_every_n_epochs ?? 2;
      document.getElementById('lora-res-w').value = (res[0] || '1024').trim();
      document.getElementById('lora-res-h').value = (res[1] || res[0] || '1024').trim();
      document.getElementById('lora-dim').value = config.network_dim ?? 64;
      document.getElementById('lora-alpha').value = config.network_alpha ?? 32;
      document.getElementById('lora-unet-lr').value = config.unet_lr ?? config.learning_rate ?? 0.0001;
      document.getElementById('lora-keep-tokens').value = config.keep_tokens ?? 1;
      document.getElementById('lora-bucket-no-upscale').checked = Boolean(config.bucket_no_upscale);
      document.getElementById('lora-full-bf16').checked = Boolean(config.full_bf16);
    } catch (e) {
      appendLog('加载预设失败', [String(e.message || e)]);
    }
  }

  function collectLoraTrainBody(preset) {
    const trainDir = document.getElementById('lora-train-dir').value.trim();
    const baseModel = document.getElementById('lora-base-model').value.trim();
    if (!trainDir || !baseModel) {
      return null;
    }
    return {
      preset,
      train_data_dir: trainDir,
      pretrained_model_name_or_path: baseModel,
      output_name: document.getElementById('lora-output-name').value.trim(),
      output_dir: document.getElementById('lora-output-dir').value.trim(),
      max_train_epochs: Number(document.getElementById('lora-epochs').value),
      train_batch_size: Number(document.getElementById('lora-batch-size').value),
      save_every_n_epochs: Number(document.getElementById('lora-save-every').value),
      resolution_width: Number(document.getElementById('lora-res-w').value),
      resolution_height: Number(document.getElementById('lora-res-h').value),
      network_dim: Number(document.getElementById('lora-dim').value),
      network_alpha: Number(document.getElementById('lora-alpha').value),
      unet_lr: Number(document.getElementById('lora-unet-lr').value),
      keep_tokens: Number(document.getElementById('lora-keep-tokens').value),
      bucket_no_upscale: document.getElementById('lora-bucket-no-upscale').checked,
      full_bf16: document.getElementById('lora-full-bf16').checked,
    };
  }

  api('/api/lora/presets')
    .then(async (data) => {
      select.innerHTML = '';
      for (const p of data.presets || []) {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        select.appendChild(opt);
      }
      if (!select.options.length) {
        const opt = document.createElement('option');
        opt.value = 'morgana_star_nemesis';
        opt.textContent = 'morgana_star_nemesis';
        select.appendChild(opt);
      }
      await fillLoraFormFromPreset(select.value);
    })
    .catch(() => {
      select.innerHTML = '<option value="morgana_star_nemesis">morgana_star_nemesis</option>';
      fillLoraFormFromPreset('morgana_star_nemesis');
    });

  select.addEventListener('change', () => fillLoraFormFromPreset(select.value));

  document.getElementById('btn-lora-train').addEventListener('click', () => {
    const preset = select.value;
    if (!preset) {
      appendLog('请选择训练预设', []);
      return;
    }
    if (!confirm('即将启动 LoRA 训练，过程可能耗时较长，是否继续？')) {
      return;
    }
    const body = collectLoraTrainBody(preset);
    if (!body) {
      appendLog('请填写训练数据目录与底模路径', []);
      return;
    }
    runJobLive('/api/jobs/lora-train', body);
  });
}

function initRename() {
  document.querySelectorAll('.rename-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      applyRenameMode(tab.dataset.renameMode);
      saveFormState('rename');
    });
  });

  document.getElementById('btn-rename').addEventListener('click', () => {
    const folder_path = document.getElementById('rename-folder').value.trim();
    if (!folder_path) {
      appendLog('请填写文件夹路径', []);
      return;
    }
    const dry_run = document.getElementById('rename-dry-run').checked;
    const body = {
      mode: renameMode,
      folder_path,
      dry_run,
    };
    if (renameMode === 'numbered') {
      body.prefix = document.getElementById('rename-prefix').value;
      body.start_num = Number(document.getElementById('rename-start-num').value);
      body.digits = Number(document.getElementById('rename-digits').value);
    } else {
      body.start_index = Number(document.getElementById('rename-start-index').value);
    }
    runJob('/api/jobs/rename', body, 'rename');
  });
}

function initMp4ToMp3() {
  document.getElementById('btn-mp3')?.addEventListener('click', () => {
    const input_path = document.getElementById('mp3-input').value.trim();
    if (!input_path) {
      appendLog('请填写输入路径', ['单个 MP4 文件或包含视频的文件夹']);
      return;
    }
    const output_dir = document.getElementById('mp3-output').value.trim() || null;
    runJob(
      '/api/jobs/mp4-to-mp3',
      {
        input_path,
        output_dir,
        recursive: document.getElementById('mp3-recursive').checked,
        overwrite: document.getElementById('mp3-overwrite').checked,
      },
      'mp4ToMp3',
    );
  });
}

// --- Init ---

function initNav() {
  initNavSections();
  document.querySelectorAll('.nav-section-toggle').forEach((toggle) => {
    toggle.addEventListener('click', () => {
      const section = toggle.closest('.nav-section');
      const id = section?.dataset.section;
      if (!id) return;
      const willCollapse = !section.classList.contains('collapsed');
      setSectionCollapsed(id, willCollapse);
      const state = readNavSections();
      state[id] = willCollapse;
      writeNavSections(state);
    });
  });
  document.querySelectorAll('#sidebar-nav .nav-item').forEach((btn) => {
    btn.addEventListener('click', () => showPage(btn.dataset.page));
  });
}

function initBrowse() {
  document.querySelectorAll('.browse-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const wrap = btn.closest('.path-field');
      const input = wrap?.querySelector('input');
      if (input) openBrowse(input);
    });
  });
  document.querySelectorAll('.browse-file-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const wrap = btn.closest('.path-field');
      const input = wrap?.querySelector('input');
      if (input) openBrowse(input, 'media');
    });
  });
  document.querySelectorAll('[data-close-modal]').forEach((el) => {
    el.addEventListener('click', closeBrowse);
  });
  document.getElementById('browse-select').addEventListener('click', confirmBrowse);
}

document.getElementById('log-clear').addEventListener('click', () => {
  document.getElementById('log-summary').textContent = '等待任务…';
  document.getElementById('log-body').textContent = '在此显示处理结果与详情。';
  setLogPanelState('idle');
});

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initNav();
  initBrowse();
  initWorkflow();
  initVideo();
  initVideoBatch();
  initConvert();
  initToIco();
  initCompress();
  initFormatConvert();
  initResize();
  initCrop();
  initFilter();
  initRename();
  initMp4ToMp3();
  syncVideoOptions();
  restoreAllFormState();
  bindAllFormAutoSave();
  const lastPage = localStorage.getItem(LAST_PAGE_KEY);
  showPage(lastPage && PAGE_META[lastPage] ? lastPage : 'workflow');
  if (activePage === 'video') {
    refreshVideoQueue();
    startVideoQueuePolling();
  }
  loadHealth();
});
