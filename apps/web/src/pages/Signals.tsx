import React from 'react';
import { api, useApiQuery } from '@/lib/api';
import { QueryState } from '@/components/QueryState';

export default function SignalsPage() {
  const signalsQuery = useApiQuery(() => api.getSignals(), []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Trading Signals</h1>
        <p className="text-sm text-slate-400">Sinyal algoritma dan AI yang dihasilkan sistem.</p>
      </div>

      <QueryState isLoading={signalsQuery.isLoading} isError={signalsQuery.isError} error={signalsQuery.error}>
        <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="p-4">Symbol</th>
                <th className="p-4">Direction</th>
                <th className="p-4">Confidence</th>
                <th className="p-4">Timeframe</th>
                <th className="p-4">Source</th>
                <th className="p-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {(signalsQuery.data?.signals || []).length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-slate-500">
                    Belum ada sinyal tercatat.
                  </td>
                </tr>
              ) : (
                signalsQuery.data.signals.map((s: any) => (
                  <tr key={s.id} className="border-b border-slate-800/60">
                    <td className="p-4 font-semibold">{s.symbol}</td>
                    <td className="p-4 uppercase font-bold text-sky-400">{s.direction}</td>
                    <td className="p-4 font-mono">{(s.confidence * 100).toFixed(0)}%</td>
                    <td className="p-4">{s.timeframe}</td>
                    <td className="p-4">{s.source}</td>
                    <td className="p-4">{s.status}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </QueryState>
    </div>
  );
}
