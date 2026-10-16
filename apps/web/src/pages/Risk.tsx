import { useState } from "react";
import { useRiskConfig, useUpdateRiskConfig } from "../lib/queries";
import { Card, QueryState } from "../components/ui";

const editable: { key: string; label: string; hint: string }[] = [
  { key: "max_position_allocation_usd", label: "Max position allocation (USD)", hint: "Batas alokasi per posisi" },
  { key: "max_total_exposure_usd", label: "Max total exposure (USD)", hint: "Batas total eksposur" },
  { key: "daily_loss_limit_usd", label: "Daily loss limit (USD)", hint: "Batas rugi harian" },
  { key: "max_drawdown_pct", label: "Max drawdown (%)", hint: "Batas drawdown" },
  { key: "max_concurrent_positions", label: "Max concurrent positions", hint: "Maks posisi bersamaan" },
  { key: "cooldown_after_loss_seconds", label: "Cooldown after loss (s)", hint: "Jeda setelah rugi" },
  { key: "max_slippage_pct", label: "Max slippage (%)", hint: "Slippage maksimum" },
  { key: "min_liquidity_usd", label: "Min liquidity (USD)", hint: "Likuiditas minimum" },
  { key: "max_fee_pct", label: "Max fee (%)", hint: "Fee maksimum" },
  { key: "max_price_impact_pct", label: "Max price impact (%)", hint: "Dampak harga maksimum" },
  { key: "max_signal_age_seconds", label: "Max signal age (s)", hint: "Umur sinyal maksimum" },
  { key: "min_risk_reward", label: "Min risk/reward", hint: "R/R minimum" },
  { key: "max_position_pct_of_equity", label: "Max position % of equity", hint: "% ekuitas per posisi" },
];

export default function Risk() {
  const cfg = useRiskConfig();
  const update = useUpdateRiskConfig();
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);

  const save = async () => {
    setMsg(null);
    const body: Record<string, number> = {};
    for (const [k, v] of Object.entries(draft)) {
      const n = Number(v);
      if (v !== "" && Number.isFinite(n)) body[k] = n;
    }
    if (Object.keys(body).length === 0) {
      setMsg("Tidak ada perubahan.");
      return;
    }
    try {
      await update.mutateAsync(body);
      setDraft({});
      setMsg("Risk config tersimpan (tercatat di audit log).");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "gagal menyimpan");
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Risk Management</h1>
      <p className="text-xs text-zinc-500">Risk Engine adalah gerbang terakhir sebelum eksekusi — fail-closed, tanpa override AI.</p>
      <Card title="Risk parameters" action={<button onClick={save} className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500">Simpan</button>}>
        <QueryState isLoading={cfg.isLoading} isError={cfg.isError} error={cfg.error}>
          <div className="grid gap-3 md:grid-cols-2">
            {editable.map((f) => (
              <label key={f.key} className="block rounded-lg border border-zinc-800 p-3">
                <span className="text-sm font-medium">{f.label}</span>
                <span className="block text-xs text-zinc-500">{f.hint} · saat ini: {String(cfg.data?.[f.key] ?? "—")}</span>
                <input
                  value={draft[f.key] ?? ""}
                  onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                  placeholder={`baru (cth: ${cfg.data?.[f.key] ?? ""})`}
                  inputMode="decimal"
                  className="mt-1 w-full rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
                />
              </label>
            ))}
          </div>
          {msg && <p className="mt-2 text-xs text-zinc-400">{msg}</p>}
        </QueryState>
      </Card>
    </div>
  );
}
