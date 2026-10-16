import { useState } from "react";

import { Badge, Card, QueryState } from "../components/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post } from "../lib/api";
import type { AlertItem, WalletItem } from "../lib/types";

/** Atomic units -> display. Balances are integers in lamports / USDC base
 * units; a null balance is unknown, not zero, and renders as a dash. */
function fmtAtomic(amount: number | null | undefined, decimals: number, symbol: string) {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return "—";
  return `${(amount / 10 ** decimals).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  })} ${symbol}`;
}

const STATUS_TONE: Record<string, string> = {
  OK: "ok",
  SENT: "ok",
  CONFIRMED: "ok",
  SKIPPED: "mute",
  UNAVAILABLE: "warn",
  UNKNOWN: "bad",
  PENDING: "warn",
  FAILED: "bad",
};

export default function Wallet() {
  const qc = useQueryClient();
  const wallets = useQuery({ queryKey: ["wallets"], queryFn: () => get<{ items: WalletItem[] }>("/api/v1/wallets") });
  const [selected, setSelected] = useState<string>("");
  const walletId = selected || wallets.data?.items?.[0]?.id || "";

  const balances = useQuery({
    queryKey: ["wallet-balances", walletId],
    queryFn: () => get<{ wallet: WalletItem; items: { asset: string; decimals: number; balance_atomic: number | null; spendable_atomic: number | null; status: string; age_seconds?: number; observed_at?: string | null; rpc_provider?: string | null }[] }>(
      `/api/v1/wallets/${walletId}/balances`,
    ),
    enabled: Boolean(walletId),
    refetchInterval: 30_000,
  });

  const reserve = useQuery({
    queryKey: ["wallet-reserve", walletId],
    queryFn: () => get<{ reserve: Record<string, number>; reasons?: string[] }>(`/api/v1/wallets/${walletId}/reserve`),
    enabled: Boolean(walletId),
  });

  const transfers = useQuery({
    queryKey: ["wallet-transfers"],
    queryFn: () => get<{ items: { id: string; state: string; trigger_type: string; asset: string; amount_atomic: number; estimated_fee_atomic: number; created_at: string | null; failure_reason: string | null }[] }>(
      "/api/v1/wallet-transfers?limit=25",
    ),
  });

  const refresh = useMutation({
    mutationFn: () => post("/api/v1/wallets/balances/refresh", {}),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["wallet-balances"] }),
  });

  const [withdrawMsg, setWithdrawMsg] = useState<string | null>(null);
  const withdraw = useMutation({
    mutationFn: (body: Record<string, unknown>) => post("/api/v1/wallet-transfers", body),
    onSuccess: () => {
      setWithdrawMsg("Withdrawal intent dibuat (belum ditandatangani).");
      void qc.invalidateQueries({ queryKey: ["wallet-transfers"] });
    },
    onError: (e: Error) => setWithdrawMsg(e.message),
  });

  const [asset, setAsset] = useState("SOL");
  const [amount, setAmount] = useState("1");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Wallets &amp; Profit Sweep</h1>
        <button
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending}
          className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
        >
          {refresh.isPending ? "Membaca on-chain…" : "Refresh saldo on-chain"}
        </button>
      </div>

      <Card title="Registered wallets">
        <QueryState
          isLoading={wallets.isLoading}
          isError={wallets.isError}
          error={wallets.error}
          isEmpty={(wallets.data?.items.length ?? 0) === 0}
          emptyText="Belum ada wallet terdaftar. Daftarkan MAIN wallet untuk mengaktifkan sweep."
        >
          <ul className="space-y-1 text-sm">
            {(wallets.data?.items ?? []).map((w) => (
              <li key={w.id}>
                <button
                  onClick={() => setSelected(w.id)}
                  className={`flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-left ${
                    w.id === walletId ? "border-emerald-700 bg-zinc-900" : "border-zinc-800"
                  }`}
                >
                  <Badge level={w.wallet_role === "MAIN" ? "ok" : "info"}>{w.wallet_role}</Badge>
                  <span className="font-mono text-xs">{w.public_address.slice(0, 24)}…</span>
                  <span className="ml-auto text-xs text-zinc-500">{w.status}</span>
                </button>
              </li>
            ))}
          </ul>
        </QueryState>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="On-chain balances">
          <QueryState
            isLoading={balances.isLoading}
            isError={balances.isError}
            error={balances.error}
            isUnavailable={Boolean(walletId) && (balances.data?.items ?? []).length > 0 &&
              (balances.data?.items ?? []).every((i) => i.status !== "OK")}
            unavailableText="Saldo tidak terbaca. Sweep akan ditolak sampai ada pembacaan yang valid — bukan dianggap nol."
          >
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-zinc-500">
                  <th className="py-1">Asset</th>
                  <th className="text-right">Balance</th>
                  <th className="text-right">Spendable</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(balances.data?.items ?? []).map((i) => (
                  <tr key={i.asset} className="border-t border-zinc-800/60">
                    <td className="py-1.5 font-mono text-xs">{i.asset}</td>
                    <td className="text-right font-mono">{fmtAtomic(i.balance_atomic, i.decimals, i.asset)}</td>
                    <td className="text-right font-mono">{fmtAtomic(i.spendable_atomic, i.decimals, i.asset)}</td>
                    <td>
                      <Badge level={STATUS_TONE[i.status] ?? "mute"}>{i.status}</Badge>
                      {i.age_seconds !== undefined && <span className="ml-1 text-xs text-zinc-500">{i.age_seconds.toFixed(0)}s</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-zinc-500">
              Dibaca dari Solana RPC. Nilai <code>UNKNOWN</code> berarti pembacaan gagal — bukan saldo nol.
            </p>
          </QueryState>
        </Card>

        <Card title="Dynamic reserve">
          <QueryState isLoading={reserve.isLoading} isError={reserve.isError} error={reserve.error}>
            <pre className="overflow-x-auto text-xs font-mono text-zinc-400">
              {JSON.stringify(reserve.data?.reserve ?? {}, null, 2)}
            </pre>
            {(reserve.data?.reasons ?? []).length > 0 && (
              <ul className="mt-2 space-y-1 text-xs text-amber-300">
                {(reserve.data?.reasons ?? []).map((r) => (
                  <li key={r}>◍ {r}</li>
                ))}
              </ul>
            )}
          </QueryState>
        </Card>
      </div>

      <Card title="Manual withdrawal (PAPER — tidak menandatangani apa pun)">
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs text-zinc-500">
            asset
            <select
              value={asset}
              onChange={(e) => setAsset(e.target.value)}
              className="mt-1 block rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
            >
              <option value="SOL">SOL</option>
              <option value="USDC">USDC</option>
            </select>
          </label>
          <label className="text-xs text-zinc-500">
            jumlah
            <input
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              inputMode="decimal"
              className="mt-1 block w-32 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 font-mono text-sm"
            />
          </label>
          <button
            onClick={() =>
              withdraw.mutate({ source_wallet_id: walletId, asset, amount: Number(amount) })
            }
            disabled={!walletId || withdraw.isPending}
            className="rounded-md bg-sky-700 px-3 py-1.5 text-sm font-medium hover:bg-sky-600 disabled:opacity-50"
          >
            Buat intent
          </button>
        </div>
        {withdrawMsg && <p className="mt-2 text-xs text-zinc-400">{withdrawMsg}</p>}
        <p className="mt-2 text-xs text-amber-400">
          Feature gate live-transfer tetap OFF. Intent berhenti di AWAITING_CONFIRMATION dan tidak pernah
          ditandatangani oleh V1 ini.
        </p>
      </Card>

      <Card title="Transfer intents">
        <QueryState
          isLoading={transfers.isLoading}
          isError={transfers.isError}
          error={transfers.error}
          isEmpty={(transfers.data?.items.length ?? 0) === 0}
          emptyText="Belum ada intent transfer."
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-500">
                <th className="py-1">Asset</th>
                <th className="text-right">Amount</th>
                <th>Trigger</th>
                <th>State</th>
                <th>Dibuat</th>
              </tr>
            </thead>
            <tbody>
              {(transfers.data?.items ?? []).map((t) => (
                <tr key={t.id} className="border-t border-zinc-800/60">
                  <td className="py-1.5 font-mono text-xs">{t.asset}</td>
                  <td className="text-right font-mono">{t.amount_atomic}</td>
                  <td className="text-xs">{t.trigger_type}</td>
                  <td>
                    <Badge level={STATUS_TONE[t.state] ?? "mute"}>{t.state}</Badge>
                    {t.failure_reason && <span className="ml-1 text-xs text-red-400">{t.failure_reason}</span>}
                  </td>
                  <td className="text-xs text-zinc-500">{t.created_at ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </Card>
    </div>
  );
}

export type { AlertItem };
