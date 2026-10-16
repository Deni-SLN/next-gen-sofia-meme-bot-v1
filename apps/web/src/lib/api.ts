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

export function formatIdr(amountIdr: number | undefined | null): string {
  const val = Number(amountIdr || 0);
  const sign = val < 0 ? '-' : '';
  const abs = Math.abs(val);
  if (abs > 0 && abs < 100) {
    return `${sign}Rp ${abs.toLocaleString('id-ID', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `${sign}Rp ${Math.round(abs).toLocaleString('id-ID')}`;
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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
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
}

export function useApiQuery<T>(fetcher: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isError, setIsError] = useState<boolean>(false);
  const [error, setError] = useState<any>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setError(null);
    try {
      const result = await fetcher();
      setData(result);
    } catch (err) {
      setIsError(true);
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, deps);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, isLoading, isError, error, refetch, setData };
}

export const api = {
  login: (password: string) =>
    request<{ token: string; actor: string; role: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),
  getBotStatus: () => request<any>('/bot/status'),
  getBotActivity: (tick: boolean = true, forceTrade: boolean = false) =>
    request<any>(`/bot/activity?tick=${tick ? 'true' : 'false'}${forceTrade ? '&force_trade=true' : ''}`),
  startBot: (mode: string) =>
    request<any>('/bot/start', { method: 'POST', body: JSON.stringify({ mode }) }),
  stopBot: () => request<any>('/bot/stop', { method: 'POST' }),
  getPortfolio: () => request<any>('/portfolio/overview'),
  addHolding: (data: { symbol: string; quantity: number; avg_entry_price: number; current_price?: number }) =>
    request<any>('/portfolio/holdings', { method: 'POST', body: JSON.stringify(data) }),
  sellHolding: (symbol: string, sell_pct: number = 100) =>
    request<any>('/portfolio/sell', { method: 'POST', body: JSON.stringify({ symbol, sell_pct }) }),
  resetPaperAccount: () =>
    request<any>('/portfolio/reset-paper', { method: 'POST' }),
  getSignals: (status?: string) =>
    request<any>(`/signals${status ? `?status=${encodeURIComponent(status)}` : ''}`),
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
  createWallet: (data: any) =>
    request<any>('/wallets', { method: 'POST', body: JSON.stringify(data) }),
  updateWallet: (walletId: number, data: any) =>
    request<any>(`/wallets/${walletId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteWallet: (walletId: number) =>
    request<any>(`/wallets/${walletId}`, { method: 'DELETE' }),
  // Meme Coin Live Market Endpoints
  getFx: () => request<{ usd_idr: number; source: string; updated_at: string }>('/memecoins/fx'),
  getPulse: () => request<any>('/memecoins/pulse'),
  rugCheck: (q: string) => request<any>(`/memecoins/rugcheck?q=${encodeURIComponent(q)}`),
  snipeToken: (data: {
    symbol: string;
    amount_usd?: number;
    amount_idr?: number;
    price?: number;
    slippage_pct?: number;
    priority_fee_sol?: number;
    anti_mev?: boolean;
    force_unsafe?: boolean;
    mode?: string;
  }) => request<any>('/memecoins/snipe', { method: 'POST', body: JSON.stringify(data) }),
  getSmartMoney: () => request<any>('/memecoins/smart-money'),
  toggleCopyWallet: (walletId: number, enabled: boolean, max_copy_usd?: number) =>
    request<any>(`/memecoins/smart-money/${walletId}/toggle`, {
      method: 'POST',
      body: JSON.stringify({ enabled, max_copy_usd }),
    }),
  // Live Trading Journal Endpoints (Neonbase)
  getJournal: (q?: string, outcome?: string, limit: number = 10) => {
    const params = new URLSearchParams();
    if (q) params.append('q', q);
    if (outcome) params.append('outcome', outcome);
    if (limit) params.append('limit', String(limit));
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
};

