import { useState } from "react";
import { Link } from "react-router-dom";
import { post } from "../lib/api";
import { useWatchlists } from "../lib/queries";
import { Card, QueryState } from "../components/ui";

export default function Watchlist() {
  const lists = useWatchlists();
  const [name, setName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  const create = async () => {
    setMsg(null);
    try {
      await post("/api/v1/watchlists", { name });
      setName("");
      lists.refetch();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "gagal membuat watchlist");
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Watchlist</h1>
      <Card title="Buat watchlist">
        <div className="flex gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="cth: moonshots" className="w-64 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm" />
          <button onClick={create} className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500">Buat</button>
        </div>
        {msg && <p className="mt-2 text-xs text-red-400">{msg}</p>}
      </Card>
      <QueryState isLoading={lists.isLoading} isError={lists.isError} error={lists.error} isEmpty={(lists.data?.items.length ?? 0) === 0} emptyText="Belum ada watchlist.">
        <div className="grid gap-4 md:grid-cols-2">
          {(lists.data?.items ?? []).map((w) => (
            <Card key={w.id} title={w.name}>
              {w.items.length === 0 ? (
                <p className="text-sm text-zinc-500">Kosong.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {w.items.map((i) => (
                    <li key={i.mint_address} className="flex items-center justify-between">
                      <Link to={`/tokens/${i.mint_address}`} className="font-mono text-xs text-emerald-300 hover:underline">{i.mint_address.slice(0, 16)}…</Link>
                      <span className="text-xs text-zinc-500">{i.note ?? ""}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          ))}
        </div>
      </QueryState>
    </div>
  );
}
