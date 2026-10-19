import React from 'react';
import { api, useApiQuery, formatIdr, formatUsd } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';
import { useUltrawide, toggleUltrawide } from '@/lib/useUltrawide';

export default function CopyTradePage() {
  const isUltrawide = useUltrawide();
  const smQuery = useApiQuery(() => api.getSmartMoney(), []);
  const usdIdr = smQuery.data?.usd_idr || 16500;

  const handleToggle = async (wallet: any) => {
    await api.toggleCopyWallet(wallet.id, !wallet.copy_enabled, wallet.max_copy_usd);
    smQuery.refetch();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2">
            <span>🐋</span> Smart Money &amp; Auto Copy-Trade
          </h1>
          <p className="text-sm text-slate-400">
            Pantau dompet whale berkinerja tinggi dan salin transaksi mereka otomatis • Kurs Hari Ini: $1 ={' '}
            <span className="text-emerald-400 font-mono font-bold">{formatIdr(usdIdr)}</span>
          </p>
        </div>

        <button
          type="button"
          onClick={() => toggleUltrawide(!isUltrawide)}
          className={`px-3 py-1.5 rounded-xl border text-xs font-mono font-bold transition flex items-center gap-2 ${
            isUltrawide
              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm'
              : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
          }`}
          title="Mode Layar Lebar: Menampilkan dompet whale berdampingan multi-kolom horizontal"
        >
          <LucideIcon name={isUltrawide ? 'Minimize2' : 'Maximize2'} className="w-4 h-4" />
          <span>{isUltrawide ? 'Layar Biasa' : 'Mode Layar Lebar'}</span>
        </button>
      </div>

      <QueryState isLoading={smQuery.isLoading} isError={smQuery.isError} error={smQuery.error}>
        <div className={isUltrawide ? 'grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-4 items-stretch' : 'grid grid-cols-1 gap-4'}>
          {(smQuery.data?.wallets || []).map((w: any) => (
            <div
              key={w.id}
              className="p-6 rounded-2xl bg-[#0b0f17] border border-slate-800 flex flex-wrap items-center justify-between gap-6"
            >
              <div className="space-y-1.5">
                <div className="flex items-center gap-2.5">
                  <span className="text-lg font-extrabold text-slate-100">{w.label}</span>
                  <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-sky-500/15 text-sky-300 border border-sky-500/30">
                    {w.chain}
                  </span>
                  {w.copy_enabled && (
                    <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      ⚡ AUTO-MIRROR ACTIVE
                    </span>
                  )}
                </div>
                <div className="text-xs font-mono text-slate-500">{w.address}</div>
                <div className="text-xs font-mono text-amber-300 pt-1">🔔 Activity: {w.last_Action}</div>
              </div>

              <div className="flex flex-wrap items-center gap-6 font-mono">
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">7D Win Rate</div>
                  <div className="text-lg font-bold text-emerald-400">{w.win_rate}%</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">7D Realized PnL</div>
                  <div className="text-lg font-bold text-emerald-400">+{formatUsd(w.pnl_7d)}</div>
                  <div className="text-[10px] text-slate-400">≈ +{formatIdr(w.pnl_7d * usdIdr)}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">Avg Hold</div>
                  <div className="text-sm font-semibold text-slate-200">{w.avg_hold_time}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">Max Copy / Trade</div>
                  <div className="text-sm font-bold text-sky-400">{formatUsd(w.max_copy_usd)}</div>
                  <div className="text-[10px] text-slate-400">≈ {formatIdr(w.max_copy_usd * usdIdr)}</div>
                </div>

                <button
                  onClick={() => handleToggle(w)}
                  className={`px-4 py-2 rounded-xl text-xs font-mono font-bold transition ${
                    w.copy_enabled
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30'
                      : 'bg-emerald-500 text-slate-950 hover:bg-emerald-400'
                  }`}
                >
                  {w.copy_enabled ? '⏸ Pause Copy Trade' : '▶️ Enable Copy Trade'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </QueryState>
    </div>
  );
}
