/** 阵容编辑器与面板预览。 */
import { state } from './state.js';
import { api } from './api.js';
import { saveSession } from './session.js';

export function createRosterEditor({ $, esc, formFor, pokemonRow, baseName, renderTeamCard, toast }) {
  /** 注入界面回调，保持网络和展示模块职责清晰。 */
  const aptitudeFieldDict = {'生命': 'hp', '物攻': 'atk', '魔攻': 'spatk', '物防': 'def', '魔防': 'spdef', '速度': 'speed'}
  const aptitudeNamesDict = {'hp': '生命', 'atk': '物攻', 'spatk': '魔攻', 'def': '物防', 'spdef': '魔防', 'speed': '速度'}
  function aptitudeField(name) {
    return aptitudeFieldDict[name] || 'unknown';
  }
  
  function aptitudeName(field) {
    return aptitudeNamesDict[field] || '未知';
  }
  
  function natureBonusText(index, nature) {
    const item = state.teams.own[index];
    const form = item ? formFor(item.name) || item.form || {} : {};
    const bonus = form.customization?.nature_bonus?.[nature] || {};
    const labels = { hp: '生命', atk: '物攻', def: '物防', spatk: '魔攻', spdef: '魔防', speed: '速度' };
    return Object.entries(bonus).filter(([, value]) => Number(value)).map(([key, value]) => `${labels[key] || key} ${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(1)}`).join(' / ');
  }
  
  function editorFieldMarkup(field, value, choices) {
    const options = choices.map((choice) => `<button type="button" data-editor-option="${esc(choice.name)}" data-editor-option-field="${field}">${esc(choice.name)}${choice.percentage ? ` <small>(${Number(choice.percentage).toFixed(1)}%)</small>` : ''}${choice.bonus_text ? ` <small>${esc(choice.bonus_text)}</small>` : ''}</button>`).join('');
    return `<div class="editor-autocomplete"><input type="text" autocomplete="off" data-editor-autocomplete data-editor-field="${field}" value="${esc(value)}"><div class="editor-suggest hidden" data-editor-suggest="${field}">${options}</div></div>`;
  }
  
  function choiceMatches(choices, query) {
    const text = String(query || '').trim().toLowerCase();
    if (!text) return choices;
    let result = choices.filter((choice) => [choice.name, choice.initials, choice.pinyin, ...(choice.aliases || [])].some((value) => String(value || '').toLowerCase().includes(text)));
    if (result.length < 5) {
      result = [...result, ...choices.filter((choice) => choice.pinyin.includes(text))];
    }
    return result.sort((a, b) => a.name.length - b.name.length).slice(0, 5);
  }
  
  function editorChoices(index, field) {
    const item = state.teams.own[index];
    const form = item ? formFor(item.name) || item.form || {} : {};
    const customization = form.customization || {};
    if (field === 'nature') return customization.natures || [];
    if (field === 'bloodline') return customization.bloodlines || [];
    if (field === 'aptitude')
    {
        const aptitudes = customization.aptitudes || [];
        const values = selectedAptitudes(item, customization).map((aptitude) => aptitude.name);
        return aptitudes.filter((aptitude) => !values.includes(aptitude.name));
    }
    if (field === 'skill') {
      const skills = state.catalog.skills || [];
      const values = selectedSkills(item);
      return skills.filter((skill) => !values.includes(skill.name) || skill.name === '借用');
    }
    return [];
  }
  
  function renderEditorSuggestions(input) {
    const box = input?.parentElement?.querySelector('[data-editor-suggest]');
    if (!input || !box) return;
    const query = String(input.value || '').trim().toLowerCase();
    const index = Number($('#hover-card')?.dataset.floatingEditIndex);
    const choices = editorChoices(index, input.dataset.editorField).map((choice) => input.dataset.editorField === 'nature' ? { ...choice, bonus_text: natureBonusText(index, choice.name) } : choice);
    const rows = choiceMatches(choices, query);
    box.innerHTML = rows.map((choice) => `<button type="button" data-editor-option="${esc(choice.name)}" data-editor-option-field="${esc(input.dataset.editorField)}">${esc(choice.name)}${choice.percentage ? ` <small>(${Number(choice.percentage).toFixed(1)}%)</small>` : ''}${choice.bonus_text ? ` <small>${esc(choice.bonus_text)}</small>` : ''}</button>`).join('');
    box.classList.toggle('hidden', !rows.length);
  }
  
  function applyEditorOption(button) {
    const field = button.dataset.editorOptionField;
    const value = button.dataset.editorOption;
    const index = Number($('#hover-card')?.dataset.floatingEditIndex);
    if (!field || !Number.isInteger(index) || index < 0) return false;
    if (field === 'aptitude') return addAptitude(index, value);
    if (field === 'skill') return addSkill(index, value);
    updateCreatureBase(index, field, value);
    const anchor = document.querySelector(`#own-team [data-edit-index="${index}"]`);
    renderCreatureEditor(index, anchor);
    return true;
  }
  
  function editorPosition(anchor) {
    const card = $('#hover-card');
    if (!card || !anchor) return;
    const rect = anchor.getBoundingClientRect();
    const gap = 10;
    const left = Math.min(window.innerWidth - card.offsetWidth - 12, Math.max(12, rect.right + gap));
    const top = Math.min(window.innerHeight - card.offsetHeight - 12, Math.max(12, rect.top));
    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
  }
  
  function renderCreatureEditor(index, anchor=null) {
    if (!anchor) anchor = document.querySelector(`#own-team [data-edit-index="${index}"]`);
    const item = state.teams.own[index];
    if (!item) return;
    const form = formFor(item.name) || item.form || {};
    const customization = form.customization || {};
    const base = item.base || {};
    const nature = base.nature || customization.natures?.[0]?.name || '';
    const bloodline = Array.isArray(base.bloodline_attributes) ? base.bloodline_attributes[0] || '' : base.bloodline_attributes || '';
    const bonusText = natureBonusText(index, nature);
    const forms = (pokemonRow(item.name)?.forms || []).map((choice) => `<button type="button" class="form-choice ${choice.name === item.name ? 'active' : ''}" data-editor-form="${esc(choice.name)}">${esc(choice.name)}</button>`).join('');
    const natures = editorFieldMarkup('nature', nature, (customization.natures || []).map((choice) => ({ ...choice, bonus_text: natureBonusText(index, choice.name) })));
    const bloodlines = editorFieldMarkup('bloodline', bloodline, customization.bloodlines || []);
    const aptitudes = aptitudeEditorMarkup(item, customization);
    const skills = skillEditorMarkup(item);
    const card = $('#hover-card');
    card.innerHTML = `<div class="hover-title"><b>${esc(item.name)}</b><button type="button" data-editor-close>×</button></div><img class="art" src="${esc(form.portrait || form.art || '')}" alt=""><label class="editor-label">Form</label><div class="form-list">${forms}</div><label class="editor-label">Nature</label><div class="editor-field">${natures}<span class="nature-bonus">${esc(bonusText)}</span></div><label class="editor-label">Bloodline</label><div class="editor-field">${bloodlines}</div><label class="editor-label">Aptitudes</label><div class="editor-field">${aptitudes}</div><label class="editor-label">Skills</label><div class="editor-field">${skills}</div><small class="hover-help">Changes are saved to this roster.</small>`;
    card.dataset.floatingEditIndex = String(index);
    card.classList.remove('hidden');
    editorPosition(anchor);
  }
  
  function closeCreatureEditor() {
    const card = $('#hover-card');
    card.classList.add('hidden');
    card.removeAttribute('data-floating-edit-index');
  }
  
  function updateCreatureBase(index, field, value) {
    const item = state.teams.own[index];
    if (!item) return;
    item.base = { ...(item.base || {}) };
    if (field === 'bloodline') item.base.bloodline_attributes = value ? [value] : [];
    else item.base[field] = value;
    saveSession();
  }
  
  function setForm(index, formName) {
    const item = state.teams.own[index];
    if (!item) return;
    item.name = formName;
    item.base_name = baseName(item.name);
    item.form = formFor(item.name) || item.form;
    saveSession();
    renderTeamCard('own', index, item);
  }
  
  function selectedAptitudes(item, customization) {
    const values = item.base?.individual_values || {};
    const result = Object.entries(values).map(([field, value]) => {
      return { field, name: aptitudeName(field) || field, value: Math.min(10, Math.max(1, Number(value) || 8)) };
    }).slice(0, 3);
    return result;
  }
  
  function aptitudeEditorMarkup(item, customization) {
    const selected = selectedAptitudes(item, customization);
    const rows = selected.map((entry) => `<div class="editor-entry aptitude-entry"><span>${esc(entry.name)}</span><input type="number" min="1" max="10" step="1" value="${entry.value}" data-aptitude-value="${esc(entry.field)}"><button type="button" data-remove-aptitude="${esc(entry.field)}">×</button></div>`).join('');
    const input = `<div class="editor-autocomplete"><input type="text" autocomplete="off" placeholder="输入资质名称 / 拼音 / 首字母" data-editor-autocomplete data-editor-field="aptitude"><div class="editor-suggest hidden" data-editor-suggest="aptitude"></div></div>`;
    return `${rows}${input}<small class="hover-help">最多选择 3 项，新增资质默认 8</small>`;
  }
  
  function selectedSkills(item) {
    return (item.skills || []).map((skill) => skill.name);
  }
  
  function normalizedBase(item) {
    const base = { ...(item.base || {}) };
    const values = Object.entries(base.individual_values || {})
      .filter(([, value]) => Number(value) > 0)
      .slice(0, 3)
      .reduce((result, [field, value]) => {
        result[field] = Math.min(10, Math.max(1, Number(value) || 8));
        return result;
      }, {});
    base.individual_values = values;
    return base;
  }
  
  function skillEditorMarkup(item) {
    const selected = selectedSkills(item);
    const rows = selected.map((name, index) => `<div class="editor-entry skill-entry"><span>${index + 1}. ${esc(name)}</span><button type="button" data-remove-skill="${index}">×</button></div>`).join('');
    const input = `<div class="editor-autocomplete"><input type="text" autocomplete="off" placeholder="输入技能名称 / 拼音 / 首字母" data-editor-autocomplete data-editor-field="skill"><div class="editor-suggest hidden" data-editor-suggest="skill"></div></div>`;
    return `${rows}${input}<small class="hover-help">最多选择 4 个技能</small>`;
  }
  
  function addAptitude(index, name) {
    const item = state.teams.own[index];
    if (!item) return false;
    const field = aptitudeField(name);
    item.base = { ...(item.base || {}), individual_values: { ...(item.base?.individual_values || {}) } };
    const values = item.base.individual_values;
    if (values[field] != null) return false;
    if (Object.keys(values).length >= 3) {
      toast('最多添加 3 项资质');
      renderCreatureEditor(index);
      return false;
    }
    values[field] = 8;
    saveSession();
    renderCreatureEditor(index);
    return true;
  }
  
  function removeAptitude(index, field) {
    const item = state.teams.own[index];
    if (!item) return;
    item.base = { ...(item.base || {}), individual_values: { ...(item.base?.individual_values || {}) } };
    delete item.base.individual_values[field];
    saveSession();
    renderCreatureEditor(index);
  }
  
  function addSkill(index, name) {
    const item = state.teams.own[index];
    if (!item) return false;
    const skills = selectedSkills(item);
    if (skills.includes(name) && name !== '借用') return false;
    if (skills.length >= 4) {
      toast('最多添加 4 个技能');
      renderCreatureEditor(index);
      return false;
    }
    item.skills = [...skills, name].map((skill) => ({ name: skill }));
    saveSession();
    renderCreatureEditor(index);
    return true;
  }
  
  function removeSkill(index, skillIndex) {
    const item = state.teams.own[index];
    if (!item) return;
    item.skills = selectedSkills(item).filter((_, currentIndex) => currentIndex !== Number(skillIndex)).map((name) => ({ name }));
    saveSession();
    renderCreatureEditor(index);
  }
  
  function previewPosition(anchor) {
    const card = $('#preview-card');
    if (!card || !anchor) return;
    const rect = anchor.getBoundingClientRect();
    const gap = 10;
    const left = Math.min(window.innerWidth - card.offsetWidth - 12, Math.max(12, rect.right + gap));
    const top = Math.min(window.innerHeight - card.offsetHeight - 12, Math.max(12, rect.top));
    card.style.left = `${left}px`;
    card.style.top = `${top}px`;
  }
  
  function previewPayload(item) {
    return {
      name: item.name,
      base: normalizedBase(item),
      skills: selectedSkills(item),
    };
  }
  
  function renderCreaturePreview(data) {
    const stats = data.stats || {};
    const stat_icons = data.stat_icons || {};
    const entries = [
      ['hp', 'HP'], ['def', 'DEF'],
      ['atk', 'ATK'], ['spdef', 'M.DEF'], 
      ['spatk', 'M.ATK'], ['speed', 'SPD'],
    ];
    const statHtml = entries.map(([key, label]) => `<div class="preview-stat"><img src="${esc(stat_icons[key] || '')}" alt="${label}"><b>${label}</b><span>${esc(data.stats_known?.[key] === false ? '?' : (stats[key] ?? '-'))}</span></div>`).join('');
    const bloodline = (data.bloodline_attributes || []).join(' / ');
    $('#preview-card').innerHTML = `<img class="preview-art" src="${esc(data.portrait || '')}" alt=""><div class="preview-title"><b>${esc(data.name || '')}</b><span>${esc(data.nature || '?')}</span></div><div class="preview-bloodline">${data.bloodline_icon ? `<img src="${esc(data.bloodline_icon)}" alt="">` : ''}<span>${esc(bloodline || '-')}</span></div><div class="preview-stats">${statHtml}</div>`;
  }
  
  function previewForms(index) {
    const item = state.teams.own[index];
    return item ? (pokemonRow(item.name)?.forms || []) : [];
  }
  
  async function loadCreaturePreview(index, anchor, name) {
    const item = state.teams.own[index];
    const card = $('#preview-card');
    if (!item || !card) return;
    const requestId = ++state.previewRequest;
    state.previewAnchor = anchor;
    card.dataset.previewIndex = String(index);
    card.innerHTML = '<div class="preview-loading">Loading…</div>';
    card.classList.remove('hidden');
    previewPosition(anchor);
    try {
      const data = await api('/api/pokemon/preview', { method: 'POST', body: JSON.stringify({ ...previewPayload(item), name }) });
      if (requestId !== state.previewRequest || state.previewAnchor !== anchor) return;
      renderCreaturePreview(data);
      previewPosition(anchor);
    } catch (error) {
      if (requestId === state.previewRequest) card.innerHTML = `<div class="preview-loading">${esc(error.message)}</div>`;
    }
  }
  
  async function showCreaturePreview(index, anchor) {
    const item = state.teams.own[index];
    if (!item) return;
    const forms = previewForms(index);
    state.previewFormIndex = Math.max(0, forms.findIndex((form) => form.name === item.name));
    await loadCreaturePreview(index, anchor, forms[state.previewFormIndex]?.name || item.name);
  }
  
  function cyclePreviewForm(delta) {
    const card = $('#preview-card');
    const index = Number(card?.dataset.previewIndex);
    if (!card || card.classList.contains('hidden') || !Number.isInteger(index) || !state.previewAnchor) return;
    const forms = previewForms(index);
    if (forms.length < 2) return;
    state.previewFormIndex = (state.previewFormIndex + delta + forms.length) % forms.length;
    loadCreaturePreview(index, state.previewAnchor, forms[state.previewFormIndex].name);
    setForm(index, forms[state.previewFormIndex].name);
  }
  
  function hideCreaturePreview() {
    state.previewRequest += 1;
    state.previewAnchor = null;
    state.previewFormIndex = 0;
    $('#preview-card')?.classList.add('hidden');
  }
  

  return { aptitudeField, aptitudeName, natureBonusText, editorFieldMarkup, choiceMatches, editorChoices, renderEditorSuggestions, applyEditorOption, editorPosition, renderCreatureEditor, closeCreatureEditor, updateCreatureBase, setForm, selectedAptitudes, aptitudeEditorMarkup, selectedSkills, normalizedBase, skillEditorMarkup, addAptitude, removeAptitude, addSkill, removeSkill, previewPosition, previewPayload, renderCreaturePreview, previewForms, loadCreaturePreview, showCreaturePreview, cyclePreviewForm, hideCreaturePreview };
}

