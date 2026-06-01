/**
 * AITrainScripts Hub — 前端逻辑
 */

const PAGE_META = {
  workflow: {
    title: 'LoRA 工作流',
    subtitle: '转换/缩放 → 输出 → 批量重命名，一键完成数据准备',
  },
  convert: {
    title: '格式转换',
    subtitle: '多格式转 PNG；按目标像素总面积智能缩放（非固定输出宽高）',
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
};

let activePage = 'convert';
let browseTargetInput = null;
let browseCurrentPath = null;
let renameMode = 'numbered';
let wfRenameMode = 'numbered';
let filterPreviewDone = false;
let busy = false;

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

function showPage(page) {
  activePage = page;
  document.querySelectorAll('.page-panel').forEach((el) => el.classList.add('hidden'));
  const panel = document.getElementById(`page-${page}`);
  if (panel) panel.classList.remove('hidden');

  document.querySelectorAll('.nav-item').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.page === page);
  });

  const meta = PAGE_META[page] || PAGE_META.convert;
  document.getElementById('page-title').textContent = meta.title;
  document.getElementById('page-subtitle').textContent = meta.subtitle;
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

async function pollJob(jobId) {
  const maxAttempts = 3600;
  for (let i = 0; i < maxAttempts; i++) {
    const job = await api(`/api/jobs/${jobId}`);
    if (job.status === 'completed' || job.status === 'failed') {
      return job;
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error('任务超时');
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

function appendLog(summary, lines) {
  document.getElementById('log-summary').textContent = summary;
  const body = document.getElementById('log-body');
  body.textContent = lines.join('\n') || '（无详情）';
  body.scrollTop = body.scrollHeight;
}

function formatJobResult(job) {
  if (job.status === 'failed') {
    return { summary: `失败：${job.error}`, lines: [job.error || '未知错误'] };
  }
  const r = job.result;
  if (!r) return { summary: '完成（无结果数据）', lines: [] };
  const summary = `${r.message} · 处理 ${r.processed} · 跳过 ${r.skipped}`;
  const lines = [...(r.details || []), ...(r.errors || []).map((e) => `错误: ${e}`)];
  return { summary, lines };
}

async function runJob(endpoint, body) {
  setBusy(true);
  appendLog('任务运行中…', ['请稍候']);
  try {
    const { job_id } = await api(endpoint, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    const job = await pollJob(job_id);
    const { summary, lines } = formatJobResult(job);
    appendLog(summary, lines);
    return job;
  } catch (e) {
    appendLog('出错', [String(e.message || e)]);
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
    const labels = { pillow: 'Pillow', pillow_heif: 'HEIF', natsort: 'natsort' };
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

async function openBrowse(inputEl) {
  browseTargetInput = inputEl;
  const start = inputEl.value.trim() || null;
  await loadBrowseList(start);
  document.getElementById('browse-modal').classList.remove('hidden');
}

async function loadBrowseList(path) {
  const q = path ? `?path=${encodeURIComponent(path)}` : '';
  const data = await api(`/api/browse${q}`);
  browseCurrentPath = data.current;
  document.getElementById('browse-current').textContent = data.current;
  const list = document.getElementById('browse-list');
  list.innerHTML = '';
  for (const entry of data.entries) {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = entry.is_dir ? `📁 ${entry.name}` : entry.name;
    btn.addEventListener('click', () => {
      if (entry.name === '..') {
        loadBrowseList(entry.path);
      } else {
        loadBrowseList(entry.path);
      }
    });
    li.appendChild(btn);
    list.appendChild(li);
  }
}

function closeBrowse() {
  document.getElementById('browse-modal').classList.add('hidden');
  browseTargetInput = null;
}

function confirmBrowse() {
  if (browseTargetInput && browseCurrentPath) {
    browseTargetInput.value = browseCurrentPath;
  }
  closeBrowse();
}

// --- Page actions ---

function filterDimensions() {
  return {
    target_width: Number(document.getElementById('filter-w').value),
    target_height: Number(document.getElementById('filter-h').value),
  };
}

function initWorkflow() {
  document.querySelectorAll('.wf-rename-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      wfRenameMode = tab.dataset.wfRename;
      document.querySelectorAll('.wf-rename-tab').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      const numbered = wfRenameMode === 'numbered';
      document.getElementById('wf-numbered-fields').classList.toggle('hidden', !numbered);
      document.getElementById('wf-sequential-fields').classList.toggle('hidden', wfRenameMode !== 'sequential');
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
    runJob('/api/jobs/workflow', body);
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
    });
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
    });
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
    runJob('/api/jobs/crop-2k', { input_root, output_root });
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
    });
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
    runJob('/api/jobs/filter-2k', { target_dir, dry_run: false, ...dims }).then(() => {
      confirmBlock.classList.add('hidden');
      filterPreviewDone = false;
    });
  });
}

function initRename() {
  document.querySelectorAll('.rename-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      renameMode = tab.dataset.renameMode;
      document.querySelectorAll('.rename-tab').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById('rename-numbered-fields').classList.toggle('hidden', renameMode !== 'numbered');
      document.getElementById('rename-sequential-fields').classList.toggle('hidden', renameMode !== 'sequential');
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
    runJob('/api/jobs/rename', body);
  });
}

// --- Init ---

function initNav() {
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
  document.querySelectorAll('[data-close-modal]').forEach((el) => {
    el.addEventListener('click', closeBrowse);
  });
  document.getElementById('browse-select').addEventListener('click', confirmBrowse);
}

document.getElementById('log-clear').addEventListener('click', () => {
  document.getElementById('log-summary').textContent = '等待任务…';
  document.getElementById('log-body').textContent = '在此显示处理结果与详情。';
});

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initNav();
  initBrowse();
  initWorkflow();
  initConvert();
  initResize();
  initCrop();
  initFilter();
  initRename();
  showPage('workflow');
  loadHealth();
});
