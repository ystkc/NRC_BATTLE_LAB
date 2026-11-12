/** 对方阵容悬浮窗，仅渲染平台已公开的观测信息。 */
import { state } from './state.js';

export function createOpponentRoster({ esc, typeIcon, typeKey, freezeState, drawerEffects }) {
  const anchor = document.querySelector('#enemy-pips');
  const popup = document.createElement('div');
  popup.id = 'opponent-roster-popup';
  popup.className = 'opponent-roster-popup hidden';
  popup.setAttribute('role', 'region');
  popup.setAttribute('aria-label', '已知对方阵容');
  document.body.append(popup);
  anchor.tabIndex = 0;
  anchor.setAttribute('aria-label', '查看已知对方阵容');
  let hideTimer;

  /** 从当前观测生成公开阵容卡片，不按名称补全隐藏配置。 */
  function render() {
    const team = (state.teams.opponent || []).filter(item => item.known);
    popup.innerHTML = '<b>已知对方阵容</b>' + (team.map(item => {
      const frozen = freezeState(item);
      const types = (item.types || []).map(type => `<img class="field-type" src="${esc(typeIcon(type))}" alt="${esc(typeKey(type))}">`).join('');
      const hp = item.hp == null ? `${item.hp_percent ?? '?'}%` : `${item.hp} / ${item.max_hp}`;
      return `<div class="opponent-roster-member side-state"><div class="spirit-inline"><div class="field-avatar">${item.portrait ? `<img src="${esc(item.portrait)}" alt="">` : ''}<div class="field-types">${types}</div></div><div class="spirit-copy"><div class="side-name"><b>${esc(item.name)}</b><span>${item.fainted ? '力竭' : item.active ? '在场' : '后备'}</span></div><div>生命 ${esc(hp)} · 能量 ${esc(item.energy ?? '?')}</div>${frozen.visible ? `<div class="freeze-tag">冻结 ${frozen.freeze} 层</div>` : ''}<div>血脉 ${esc((item.bloodline_attributes || []).join(' / ') || '?')}</div>${item.ability ? `<div>特性 ${esc(item.ability)}</div>` : ''}<div class="field-effects">${drawerEffects(item)}</div></div></div></div>`;
    }).join('') || '<p>暂无已知精灵</p>');
  }

  /** 将弹窗放在阵容圆点下方，并限制在视口内。 */
  function show() {
    clearTimeout(hideTimer);
    render();
    popup.classList.remove('hidden');
    const rect = anchor.getBoundingClientRect();
    popup.style.left = `${Math.max(8, Math.min(rect.left, innerWidth - popup.offsetWidth - 8))}px`;
    popup.style.top = `${Math.max(8, Math.min(rect.bottom, innerHeight - popup.offsetHeight - 8))}px`;
  }

  /** 鼠标可从圆点移入弹窗阅读及滚动。 */
  function hideLater() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hide, 120);
  }

  function hide() {
    clearTimeout(hideTimer);
    popup.classList.add('hidden');
  }

  anchor.addEventListener('pointerenter', show);
  anchor.addEventListener('pointerleave', hideLater);
  anchor.addEventListener('focus', show);
  anchor.addEventListener('blur', hideLater);
  popup.addEventListener('pointerenter', () => clearTimeout(hideTimer));
  popup.addEventListener('pointerleave', hideLater);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); });
  window.addEventListener('resize', hide);
  return { hide, refresh: () => { if (!popup.classList.contains('hidden')) show(); } };
}
