import { useState } from "react";
import { post } from "../lib/api";
import { useAgents, useAiUsage, useProvidersStatus } from "../lib/queries";
import { Badge, Card, QueryState } from "../components/ui";

export default function AiCenter() {
  const agents = useAgents();
  const providers = useProvidersStatus();
  const usage = useAiUsage();
  const [msg, setMsg] = useState<string | null>(null);

  const test = async (provider: string) => {
    setMsg(null);
    try {
      const r = await post<{ ok: boolean; detail?: string; hint?: string }>(`/api/v1/providers/${provider}/test`, {});
      setMsg(`${provider}: ${r.ok ? "OK" : "GAGAL"} ${r.detail ?? ""} ${r.hint ?? ""}`);
      providers.refetch();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "gagal");
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">AI & Agent Center</h1>
      <Card title="OpenRouter Free-First">
        <p className="text-sm text-zinc-400">
          Default <span className="font-mono text-emerald-300">openrouter/free</span>. Model berbayar hanya lewat pemilihan manual + konfirmasi eksplisit;
          backend menolak pemakaian berbayar tanpa persetujuan per-model. Fallback otomatis hanya ke model gratis.
        </p>
      </Card>
      <Card title="Agents">
        <QueryState isLoading={agents.isLoading} isError={agents.isError} error={agents.error} isEmpty={(agents.data?.agents.length ?? 0) === 0}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-500">
                <th className="py-1">Agent</th>
                <th>Provider</th>
                <th>Model</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(agents.data?.agents ?? []).map((a) => (
                <tr key={a.id} className="border-t border-zinc-800/60">
                  <td className="py-1.5 font-medium">{a.agent_name}</td>
                  <td className="font-mono text-xs">{a.provider ?? "—"}</td>
                  <td className="font-mono text-xs">{a.model_id ?? "—"}</td>
                  <td>{a.enabled ? <Badge level="ok">ON</Badge> : <Badge level="mute">OFF</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </Card>
      <Card title="Providers">
        <QueryState isLoading={providers.isLoading} isError={providers.isError} error={providers.error}>
          <ul className="space-y-2 text-sm">
            {(providers.data?.providers ?? []).map((p) => (
              <li key={p.provider} className="flex items-center justify-between rounded-lg border border-zinc-800 p-2">
                <span>{p.provider} <span className="text-xs text-zinc-500">{p.latency_ms ? `${p.latency_ms}ms` : ""}</span></span>
                <span className="flex items-center gap-2">
                  <Badge level={p.status === "UP" ? "ok" : p.status === "DOWN" ? "bad" : "mute"}>{p.status}</Badge>
                  <button onClick={() => test(p.provider)} className="rounded-md border border-zinc-700 px-2 py-1 text-xs hover:bg-zinc-900">Test</button>
                </span>
              </li>
            ))}
          </ul>
          {msg && <p className="mt-2 text-xs text-zinc-400">{msg}</p>}
        </QueryState>
      </Card>
      <Card title="Token & Cost Analytics">
        <QueryState isLoading={usage.isLoading} isError={usage.isError} error={usage.error}>
          <p className="text-sm">Requests: <span className="font-mono">{usage.data?.requests}</span> · Tokens: <span className="font-mono">{usage.data?.total_tokens}</span> · Cost (known): <span className="font-mono">${usage.data?.cost_usd_known}</span></p>
          <p className="mt-1 text-xs text-zinc-500">Biaya yang tak terverifikasi tampil sebagai unknown — tidak pernah dipalsukan jadi nol.</p>
        </QueryState>
      </Card>
    </div>
  );
}
