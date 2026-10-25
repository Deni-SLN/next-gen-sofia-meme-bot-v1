import { useEffect, useState, useCallback } from 'react';

const BASE = '/api/v1';

export function getToken(): string | null {
  return typeof window !== 'undefined' ? localStorage.getItem('sofia_token') : null;
}

export function setToken(token: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('sofia_token', token);
  }
}

export function clearToken(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('sofia_token');
  }
}

export function getTradingMode(): 'PAPER' | 'LIVE' {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem('sofia_trading_mode');
    if (saved === 'LIVE' || saved === 'PAPER') return saved;
  }
  return 'PAPER';
}

export function setTradingMode(mode: 'PAPER' | 'LIVE'): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('sofia_trading_mode', mode);
    window.dispatchEvent(new CustomEvent('sofia-mode-change', { detail: mode }));
  }
}

export function getStrategyMode(): 'SAFE' | 'DEFAULT' | 'AGGRESSIVE' {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem('sofia_strategy_mode');
    if (saved === 'SAFE' || saved === 'DEFAULT' || saved === 'AGGRESSIVE') return saved;
  }
  return 'AGGRESSIVE';
}

export function setStrategyModeStorage(mode: 'SAFE' | 'DEFAULT' | 'AGGRESSIVE'): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('sofia_strategy_mode', mode);
    window.dispatchEvent(new CustomEvent('sofia-strategy-mode-change', { detail: mode }));
  }
}

