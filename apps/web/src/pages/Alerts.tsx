import { useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge, Card, QueryState } from "../components/ui";
import { get, post } from "../lib/api";
import type { AlertItem } from "../lib/types";

const STATUS_TONE: Record<string, string> = {
  SENT: "ok",
  SKIPPED: "mute",
  PENDING: "warn",
  FAILED: "bad",
};

export default function Alerts() {
  const qc = useQueryClient();
  const [status, setStatus] = useState<string>("");

  const alerts = useQuery({
    queryKey: ["alerts", status],
    queryFn: () =>
      get<{ items: AlertItem[]; total: number; telegram_configured: boolean }>(
        `/api/v1/alerts?limit=50${status ? `&status=${status}` : ""}`,
      ),
    refetchInterval: 30_000,
  });

  const flush = useMutation({
    mutationFn: () => post<Record<string, number>>("/api/v1/alerts/flush", {}),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const evaluate = useMutation({
    mutationFn: () => post<{ recorded: number }>("/api/v1/alerts/evaluate", {}),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const [msg, setMsg] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">Alerts &amp; Journal</h1>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
          >
            <option value="">Semua status</option>
            {["PENDING", "SENT", "SKIPPED", "FAILED"].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button
            onClick={() =>
              evaluate
                .mutateAsync()
                .then((r) => setMsg(`Rules dievaluasi: ${(r as { recorded: number }).recorded} alert baru.`))
                .catch((e: Error) => setMsg(e.message))
            }
            disabled={evaluate.isPending}
            className="rounded-md bg-zinc-700 px-3 py-1.5 text-sm font-medium hover:bg-zinc-600 disabled:opacity-50"
          >
            Evaluate rules
          </button>
          <button
            onClick={() =>
              flush
                .mutateAsync()
                .then((r) => setMsg(JSON.stringify(r)))
                .catch((e: Error) => setMsg(e.message))
            }
            disabled={flush.isPending}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
          >
            Kirim pending
          </button>
        </div>
      </div>

      {!alerts.data?.telegram_configured && (
        <p className="rounded-lg border border-amber-900/70 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          ◍ Telegram belum dikonfigurasi (SOFIA_TELEGRAM_BOT_TOKEN / SOFIA_TELEGRAM_CHAT_ID kosong).
          Alert tetap dievaluasi dan dicatat sebagai SKIPPED — bukan gagal, dan tidak pernah mengirim apa pun.
        </p>
      )}

      {msg && <p className="text-xs text-zinc-400">{msg}</p>}

      <Card title={`Alert (${alerts.data?.total ?? 0})`}>
        <QueryState
          isLoading={alerts.isLoading}
          isError={alerts.isError}
          error={alerts.error}
          isEmpty={(alerts.data?.items.length ?? 0) === 0}
          emptyText="Belum ada alert. Rules dievaluasi berkala oleh worker."
        >
          <ul className="space-y-2">
            {(alerts.data?.items ?? []).map((a) => (
              <li key={a.id} className="rounded-lg border border-zinc-800 p-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge level={STATUS_TONE[a.delivery_status] ?? "mute"}>{a.delivery_status}</Badge>
                  <span className="text-sm font-medium">{a.title ?? "(tanpa judul)"}</span>
                  <span className="ml-auto font-mono text-xs text-zinc-500">{a.dedup_key}</span>
                </div>
                {a.body && <p className="mt-1 whitespace-pre-wrap text-xs text-zinc-400">{a.body}</p>}
                <p className="mt-1 text-xs text-zinc-600">
                  {a.created_at ?? "—"} · attempts {a.attempt_count}
                  {a.sent_at ? ` · terkirim ${a.sent_at}` : ""}
                </p>
              </li>
            ))}
          </ul>
        </QueryState>
      </Card>
    </div>
  );
}
