/* 连接浏览器草稿、截图编辑器和识别任务。 */

import {SelectionCanvas} from "./canvas.js";
import {rulesEditor} from "./rules.js";

const id = name => document.getElementById(name);
const storageKey = "screen-ocr-program";
const geometryInputs = ["x", "y", "width", "height", "angle"];
const regionDefaults = {periodic: true, detect: true, confidence: 0, frame_diff_threshold: 0, allowed_chars: ""};
const regionChecks = [["region-periodic", "periodic"], ["region-detect", "detect"]];
const regionThresholds = [["region-confidence", "confidence"], ["region-frame-diff", "frame_diff_threshold"]];
let program = {
  version: 1, monitor: null, window: null, frequency_hz: 1, start_delay: 3,
  include_scores: false, record_timings: false,
  ocr_models: {detection: "small", recognition: "small"},
  regions: [], triggers: [],
};
const modelPaths = [
  ["detection-path", "detection_path"],
  ["recognition-path", "recognition_path"],
  ["recognition-keys-path", "recognition_keys_path"],
];
let sources = [];
let selected = null;
let pickTarget = null;
let pending = false;
let revision = 0;
let status = {active: false, phase: "idle", yaml: "", error: ""};
let previewing = false;
let previewKey = "";

/** 在能使用浏览器存储时恢复草稿。 */
function restore() {
  try {
    const draft = JSON.parse(localStorage.getItem(storageKey));
    if (draft?.version === 1 && Array.isArray(draft.regions) && Array.isArray(draft.triggers)) {
      program = {...program, ...draft};
      program.regions = program.regions.map(region => ({...regionDefaults, ...region}));
    }
  } catch {
    // 旧草稿读取失败时仍可导入和导出配置文件。
  }
}

/** 保存编辑中的配置。 */
function save() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(program));
  } catch {
    // 浏览器禁用存储时仍可导出配置。
  }
}

/** 显示操作反馈或服务端返回的校验错误。 */
function notice(message = "", kind = "error") {
  const target = id("notice");
  target.textContent = message;
  target.dataset.kind = kind;
  target.hidden = !message;
}

/** 发送同源请求并提取可读错误。 */
async function api(path, data) {
  const options = {cache: "no-store"};
  if (data !== undefined) {
    options.method = "POST";
    options.headers = {"Content-Type": "application/json"};
    options.body = JSON.stringify(data);
  }
  const response = await fetch(`/api/${path}`, options);
  if (response.ok) return response;
  const detail = (await response.json().catch(() => ({}))).detail;
  if (Array.isArray(detail)) {
    const lines = detail.map(error => {
      if (error.msg.startsWith("Value error, ")) return error.msg.slice(13);
      const location = error.loc.filter(part => part !== "body").join(" / ");
      return location ? `${location}：${error.msg}` : error.msg;
    });
    throw new Error(lines.join("\n"));
  }
  throw new Error(detail ?? `请求失败（${response.status}）`);
}

/** 在跑任务、读取文件或截屏时锁定相关控件。 */
function controls() {
  const locked = pending || status.active;
  const current = program.window ?? program.monitor;
  const sourceAvailable = sources.some(source => sameSource(source, current));
  editor.enabled = editor.ready && !locked && !previewing;
  id("run-settings").disabled = locked;
  id("capture-settings").disabled = locked;
  id("region-editor").disabled = locked;
  id("rules-editor").disabled = locked;
  id("start").disabled = id("trial").disabled = locked || !sourceAvailable;
  id("start").hidden = id("trial").hidden = status.active;
  id("stop").hidden = !status.active;
  id("stop").disabled = pending || status.phase === "stopping";
  id("capture").disabled = !sourceAvailable;
  id("export-config").disabled = locked || !current;
  id("import-config").disabled = id("add-trigger").disabled = locked;
  id("select-tool").disabled = id("draw-tool").disabled = !editor.enabled;
  id("redraw-region").disabled = !editor.ready;
  id("select-tool").setAttribute("aria-pressed", String(editor.ready && !previewing && editor.mode === "select"));
  id("draw-tool").setAttribute("aria-pressed", String(editor.ready && !previewing && editor.mode === "draw"));
  id("cancel-pick").hidden = editor.mode !== "pick";
  id("cancel-pick").disabled = locked;

  const hints = {
    select: "拖动矩形移动区域，拖动圆形手柄旋转",
    draw: editor.redrawTarget ? "拖拽重画当前区域" : "拖拽创建识别区域",
    pick: pickTarget?.kind === "color" ? "点选像素以设置坐标和参考色" : "点选一个点击位置",
  };
  let hint = editor.ready ? hints[editor.mode] : "选择显示器或窗口并获取截图";
  if (previewing) {
    hint = id("round-preview").hidden ? "正在加载本轮画面" : "浅青色轮廓标出最近有效识别的文字";
  }
  id("canvas-help").textContent = hint;
}

