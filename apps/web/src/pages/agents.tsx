import React from 'react';
import { api, useApiQuery } from '@/lib/api';
import { QueryState } from '@/components/QueryState';

export default function AgentsPage() {
  const agentsQuery = useApiQuery(() => api.getAgents(), []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">AI Agents</h1>
        <p className="text-sm text-slate-400">Agen LLM terdaftar dengan validasi skema JSON ketat.</p>
      </div>

      <QueryState isLoading={agentsQuery.isLoading} isError={agentsQuery.isError} error={agentsQuery.error}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(agentsQuery.data?.agents || []).map((a: any) => (
            <div key={a.id} className="p-6 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <div className="font-bold text-lg text-slate-100">{a.name}</div>
                <span className="px-2.5 py-0.5 rounded-full text-xs bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  {a.status}
                </span>
              </div>
              <div className="text-xs uppercase text-sky-400">Type: {a.agent_type}</div>
              <p className="text-sm text-slate-400">{a.description}</p>
            </div>
          ))}
        </div>
      </QueryState>
    </div>
  );
}
