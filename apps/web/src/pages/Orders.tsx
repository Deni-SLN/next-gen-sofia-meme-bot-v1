import { get } from "../lib/api";
import { useSystemStatus } from "../lib/queries";
import { Badge, Card, QueryState } from "../components/ui";

export default function Orders() {
  return <OrdersInner />;
}

import { useQuery } from "@tanstack/react-query";

function OrdersInner() {
  const sys = useSystemStatus();
  const orders = useQuery({
    queryKey: ["orders-all"],
    queryFn: () => get<{ items: { id: string; mode: string; side: string; requested_size: number | null; status: string; risk_decision: string }[]; total: number }>("/api/v1/portfolio/orders"),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Order & Execution</h1>
      <Card title="Mode eksekusi">
        <QueryState isLoading={sys.isLoading} isError={sys.isError} error={sys.error}>
          <div className="flex gap-2">
            <Badge level="ok">PAPER — simulasi dengan harga pasar riil</Badge>
            <Badge level="bad">LIVE — disabled di V1</Badge>
          </div>
          <p className="mt-2 text-xs text-zinc-500">Semua fill PAPER bertanda SIMULATED; tidak pernah menandatangani/mengirim transaksi blockchain.</p>
        </QueryState>
      </Card>
      <Card title="Order intents">
        <QueryState isLoading={orders.isLoading} isError={orders.isError} error={orders.error} isEmpty={(orders.data?.items.length ?? 0) === 0} emptyText="Belum ada order.">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-500">
                <th className="py-1">ID</th>
                <th>Mode</th>
                <th>Side</th>
                <th className="text-right">Size</th>
                <th>Risk</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(orders.data?.items ?? []).map((o) => (
                <tr key={o.id} className="border-t border-zinc-800/60">
                  <td className="py-1.5 font-mono text-xs">{o.id.slice(0, 8)}</td>
                  <td>{o.mode}</td>
                  <td>{o.side}</td>
                  <td className="text-right font-mono">{o.requested_size ?? "—"}</td>
                  <td><Badge level={o.risk_decision === "APPROVED" ? "ok" : "bad"}>{o.risk_decision}</Badge></td>
                  <td className="font-mono text-xs">{o.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </Card>
    </div>
  );
}