/** 避免并发操作或较早的状态请求覆盖当前状态。 */
async function perform(operation) {
  if (pending) return;
  pending = true;
  revision++;
  notice();
  controls();
  try {
    await operation();
  } catch (error) {
    notice(error.message);
  } finally {
    pending = false;
    controls();
  }
}

/** 得到窗口或显示器在来源菜单中的标识。 */
function sourceKey(source) {
  if (!source) return "";
  return source.handle ? `window:${source.handle}:${source.pid}:${source.class_name}` : `monitor:${source.index}`;
}

/** 比较来源及其截图坐标系。 */
function sameSource(a, b) {
  return Boolean(a && b && sourceKey(a) === sourceKey(b)
    && ["width", "height", "left", "top"].every(key => a[key] === b[key]));
}

/** 更新配置中的截图来源。 */
function setSource(source) {
  program.monitor = source && !source.handle ? source : null;
  program.window = source?.handle ? source : null;
}

/** 显示当前可选的显示器和窗口。 */
function showSources() {
  const menu = id("capture-source");
  const current = program.window ?? program.monitor;
  const matched = sources.find(source => sameSource(source, current));
  const displays = document.createElement("optgroup");
  const windows = document.createElement("optgroup");
  displays.label = "显示器";
  windows.label = "窗口";
  menu.replaceChildren();
  if (!matched) {
    const placeholder = current?.handle ? "窗口不可用，请刷新或重新选择" : "请选择显示器或窗口";
    menu.add(new Option(placeholder, ""));
  }
  for (const source of sources) {
    const name = source.handle ? source.title : `显示器 ${source.index}`;
    const option = new Option(`${name} · ${source.width} × ${source.height}`, sourceKey(source));
    (source.handle ? windows : displays).append(option);
  }
  for (const group of [displays, windows]) {
    if (group.children.length) menu.append(group);
  }
  menu.value = sourceKey(matched);
}

/** 刷新来源并清除已经失效的截图预览。 */
async function refreshSources() {
  const lists = await Promise.all(["monitors", "windows"].map(async path => (await api(path)).json()));
  sources = lists.flat();
  const current = program.window ?? program.monitor;
  if (!current && lists[0].length) {
    setSource(lists[0][0]);
    save();
  }
  if (current && !sources.some(source => sameSource(source, current))) {
    editor.clear();
    tool("select");
    showGeometry();
    if (current.handle && sources.some(source => sourceKey(source) === sourceKey(current))) {
      notice("窗口尺寸已变更，请重新选择窗口并检查截图中的区域和坐标", "info");
    }
  }
  showSources();
}

/** 切换截图工具并取消旧的取点目标。 */
function tool(mode, target = null) {
  pickTarget = null;
  if (previewing) showRoundPreview(false);
  editor.tool(mode, {target});
  controls();
}

/** 将原始像素坐标显示在截图工具栏。 */
function showPosition(position) {
  id("pixel-position").textContent = position
    ? `X ${position.x} · Y ${position.y}${position.color ? ` · ${position.color}` : ""}`
    : "";
}

/** 从条件表单进入取点模式，并在选择后回到该表单。 */
function beginPick(button, kind, receive) {
  id("workbench").scrollIntoView({block: "start"});
  if (previewing) showRoundPreview(false);
  if (!editor.ready) {
    id("capture").focus({preventScroll: true});
    notice("请先获取截图，再在截图中点选");
    return;
  }
  pickTarget = {button, kind};
  editor.tool("pick", {picker(point, color) {
    if (button.isConnected) receive(point, color);
    finishPick();
  }});
  controls();
}

/** 结束取点并恢复对应条件的位置。 */
function finishPick() {
  const button = pickTarget?.button;
  tool("select");
  if (button?.isConnected) {
    button.scrollIntoView({block: "nearest"});
    button.focus({preventScroll: true});
  }
}

/** 更新选区的几何输入和校正预览。 */
function showGeometry() {
  id("crop-preview").hidden = !selected || !editor.ready;
  if (!selected) return;
  for (const key of geometryInputs) id(`region-${key}`).value = selected[key];
  if (editor.ready) editor.preview(id("rectified"), selected);
}

