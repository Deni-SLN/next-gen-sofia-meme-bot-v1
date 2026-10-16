import { useQuery } from "@tanstack/react-query";
import { get } from "../lib/api";
import { useSystemStatus } from "../lib/queries";
import { Badge, Card, QueryState } from "../components/ui";

export default function Settings() {
  const sys = useSystemStatus();
  const audit = useQuery({
    queryKey: ["audit"],
    queryFn: () => get<{ items: { id: string; actor: string; action: string; entity_type: string | null; created_at: string }[] }>("/api/v1/system/audit-logs"),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Settings & System Health</h1>
      <Card title="System">
        <QueryState isLoading={sys.isLoading} isError={sys.isError} error={sys.error}>
          <dl className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3">
            <div className="rounded-lg border border-zinc-800 p-2"><dt className="text-xs text-zinc-500">App</dt><dd>{sys.data?.app}</dd></div>
            <div className="rounded-lg border border-zinc-800 p-2"><dt className="text-xs text-zinc-500">Engine</dt><dd className="font-mono">{sys.data?.engine_version}</dd></div>
            <div className="rounded-lg border border-zinc-800 p-2"><dt className="text-xs text-zinc-500">Scoring</dt><dd className="font-mono">{sys.data?.scoring_config_version}</dd></div>
            <div className="rounded-lg border border-zinc-800 p-2"><dt className="text-xs text-zinc-500">Risk rules</dt><dd className="font-mono">{sys.data?.risk_rule_version}</dd></div>
            <div className="rounded-lg border border-zinc-800 p-2"><dt className="text-xs text-zinc-500">Live trading</dt><dd><Badge level="bad">DISABLED</Badge></dd></div>
            <div className="rounded-lg border border-zinc-800 p-2"><dt className="text-xs text-zinc-500">Server time</dt><dd className="font-mono text-xs">{sys.data?.server_time}</dd></div>
          </dl>
        </QueryState>
      </Card>
      <Card title="Worker Health">
        <p className="text-sm text-zinc-400">
          Worker Python berjalan sebagai service terpisah (discovery → analysis → lifecycle → evaluation). Interval via{" "}
          <span className="font-mono">SOFIA_WORKER_*_INTERVAL</span>. Cek log container <span className="font-mono">worker</span> untuk kesehatan job.
        </p>
      </Card>
      <Card title="Audit Log (perubahan sensitif)">
        <QueryState isLoading={audit.isLoading} isError={audit.isError} error={audit.error} isEmpty={(audit.data?.items.length ?? 0) === 0} emptyText="Belum ada entri audit.">
          <ul className="max-h-64 space-y-1 overflow-y-auto text-sm">
            {(audit.data?.items ?? []).slice(0, 50).map((a) => (
              <li key={a.id} className="flex items-center justify-between rounded border border-zinc-800/60 px-2 py-1">
                <span><span className="font-medium">{a.action}</span> <span className="text-xs text-zinc-500">oleh {a.actor} · {a.entity_type ?? "—"}</span></span>
                <span className="font-mono text-xs text-zinc-500">{a.created_at.slice(0, 19)}</span>
              </li>
            ))}
          </ul>
        </QueryState>
      </Card>
      <Card title="Backup">
        <p className="text-sm text-zinc-400">
          Database PostgreSQL (managed: Supabase opsional). Backup via <span className="font-mono">pg_dump</span> terjadwal di lingkungan deployment —
          lihat <span className="font-mono">docker-compose.yml</span> & README.
        </p>
      </Card>
    </div>
  );
}
