/** 浏览器界面状态。 */
export const state = {
  effectDescriptions: {},
  catalog: { pokemon: [], skills: [] },
  battle: null,
  playerToken: '',
  side: '',
  teams: { own: [], opponent: [] },
  selectedStart: 0,
  actions: [],
  relations: [],
  display: { skills: [] },
  events: [],
  eventCursor: null,
  pending: false,
  submitting: false,
  syncing: false,
  opponentPending: false,
  resolving: false,
  resolutionToken: 0,
  pollTimer: null,
  pollInFlight: false,
  previewAnchor: null,
  previewRequest: 0,
  previewFormIndex: 0,
  locked: false,
};


