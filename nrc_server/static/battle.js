/** 对局同步、战报拉取与行动提交。 */
import { state } from './state.js';
import { api } from './api.js';

export function createBattleSync({ renderEvents, setResolving, playResolution, renderSetup, updateBattleMeta, mergeObservation, renderSide, reset, toast, updateBattleLock, closeDrawer }) {
  /** 注入界面回调，保持网络和展示模块职责清晰。 */
  async function fetchMatchups(battleId) {
    try {
      const data = await api(`/api/battles/${battleId}/matchups?side=own`);
      state.relations = data.relations || [];
    } catch {
      state.relations = [];
    }
  }
  
  async function syncEvents({ animate = false, data = null } = {}) {
    const since = state.eventCursor ?? 0;
    const payload = await api(`/api/battles/${state.battle.battle_id}/events?since=${since}`);
    const incoming = payload.events || [];
    state.eventCursor = payload.cursor ?? since + incoming.length;
    if (!incoming.length) return false;
    if (animate) {
      setResolving(true);
      const token = ++state.resolutionToken;
      return playResolution(incoming, data, token);
    }
    state.events.push(...incoming);
    renderEvents();
    return false;
  }
  
  async function refreshBattle({ refreshDisplay = false, animateEvents = false } = {}) {
    if (!state.battle) return;
    if (state.syncing || state.resolving) return;
    state.syncing = true;
    updateBattleLock();
    try {
      const id = state.battle.battle_id;
      const previous = state.battle;
      const previousPending = state.pending;
      const summary = await api(`/api/battles/${id}`);
      const statusChanged = summary.turn !== previous.turn
        || summary.phase !== previous.phase
        || summary.decision_index !== previous.decision_index
        || Boolean(summary.pending) !== Boolean(previousPending);
      state.battle = { ...state.battle, ...summary };
      if (!summary.initialized) return renderSetup();
      const firstLoad = state.eventCursor === null;
      const nextData = (await api(`/api/battles/${id}/state?side=own`)).data;
      const displayChanged = refreshDisplay || statusChanged || !state.display.skills?.length;
      if (displayChanged) {
        state.display = (await api(`/api/battles/${id}/display?side=own`));
        state.actions = (await api(`/api/battles/${id}/actions?side=own`)).actions || [];
        await fetchMatchups(id);
      }
      state.pending = Boolean(summary.pending);
      updateBattleMeta();
      const animated = await syncEvents({ animate: animateEvents && !firstLoad && statusChanged, data: nextData });
      if (!animated) {
        mergeObservation(nextData);
        renderSide('own');
        renderSide('opponent');
      }
    } catch (error) {
      if (error.status === 404) {
        reset();
        toast('对局已失效，请重新创建或加入');
      } else toast(error.message);
    } finally {
      state.syncing = false;
      setResolving(false);
    }
  }
  
  async function submitAction(key) {
    if (!key || state.pending || state.submitting || state.syncing || state.resolving || !state.battle || state.battle.terminal) return;
    state.submitting = true;
    updateBattleLock();
    try {
      const result = await api(`/api/battles/${state.battle.battle_id}/selection`, { method: 'POST', body: JSON.stringify({ action_key: key, request_id: crypto.randomUUID(), decision_index: state.battle.decision_index }) });
      state.pending = !result.resolved;
      state.opponentPending = false;
      // 提交锁持续覆盖结算拉取与播放；等待对手时只保留 pending。
      if (result.resolved) await refreshBattle({ refreshDisplay: true, animateEvents: true });
      closeDrawer();
      if (result.terminated) toast(result.winner === 0 ? '我方获胜' : result.winner === 1 ? '敌方获胜' : '对局结束');
    } catch (error) {
      toast(error.message);
      await refreshBattle({ refreshDisplay: true, animateEvents: true });
    } finally {
      state.submitting = false;
      updateBattleLock();
    }
  }
  

  return { fetchMatchups, syncEvents, refreshBattle, submitAction };
}

