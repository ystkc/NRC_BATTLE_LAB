/** 战报与状态名称的纯展示格式。 */
export const RELATION_NAMES = { immune: '无', very_resistant: '双重抵抗', resistant: '抵抗', normal: '平衡', effective: '克制', super_effective: '双重克制', unknown: '无' };

const EFFECT_NAMES = { poison: '中毒', burn: '灼烧', freeze: '冻结', leech: '寄生', electric: '引电', meteor: '星陨', cute: '萌化', best_partner: '最好的伙伴', hp: '生命', energy: '能量', status: '状态', fainted: '力竭', ability: '特性', atk: '攻击', def: '物防', spatk: '魔攻', spdef: '魔防', speed: '速度', combo: '连击', priority: '先手', action_speed: '行动速度', skill_power: '全技能威力', skill_power_pct: '全技能威力', skill_cost: '全技能能耗', power_multiplier: '威力倍率加成', life_drain: '吸血', next_attack_power: '下次攻击威力', next_attack_power_pct: '下次攻击威力比例' };

export function relationLabel(value) { return RELATION_NAMES[String(value || 'unknown')] || String(value || '无'); }

export function effectName(value) {
  const name = String(value || '');
  const stat = name.match(/^(atk|def|spatk|spdef|speed)_(up|down)$/);
  if (stat) return `${EFFECT_NAMES[stat[1]]}${stat[2] === 'up' ? '提升' : '降低'}`;
  return EFFECT_NAMES[name] || name.replaceAll('_', ' ');
}


export function eventText(event) {
  const actor = event.team === 'a' ? '我方' : event.team === 'b' ? '敌方' : '';
  if (event.type === 'round_start') return `## 第${event.turn || '?'}回合`;
  if (event.type === 'battle_start') return '[对战开始] 双方选择行动';
  if (event.type === 'ability') {
    const detail = (event.description || event.message || '').replace(/^\[[^\]]*\]\s*/, '');
    return `[特性：${event.ability || '未知特性'}] ${detail}`.trim();
  }
  if (event.type === 'selection') {
    if (event.resonance) {
      const names = { boss: '进化之力', willpower: '愿力强化', solar_heal: '光合治疗' };
      return `[${actor}使用共鸣魔法] ${names[event.resonance] || event.resonance}`;
    }
    if (event.kind === 'switch') return `[${actor}选择切换精灵] ${event.switch_name || '完成'}`;
    if (event.status === 'locked') return event.skill ? `[${actor}选择技能] ${event.skill}，选择了技能` : `[${actor}选择技能] 完成`;
    return `[${actor}选择技能] ${event.skill || event.action_key || '完成'}`;
  }
  if (event.type === 'skill') {
    const details = [];
    if (event.final_power != null && Number(event.final_power) >= 0) details.push(`威力 ${event.final_power}`);
    if (Number(event.final_damage) > 0) details.push(`造成 ${event.final_damage} 伤害${event.effect_indicator && event.effect_indicator !== 'normal' ? `（${relationLabel(event.effect_indicator)}）` : ''}`);
    if (Number(event.damage_per_hit) > 0 && Number(event.hits || 1) > 1) details.push(`${event.damage_per_hit}/段 × ${event.hits}`);
    if (event.energy_cost != null) details.push(`能耗 ${event.energy_cost}`);
    if (event.remaining_energy != null) details.push(`剩余能量 ${event.remaining_energy}`);
    for (const change of event.resource_changes || []) {
      const side = change.team === 'a' ? '我方' : '敌方';
      details.push(`${side}${change.pokemon || '精灵'}${effectName(change.kind)} ${change.before}→${change.after}`);
    }
    return `[${actor}使用技能] ${event.skill || '技能'}${details.length ? `，${details.join('，')}` : ''}`;
  }
  if (event.type === 'switch' || event.switched_to || event.target_switched_to) return `[${actor}切换精灵] ${event.switched_to || event.target_switched_to || '未知精灵'}`;
  if (event.type === 'turn') return `[回合结束] 第${event.after?.turn || event.turn || '?'}回合`;
  if (event.type === 'status') return `[状态结算] ${event.status || event.message || '状态变化'}`;
  if (event.type === 'state_change') {
    const changes = (event.changes || []).map((change) => {
      const before = change.before == null ? '-' : change.before;
      const after = change.after == null ? '-' : change.after;
      if (change.kind === 'skill') {
        const field = { energy_cost: '能耗', power: '威力', hit_count: '连击', priority_mod: '先手' }[change.field] || change.field;
        return `${change.name} ${field} ${before}→${after}`;
      }
      if (change.kind === 'modifier') {
        const field = { energy_cost: '全技能能耗', power: '全技能威力', power_pct: '全技能威力比例', hit_count: '全技能连击', priority_mod: '全技能先手' }[change.name] || effectName(change.name);
        return `${field} ${before}→${after}${change.name === 'power_pct' ? '%' : ''}`;
      }
      const skillChange = change.name?.match(/^skill_(cost|power|hits|priority):(.+)$/);
      if (skillChange) return `${skillChange[2]} ${({ cost: '能耗', power: '威力', hits: '连击', priority: '先手' })[skillChange[1]]} ${before}→${after}`;
      return `${effectName(change.name || change.kind)} ${before}→${after}`;
    });
    return `[状态变化] ${event.pokemon || '精灵'}：${changes.join('，') || '其他状态有变化'}`;
  }
  return event.description || event.message || event.text || `[${event.type || '战斗事件'}]`;
}


