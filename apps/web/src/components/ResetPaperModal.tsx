import React, { useState, useEffect } from 'react';
import { LucideIcon } from './LucideIcon';
import { formatIdr } from '../lib/api';

interface ResetPaperModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (initialUsd: number) => Promise<void>;
  currentInitialUsd?: number;
  usdIdr?: number;
}

export function ResetPaperModal({
  isOpen,
  onClose,
  onConfirm,
  currentInitialUsd = 10.0,
  usdIdr = 16300,
}: ResetPaperModalProps) {
  const [amountUsd, setAmountUsd] = useState<number>(currentInitialUsd);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      setAmountUsd(currentInitialUsd > 0 ? currentInitialUsd : 10.0);
      setErrorMsg('');
      setLoading(false);
    }
  }, [isOpen, currentInitialUsd]);

  if (!isOpen) return null;

  const amountIdr = amountUsd * usdIdr;

  const quickPresets = [
    { label: '$10 (~Rp 160rb)', value: 10 },
    { label: '$50 (~Rp 800rb)', value: 50 },
    { label: '$100 (~Rp 1.6jt)', value: 100 },
    { label: '$250 (~Rp 4jt)', value: 250 },
    { label: '$500 (~Rp 8jt)', value: 500 },
    { label: '$1,000 (~Rp 16jt)', value: 1000 },
    { label: '$5,000 (~Rp 81jt)', value: 5000 },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    if (amountUsd <= 0 || isNaN(amountUsd)) {
      setErrorMsg('Modal awal simulasi harus lebih besar dari $0.');
      return;
    }

    try {
      setLoading(true);
      await onConfirm(Number(amountUsd));
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMsg(err.message);
      } else if (typeof err === 'object' && err !== null && 'message' in err) {
        setErrorMsg(String(err.message));
      } else {
        setErrorMsg('Gagal mereset modal paper.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div
        className="w-full max-w-md bg-obsidian-900 border border-obsidian-700/90 rounded-2xl p-6 shadow-2xl space-y-5 text-slate-100 font-mono relative overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Glow accent */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 via-cyan-500 to-indigo-500" />

        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-obsidian-800 pb-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                <LucideIcon name="sliders" className="w-4 h-4" />
              </span>
              <h2 className="text-base font-extrabold uppercase tracking-wide text-white">
                Atur Modal Awal Paper Trading
              </h2>
            </div>
            <p className="text-xs text-slate-400 font-sans">
              Tentukan saldo awal simulasi sesuai keinginan Anda untuk menguji strategi dan performa bot.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-obsidian-800 transition"
            aria-label="Tutup"
          >
            ✕
          </button>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-300 text-xs">
            ⚠️ {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Custom Input */}
          <div className="space-y-2 p-3.5 rounded-xl bg-obsidian-950/80 border border-obsidian-800">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <LucideIcon name="banknote" className="w-4 h-4 text-emerald-400" />
                <span>Modal Awal Simulasi ($ USD)</span>
              </label>
              <span className="text-[11px] text-emerald-400 font-bold">
                ≈ {formatIdr(amountIdr)}
              </span>
            </div>

            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-sm">
                $
              </span>
              <input
                type="number"
                step="1"
                min="1"
                max="1000000"
                value={amountUsd}
                onChange={(e) => setAmountUsd(parseFloat(e.target.value) || 0)}
                className="w-full pl-7 pr-4 py-2.5 rounded-lg bg-obsidian-900 border border-obsidian-700 focus:border-emerald-500 text-white font-extrabold text-base focus:outline-none transition"
                placeholder="100"
                required
              />
            </div>

            {/* Quick chips */}
            <div className="flex flex-wrap gap-1.5 pt-1.5">
              {quickPresets.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setAmountUsd(p.value)}
                  className={`px-2 py-1 rounded text-[11px] font-bold border transition ${
                    amountUsd === p.value
                      ? 'bg-emerald-500 text-obsidian-950 border-emerald-400 shadow-sm'
                      : 'bg-obsidian-850 hover:bg-obsidian-800 text-slate-300 border-obsidian-700'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-200/90 font-sans space-y-1">
            <div className="font-bold font-mono text-amber-300">ℹ️ Perhatian:</div>
            <p>
              Menerapkan modal baru akan membersihkan portofolio &amp; riwayat posisi aktif pada mode Paper dan mengatur ulang ekuitas dasar ke <strong>${amountUsd.toLocaleString()} (≈ {formatIdr(amountIdr)})</strong>.
            </p>
          </div>

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-3 pt-2 border-t border-obsidian-800">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 rounded-xl bg-obsidian-850 hover:bg-obsidian-800 border border-obsidian-700 text-slate-300 font-bold text-xs transition disabled:opacity-50"
            >
              Batal
            </button>

            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 font-extrabold text-xs shadow-glow-emerald transition flex items-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <span className="inline-block w-3.5 h-3.5 border-2 border-obsidian-950 border-t-transparent rounded-full animate-spin" />
                  <span>Mereset Modal...</span>
                </>
              ) : (
                <>
                  <span>🔄</span>
                  <span>Terapkan Modal Baru</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