/** 收集可能引用 OCR 区域的条件和操作。 */
function triggerRegionReferences(trigger) {
  const references = [...trigger.conditions];
  for (const action of trigger.actions) {
    if (action.type === "ocr") references.push(action);
    if (action.type === "click") {
      for (const candidate of action.candidates) references.push(...candidate.conditions);
    }
  }
  return references;
}

/** 只将符合显示条件的区域标在截图上。 */
function showRegionOverlay() {
  const names = new Set();
  for (const trigger of program.triggers) {
    if (trigger.show === false) continue;
    for (const reference of triggerRegionReferences(trigger)) names.add(reference.region);
  }
  editor.regions = program.regions.filter(region => region.periodic || names.has(region.name));
  editor.selected = selected;
  editor.paint();
}

/** 绘制区域列表以及当前区域的备注。 */
function showRegions() {
  const list = id("region-list");
  list.replaceChildren();
  for (const region of program.regions) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "region-item";
    item.setAttribute("aria-pressed", String(region === selected));
    const name = document.createElement("span");
    name.textContent = region.name;
    const mode = document.createElement("span");
    mode.className = "meta";
    mode.textContent = region.periodic ? "每轮" : "按触发器";
    item.append(name, mode);
    item.addEventListener("click", () => {
      selectRegion(region);
      tool("select");
    });
    list.append(item);
  }
  id("region-count").textContent = `${program.regions.length} 个`;
  id("regions-empty").hidden = program.regions.length > 0;
  id("region-details").hidden = !selected;
  if (selected) {
    id("region-name").value = selected.name;
    id("region-allowed-chars").value = selected.allowed_chars ?? "";
    for (const [input, field] of regionChecks) id(input).checked = selected[field];
    for (const [input, field] of regionThresholds) id(input).value = selected[field];
  }
  showGeometry();
  showRegionOverlay();
}

/** 将区域标为当前编辑项。 */
function selectRegion(region) {
  if (selected === region) return;
  selected = region;
  showRegions();
}

/** 保存新画的区域或替换已有区域的几何形状。 */
function createRegion(rect, target) {
  if (!target) {
    const names = new Set(program.regions.map(region => region.name));
    let number = 1;
    while (names.has(`区域 ${number}`)) number++;
    target = {...regionDefaults, name: `区域 ${number}`};
    program.regions.push(target);
  }
  Object.assign(target, rect);
  finishRegionEdit(target);
}

/** 复制当前区域的几何和识别设置，并生成唯一备注名。 */
function copyRegion() {
  const base = `${selected.name} 副本`;
  const names = new Set(program.regions.map(region => region.name));
  let name = base;
  for (let number = 2; names.has(name); number++) name = `${base} ${number}`;
  const region = {...selected, name};
  program.regions.push(region);
  finishRegionEdit(region);
}

/** 保存新区域并选中备注名，方便继续调整。 */
function finishRegionEdit(region) {
  selected = region;
  tool("select");
  showRegions();
  rules.render();
  save();
  id("region-name").focus({preventScroll: true});
  id("region-name").select();
}

/** 更新触发器对重命名或删除区域的引用。 */
function replaceRegionReferences(previous, next) {
  for (const trigger of program.triggers) {
    for (const reference of triggerRegionReferences(trigger)) {
      if (reference.region === previous) reference.region = next;
    }
  }
}

