/**
 * AITrainScripts Hub — 前端逻辑
 */

const PAGE_META = {
  workflow: {
    title: 'LoRA 完整流程',
    subtitle: '移动原图 → 裁切转化 → 打标 → 清洗 → 训练（8 步一键完成）',
  },
  autoTag: {
    title: '自动打标',
    subtitle: 'WD14 打标 + Caption 预设（排除脏 tag + 规则清洗）',
  },
  captionClean: {
    title: 'Caption 清洗',
    subtitle: '按预设删除脏 tag、补角色 tag、标记异常待复核',
  },
  loraTrain: {
    title: 'LoRA 训练',
    subtitle: '读取预设配置，调用 lora-scripts 启动 Kohya 训练',
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
    subtitle: '图片文件重命名 / 子文件夹加 10_ 前缀并去空格',
  },
};

let activePage = 'convert';
let browseTargetInput = null;
let browseCurrentPath = null;
let renameMode = 'numbered';
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

async function pollJob(jobId, maxAttempts = 3600) {
  for (let i = 0; i < maxAttempts; i++) {
    const job = await api(`/api/jobs/${jobId}`);
    if (job.status === 'completed' || job.status === 'failed') {
      return job;
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error('任务超时');
}

async function runJob(endpoint, body, options = {}) {
  const maxAttempts = options.maxAttempts ?? 3600;
  setBusy(true);
  appendLog('任务运行中…', ['请稍候']);
  try {
    const { job_id } = await api(endpoint, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    const job = await pollJob(job_id, maxAttempts);
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

function updatePipelineProgressUI(job) {
  const panel = document.getElementById('pipe-progress-panel');
  const logBody = document.getElementById('log-body');
  if (!panel) return;

  const isPipe = job.type === 'lora-pipeline';
  const running = job.status === 'running' || job.status === 'pending';

  if (isPipe && (running || job.progress)) {
    panel.classList.remove('hidden');
    logBody?.classList.add('log-body-training');
  } else if (!running && isPipe) {
    panel.classList.add('hidden');
    logBody?.classList.remove('log-body-training');
  }

  const p = job.progress || {};
  const pct = Math.min(100, Math.max(0, Number(p.percent) || 0));
  document.getElementById('pipe-progress-bar').style.width = `${pct}%`;
  document.getElementById('pipe-progress-label').textContent =
    p.message || (running ? '流程进行中…' : '流程进度');
  const step = p.step || 0;
  const total = p.total_steps || 8;
  document.getElementById('pipe-progress-step').textContent =
    step > 0 ? `步骤 ${step}/${total}` : '—';

  let detail = p.message || '—';
  if (p.max_epochs > 0 && step >= 7) {
    detail += ` · Epoch ${p.epoch || 0}/${p.max_epochs}`;
    if (p.loss != null) detail += ` · Loss ${Number(p.loss).toFixed(4)}`;
  }
  document.getElementById('pipe-progress-detail').textContent = detail;

  if (job.log_tail && job.log_tail.length) {
    document.getElementById('log-summary').textContent =
      running ? 'LoRA 完整流程运行中…' : formatJobResult(job).summary;
    logBody.textContent = job.log_tail.join('\n');
    logBody.scrollTop = logBody.scrollHeight;
  }
}

function updateLiveJobUI(job) {
  if (job.type === 'lora-pipeline') {
    updatePipelineProgressUI(job);
    return;
  }
  updateTrainProgressUI(job);
}

function updateTrainProgressUI(job) {
  const panel = document.getElementById('train-progress-panel');
  const logBody = document.getElementById('log-body');
  if (!panel) return;

  const isTrain = job.type === 'lora-train';
  const running = job.status === 'running' || job.status === 'pending';

  if (isTrain && (running || job.progress)) {
    panel.classList.remove('hidden');
    logBody?.classList.add('log-body-training');
  } else if (!running) {
    panel.classList.add('hidden');
    logBody?.classList.remove('log-body-training');
  }

  const p = job.progress || {};
  const pct = Math.min(100, Math.max(0, Number(p.percent) || 0));
  document.getElementById('train-progress-bar').style.width = `${pct}%`;
  document.getElementById('train-progress-label').textContent =
    p.message || (running ? '训练中…' : '训练进度');
  document.getElementById('train-progress-epoch').textContent =
    p.max_epochs > 0 ? `Epoch ${p.epoch || 0}/${p.max_epochs}` : '—';
  document.getElementById('train-progress-step').textContent =
    p.max_steps > 0 ? `步数 ${p.step || 0}/${p.max_steps}` : '步数 —';
  document.getElementById('train-progress-loss').textContent =
    p.loss != null ? `Loss ${Number(p.loss).toFixed(4)}` : 'Loss —';

  if (job.log_tail && job.log_tail.length) {
    document.getElementById('log-summary').textContent =
      running ? '训练进行中…' : formatJobResult(job).summary;
    logBody.textContent = job.log_tail.join('\n');
    logBody.scrollTop = logBody.scrollHeight;
  }
}

async function pollJobLive(jobId, onUpdate, maxAttempts = 86400) {
  for (let i = 0; i < maxAttempts; i++) {
    const job = await api(`/api/jobs/${jobId}`);
    if (onUpdate) onUpdate(job);
    if (job.status === 'completed' || job.status === 'failed') {
      return job;
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error('任务超时');
}

async function runJobLive(endpoint, body, options = {}) {
  const maxAttempts = options.maxAttempts ?? 86400;
  setBusy(true);
  appendLog('任务运行中…', ['请稍候']);
  try {
    const { job_id } = await api(endpoint, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    const job = await pollJobLive(job_id, updateLiveJobUI, maxAttempts);
    updateLiveJobUI(job);
    const { summary, lines } = formatJobResult(job);
    if (!job.log_tail || !job.log_tail.length) {
      appendLog(summary, lines);
    } else {
      document.getElementById('log-summary').textContent = summary;
    }
    return job;
  } catch (e) {
    appendLog('出错', [String(e.message || e)]);
    document.getElementById('train-progress-panel')?.classList.add('hidden');
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
    const labels = { pillow: 'Pillow', pillow_heif: 'HEIF', natsort: 'natsort', onnxruntime: 'ONNX' };
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

function initLoraPipeline() {
  const captionSelect = document.getElementById('pipe-caption-preset');
  const loraSelect = document.getElementById('pipe-lora-preset');

  async function fillCaptionPreset(presetId) {
    try {
      const data = await api(`/api/caption/presets/${encodeURIComponent(presetId)}`);
      const trigger = document.getElementById('pipe-trigger');
      if (!trigger.value.trim() && data.trigger_word) {
        trigger.value = data.trigger_word;
      }
    } catch {
      /* ignore */
    }
  }

  async function fillLoraPreset(presetId) {
    try {
      const { config } = await api(`/api/lora/presets/${encodeURIComponent(presetId)}`);
      document.getElementById('pipe-base-model').value = config.pretrained_model_name_or_path || '';
      document.getElementById('pipe-output-name').value = config.output_name || '';
      document.getElementById('pipe-output-dir').value = config.output_dir || '';
      document.getElementById('pipe-epochs').value = config.max_train_epochs ?? 10;
      document.getElementById('pipe-batch-size').value = config.train_batch_size ?? 2;
      document.getElementById('pipe-dim').value = config.network_dim ?? 64;
      document.getElementById('pipe-unet-lr').value = config.unet_lr ?? config.learning_rate ?? 0.0001;
      document.getElementById('pipe-keep-tokens').value = config.keep_tokens ?? 1;
    } catch (e) {
      appendLog('加载训练预设失败', [String(e.message || e)]);
    }
  }

  api('/api/caption/presets')
    .then(async (data) => {
      captionSelect.innerHTML = '';
      for (const p of data.presets || []) {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        captionSelect.appendChild(opt);
      }
      if (!captionSelect.options.length) {
        captionSelect.innerHTML = '<option value="default">default</option>';
      }
      await fillCaptionPreset(captionSelect.value);
    })
    .catch(() => {
      captionSelect.innerHTML = '<option value="default">default</option>';
    });

  captionSelect.addEventListener('change', () => fillCaptionPreset(captionSelect.value));

  api('/api/lora/presets')
    .then(async (data) => {
      loraSelect.innerHTML = '';
      for (const p of data.presets || []) {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        loraSelect.appendChild(opt);
      }
      if (!loraSelect.options.length) {
        loraSelect.innerHTML = '<option value="morgana_star_nemesis">morgana_star_nemesis</option>';
      }
      await fillLoraPreset(loraSelect.value);
    })
    .catch(() => {
      loraSelect.innerHTML = '<option value="morgana_star_nemesis">morgana_star_nemesis</option>';
      fillLoraPreset('morgana_star_nemesis');
    });

  loraSelect.addEventListener('change', () => fillLoraPreset(loraSelect.value));

  document.getElementById('btn-lora-pipeline').addEventListener('click', () => {
    const character_root = document.getElementById('pipe-root').value.trim();
    if (!character_root) {
      appendLog('请填写角色根目录', []);
      return;
    }
    const repeat = Number(document.getElementById('pipe-repeat').value);
    const baseModel = document.getElementById('pipe-base-model').value.trim();
    if (!baseModel) {
      appendLog('请填写底模路径', []);
      return;
    }
    if (
      !confirm(
        `即将对「${character_root}」执行完整 LoRA 流程（8 步），\n` +
          `包含移动原图、处理、打标、清洗与训练，耗时可能较长，是否继续？`
      )
    ) {
      return;
    }

    const mode = document.querySelector('input[name="pipe-mode"]:checked')?.value || 'area_64';
    runJobLive('/api/jobs/lora-pipeline', {
      character_root,
      repeat_count: repeat,
      resize_mode: mode,
      target_width: Number(document.getElementById('pipe-width').value),
      target_height: Number(document.getElementById('pipe-height').value),
      rename_prefix: document.getElementById('pipe-prefix').value,
      rename_digits: Number(document.getElementById('pipe-digits').value),
      caption_preset: captionSelect.value,
      trigger_word: document.getElementById('pipe-trigger').value.trim(),
      tag_general_threshold: Number(document.getElementById('pipe-general-thresh').value),
      tag_character_threshold: Number(document.getElementById('pipe-char-thresh').value),
      lora_preset: loraSelect.value,
      pretrained_model_name_or_path: baseModel,
      output_name: document.getElementById('pipe-output-name').value.trim(),
      output_dir: document.getElementById('pipe-output-dir').value.trim(),
      max_train_epochs: Number(document.getElementById('pipe-epochs').value),
      train_batch_size: Number(document.getElementById('pipe-batch-size').value),
      network_dim: Number(document.getElementById('pipe-dim').value),
      unet_lr: Number(document.getElementById('pipe-unet-lr').value),
      keep_tokens: Number(document.getElementById('pipe-keep-tokens').value),
    }).then((job) => {
      if (job.status === 'completed' && job.result?.ok) {
        alert(job.result.message || '训练已完成！');
      }
    });
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

function initToIco() {
  document.getElementById('btn-to-ico').addEventListener('click', () => {
    const input_dir = document.getElementById('ico-input').value.trim();
    if (!input_dir) {
      appendLog('请填写图片来源目录', []);
      return;
    }
    const output_dir = document.getElementById('ico-output').value.trim() || null;
    runJob('/api/jobs/to-ico', {
      input_dir,
      output_dir,
      sizes: document.getElementById('ico-sizes').value.trim(),
      max_canvas: Number(document.getElementById('ico-max-canvas').value),
      recursive: document.getElementById('ico-recursive').checked,
    });
  });
}

function toggleInPlaceOutput(checkboxId, blockId) {
  const checked = document.getElementById(checkboxId).checked;
  document.getElementById(blockId).classList.toggle('hidden', checked);
}

function initCompress() {
  const inPlace = document.getElementById('compress-in-place');
  inPlace.addEventListener('change', () => toggleInPlaceOutput('compress-in-place', 'compress-output-block'));
  toggleInPlaceOutput('compress-in-place', 'compress-output-block');

  document.querySelectorAll('[data-preset-compress]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const preset = btn.dataset.presetCompress;
      if (preset === '500kb') {
        document.getElementById('compress-max-size').value = 500;
        document.getElementById('compress-unit').value = 'kb';
      } else if (preset === '1mb') {
        document.getElementById('compress-max-size').value = 1;
        document.getElementById('compress-unit').value = 'mb';
      } else if (preset === '2mb') {
        document.getElementById('compress-max-size').value = 2;
        document.getElementById('compress-unit').value = 'mb';
      }
    });
  });

  document.getElementById('btn-compress').addEventListener('click', () => {
    const input_dir = document.getElementById('compress-input').value.trim();
    if (!input_dir) {
      appendLog('请填写目标文件夹', []);
      return;
    }
    const in_place = document.getElementById('compress-in-place').checked;
    runJob('/api/jobs/compress', {
      input_dir,
      output_dir: in_place ? null : document.getElementById('compress-output').value.trim() || null,
      max_size: Number(document.getElementById('compress-max-size').value),
      size_unit: document.getElementById('compress-unit').value,
      output_format: document.getElementById('compress-format').value,
      recursive: document.getElementById('compress-recursive').checked,
      in_place,
    });
  });
}

function initFormatConvert() {
  const inPlace = document.getElementById('fmt-in-place');
  inPlace.addEventListener('change', () => toggleInPlaceOutput('fmt-in-place', 'fmt-output-block'));
  toggleInPlaceOutput('fmt-in-place', 'fmt-output-block');

  document.getElementById('btn-format-convert').addEventListener('click', () => {
    const input_dir = document.getElementById('fmt-input').value.trim();
    if (!input_dir) {
      appendLog('请填写目标文件夹', []);
      return;
    }
    const in_place = document.getElementById('fmt-in-place').checked;
    runJob('/api/jobs/format-convert', {
      input_dir,
      output_dir: in_place ? null : document.getElementById('fmt-output').value.trim() || null,
      target_format: document.getElementById('fmt-target').value,
      quality: Number(document.getElementById('fmt-quality').value),
      recursive: document.getElementById('fmt-recursive').checked,
      in_place,
      skip_same_format: document.getElementById('fmt-skip-same').checked,
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

  document.getElementById('btn-rename-subfolders').addEventListener('click', () => {
    const root_dir = document.getElementById('subfolder-root').value.trim();
    if (!root_dir) {
      appendLog('请填写目标根目录', []);
      return;
    }
    runJob('/api/jobs/rename-subfolders', {
      root_dir,
      prefix: document.getElementById('subfolder-prefix').value,
      remove_spaces: document.getElementById('subfolder-remove-spaces').checked,
      recursive: document.getElementById('subfolder-recursive').checked,
      dry_run: document.getElementById('subfolder-dry-run').checked,
    });
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
  document.getElementById('log-body').classList.remove('log-body-training');
  document.getElementById('train-progress-panel')?.classList.add('hidden');
});

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initNav();
  initBrowse();
  initLoraPipeline();
  initAutoTag();
  initCaptionClean();
  initLoraTrain();
  initConvert();
  initToIco();
  initCompress();
  initFormatConvert();
  initResize();
  initCrop();
  initFilter();
  initRename();
  showPage('workflow');
  loadHealth();
});
