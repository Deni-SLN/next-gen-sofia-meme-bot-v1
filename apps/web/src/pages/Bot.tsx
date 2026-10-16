import { useBotMutation, useBotStatus } from "../lib/queries";
import { Badge, Card, QueryState } from "../components/ui";

export default function Bot() {
  const bot = useBotStatus();
  const start = useBotMutation("start");
  const pause = useBotMutation("pause");
  const resume = useBotMutation("resume");
  const stop = useBotMutation("stop");
  const emergency = useBotMutation("emergency-stop");
  const clearKs = useBotMutation("clear-kill-switch");

  const err = (m: { isError: boolean; error: unknown }) =>
    m.isError ? <p className="mt-1 text-xs text-red-400">{m.error instanceof Error ? m.error.message : "gagal"}</p> : null;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Bot Control Center</h1>
      <Card title="Status">
        <QueryState isLoading={bot.isLoading} isError={bot.isError} error={bot.error}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge level={bot.data?.status === "RUNNING" ? "ok" : "mute"}>{bot.data?.status}</Badge>
            <Badge level="info">{bot.data?.mode}</Badge>
            {bot.data?.kill_switch_active && <Badge level="bad">KILL-SWITCH AKTIF</Badge>}
          </div>
        </QueryState>
      </Card>
      <Card title="Kontrol">
        <div className="flex flex-wrap gap-2">
          <button onClick={() => start.mutate({ mode: "PAPER" })} className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500">Start PAPER</button>
          <button onClick={() => start.mutate({ mode: "ANALYSIS_ONLY" })} className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm hover:bg-zinc-900">Start Analysis-only</button>
          <button onClick={() => pause.mutate()} className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm hover:bg-zinc-900">Pause</button>
          <button onClick={() => resume.mutate()} className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm hover:bg-zinc-900">Resume</button>
          <button onClick={() => stop.mutate({ reason: "operator stop" })} className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm hover:bg-zinc-900">Stop</button>
          <button onClick={() => emergency.mutate()} className="rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium hover:bg-red-600">Emergency Stop</button>
          <button onClick={() => clearKs.mutate()} className="rounded-md border border-amber-700 px-3 py-1.5 text-sm text-amber-300 hover:bg-amber-950">Clear kill-switch</button>
        </div>
        {err(start)}{err(pause)}{err(resume)}{err(stop)}{err(emergency)}{err(clearKs)}
        <p className="mt-3 text-xs text-zinc-500">
          Tombol “Start LIVE” tidak disediakan — backend selalu menolak start LIVE di V1 (klik tidak mungkin mengirim mode LIVE dari UI ini).
        </p>
      </Card>
    </div>
  );
}