/** 截图倒计时结束后加载所选来源的原图。 */
async function screenshot() {
  try {
    for (let remaining = Number(id("capture-delay").value); remaining > 0; remaining--) {
      id("capture").textContent = `${remaining} 秒后截图`;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    id("capture").textContent = "正在截图…";
    await editor.load(await (await api("screenshot", program.window ?? program.monitor)).blob());
    tool(program.regions.length ? "select" : "draw");
    showGeometry();
  } finally {
    id("capture").textContent = "获取截图";
  }
}

/** 显示运行画面或返回保留的截图编辑界面。 */
function showRoundPreview(show) {
  const wasPreviewing = previewing;
  previewing = show && Boolean(status.recording);
  const button = id("round-view");
  const image = id("round-preview");
  button.hidden = !status.recording;
  button.setAttribute("aria-pressed", String(previewing));
  image.hidden = !previewing || previewKey !== `${status.recording}/${status.rounds}`
    || !image.complete || !image.naturalWidth;
  editor.stage.hidden = previewing || !editor.ready;
  editor.empty.hidden = previewing || editor.ready;
  if (wasPreviewing && !previewing) editor.fit();
  controls();
}

/** 显示每个区域的最近有效文字和帧差跳过次数。 */
function showRegionResults(regions) {
  const rows = regions.map(region => {
    const row = document.createElement("tr");
    const name = document.createElement("th");
    name.scope = "row";
    name.textContent = region.name;
    row.append(name);
    row.insertCell().textContent = region.last_valid.join("\n") || "—";
    row.insertCell().textContent = region.skipped_frames;
    return row;
  });
  id("region-result-rows").replaceChildren(...rows);
  id("region-results").hidden = !rows.length;
}

/** 更新任务状态、轮次和下载入口。 */
function showStatus({preview_jpeg: jpeg, ...next}) {
  if (next.error && next.error !== status.error) notice(next.error);
  const newRecording = next.recording !== status.recording;
  const newRound = newRecording || next.rounds !== status.rounds;
  status = next;
  const badge = id("run-status");
  badge.dataset.phase = status.phase;
  const seconds = (status.remaining_seconds ?? 0).toFixed(1);
  badge.textContent = {
    preparing: "准备 OCR 模型",
    starting: `准备中 · ${seconds} 秒`,
    running: status.trial ? "试跑中" : "运行中",
    waiting: `等待中 · ${seconds} 秒`,
    stopping: "正在停止",
    error: "运行中断",
    idle: "待机",
  }[status.phase];
  id("round-count").textContent = status.rounds ? `第 ${status.rounds} 轮` : "";
  const output = id("yaml-output");
  const text = status.yaml || "运行后显示最近一轮的 YAML。";
  if (output.textContent !== text) output.textContent = text;
  output.dataset.empty = String(!status.yaml);
  id("copy-result").disabled = !status.yaml;
  id("download-record").disabled = !status.recording;
  if (newRound) showRegionResults(status.regions ?? []);
  if (newRecording) {
    previewKey = "";
    id("round-preview").removeAttribute("src");
  }
  if (jpeg) {
    previewKey = `${status.recording}/${status.rounds}`;
    id("round-preview").src = `data:image/jpeg;base64,${jpeg}`;
  }
  if (newRound || jpeg) {
    showRoundPreview(newRecording || previewing);
  } else {
    controls();
  }
}

/** 定时刷新状态，忽略较旧请求返回的结果。 */
async function poll() {
  const connection = id("connection");
  const requested = revision;
  try {
    if (!pending) {
      const preview = previewing || !status.recording ? `?after_preview=${encodeURIComponent(previewKey)}` : "";
      const next = await (await api(`status${preview}`)).json();
      if (requested === revision && !pending) showStatus(next);
      connection.hidden = true;
    }
  } catch {
    connection.textContent = "与本机 OCR 服务的连接中断，正在重连。";
    connection.hidden = false;
  } finally {
    setTimeout(poll, status.active ? 250 : 700);
  }
}

/** 在任务提交前退出取点或框选模式。 */
async function start(trial) {
  tool("select");
  showStatus(await (await api("start", {program, trial})).json());
}

/** 将文件内容交给浏览器下载。 */
function download(url, filename = "") {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
}

/** 仅显示选中本地模型对应的文件路径输入。 */
function showModelFiles() {
  const localDetection = program.ocr_models.detection === "local";
  const localRecognition = program.ocr_models.recognition === "local";
  id("model-files").hidden = !localDetection && !localRecognition;
  id("detection-file").hidden = !localDetection;
  id("recognition-file").hidden = !localRecognition;
  id("recognition-keys-file").hidden = !localRecognition;
}

/** 用当前配置填充界面。 */
function showProgram() {
  id("frequency").value = program.frequency_hz ?? "";
  id("start-delay").value = program.start_delay ?? "";
  id("include-scores").checked = program.include_scores;
  id("record-timings").checked = program.record_timings;
  id("detection-model").value = program.ocr_models.detection;
  id("recognition-model").value = program.ocr_models.recognition;
  for (const [input, field] of modelPaths) id(input).value = program.ocr_models[field] ?? "";
  showModelFiles();
  showSources();
  showRegions();
  rules.render();
  controls();
}

const editor = new SelectionCanvas({
  viewport: id("viewport"),
  stage: id("stage"),
  overlay: id("overlay"),
  image: id("snapshot"),
  empty: id("capture-empty"),
  select: selectRegion,
  create: createRegion,
  change(commit) {
    showGeometry();
    if (commit) save();
  },
  position: showPosition,
});
const rules = rulesEditor(id("rules"), () => program, () => {
  save();
  showRegionOverlay();
}, beginPick);

id("capture-source").addEventListener("change", event => {
  const source = sources.find(item => sourceKey(item) === event.target.value);
  setSource(source);
  editor.clear();
  tool("select");
  showGeometry();
  save();
});
id("refresh-sources").addEventListener("click", () => perform(refreshSources));
id("capture").addEventListener("click", () => perform(screenshot));
id("select-tool").addEventListener("click", () => tool("select"));
id("draw-tool").addEventListener("click", () => tool("draw"));
id("cancel-pick").addEventListener("click", finishPick);
id("round-view").addEventListener("click", () => {
  if (pickTarget) finishPick();
  showRoundPreview(!previewing);
});
id("round-preview").addEventListener("load", () => {
  if (previewing) showRoundPreview(true);
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && pickTarget) finishPick();
});
id("redraw-region").addEventListener("click", () => tool("draw", selected));
id("copy-region").addEventListener("click", copyRegion);
id("delete-region").addEventListener("click", () => {
  replaceRegionReferences(selected.name, "");
  program.regions = program.regions.filter(region => region !== selected);
  selectRegion(null);
  tool("select");
  rules.render();
  save();
});
id("region-name").addEventListener("change", event => {
  const name = event.target.value.trim();
  if (!name || program.regions.some(region => region !== selected && region.name === name)) {
    event.target.value = selected.name;
    notice("请为区域填写唯一的备注名");
    return;
  }
  replaceRegionReferences(selected.name, name);
  selected.name = name;
  notice();
  showRegions();
  rules.render();
  save();
});
for (const [input, field] of regionChecks) {
  id(input).addEventListener("change", event => {
    selected[field] = event.target.checked;
    showRegions();
    save();
  });
}
id("region-allowed-chars").addEventListener("input", event => {
  selected.allowed_chars = event.target.value;
  save();
});
for (const [input, field] of regionThresholds) {
  id(input).addEventListener("change", event => {
    const target = event.target;
    if (target.value !== "" && target.validity.valid) {
      selected[field] = target.valueAsNumber;
      save();
    }
    target.value = selected[field];
  });
}
for (const key of geometryInputs) {
  id(`region-${key}`).addEventListener("change", event => {
    const input = event.target;
    if (input.value !== "" && input.validity.valid) {
      selected[key] = input.valueAsNumber;
      editor.paint();
      save();
    }
    showGeometry();
  });
}
id("add-trigger").addEventListener("click", rules.add);

