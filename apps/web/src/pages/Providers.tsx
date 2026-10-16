import { useState } from "react";
import { get, post } from "../lib/api";
import { useProvidersStatus, useSystemStatus } from "../lib/queries";
import { Badge, Card, QueryState } from "../components/ui";

export default function Providers() {
  const st = useProvidersStatus();
  const sys = useSystemStatus();
  const [models, setModels] = useState<{ provider: string; models: { id: string; free?: boolean }[] } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const loadModels = async (provider: string) => {
    setMsg(null);
    try {
      const r = await get<{ provider: string; models: { id: string; free?: boolean }[] }>(`/api/v1/providers/${provider}/models`);
      setModels(r);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "gagal memuat models");
    }
  };

  const approve = async (modelId: string) => {
    if (!window.confirm(`Setujui model BERBAYAR ${modelId}? Persetujuan tercatat per-model.`)) return;
    try {
      await post("/api/v1/ai/openrouter/approve-paid", { model_id: modelId });
      setMsg(`Model ${modelId} disetujui (per-model, tercatat di audit).`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "gagal menyetujui");
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Providers</h1>
      <Card title="Market & on-chain status">
        <QueryState isLoading={st.isLoading} isError={st.isError} error={st.error} isEmpty={(st.data?.providers.length ?? 0) === 0} emptyText="Belum ada data health.">
          <ul className="space-y-2 text-sm">
            {(st.data?.providers ?? []).map((p) => (
              <li key={p.provider} className="flex items-center justify-between rounded-lg border border-zinc-800 p-2">
                <span>
                  {p.provider}
                  {p.last_error_message && <span className="block text-xs text-red-400">{p.last_error_message}</span>}
                </span>
                <span className="flex items-center gap-2">
                  <Badge level={p.status === "UP" ? "ok" : p.status === "DOWN" ? "bad" : "mute"}>{p.status}</Badge>
                  <button onClick={() => loadModels(p.provider)} className="rounded-md border border-zinc-700 px-2 py-1 text-xs hover:bg-zinc-900">Models</button>
                </span>
              </li>
            ))}
          </ul>
        </QueryState>
      </Card>
      {models && (
        <Card title={`Models — ${models.provider}`}>
          <ul className="max-h-64 space-y-1 overflow-y-auto text-sm">
            {models.models.slice(0, 100).map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2 rounded border border-zinc-800/60 px-2 py-1">
                <span className="font-mono text-xs">{m.id}</span>
                <span className="flex items-center gap-2">
                  {m.free ? <Badge level="ok">FREE</Badge> : <Badge level="warn">PAID</Badge>}
                  {!m.free && models.provider === "openrouter" && (
                    <button onClick={() => approve(m.id)} className="rounded border border-amber-700 px-1.5 py-0.5 text-[11px] text-amber-300 hover:bg-amber-950">Approve paid</button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {msg && <p className="text-xs text-zinc-400">{msg}</p>}
      <Card title="Solana RPC">
        <QueryState isLoading={sys.isLoading} isError={sys.isError} error={sys.error}>
          <p className="text-sm text-zinc-400">Endpoint dikonfigurasi via <span className="font-mono">SOFIA_SOLANA_RPC_URL</span> tanpa perubahan kode. Public RPC hanya untuk prototipe volume rendah.</p>
        </QueryState>
      </Card>
    </div>
  );
}
