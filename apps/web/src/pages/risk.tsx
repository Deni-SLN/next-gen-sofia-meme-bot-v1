import React, { useState, useEffect } from 'react';
import { api, useApiQuery } from '@/lib/api';
import { QueryState } from '@/components/QueryState';

export default function RiskPage() {
  const riskQuery = useApiQuery(() => api.getRiskConfig(), []);
  const [form, setForm] = useState<any>(null);
  const [savedMsg, setSavedMsg] = useState<string>('');

  useEffect(() => {
    if (riskQuery.data) {
      setForm(riskQuery.data);
    }
  }, [riskQuery.data]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavedMsg('');
    await api.updateRiskConfig(form);
    setSavedMsg('Konfigurasi risiko berhasil disimpan.');
    riskQuery.refetch();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Risk Management</h1>
        <p className="text-sm text-slate-400">Atur batas eksposur dan parameter proteksi modal.</p>
      </div>

      {savedMsg && (
        <div className="p-4 rounded-xl bg-emerald-950/50 border border-emerald-800 text-emerald-200 text-sm">
          {savedMsg}
        </div>
      )}

      <QueryState isLoading={riskQuery.isLoading} isError={riskQuery.isError} error={riskQuery.error}>
        {form && (
          <form onSubmit={handleSave} className="p-6 rounded-xl bg-slate-900 border border-slate-800 space-y-4 max-w-xl">
            <div>
              <label className="block text-xs text-slate-400 uppercase mb-1">Max Position Size (%)</label>
              <input
                type="number"
                step="0.1"
                value={form.max_position_size_pct}
                onChange={(e) => setForm({ ...form, max_position_size_pct: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-slate-100"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 uppercase mb-1">Max Daily Loss (%)</label>
              <input
                type="number"
                step="0.1"
                value={form.max_daily_loss_pct}
                onChange={(e) => setForm({ ...form, max_daily_loss_pct: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-slate-100"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 uppercase mb-1">Stop Loss (%)</label>
              <input
                type="number"
                step="0.1"
                value={form.stop_loss_pct}
                onChange={(e) => setForm({ ...form, stop_loss_pct: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-slate-100"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-sm font-medium transition"
            >
              Simpan Konfigurasi
            </button>
          </form>
        )}
      </QueryState>
    </div>
  );
}