for (const [input, field] of [["frequency", "frequency_hz"], ["start-delay", "start_delay"]]) {
  id(input).addEventListener("input", event => {
    const value = event.target.valueAsNumber;
    program[field] = Number.isFinite(value) ? value : null;
    save();
  });
}
id("include-scores").addEventListener("change", event => {
  program.include_scores = event.target.checked;
  save();
});
id("record-timings").addEventListener("change", event => {
  program.record_timings = event.target.checked;
  save();
});
for (const stage of ["detection", "recognition"]) {
  id(`${stage}-model`).addEventListener("change", event => {
    program.ocr_models[stage] = event.target.value;
    showModelFiles();
    save();
  });
}
for (const [input, field] of modelPaths) {
  id(input).addEventListener("input", event => {
    program.ocr_models[field] = event.target.value.trim() || null;
    save();
  });
}
id("trial").addEventListener("click", () => perform(() => start(true)));
id("start").addEventListener("click", () => perform(() => start(false)));
id("stop").addEventListener("click", () => perform(async () => {
  showStatus(await (await api("stop", {})).json());
}));
id("copy-result").addEventListener("click", async event => {
  const button = event.currentTarget;
  try {
    await navigator.clipboard.writeText(status.yaml);
    button.textContent = "已复制";
    setTimeout(() => { button.textContent = "复制本轮"; }, 1300);
  } catch (error) {
    notice(error.message);
  }
});
id("download-record").addEventListener("click", () => {
  if (status.recording) download(`/api/recordings/${status.recording}`, status.recording);
});
id("import-config").addEventListener("click", () => id("config-file").click());
id("config-file").addEventListener("change", event => {
  const file = event.target.files[0];
  event.target.value = "";
  if (!file) return;
  perform(async () => {
    const imported = await (await api("config/import", {yaml: await file.text()})).json();
    if (!sameSource(program.window ?? program.monitor, imported.window ?? imported.monitor)) editor.clear();
    program = imported;
    selected = null;
    tool("select");
    showProgram();
    save();
    notice("已导入配置", "info");
  });
});
id("export-config").addEventListener("click", () => perform(async () => {
  const result = await api("config/export", program);
  const url = URL.createObjectURL(await result.blob());
  download(url, "screen-ocr.yaml");
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}));

restore();
showProgram();
await perform(refreshSources);
poll();