export function formatIdr(amountIdr: number | undefined | null): string {
  const val = Number(amountIdr || 0);
  const sign = val < 0 ? '-' : '';
  const abs = Math.abs(val);
  if (abs > 0 && abs < 100) {
    return `${sign}Rp ${abs.toLocaleString('id-ID', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `${sign}Rp ${Math.round(abs).toLocaleString('id-ID')}`;
}

export interface StockInsightItem {
  ticker: string;
  name: string;
  sector: string;
  quality_badge: string;
  safety_score: number;
  catalyst: string;
  current_price: number;
  change_pct: number;
  currency: string;
  action: string;
  action_color: 'emerald' | 'cyan' | 'amber' | 'rose' | string;
  entry_zone: string;
  tp_1: number;
  tp_1_pct: number;
  tp_2: number;
  tp_2_pct: number;
  stop_loss: number;
  stop_loss_pct: number;
  risk_reward: string;
  technical_summary: string;
  detail_url: string;
}

export interface CryptoInsightItem {
  symbol: string;
  name: string;
  category: string;
  tier_badge: string;
  safety_score: number;
  catalyst: string;
  current_price_usd: number;
  current_price_idr: number;
  change_24h_pct: number;
  action: string;
  action_color: 'emerald' | 'cyan' | 'amber' | 'rose' | string;
  entry_zone_usd: string;
  tp_1_usd: number;
  tp_1_pct: number;
  tp_2_usd: number;
  tp_2_pct: number;
  stop_loss_usd: number;
  stop_loss_pct: number;
  risk_reward: string;
  technical_summary: string;
  detail_url: string;
}

export interface SignalInsightsResponse {
  stocks: StockInsightItem[];
  crypto: CryptoInsightItem[];
  updated_at: string;
  cached?: boolean;
}

export function formatUsd(amountUsd: number | undefined | null): string {
  const val = Number(amountUsd || 0);
  const sign = val < 0 ? '-' : '';
  const abs = Math.abs(val);
  if (abs > 0 && abs < 0.01) {
    return `${sign}$${abs.toFixed(6)}`;
  }
  if (abs > 0 && abs < 1) {
    return `${sign}$${abs.toFixed(4)}`;
  }
  return `${sign}$${abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const _activeReadControllers = new Set<AbortController>();

if (typeof window !== 'undefined') {
  window.addEventListener('sofia-nav-start', () => {
    _activeReadControllers.forEach((ctrl) => {
      try {
        ctrl.abort();
      } catch {
        // ignore abort errors
      }
    });
    _activeReadControllers.clear();
  });
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const isGet = !options.method || options.method.toUpperCase() === 'GET';
  const ctrl = new AbortController();
  if (isGet) {
    _activeReadControllers.add(ctrl);
  }
  const timeoutId = setTimeout(() => {
    try {
      ctrl.abort();
    } catch {
      // ignore
    }
  }, isGet ? 9000 : 20000);

  try {
    const res = await fetch(`${BASE}${path}`, {
      ...options,
      headers,
      signal: options.signal || ctrl.signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw {
        status: res.status,
        message: err?.error?.message || err?.detail || `HTTP Error ${res.status}`,
        code: err?.error?.code || 'REQUEST_FAILED',
        request_id: res.headers.get('x-request-id') || undefined,
      };
    }
    return res.json();
  } finally {
    clearTimeout(timeoutId);
    if (isGet) {
      _activeReadControllers.delete(ctrl);
    }
  }
}

export function useApiQuery<T>(fetcher: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isFetching, setIsFetching] = useState<boolean>(false);
  const [isError, setIsError] = useState<boolean>(false);
  const [error, setError] = useState<any>(null);
  const hasDataRef = useState<{ current: boolean }>({ current: false })[0];
  const inFlightRef = useState<{ current: boolean }>({ current: false })[0];

  const refetch = useCallback(async () => {
    // Prevent overlapping duplicate requests from exhausting the browser's 6-connection pool
    if (inFlightRef.current) {
      return;
    }
    inFlightRef.current = true;
    // Only trigger full skeleton/loading state if data hasn't been loaded yet
    if (!hasDataRef.current) {
      setIsLoading(true);
    }
    setIsFetching(true);
    setIsError(false);
    setError(null);
    try {
      const result = await fetcher();
      hasDataRef.current = true;
      setData(result);
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        return;
      }
      if (!hasDataRef.current) {
        setIsError(true);
        setError(err);
      }
    } finally {
      inFlightRef.current = false;
      setIsLoading(false);
      setIsFetching(false);
    }
  }, deps);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, isLoading, isFetching, isError, error, refetch, setData };
}

export const api = {
  login: (password: string, username?: string) =>
    request<{ token: string; actor: string; role: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password, username: username || 'admin' }),
    }),
  getBotStatus: () => request<any>('/bot/status'),
  getSniperConfig: () => request<any>('/bot/config'),
  updateSniperConfig: (data: any) =>
    request<any>('/bot/config', { method: 'PUT', body: JSON.stringify(data) }),
  getBotActivity: (tick: boolean = true, forceTrade: boolean = false) =>
    request<any>(`/bot/activity?tick=${tick ? 'true' : 'false'}${forceTrade ? '&force_trade=true' : ''}`),
  startBot: (
    mode: string,
    strategy_mode?: string,
    params?: {
      buy_amount_usd?: number;
      buy_amount_idr?: number;
      max_open_positions?: number;
      slippage_pct?: number;
    }
  ) =>
    request<Record<string, unknown>>('/bot/start', {
      method: 'POST',
      body: JSON.stringify({ mode, strategy_mode, ...(params || {}) }),
    }),
  stopBot: () => request<any>('/bot/stop', { method: 'POST' }),
  getPortfolio: (mode?: string) =>
    request<any>(`/portfolio/overview${mode ? `?mode=${encodeURIComponent(mode)}` : ''}`),
  addHolding: (data: { symbol: string; quantity: number; avg_entry_price: number; current_price?: number }) =>
    request<any>('/portfolio/holdings', { method: 'POST', body: JSON.stringify(data) }),
  sellHolding: (symbol: string, sell_pct: number = 100, mode?: string) =>
    request<any>('/portfolio/sell', { method: 'POST', body: JSON.stringify({ symbol, sell_pct, mode }) }),
  panicSellAll: (mode?: string) =>
    request<any>('/portfolio/sell-all', { method: 'POST', body: JSON.stringify({ mode }) }),
  resetPaperAccount: (params?: { initial_capital_usd?: number; initial_capital_idr?: number }) =>
    request<Record<string, unknown>>('/portfolio/reset-paper', {
      method: 'POST',
      body: JSON.stringify(params || {}),
    }),
  getPaperCapital: () =>
    request<{ paper_initial_capital_idr: number; paper_initial_capital_usd: number; usd_idr: number }>('/portfolio/paper-capital'),
  setPaperCapital: (params: { initial_capital_idr?: number; initial_capital_usd?: number }) =>
    request<any>('/portfolio/paper-capital', {
      method: 'PUT',
      body: JSON.stringify(params),
    }),
  getSignals: (status?: string) =>
    request<any>(`/signals${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  getSignalInsights: (refresh: boolean = false) =>
    request<SignalInsightsResponse>(`/signals/insights${refresh ? '?refresh=true' : ''}`),
  getStockInsights: (refresh: boolean = false) =>
    request<{ stocks: StockInsightItem[]; updated_at: string }>(`/signals/stock-insights${refresh ? '?refresh=true' : ''}`),
  getCryptoInsights: (refresh: boolean = false) =>
    request<{ crypto: CryptoInsightItem[]; updated_at: string }>(`/signals/crypto-insights${refresh ? '?refresh=true' : ''}`),
  createSignal: (data: any) =>
    request<any>('/signals', { method: 'POST', body: JSON.stringify(data) }),
  getAgents: () => request<any>('/ai/agents'),
  createAgent: (data: any) =>
    request<any>('/ai/agents', { method: 'POST', body: JSON.stringify(data) }),
  getRiskConfig: () => request<any>('/risk/config'),
  updateRiskConfig: (data: any) =>
    request<any>('/risk/config', { method: 'PUT', body: JSON.stringify(data) }),
  getPerformance: () => request<any>('/performance/summary'),
  getDailyCalendar: (mode: string = 'ALL', year?: number, month?: number) => {
    const params = new URLSearchParams({ mode });
    if (year) params.append('year', String(year));
    if (month) params.append('month', String(month));
    return request<any>(`/performance/daily-calendar?${params.toString()}`);
  },
  getTreasurySummary: () => request<any>('/wallets/treasury/summary'),
  topupGasReserve: (amount_idr: number = 5000) =>
    request<any>('/wallets/treasury/topup-gas', { method: 'POST', body: JSON.stringify({ amount_idr }) }),
  triggerSettlement: (simulate_net_profit_idr?: number) =>
    request<any>('/wallets/treasury/settle', {
      method: 'POST',
      body: JSON.stringify({ trigger: 'manual_check_0500_wib', simulate_net_profit_idr }),
    }),
  getWallets: () => request<any>('/wallets'),
  getLiveWalletStatus: () => request<any>('/wallets/live-status'),
  createWallet: (data: any) =>
    request<any>('/wallets', { method: 'POST', body: JSON.stringify(data) }),
  updateWallet: (walletId: number, data: any) =>
    request<any>(`/wallets/${walletId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteWallet: (walletId: number) =>
    request<any>(`/wallets/${walletId}`, { method: 'DELETE' }),
  syncWalletOnchain: (walletId: number, apply_onchain_balance: boolean = false) =>
    request<any>(`/wallets/${walletId}/sync-onchain`, {
      method: 'POST',
      body: JSON.stringify({ apply_onchain_balance }),
    }),

  // Meme Coin Live Market Endpoints
  getFx: () => request<{ usd_idr: number; source: string; updated_at: string }>('/memecoins/fx'),
  getPulse: () => request<any>('/memecoins/pulse'),
  rugCheck: (q: string) => request<any>(`/memecoins/rugcheck?q=${encodeURIComponent(q)}`),
  snipeToken: (data: {
    symbol: string;
    contract?: string;
    amount_usd?: number;
    amount_idr?: number;
    price?: number;
    slippage_pct?: number;
    priority_fee_sol?: number;
    anti_mev?: boolean;
    force_unsafe?: boolean;
    block_legacy_tokens?: boolean;
    mode?: string;
  }) => request<any>('/memecoins/snipe', { method: 'POST', body: JSON.stringify(data) }),
  getSmartMoney: () => request<any>('/memecoins/smart-money'),
  toggleCopyWallet: (walletId: number, enabled: boolean, max_copy_usd?: number) =>
    request<any>(`/memecoins/smart-money/${walletId}/toggle`, {
      method: 'POST',
      body: JSON.stringify({ enabled, max_copy_usd }),
    }),
  // Live Trading Journal Endpoints (Neonbase)
  getJournal: (q?: string, outcome?: string, limit: number = 20, page: number = 1) => {
    const params = new URLSearchParams();
    if (q) params.append('q', q);
    if (outcome) params.append('outcome', outcome);
    if (limit) params.append('limit', String(limit));
    if (page) params.append('page', String(page));
    const qs = params.toString();
    return request<any>(`/journal${qs ? `?${qs}` : ''}`);
  },
  recordJournalTrade: (data: any) =>
    request<any>('/journal/trades', { method: 'POST', body: JSON.stringify(data) }),
  deleteJournalTrade: (tradeId: number) =>
    request<any>(`/journal/trades/${tradeId}`, { method: 'DELETE' }),
  downloadJournalExcel: async () => {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await fetch(`${BASE}/journal/export-excel`, { headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.message || err?.detail || 'Gagal mengunduh file Excel Jurnal Trading');
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const nowStr = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    a.download = `Jurnal_Trading_Live_Neonbase_${nowStr}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },
  // Indonesian News Feed Endpoints (Crypto, Saham, Emas, Ekonomi, Teknologi)
  getNews: (category: string = 'all', q?: string, refresh: boolean = false, limit: number = 24) => {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (q) params.append('q', q);
    if (refresh) params.append('refresh', 'true');
    if (limit) params.append('limit', String(limit));
    const qs = params.toString();
    return request<any>(`/news${qs ? `?${qs}` : ''}`);
  },
  // Indonesian Stock Analysis Endpoint (BEI / IDX)
  analyzeStock: (q: string = 'BBRI', refresh: boolean = false, timeframe: string = '1d') => {
    const params = new URLSearchParams({ q, timeframe });
    if (refresh) params.append('refresh', 'true');
    return request<any>(`/stocks/analyze?${params.toString()}`);
  },
  calculateStockRisk: (data: {
    capital_idr: number;
    entry_price: number;
    stop_loss: number;
    target_price: number;
    max_risk_pct?: number;
    lots?: number;
    buy_fee_pct?: number;
    sell_fee_pct?: number;
    slippage_pct?: number;
    existing_portfolio_value_idr?: number;
    is_idx?: boolean;
  }) => request<any>('/stocks/risk-calculator', { method: 'POST', body: JSON.stringify(data) }),
  getStockPortfolio: () => request<any>('/stocks/portfolio'),
  saveStockPosition: (data: { code: string; lots: number; avg_buy_price: number; notes?: string }) =>
    request<any>('/stocks/portfolio', { method: 'POST', body: JSON.stringify(data) }),
  deleteStockPosition: (positionId: number) =>
    request<any>(`/stocks/portfolio/${positionId}`, { method: 'DELETE' }),
  saveStockWatchlist: (data: {
    code: string;
    target_entry_price?: number;
    target_tp_price?: number;
    stop_loss_price?: number;
    notes?: string;
  }) => request<any>('/stocks/watchlist', { method: 'POST', body: JSON.stringify(data) }),
  deleteStockWatchlist: (itemId: number) =>
    request<any>(`/stocks/watchlist/${itemId}`, { method: 'DELETE' }),
  recordStockSignal: (data: { code: string; timeframe: string; notes?: string }) =>
    request<any>('/stocks/signal-journal', { method: 'POST', body: JSON.stringify(data) }),
  // Gold Price, Manual Portfolio & Buyback Simulator Endpoints
  getGoldDashboard: (refresh: boolean = false) =>
    request<any>(`/gold${refresh ? '?refresh=true' : ''}`),
  addGoldHolding: (data: {
    weight_grams: number;
    buy_price_per_gram_idr?: number;
    total_cost_idr?: number;
    brand?: string;
    label?: string;
    purchased_at?: string;
    notes?: string;
  }) => request<any>('/gold/holdings', { method: 'POST', body: JSON.stringify(data) }),
  updateGoldHolding: (
    holdingId: number,
    data: {
      weight_grams?: number;
      buy_price_per_gram_idr?: number;
      total_cost_idr?: number;
      brand?: string;
      label?: string;
      purchased_at?: string;
      notes?: string;
    }
  ) => request<any>(`/gold/holdings/${holdingId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteGoldHolding: (holdingId: number) =>
    request<any>(`/gold/holdings/${holdingId}`, { method: 'DELETE' }),
  simulateGoldSell: (data: {
    weight_grams: number;
    total_cost_idr?: number;
    retail_buy_price_per_gram_idr?: number;
    spread_pct?: number;
    tax_pct?: number | null;
    has_npwp?: boolean;
    include_stamp_duty?: boolean;
  }) => request<any>('/gold/simulate-sell', { method: 'POST', body: JSON.stringify(data) }),
  // Global Crypto Asset Analysis & Risk Calculator Endpoints
  analyzeCrypto: (q: string = 'BTC', refresh: boolean = false, timeframe: string = '1d') => {
    const params = new URLSearchParams({ q, timeframe });
    if (refresh) params.append('refresh', 'true');
    return request<any>(`/crypto/analyze?${params.toString()}`);
  },
  calculateCryptoRisk: (data: {
    capital_idr: number;
    entry_price_usd: number;
    stop_loss_usd: number;
    target_price_usd: number;
    max_risk_pct?: number;
    investment_idr?: number;
    exchange_fee_pct?: number;
    tax_pct?: number;
  }) => request<any>('/crypto/risk-calculator', { method: 'POST', body: JSON.stringify(data) }),
  // AI Chat, Sessions & Tool-Assisted Research Endpoints
  getChatSessions: () => request<any>('/chat/sessions'),
  createChatSession: (data: { title?: string; provider?: string; model?: string }) =>
    request<any>('/chat/sessions', { method: 'POST', body: JSON.stringify(data) }),
  getChatSession: (sessionId: string) => request<any>(`/chat/sessions/${sessionId}`),
  updateChatSession: (
    sessionId: string,
    data: { title?: string; provider?: string; model?: string }
  ) => request<any>(`/chat/sessions/${sessionId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteChatSession: (sessionId: string) =>
    request<any>(`/chat/sessions/${sessionId}`, { method: 'DELETE' }),
  getChatModels: (provider: string = 'openrouter', freeOnly: boolean = false, refresh: boolean = false) => {
    const params = new URLSearchParams({ provider });
    if (freeOnly) params.append('free_only', 'true');
    if (refresh) params.append('refresh', 'true');
    return request<any>(`/chat/models?${params.toString()}`);
  },
  getChatTools: () => request<any>('/chat/tools'),
  sendChatMessage: (data: {
    session_id?: string;
    message: string;
    provider?: string;
    model?: string;
    api_key?: string;
  }) => request<any>('/chat/completions', { method: 'POST', body: JSON.stringify(data) }),

  // Telegram Public Bots & Community Alpha Signals
  getTelegramBots: (category?: string) =>
    request<any>(`/telegram/bots${category ? `?category=${encodeURIComponent(category)}` : ''}`),
  getTelegramQueryLinks: (symbol: string, contract?: string) => {
    const params = new URLSearchParams({ symbol });
    if (contract) params.append('contract', contract);
    return request<any>(`/telegram/query-links?${params.toString()}`);
  },
  getTelegramSignals: () => request<any>('/telegram/signals'),
  sendTestTelegramAlert: (data: { token: string; chat_id: string; message?: string }) =>
    request<any>('/telegram/test-alert', { method: 'POST', body: JSON.stringify(data) }),
};


