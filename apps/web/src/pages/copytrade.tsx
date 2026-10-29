import React from 'react';
import { api, useApiQuery, formatIdr, formatUsd } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';
import { useUltrawide, toggleUltrawide } from '@/lib/useUltrawide';

export default function CopyTradePage() {
  const isUltrawide = useUltrawide();
  const smQuery = useApiQuery(() => api.getSmartMoney(), []);
  const [copiedId, setCopiedId] = React.useState<number | null>(null);
  const [copiedWallets, setCopiedWallets] = React.useState<string[]>(() => {
    if (typeof window !== 'undefined') {
      try {
        const raw = localStorage.getItem('sofia_copied_wallets');
        return raw ? JSON.parse(raw) : [];
      } catch {
        return [];
      }
    }
    return [];
  });
  const usdIdr = smQuery.data?.usd_idr || 16500;

  const handleCopy = (address: string, id: number) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(address);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2500);

      const clean = (address || '').trim().toLowerCase();
      if (clean) {
        setCopiedWallets((prev) => {
          const next = Array.from(new Set([...prev, clean]));
          if (typeof window !== 'undefined') {
            try {
              localStorage.setItem('sofia_copied_wallets', JSON.stringify(next));
            } catch {}
          }
          return next;
        });
      }
    }
  };

  const handleResetCopied = () => {
    setCopiedWallets([]);
    if (typeof window !== 'undefined') {
      try {
        localStorage.removeItem('sofia_copied_wallets');
      } catch {}
    }
  };

  const handleToggle = async (wallet: any) => {
    await api.toggleCopyWallet(wallet.id, !wallet.copy_enabled, wallet.max_copy_usd);
    smQuery.refetch();
  };

  const visibleWallets = (smQuery.data?.wallets || []).filter(
    (w: any) => !copiedWallets.includes(String(w.address || '').trim().toLowerCase())
  );

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
        {copiedWallets.length > 0 && (
          <button
            type="button"
            onClick={handleResetCopied}
            className="px-3 py-1.5 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 text-xs font-mono font-bold transition flex items-center gap-1.5"
            title="Klik untuk menampilkan kembali dompet whale yang pernah disalin"
          >
            <span>👁️ Dompet Disalin: {copiedWallets.length} (Reset / Tampilkan)</span>
          </button>
        )}
      </div>

      <QueryState isLoading={smQuery.isLoading} isError={smQuery.isError} error={smQuery.error}>
        <div className={isUltrawide ? 'grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-4 items-stretch' : 'grid grid-cols-1 gap-4'}>
          {visibleWallets.length === 0 ? (
            <div className="p-8 text-center rounded-2xl bg-obsidian-900 border border-obsidian-800 text-slate-400 font-mono text-sm col-span-full">
              Semua dompet whale yang tersedia telah disalin dan disembunyikan. Gunakan tombol &ldquo;Reset / Tampilkan&rdquo; di atas untuk menampilkan kembali.
            </div>
          ) : (
            visibleWallets.map((w: any) => (
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
                <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                  <span title={w.address}>{w.address}</span>
                  <button
                    type="button"
                    onClick={() => handleCopy(w.address, w.id)}
                    className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 text-[10px] font-mono flex items-center gap-1 transition"
                    title="Salin Alamat Dompet Whale"
                  >
                    <LucideIcon name={copiedId === w.id ? 'check' : 'copy'} className="w-3 h-3" />
                    <span>{copiedId === w.id ? '✓ Tersalin' : 'Salin Wallet'}</span>
                  </button>
                </div>
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
          )))}
        </div>
      </QueryState>
    </div>
  );
}
