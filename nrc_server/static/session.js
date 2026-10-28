/** 当前标签页的对局恢复信息。 */
import { state } from './state.js';

export const SESSION_KEY = 'nrc-battle-session';

export function saveSession() {
  if (!state.battle?.battle_id || !state.playerToken) return;
  sessionStorage.setItem(SESSION_KEY, JSON.stringify({ battleId: state.battle.battle_id, playerToken: state.playerToken, side: state.side, selectedStart: state.selectedStart, teams: state.teams.own }));
}

export function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
  state.battle = null;
  state.playerToken = '';
  state.side = '';
  state.teams = { own: [], opponent: [] };
  state.selectedStart = 0;
  state.events = [];
  state.eventCursor = null;
  state.resolutionToken += 1;
  state.pending = false;
  state.submitting = false;
  state.syncing = false;
  state.resolving = false;
  state.opponentPending = false;
  clearTimeout(state.pollTimer);
  state.pollTimer = null;
  state.locked = false;
}


