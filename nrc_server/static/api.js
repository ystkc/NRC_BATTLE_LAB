/** 携带稳定身份令牌的 HTTP 请求。 */
import { state } from './state.js';

function headers() {
  const result = { 'Content-Type': 'application/json' };
  if (state.playerToken) result['X-Player-Token'] = state.playerToken;
  return result;
}

export async function api(url, options = {}) {
  const response = await fetch(url, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.message || data.error || '请求失败');
    error.status = response.status;
    throw error;
  }
  return data;
}


