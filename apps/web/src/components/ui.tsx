import type { ReactNode } from "react";

import { ApiError } from "../lib/api";

/** Pull the PRD §12.6 correlation id out of whatever the query threw. */
function errorRequestId(error: unknown): string | undefined {
  if (error instanceof ApiError) return error.requestId;
  return undefined;
}

/** Unified async-state rendering: loading / empty / stale / unavailable / error (FR §5.1).
 *
 * The five states are deliberately distinct, because they need different
 * operator actions:
 *   - loading     : nothing decided yet, wait
 *   - error       : the request failed, a request_id is shown for the server log
 *   - unavailable : the upstream provider is down or gated off, retrying is pointless
 *   - stale       : data exists but is older than the freshness window, treat with caution
 *   - empty       : the request succeeded and there is genuinely nothing
 */
export function QueryState({
  isLoading,
  isError,
  isEmpty,
  isStale,
  isUnavailable,
  emptyText = "Belum ada data.",
  errorText = "Gagal memuat data.",
  staleText = "Data mungkin sudah basi. Periksa sumber data.",
  unavailableText = "Sumber data sedang tidak tersedia.",
  error,
  children,
}: {
  isLoading: boolean;
  isError: boolean;
  isEmpty?: boolean;
  isStale?: boolean;
  isUnavailable?: boolean;
  emptyText?: string;
  errorText?: string;
  staleText?: string;
  unavailableText?: string;
  error?: unknown;
  children: ReactNode;
}) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 text-sm text-zinc-400">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-emerald-400" />
        Memuat…
      </div>
    );
  }
  if (isUnavailable) {
    return (
      <div className="rounded-lg border border-amber-900 bg-amber-950/40 p-4 text-sm text-amber-300">
        <div>◍ {unavailableText}</div>
      </div>
    );
  }
  if (isError) {
    const requestId = errorRequestId(error);
    return (
      <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
        <div>⚠ {errorText}</div>
        {requestId ? (
          <div className="mt-1 text-xs text-red-400/70">
            request_id: <span className="font-mono">{requestId}</span>
          </div>
        ) : null}
      </div>
    );
  }
  if (isEmpty) {
    return <div className="rounded-lg border border-dashed border-zinc-700 p-4 text-sm text-zinc-500">{emptyText}</div>;
  }
  return (
    <>
      {isStale ? (
        <div className="mb-2 rounded-lg border border-amber-900/70 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          ⧗ {staleText}
        </div>
      ) : null}
      {children}
    </>
  );
}

const tone: Record<string, string> = {
  ok: "bg-emerald-950 text-emerald-300 border-emerald-800",
  warn: "bg-amber-950 text-amber-300 border-amber-800",
  bad: "bg-red-950 text-red-300 border-red-800",
  mute: "bg-zinc-900 text-zinc-400 border-zinc-700",
  info: "bg-sky-950 text-sky-300 border-sky-800",
};

export function Badge({ level = "mute", children }: { level?: keyof typeof tone | string; children: ReactNode }) {
  const cls = tone[level as keyof typeof tone] ?? tone.mute;
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>{children}</span>;
}

export function Card({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-wide text-zinc-200">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function fmtUsd(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `$${v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

export function fmtPct(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

/** Add PnL components that may be unknown.
 *
 * `a + b` in JavaScript turns `0 + null` into `0`, which is exactly how an
 * unmeasured number becomes a measured-looking zero. If any part is unknown the
 * sum is unknown.
 */
export function sumKnown(...values: (number | null | undefined)[]): number | null {
  let total = 0;
  for (const v of values) {
    if (v === null || v === undefined || Number.isNaN(v)) return null;
    total += v;
  }
  return total;
}
