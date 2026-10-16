/** TanStack Query hooks: cache + server state (FR §5.1). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { del, get, post, put } from "./api";
import type {
  AgentItem,
  AnalysisRunItem,
  BacktestResult,
  BotState,
  Paged,
  PerformanceSummary,
  PortfolioModes,
  PositionItem,
  ProviderStatus,
  SignalItem,
  SystemStatus,
  TokenItem,
} from "./types";

export const useSystemStatus = () =>
  useQuery({ queryKey: ["system-status"], queryFn: () => get<SystemStatus>("/api/v1/system/status"), refetchInterval: 10_000 });

export const useTokens = (q?: string) =>
  useQuery({
    queryKey: ["tokens", q ?? ""],
    queryFn: () => get<Paged<TokenItem>>(`/api/v1/tokens${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  });

export const useTokenCandles = (mint: string, timeframe = "M1") =>
  useQuery({
    queryKey: ["candles", mint, timeframe],
    queryFn: () => get<{ items: { time: string; open: number; high: number; low: number; close: number; volume: number }[]; timeframe: string; count: number }>(`/api/v1/tokens/${mint}/candles?timeframe=${timeframe}`),
    enabled: Boolean(mint),
  });

export const useSignals = (status?: string) =>
  useQuery({
    queryKey: ["signals", status ?? ""],
    queryFn: () => get<Paged<SignalItem>>(`/api/v1/signals${status ? `?status=${status}` : ""}`),
    refetchInterval: 15_000,
  });

export const useAnalysisRuns = () =>
  useQuery({ queryKey: ["analysis-runs"], queryFn: () => get<Paged<AnalysisRunItem>>("/api/v1/analysis/runs") });

export const useBotStatus = () =>
  useQuery({ queryKey: ["bot-status"], queryFn: () => get<BotState>("/api/v1/bot/status"), refetchInterval: 5_000 });

export const useBotMutation = (action: "start" | "pause" | "resume" | "stop" | "emergency-stop" | "clear-kill-switch") => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body?: unknown) => post<BotState>(`/api/v1/bot/${action}`, body ?? {}),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bot-status"] });
      void qc.invalidateQueries({ queryKey: ["system-status"] });
    },
  });
};

export const useRiskConfig = () => useQuery({ queryKey: ["risk-config"], queryFn: () => get<Record<string, number | string>>("/api/v1/risk/config") });

export const useUpdateRiskConfig = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, number>) => put<Record<string, number | string>>("/api/v1/risk/config", body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["risk-config"] }),
  });
};

export const usePortfolio = () =>
  useQuery({ queryKey: ["portfolio"], queryFn: () => get<PortfolioModes>("/api/v1/portfolio/overview"), refetchInterval: 10_000 });

export const usePositions = (status?: string) =>
  useQuery({
    queryKey: ["positions", status ?? ""],
    queryFn: () => get<{ mode: string; items: PositionItem[] }>(`/api/v1/portfolio/positions${status ? `?status=${status}` : ""}`),
  });

export const useEquityCurve = (mode = "PAPER") =>
  useQuery({ queryKey: ["equity-curve", mode], queryFn: () => get<{ mode: string; curve: { timestamp: string | null; equity: number }[] }>(`/api/v1/portfolio/equity-curve?mode=${mode}`) });

export const useAgents = () => useQuery({ queryKey: ["agents"], queryFn: () => get<{ agents: AgentItem[] }>("/api/v1/ai/agents") });

export const useProvidersStatus = () =>
  useQuery({ queryKey: ["providers"], queryFn: () => get<{ providers: ProviderStatus[] }>("/api/v1/providers/status"), refetchInterval: 15_000 });

export const useAiUsage = () =>
  useQuery({ queryKey: ["ai-usage"], queryFn: () => get<{ requests: number; total_tokens: number; cost_usd_known: number; by_provider: Record<string, unknown> }>("/api/v1/ai/usage") });

export const useWatchlists = () =>
  useQuery({ queryKey: ["watchlists"], queryFn: () => get<{ items: { id: string; name: string; items: { mint_address: string; note: string | null }[] }[] }>("/api/v1/watchlists") });

export const useDeleteWatchItem = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ watchlistId, mint }: { watchlistId: string; mint: string }) => del(`/api/v1/watchlists/${watchlistId}/items/${mint}`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["watchlists"] }),
  });
};

export const usePerformance = () =>
  useQuery({ queryKey: ["performance"], queryFn: () => get<PerformanceSummary>("/api/v1/performance/summary") });

export const useBacktest = () =>
  useMutation({
    mutationFn: (body: { pair_id: string; timeframe?: string }) =>
      post<BacktestResult>("/api/v1/backtest", body),
  });
