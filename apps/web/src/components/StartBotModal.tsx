import React, { useState, useEffect } from 'react';
import { LucideIcon } from './LucideIcon';
import { formatIdr, formatUsd } from '../lib/api';

export interface StartBotParams {
  buy_amount_usd: number;
  max_open_positions: number;
  slippage_pct: number;
}

interface StartBotModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (params: StartBotParams) => Promise<void>;
  mode: 'PAPER' | 'LIVE';
  strategyMode: string;
  initialBuyAmountUsd?: number;
  initialMaxPositions?: number;
  initialSlippagePct?: number;
  usdIdr?: number;
  solPrice?: number;
  liveUsdcBal?: number;
  liveGasBal?: number;
  liveGasToken?: string;
}

export function StartBotModal({
  isOpen,
  onClose,
  onConfirm,
  mode,
  strategyMode,
  initialBuyAmountUsd = 1.0,
  initialMaxPositions = 3,
  initialSlippagePct = 1.5,
  usdIdr = 16300,
  solPrice = 145,
  liveUsdcBal = 0,
  liveGasBal = 0,
  liveGasToken = 'SOL',
}: StartBotModalProps) {
  const [buyAmountUsd, setBuyAmountUsd] = useState<number | string>(initialBuyAmountUsd);
  const [maxPositions, setMaxPositions] = useState<number | string>(initialMaxPositions);
  const [slippagePct, setSlippagePct] = useState<number | string>(initialSlippagePct);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      setBuyAmountUsd(initialBuyAmountUsd > 0 ? initialBuyAmountUsd : 1.0);
      setMaxPositions(initialMaxPositions > 0 ? initialMaxPositions : 3);
      setSlippagePct(initialSlippagePct > 0 ? initialSlippagePct : 1.5);
      setErrorMsg('');
      setLoading(false);
    }
  }, [isOpen, initialBuyAmountUsd, initialMaxPositions, initialSlippagePct]);

  if (!isOpen) return null;

  const isLive = mode === 'LIVE';
  const numBuyUsd = Number(buyAmountUsd) || 0;
  const numMaxPos = Number(maxPositions) || 0;
  const numSlipPct = Number(slippagePct) || 0;
  const buyIdrEquiv = numBuyUsd * usdIdr;
  const buySolEquiv = solPrice > 0 ? numBuyUsd / solPrice : 0;

  const quickUsdPresets = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0];
  const quickPositionPresets = [1, 2, 3, 5, 8];
  const quickSlippagePresets = [0.5, 1.0, 1.5, 2.0, 2.5, 5.0];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    if (numBuyUsd <= 0 || isNaN(numBuyUsd)) {
      setErrorMsg('Nominal beli per trade harus lebih besar dari $0.');
      return;
    }
    if (numMaxPos < 1 || isNaN(numMaxPos)) {
      setErrorMsg('Maksimal posisi terbuka minimal 1 koin.');
      return;
    }
    if (numSlipPct <= 0 || isNaN(numSlipPct)) {
      setErrorMsg('Toleransi slippage harus lebih besar dari 0%.');
      return;
    }

    try {
      setLoading(true);
      await onConfirm({
        buy_amount_usd: Number(numBuyUsd),
        max_open_positions: Math.round(Number(numMaxPos)),
        slippage_pct: Number(numSlipPct),
      });
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMsg(err.message);
      } else if (typeof err === 'object' && err !== null && 'message' in err) {
        setErrorMsg(String(err.message));
      } else {
        setErrorMsg('Gagal memulai bot.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div
        className="w-full max-w-lg bg-obsidian-900 border border-obsidian-700/90 rounded-2xl p-6 shadow-2xl space-y-5 text-slate-100 font-mono relative overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Glow accent */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-cyan-500 via-emerald-500 to-amber-500" />

        {/* Modal Header */}
        <div className="flex items-start justify-between gap-4 border-b border-obsidian-800 pb-3.5">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                <LucideIcon name="sliders" className="w-4 h-4" />
              </span>
              <h2 className="text-base font-extrabold uppercase tracking-wide text-white">
                Konfigurasi Sebelum Menjalankan Bot
              </h2>
            </div>
            <p className="text-xs text-slate-400 font-sans">
              Tentukan nominal trade, slot posisi, dan toleransi slippage sebelum bot mulai memindai &amp; mengeksekusi DEX.
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

        {/* Mode & Strategy Badges */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span
            className={`px-2.5 py-1 rounded-lg font-bold border ${
              isLive
                ? 'bg-rose-500/15 text-rose-300 border-rose-500/40'
                : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
            }`}
          >
            {isLive ? '🔴 LIVE (On-Chain Solana)' : '🟢 PAPER (Simulasi Kas)'}
          </span>
          <span className="px-2.5 py-1 rounded-lg font-bold bg-obsidian-950 border border-obsidian-700 text-cyan-300">
            Strategi: {strategyMode}
          </span>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-300 text-xs">
            ⚠️ {errorMsg}
          </div>
        )}

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* FIELD 1: NOMINAL BELI PER TRADE ($ USD) */}
          <div className="space-y-2 p-3.5 rounded-xl bg-obsidian-950/80 border border-obsidian-800">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <LucideIcon name="banknote" className="w-4 h-4 text-emerald-400" />
                <span>Berapa Dolar per Trade ($ USD)?</span>
              </label>
              <span className="text-[11px] text-emerald-400 font-bold">
                ≈ {formatIdr(buyIdrEquiv)}
              </span>
            </div>

            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-sm">
                $
              </span>
              <input
                type="number"
                step="any"
                min="0.1"
                max="1000"
                value={buyAmountUsd}
                onChange={(e) => setBuyAmountUsd(e.target.value === '' ? '' : e.target.value)}
                className="w-full pl-7 pr-24 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 focus:border-cyan-500 text-white font-extrabold text-sm focus:outline-none transition"
                placeholder="1.00"
                required
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-slate-400">
                ~{buySolEquiv.toFixed(4)} SOL
              </span>
            </div>

            {/* Quick chips */}
            <div className="flex flex-wrap gap-1.5 pt-1">
              <span className="text-[10px] text-slate-400 self-center mr-1">Preset:</span>
              {quickUsdPresets.map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setBuyAmountUsd(val)}
                  className={`px-2 py-0.5 rounded text-[11px] font-bold border transition ${
                    buyAmountUsd === val
                      ? 'bg-emerald-500 text-obsidian-950 border-emerald-400 shadow-sm'
                      : 'bg-obsidian-850 hover:bg-obsidian-800 text-slate-300 border-obsidian-700'
                  }`}
                >
                  ${val.toFixed(2)}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-slate-400 font-sans">
              Jumlah dana yang dialokasikan setiap kali bot menyergap 1 meme coin baru.
            </p>
          </div>

          {/* FIELD 2: MAKSIMAL POSISI TERBUKA (MAX OPEN POSITIONS) */}
          <div className="space-y-2 p-3.5 rounded-xl bg-obsidian-950/80 border border-obsidian-800">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <LucideIcon name="crosshair" className="w-4 h-4 text-cyan-400" />
                <span>Berapa Posisi Boleh Dibuka Bersamaan?</span>
              </label>
              <span className="text-[11px] text-cyan-400 font-bold">
                {maxPositions} Koin Maksimal
              </span>
            </div>

            <input
              type="number"
              step="1"
              min="1"
              max="20"
              value={maxPositions}
              onChange={(e) => setMaxPositions(e.target.value === '' ? '' : parseInt(e.target.value, 10))}
              className="w-full px-3 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 focus:border-cyan-500 text-white font-extrabold text-sm focus:outline-none transition"
              placeholder="3"
              required
            />

            {/* Quick chips */}
            <div className="flex flex-wrap gap-1.5 pt-1">
              <span className="text-[10px] text-slate-400 self-center mr-1">Preset:</span>
              {quickPositionPresets.map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setMaxPositions(val)}
                  className={`px-2 py-0.5 rounded text-[11px] font-bold border transition ${
                    maxPositions === val
                      ? 'bg-cyan-500 text-obsidian-950 border-cyan-400 shadow-sm'
                      : 'bg-obsidian-850 hover:bg-obsidian-800 text-slate-300 border-obsidian-700'
                  }`}
                >
                  {val} Koin
                </button>
              ))}
            </div>
            <p className="text-[10px] text-slate-400 font-sans">
              Jika jumlah koin yang di-hold sudah mencapai batas ini, bot otomatis menahan pembelian koin baru sampai ada posisi yang take-profit/stop-loss.
            </p>
          </div>

          {/* FIELD 3: SLIPPAGE TOLERANCE (%) */}
          <div className="space-y-2 p-3.5 rounded-xl bg-obsidian-950/80 border border-obsidian-800">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <LucideIcon name="zap" className="w-4 h-4 text-amber-400" />
                <span>Toleransi Slippage Berapa Persen (%)?</span>
              </label>
              <span className="text-[11px] text-amber-400 font-bold">
                {slippagePct}% Toleransi
              </span>
            </div>

            <div className="relative">
              <input
                type="number"
                step="any"
                min="0.1"
                max="25"
                value={slippagePct}
                onChange={(e) => setSlippagePct(e.target.value === '' ? '' : e.target.value)}
                className="w-full px-3 pr-8 py-2 rounded-lg bg-obsidian-900 border border-obsidian-700 focus:border-cyan-500 text-white font-extrabold text-sm focus:outline-none transition"
                placeholder="1.5"
                required
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-sm">
                %
              </span>
            </div>

            {/* Quick chips */}
            <div className="flex flex-wrap gap-1.5 pt-1">
              <span className="text-[10px] text-slate-400 self-center mr-1">Preset:</span>
              {quickSlippagePresets.map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setSlippagePct(val)}
                  className={`px-2 py-0.5 rounded text-[11px] font-bold border transition ${
                    slippagePct === val
                      ? 'bg-amber-400 text-obsidian-950 border-amber-300 shadow-sm'
                      : 'bg-obsidian-850 hover:bg-obsidian-800 text-slate-300 border-obsidian-700'
                  }`}
                >
                  {val}%
                </button>
              ))}
            </div>
            <p className="text-[10px] text-slate-400 font-sans">
              Batas toleransi pergeseran harga saat swap di DEX. Nilai 1.0% - 2.5% disarankan untuk meme coin baru di Solana.
            </p>
          </div>

          {/* SAFETY CHECK SUMMARY */}
          {isLive && (
            <div className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800 text-[11px] space-y-1.5">
              <div className="text-slate-400 uppercase font-bold text-[10px] flex items-center justify-between">
                <span>Kas Wallet Live Saat Ini:</span>
                <span className="text-emerald-400">Siap Eksekusi</span>
              </div>
              <div className="flex items-center justify-between text-slate-200">
                <span>🔵 Kas USDC:</span>
                <span className="font-extrabold text-cyan-300">
                  {liveUsdcBal.toFixed(4)} USDC ({formatIdr(liveUsdcBal * usdIdr)})
                </span>
              </div>
              <div className="flex items-center justify-between text-slate-200">
                <span>🟡 Gas Fee SOL:</span>
                <span className="font-extrabold text-amber-300">
                  {liveGasBal.toFixed(6)} {liveGasToken} ({formatUsd(liveGasBal * solPrice)})
                </span>
              </div>
              <p className="text-[10px] text-slate-400 font-sans pt-1 border-t border-obsidian-800/80">
                ✓ Sistem akan otomatis menyisihkan cadangan gas SOL agar koin nantinya selalu bisa dijual (tidak gantung).
              </p>
            </div>
          )}

          {/* Modal Footer Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-obsidian-800">
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
              className="px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 text-obsidian-950 font-extrabold text-xs shadow-glow-emerald transition flex items-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <span className="inline-block w-3.5 h-3.5 border-2 border-obsidian-950 border-t-transparent rounded-full animate-spin" />
                  <span>Menyiapkan Bot...</span>
                </>
              ) : (
                <>
                  <span>🚀</span>
                  <span>Simpan &amp; Jalankan Bot</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
