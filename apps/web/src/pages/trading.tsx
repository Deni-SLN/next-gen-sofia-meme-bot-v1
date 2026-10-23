import React, { useState, useEffect } from 'react';
import {
  api,
  useApiQuery,
  formatIdr,
  formatUsd,
  getTradingMode,
  setTradingMode,
  getStrategyMode,
  setStrategyModeStorage,
} from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { BotActivityCard } from '@/components/BotActivityCard';
import { LucideIcon } from '@/components/LucideIcon';
import { StartBotModal, StartBotParams } from '@/components/StartBotModal';
import { ResetPaperModal } from '@/components/ResetPaperModal';
import { useUltrawide, toggleUltrawide } from '@/lib/useUltrawide';
const RELAY_OPTIONS = [
  { id: 'JITO_0SLOT', label: '⚡ Jito 0-Slot Bundle (Anti-MEV)', desc: 'Inklusi blok-0 langsung ke validator Jito' },
  { id: 'HELIUS_STAKED', label: '🚀 Helius Staked SwQoS', desc: 'Jalur RPC staked prioritas tinggi' },
  { id: 'BLOXROUTE', label: '🛡️ bloXroute Trader API', desc: 'Proteksi frontrun & sandwich optimal' },
  { id: 'MAINNET_STD', label: '🌐 Mainnet Standard RPC', desc: 'Tanpa biaya bribe tambahan' },
];

const BOT_STRATEGY_MODES = [
  {
    id: 'SAFE',
    badge: '🛡️ SAFE MODE',
    title: 'Safe (Konservatif)',
    subtitle: 'Token Lulus (Migrated) & Likuiditas Tinggi',
    desc: 'Hanya membeli koin Solana yang sudah lulus ke Raydium/PumpSwap dengan Likuiditas > $20K & Safety Score ≥ 82. Risiko rendah.',
    stats: 'Min Score: 82 • TP: +20% / SL: -8% • Speed: 4.0s',
    winrateBarClass: 'bg-emerald-400',
    winrateBadgeClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
    activeClass: 'border-emerald-500 bg-emerald-500/15 text-emerald-300 shadow-glow-emerald',
    badgeClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  },
  {
    id: 'DEFAULT',
    badge: '⚖️ DEFAULT MODE',
    title: 'Default (Seimbang)',
    subtitle: 'Final Stretch & Migrated Pool',
    desc: 'Seimbang antara keamanan kontrak (Score ≥ 70) dan momentum orderflow 5m pada pool Final Stretch & Migrated Solana.',
    stats: 'Min Score: 70 • TP: +30% / SL: -10% • Speed: 3.0s',
    winrateBarClass: 'bg-cyan-400',
    winrateBadgeClass: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
    activeClass: 'border-cyan-500 bg-cyan-500/15 text-cyan-300',
    badgeClass: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
  },
  {
    id: 'AGGRESSIVE',
    badge: '🔥 AGRESIF (DEXSCREENER + GMGN)',
    title: 'Agresif (Khusus Koin Baru & Cepat)',
    subtitle: 'DexScreener Latest Profiles v1 + GMGN.ai Trench Radar',
    desc: 'Khusus menyergap meme coin BARU MUNCUL (Umur < 3 Jam, MCap < $500K) via DexScreener & GMGN.ai. Memblokir 100% koin lama (BONK, PEPE, WIF, POPCAT).',
    stats: 'Max Umur: 180m • Max MCap: $500K • Quick Scalp: +12% (TP +35% / SL -12%) • 2.0s',
    winrateBarClass: 'bg-amber-400',
    winrateBadgeClass: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    activeClass: 'border-amber-500 bg-amber-500/15 text-amber-300',
    badgeClass: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  },
] as const;

const QUICK_SNIPE_PRESETS = [15000, 30000, 50000, 100000];

export default function TradingPage() {
  const isUltrawide = useUltrawide();
  const [selectedMode, setSelectedMode] = useState<'PAPER' | 'LIVE'>(() => getTradingMode());
  const botQuery = useApiQuery(() => api.getBotStatus(), []);
  const portfolioQuery = useApiQuery(() => api.getPortfolio(selectedMode), [selectedMode]);
  const walletsQuery = useApiQuery(() => api.getWallets(), []);
  const configQuery = useApiQuery(() => api.getSniperConfig(), []);
  const pulseQuery = useApiQuery(() => api.getPulse(), []);

  const [strategyMode, setStrategyMode] = useState<'SAFE' | 'DEFAULT' | 'AGGRESSIVE'>(() => getStrategyMode());
  const [actionError, setActionError] = useState<string>('');
  const [actionSuccess, setActionSuccess] = useState<string>('');

  // PumpSniper Terminal Config State
  const [relayMode, setRelayMode] = useState<string>('JITO_0SLOT');
  const [jitoTip, setJitoTip] = useState<number>(0.005);
  const [slippage, setSlippage] = useState<number>(1.5);
  const [minBondingPct, setMinBondingPct] = useState<number>(15);
  const [maxDevHoldPct, setMaxDevHoldPct] = useState<number>(5);
  const [onlyNewCreations, setOnlyNewCreations] = useState<boolean>(false);
  const [maxTokenAgeMinutes, setMaxTokenAgeMinutes] = useState<number>(2880);
  const [maxMarketCapUsd, setMaxMarketCapUsd] = useState<number>(50000000);
  const [autoTpPct, setAutoTpPct] = useState<number>(25);
  const [autoSlPct, setAutoSlPct] = useState<number>(8);
  const [trailingStop, setTrailingStop] = useState<boolean>(true);
  const [trailingPct, setTrailingPct] = useState<number>(5);
  const [multiWalletRot, setMultiWalletRot] = useState<boolean>(true);
  const [snipeAmountIdr, setSnipeAmountIdr] = useState<number>(20000);
  const [maxOpenPositions, setMaxOpenPositions] = useState<number>(3);
  const [showStartBotModal, setShowStartBotModal] = useState<boolean>(false);
  const [showResetPaperModal, setShowResetPaperModal] = useState<boolean>(false);
  const [terminalSymbol, setTerminalSymbol] = useState<string>('');
  const [terminalContract, setTerminalContract] = useState<string>('');
  const [terminalAmountIdr, setTerminalAmountIdr] = useState<number>(25000);
  const [isSniping, setIsSniping] = useState<boolean>(false);
  const [sellingKey, setSellingKey] = useState<string | null>(null);
  const [quickExitNotice, setQuickExitNotice] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  const newCreationsList: any[] = pulseQuery.data?.new_creations || [];

  useEffect(() => {
    if (!terminalSymbol && newCreationsList.length > 0) {
      const freshest = newCreationsList[0];
      setTerminalSymbol(freshest.base_symbol || freshest.symbol || '');
      setTerminalContract(freshest.contract || '');
    }
  }, [newCreationsList, terminalSymbol]);

  useEffect(() => {
    if (botQuery.data?.status === 'running') {
      const srvMode = botQuery.data?.mode;
      if ((srvMode === 'LIVE' || srvMode === 'PAPER') && srvMode !== selectedMode) {
        setSelectedMode(srvMode);
        setTradingMode(srvMode);
      }
      const srvStrat = botQuery.data?.strategy_mode;
      if (srvStrat && ['SAFE', 'DEFAULT', 'AGGRESSIVE'].includes(srvStrat) && srvStrat !== strategyMode) {
        setStrategyMode(srvStrat);
        setStrategyModeStorage(srvStrat);
      }
    }
  }, [botQuery.data]);

  const configHydratedRef = React.useRef(false);

  useEffect(() => {
    if (configQuery.data && !configHydratedRef.current) {
      configHydratedRef.current = true;
      const c = configQuery.data;
      if (c.strategy_mode && ['SAFE', 'DEFAULT', 'AGGRESSIVE'].includes(c.strategy_mode)) {
        setStrategyMode(c.strategy_mode);
        setStrategyModeStorage(c.strategy_mode);
      }
      if (c.relay_mode) setRelayMode(c.relay_mode);
      if (c.jito_bribe_sol !== undefined) setJitoTip(Number(c.jito_bribe_sol));
      const slipVal = c.slippage_pct !== undefined ? c.slippage_pct : c.max_slippage_pct;
      if (slipVal !== undefined) setSlippage(Number(slipVal));
      if (c.min_bonding_curve_pct !== undefined) setMinBondingPct(Number(c.min_bonding_curve_pct));
      if (c.max_dev_holding_pct !== undefined) setMaxDevHoldPct(Number(c.max_dev_holding_pct));
      if (c.only_new_creations !== undefined) setOnlyNewCreations(Boolean(c.only_new_creations));
      if (c.max_token_age_minutes !== undefined) setMaxTokenAgeMinutes(Number(c.max_token_age_minutes));
      if (c.max_market_cap_usd !== undefined) setMaxMarketCapUsd(Number(c.max_market_cap_usd));
      if (c.auto_tp_pct !== undefined) setAutoTpPct(Number(c.auto_tp_pct));
      if (c.auto_sl_pct !== undefined) setAutoSlPct(Number(c.auto_sl_pct));
      if (c.trailing_stop_enabled !== undefined) setTrailingStop(Boolean(c.trailing_stop_enabled));
      if (c.trailing_stop_pct !== undefined) setTrailingPct(Number(c.trailing_stop_pct));
      if (c.multi_wallet_rotation !== undefined) setMultiWalletRot(Boolean(c.multi_wallet_rotation));
      const buyVal = c.buy_amount_idr !== undefined ? c.buy_amount_idr : c.snipe_amount_idr;
      if (buyVal !== undefined) setSnipeAmountIdr(Number(buyVal));
      if (c.max_open_positions !== undefined) setMaxOpenPositions(Number(c.max_open_positions));
    }
  }, [configQuery.data]);

  useEffect(() => {
    setSelectedMode(getTradingMode());
    const handler = (e: any) => {
      setSelectedMode(e.detail);
      walletsQuery.refetch();
      portfolioQuery.refetch();
    };
    const botHandler = () => botQuery.refetch();
    const resetHandler = (e: any) => {
      if (e?.detail) portfolioQuery.setData(e.detail);
      else portfolioQuery.refetch();
      walletsQuery.refetch();
    };
    const tradeHandler = () => {
      botQuery.refetch();
      portfolioQuery.refetch();
      walletsQuery.refetch();
    };
    window.addEventListener('sofia-mode-change', handler);
    window.addEventListener('sofia-bot-status-change', botHandler);
    window.addEventListener('sofia-paper-reset', resetHandler);
    window.addEventListener('sofia-bot-trade-executed', tradeHandler);

    // Real-time auto-refresh every 8 seconds so Wallet & Terminal Positions stay 100% synced without hitting Solana RPC 429 rate-limits
    const rtInterval = setInterval(() => {
      portfolioQuery.refetch();
      walletsQuery.refetch();
    }, 8000);

    return () => {
      clearInterval(rtInterval);
      window.removeEventListener('sofia-mode-change', handler);
      window.removeEventListener('sofia-bot-status-change', botHandler);
      window.removeEventListener('sofia-paper-reset', resetHandler);
      window.removeEventListener('sofia-bot-trade-executed', tradeHandler);
    };
  }, []);

  const isRunning = botQuery.data?.status === 'running';
  const isLive = selectedMode === 'LIVE';
  const usdIdr = portfolioQuery.data?.usd_idr || 18000;

  // --- 4 AUTO-SNIPER CARDS METRICS: EKUITAS, SALDO KAS, POSISI, PNL ---
  const allWallets: any[] = walletsQuery.data?.wallets || [];
  const liveWallets = allWallets.filter((w: any) => !w.name?.includes('Modal Paper'));
  const liveTradingWallets = liveWallets.filter((w: any) => w.gate === 'trading');

  // Real on-chain equity across all live Phantom wallets
  const liveWalletsEquityUsd = liveWallets.reduce((acc: number, w: any) => acc + (Number(w.balance_usd) || 0), 0);
  const liveWalletsEquityIdr = liveWallets.reduce((acc: number, w: any) => acc + (Number(w.balance_idr) || 0), 0);

  // Available cash in Hot Wallet Trading (ready to snipe)
  const liveCashUsd = liveTradingWallets.reduce((acc: number, w: any) => acc + (Number(w.balance_usd) || 0), 0);
  const liveCashIdr = liveTradingWallets.reduce((acc: number, w: any) => acc + (Number(w.balance_idr) || 0), 0);

  // Separate USDC (Kas Trading) & Gas Fee (SOL on-chain)
  const primaryLiveTradingWallet = liveTradingWallets[0];
  const liveUsdcBal = primaryLiveTradingWallet?.usdc_balance ?? (
    (primaryLiveTradingWallet?.spl_tokens || []).find((t: any) => t.symbol === 'USDC' || t.mint === 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v')?.amount || 0
  );
  const liveUsdcUsd = primaryLiveTradingWallet?.usdc_usd ?? liveUsdcBal;
  const liveUsdcIdr = primaryLiveTradingWallet?.usdc_idr ?? (liveUsdcUsd * usdIdr);

  const liveGasBal = primaryLiveTradingWallet?.gas_fee_balance ?? (Number(primaryLiveTradingWallet?.balance) || 0);
  const liveGasToken = primaryLiveTradingWallet?.gas_fee_token || primaryLiveTradingWallet?.token || 'SOL';
  const liveGasUsd = primaryLiveTradingWallet?.gas_fee_usd ?? Math.max(0, (Number(primaryLiveTradingWallet?.balance_usd) || 0) - liveUsdcUsd);
  const liveGasIdr = primaryLiveTradingWallet?.gas_fee_idr ?? (liveGasUsd * usdIdr);

  const d = portfolioQuery.data;
  const paperInitialIdr = Number(d?.paper_initial_idr) || 150000;
  const paperInitialUsd = Number(d?.paper_initial_usd) || (paperInitialIdr / usdIdr);
  const paperCashUsd = Number(d?.paper_cash_usd) || paperInitialUsd;
  const paperCashIdr = Number(d?.paper_cash_idr) || paperInitialIdr;
  const holdingsList: any[] = portfolioQuery.data?.holdings || [];
  const holdingsCount = holdingsList.length;
  const holdingsValUsd = Number(portfolioQuery.data?.net_holdings_value_usd || portfolioQuery.data?.total_value) || 0;
  const holdingsValIdr = Number(portfolioQuery.data?.net_holdings_value_idr || portfolioQuery.data?.total_value_idr) || 0;

  // Active Total Equity: In LIVE = Real On-Chain Wallets + Holdings; In PAPER = Paper Cash + Holdings
  const activeEquityUsd = isLive
    ? (liveWalletsEquityUsd + holdingsValUsd)
    : (Number(portfolioQuery.data?.total_equity_usd) || (paperCashUsd + holdingsValUsd));
  const activeEquityIdr = isLive
    ? (liveWalletsEquityIdr + holdingsValIdr)
    : (Number(portfolioQuery.data?.total_equity_idr) || (paperCashIdr + holdingsValIdr));

  // Active Cash Available
  const activeCashUsd = isLive ? liveCashUsd : paperCashUsd;
  const activeCashIdr = isLive ? liveCashIdr : paperCashIdr;

  // PnL metrics
  const unrealizedPnlUsd = Number(portfolioQuery.data?.unrealized_pnl) || 0;
  const unrealizedPnlIdr = Number(portfolioQuery.data?.unrealized_pnl_idr) || 0;
  const unrealizedPnlPct = Number(portfolioQuery.data?.unrealized_pnl_pct) || 0;
  const pnlIsPositive = unrealizedPnlIdr >= 0;

  const handleToggleSwitch = () => {
    if (isRunning) {
      setActionError(
        '🔒 Mode PAPER / LIVE tidak dapat diubah selama Bot sedang berjalan. Silakan klik "⏹ HENTIKAN BOT SEKARANG" terlebih dahulu.'
      );
      return;
    }
    const next = selectedMode === 'PAPER' ? 'LIVE' : 'PAPER';
    setSelectedMode(next);
    setTradingMode(next);
    setActionError('');
    setActionSuccess('');
  };

  const handleSelectStrategyMode = async (newStrat: 'SAFE' | 'DEFAULT' | 'AGGRESSIVE') => {
    if (isRunning && newStrat !== strategyMode) {
      setActionError(
        `🔒 Mode Strategi (${strategyMode}) terkunci selama Bot sedang berjalan. Silakan klik "⏹ HENTIKAN BOT SEKARANG" terlebih dahulu jika ingin berpindah mode.`
      );
      return;
    }
    setStrategyMode(newStrat);
    setStrategyModeStorage(newStrat);
    setActionError('');
    setActionSuccess('');
    if (newStrat === 'AGGRESSIVE' && newCreationsList.length > 0) {
      setTerminalSymbol(newCreationsList[0].base_symbol || newCreationsList[0].symbol);
      setTerminalContract(newCreationsList[0].contract || '');
    }
    try {
      const updated = await api.updateSniperConfig({
        strategy_mode: newStrat,
        apply_preset: true,
      });
      if (updated) {
        setRelayMode(updated.relay_mode || 'JITO_0SLOT');
        setJitoTip(Number(updated.jito_bribe_sol || 0.005));
        setSlippage(Number(updated.slippage_pct || 1.2));
        setMinBondingPct(Number(updated.min_bonding_curve_pct || 15));
        setMaxDevHoldPct(Number(updated.max_dev_holding_pct || 10));
        setOnlyNewCreations(Boolean(updated.only_new_creations));
        setMaxTokenAgeMinutes(Number(updated.max_token_age_minutes || 180));
        setMaxMarketCapUsd(Number(updated.max_market_cap_usd || 500000));
        setAutoTpPct(Number(updated.auto_tp_pct || 20));
        setAutoSlPct(Number(updated.auto_sl_pct || 8));
        setTrailingStop(Boolean(updated.trailing_stop_enabled));
        setTrailingPct(Number(updated.trailing_stop_pct || 5));
        setSnipeAmountIdr(Number(updated.buy_amount_idr || 20000));
      }
      setActionSuccess(
        newStrat === 'AGGRESSIVE'
          ? '🔥 Mode AGRESIF (DexScreener + GMGN.ai) diaktifkan! Koin lama (BONK/PEPE/WIF) diblokir 100%. Bot kini hanya menyergap koin meme BARU MUNCUL (< 180 menit, MCap < $500K) & menjual otomatis koin lama jika ada di portofolio.'
          : newStrat === 'SAFE'
          ? '🛡️ Mode SAFE diaktifkan! Bot hanya membeli token yang sudah lulus (Migrated) dengan Likuiditas > $20K & Safety Score ≥ 82.'
          : '⚖️ Mode DEFAULT diaktifkan! Bot berjalan seimbang pada pool Final Stretch & Migrated.'
      );
      configQuery.refetch();
      botQuery.refetch();
      pulseQuery.refetch();
    } catch (err: any) {
      setActionError(err?.message || 'Gagal mengubah mode strategi bot');
    }
  };

  const handlePowerButton = async () => {
    setActionError('');
    setActionSuccess('');
    if (isRunning) {
      try {
        await api.stopBot();
        setActionSuccess('⏹ Mesin PumpSniper Bot berhasil dihentikan.');
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: false } }));
        }
        botQuery.refetch();
      } catch (err: unknown) {
        if (err instanceof Error) {
          setActionError(err.message);
        } else {
          setActionError('Gagal menghentikan bot.');
        }
      }
    } else {
      setShowStartBotModal(true);
    }
  };

  const handleConfirmStartBot = async (params: StartBotParams) => {
    setActionError('');
    setActionSuccess('');
    await api.startBot(selectedMode, strategyMode, {
      buy_amount_usd: params.buy_amount_usd,
      max_open_positions: params.max_open_positions,
      slippage_pct: params.slippage_pct,
    });
    setSnipeAmountIdr(params.buy_amount_usd * usdIdr);
    setMaxOpenPositions(params.max_open_positions);
    setSlippage(params.slippage_pct);
    setActionSuccess(
      selectedMode === 'PAPER'
        ? `🟢 Mesin PumpSniper Bot berjalan dalam Mode PAPER • $${params.buy_amount_usd.toFixed(2)}/trade • Maks ${params.max_open_positions} posisi • Slip ${params.slippage_pct}%.`
        : `🔴 Mesin PumpSniper Bot berjalan dalam Mode LIVE ON-CHAIN • $${params.buy_amount_usd.toFixed(2)}/trade • Maks ${params.max_open_positions} posisi • Slip ${params.slippage_pct}% (${relayMode})!`
    );
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: true } }));
    }
    botQuery.refetch();
    configQuery.refetch();
  };

  const handleConfirmResetPaper = async (initialUsd: number) => {
    setActionError('');
    setActionSuccess('');
    try {
      const freshOverview = await api.resetPaperAccount({ initial_capital_usd: initialUsd });
      portfolioQuery.setData(freshOverview);
      await walletsQuery.refetch();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sofia-paper-reset', { detail: freshOverview }));
      }
      setActionSuccess(
        `🔄 Modal awal Paper berhasil diatur ke $${initialUsd.toLocaleString()} (≈ ${formatIdr(initialUsd * usdIdr)}). Portofolio simulasi telah diatur ulang!`
      );
    } catch (err: unknown) {
      if (err instanceof Error) {
        setActionError(err.message);
      } else {
        setActionError('Gagal mereset modal simulasi.');
      }
    }
  };
  const handleSaveConfig = async () => {
    setActionError('');
    setActionSuccess('');
    try {
      await api.updateSniperConfig({
        strategy_mode: strategyMode,
        apply_preset: false,
        relay_mode: relayMode,
        jito_bribe_sol: jitoTip,
        slippage_pct: slippage,
        max_slippage_pct: slippage,
        min_bonding_curve_pct: minBondingPct,
        max_dev_holding_pct: maxDevHoldPct,
        only_new_creations: onlyNewCreations,
        max_token_age_minutes: maxTokenAgeMinutes,
        max_market_cap_usd: maxMarketCapUsd,
        auto_tp_pct: autoTpPct,
        auto_sl_pct: autoSlPct,
        trailing_stop_enabled: trailingStop,
        trailing_stop_pct: trailingPct,
        multi_wallet_rotation: multiWalletRot,
        buy_amount_idr: snipeAmountIdr,
        snipe_amount_idr: snipeAmountIdr,
        buy_amount_usd: Number((snipeAmountIdr / usdIdr).toFixed(2)),
        max_open_positions: maxOpenPositions,
      });
      setActionSuccess(
        `✅ Konfigurasi [${strategyMode}] tersimpan! $${(snipeAmountIdr / usdIdr).toFixed(2)}/trade • Maks ${maxOpenPositions} posisi • Slip ${slippage}%`
      );
      configQuery.refetch();
    } catch (err: any) {
      setActionError(err?.message || 'Gagal menyimpan konfigurasi');
    }
  };

  const handleTerminalSnipe = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!terminalSymbol.trim() && !terminalContract.trim()) return;
    setActionError('');
    setActionSuccess('');
    setIsSniping(true);
    try {
      const res = await api.snipeToken({
        symbol: terminalSymbol.trim() || terminalContract.trim(),
        contract: terminalContract.trim() || undefined,
        amount_idr: terminalAmountIdr,
        slippage_pct: slippage,
        priority_fee_sol: jitoTip,
        anti_mev: relayMode !== 'MAINNET_STD',
        force_unsafe: strategyMode === 'AGGRESSIVE',
        block_legacy_tokens: strategyMode === 'AGGRESSIVE',
        mode: selectedMode,
      });
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sofia-bot-trade-executed', { detail: res }));
      }
      setActionSuccess(
        `⚡ [${res.mode}] 1-Click Snipe sukses! Beli ${Number(res.quantity || 0).toLocaleString()} ${res.symbol} (${
          res.launchpad || 'DEX'
        } • Umur ${res.age || 'baru'}) @ ${formatUsd(res.entry_price)} (${formatIdr(res.entry_price_idr)}) senilai ${formatIdr(
          res.amount_idr
        )}${res.tx_hash ? ` • Tx: ${String(res.tx_hash).slice(0, 16)}...` : ''}`
      );
      portfolioQuery.refetch();
      walletsQuery.refetch();
    } catch (err: any) {
      setActionError(err?.message || 'Gagal mengeksekusi 1-Click Snipe');
    } finally {
      setIsSniping(false);
    }
  };

  const handleQuickSell = async (symbol: string, pct: number) => {
    setActionError('');
    setActionSuccess('');
    setQuickExitNotice(null);
    const key = `${symbol}-${pct}`;
    setSellingKey(key);
    try {
      const res = await api.sellHolding(symbol, pct, selectedMode);
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sofia-bot-trade-executed', { detail: res }));
      }
      const msg =
        res.status === 'cleared'
          ? `✅ Posisi ${symbol} telah dibersihkan (saldo on-chain 0).`
          : `✅ [${res.mode || selectedMode}] Quick Exit ${pct}% ${res.symbol} berhasil @ ${formatUsd(
              res.sell_price_usd
            )} • Realized PnL: ${res.realized_pnl_idr >= 0 ? '+' : ''}${formatIdr(res.realized_pnl_idr)}${
              res.tx_hash ? ` • Tx: ${String(res.tx_hash).slice(0, 14)}...` : ''
            }`;
      setActionSuccess(msg);
      setQuickExitNotice({ type: 'ok', text: msg });
      await portfolioQuery.refetch();
      await walletsQuery.refetch();
    } catch (err: any) {
      const errMsg = err?.message || 'Gagal menjual posisi';
      setActionError(errMsg);
      setQuickExitNotice({ type: 'err', text: `⚠️ Quick Exit gagal: ${errMsg}` });
    } finally {
      setSellingKey(null);
    }
  };

  const handlePanicSellAll = async () => {
    setActionError('');
    setActionSuccess('');
    setQuickExitNotice(null);
    setSellingKey('PANIC_ALL');
    try {
      const res = await api.panicSellAll(selectedMode);
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sofia-bot-trade-executed', { detail: res }));
      }
      const msg = `🚨 [${res.mode || selectedMode}] PANIC SELL ALL selesai! ${res.positions_closed} posisi ditutup • Total Realized PnL: ${
        res.total_realized_pnl_idr >= 0 ? '+' : ''
      }${formatIdr(res.total_realized_pnl_idr)} (${formatUsd(res.total_realized_pnl_usd)})`;
      setActionSuccess(msg);
      setQuickExitNotice({ type: 'ok', text: msg });
      await portfolioQuery.refetch();
      await walletsQuery.refetch();
    } catch (err: any) {
      const errMsg = err?.message || 'Gagal mengeksekusi Panic Sell All';
      setActionError(errMsg);
      setQuickExitNotice({ type: 'err', text: `⚠️ Panic Sell gagal: ${errMsg}` });
    } finally {
      setSellingKey(null);
    }
  };

  const holdings: any[] = portfolioQuery.data?.holdings || [];

  return (
    <div className="space-y-3">
      {/* Top Banner */}
      <div className="px-3.5 py-2.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-sm font-extrabold text-slate-100 uppercase tracking-wide font-mono flex items-center gap-2">
            <span>🎯 PumpSniper Pro Terminal &amp; Auto-Sniper Engine</span>
            <span className="px-2 py-0.5 text-[10px] rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
              {relayMode}
            </span>
          </h1>
          <p className="text-xs text-slate-400">
            Mendukung 100% <strong>Mode PAPER (Simulasi Rp 150.000)</strong> &amp;{' '}
            <strong>Mode LIVE (On-Chain Hot Wallet + Jurnal Neonbase)</strong> dengan Jito 0-Slot Anti-MEV.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[11px] font-mono">
          <span className="px-2.5 py-1 rounded-lg bg-obsidian-950 border border-obsidian-800 text-slate-300">
            Auto TP: <strong className="text-emerald-400">+{autoTpPct}%</strong> • SL:{' '}
            <strong className="text-rose-400">-{autoSlPct}%</strong>
          </span>
        </div>
      </div>

      {actionSuccess && (
        <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 text-xs font-mono">
          {actionSuccess}
        </div>
      )}
      {actionError && (
        <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-200 text-xs font-mono">
          ⚠️ {actionError}
        </div>
      )}

      <QueryState isLoading={botQuery.isLoading} isError={botQuery.isError} error={botQuery.error}>
        {(() => {
          const terminalControlsBlock = (
            <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-700/80 space-y-4 shadow-lg">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-obsidian-800 pb-4">
            {/* Left: Current Engine Status */}
            <div className="space-y-1">
              <div className="text-[10px] font-mono uppercase text-slate-400">Status Mesin Sniper</div>
              <div className="flex items-center gap-2.5">
                <span
                  className={`w-3 h-3 rounded-full ${
                    isRunning ? 'bg-emerald-400 animate-ping' : 'bg-slate-600'
                  }`}
                />
                <span className="text-xl font-extrabold uppercase text-slate-100 font-mono">
                  {botQuery.data?.status || 'idle'}
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                    selectedMode === 'PAPER'
                      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                      : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                  }`}
                >
                  MODE {selectedMode}
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-extrabold border ${
                    strategyMode === 'AGGRESSIVE'
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                      : strategyMode === 'SAFE'
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                      : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                  }`}
                >
                  STRATEGI: {strategyMode}
                </span>
              </div>
              <div className="text-xs font-mono text-slate-400 pt-0.5">
                {selectedMode === 'PAPER' ? (
                  <span>
                    🟢 <strong>Mode PAPER:</strong> Harga market 100% asli (DexScreener Live) • Sisa Kas Simulasi:{' '}
                    <strong className="text-emerald-400">
                      {formatUsd(portfolioQuery.data?.paper_cash_usd)} (≈ {formatIdr(portfolioQuery.data?.paper_cash_idr)})
                    </strong>
                  </span>
                ) : (
                  <span className="text-cyan-300">
                    🔴 <strong>Mode LIVE ON-CHAIN:</strong> Transaksi memotong/menambah Hot Wallet &amp; masuk Jurnal Neonbase • Saldo Siap DEX:{' '}
                    <strong className="text-emerald-400">
                      {formatUsd(liveCashUsd)} (≈ {formatIdr(liveCashIdr)})
                    </strong>
                  </span>
                )}
              </div>
            </div>

            {/* Right: Sliding Mode Switch + Single Power Button */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2.5 bg-obsidian-950 border border-obsidian-700 px-3 py-2 rounded-lg font-mono text-xs">
                <span
                  className={`font-bold ${
                    selectedMode === 'PAPER' ? 'text-emerald-400' : 'text-slate-500'
                  }`}
                >
                  PAPER ({formatIdr(paperInitialIdr)})
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={selectedMode === 'LIVE'}
                  onClick={handleToggleSwitch}
                  className={`relative inline-flex h-6 w-12 items-center rounded-full transition-colors ${
                    selectedMode === 'LIVE' ? 'bg-rose-600' : 'bg-emerald-500'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-obsidian-950 transition-transform ${
                      selectedMode === 'LIVE' ? 'translate-x-7' : 'translate-x-1'
                    }`}
                  />
                </button>
                <span
                  className={`font-bold ${
                    selectedMode === 'LIVE' ? 'text-rose-400' : 'text-slate-500'
                  }`}
                >
                  LIVE (Uang Asli)
                </span>
              </div>

              <button
                type="button"
                onClick={handlePowerButton}
                className={`px-4 py-2 rounded-lg font-mono font-extrabold text-xs transition ${
                  isRunning
                    ? 'bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 shadow-glow-rose'
                    : 'bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 shadow-glow-emerald'
                }`}
              >
                {isRunning
                  ? '⏹ HENTIKAN BOT SEKARANG'
                  : `▶️ JALANKAN BOT (${selectedMode} • ${strategyMode})`}
              </button>
            </div>
          </div>

          {/* TOP CARD DIRECT PARAMETERS: Modal per Trade, Batas Posisi, Slippage, Modal Paper */}
          <div className="p-3.5 rounded-xl bg-obsidian-950 border border-obsidian-800 space-y-3 font-mono text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-obsidian-800/80 pb-2.5">
              <span className="text-[11px] font-extrabold uppercase tracking-wide text-slate-200 flex items-center gap-1.5">
                <LucideIcon name="sliders" className="w-3.5 h-3.5 text-cyan-400" />
                Pengaturan Langsung: Modal per Trade, Batas Posisi &amp; Slippage
              </span>
              {!isLive ? (
                <button
                  type="button"
                  onClick={() => setShowResetPaperModal(true)}
                  className="px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/40 text-[11px] font-bold transition flex items-center gap-1"
                >
                  <span>⚙️ Atur Modal Paper:</span>
                  <span className="text-white underline">{formatIdr(paperInitialIdr)}</span>
                </button>
              ) : (
                <div className="flex items-center gap-2 text-[10px]">
                  <span className="text-slate-400">Kas Siap:</span>
                  <span className="text-cyan-300 font-bold">{liveUsdcBal.toFixed(4)} USDC</span>
                  <span className="text-slate-500">•</span>
                  <span className="text-amber-300 font-bold">{Number(liveGasBal).toFixed(4)} SOL Gas</span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Parameter 1: Dolar per Trade */}
              <div className="space-y-1 p-2.5 rounded-lg bg-obsidian-900 border border-obsidian-800">
                <label className="text-slate-300 text-[10px] uppercase font-bold flex items-center justify-between">
                  <span>1. Dolar per Trade ($ USD)</span>
                  <span className="text-emerald-400 font-bold">≈ {formatIdr(snipeAmountIdr)}</span>
                </label>
                <div className="relative">
                  <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 font-bold">$</span>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    value={Number((snipeAmountIdr / usdIdr).toFixed(2))}
                    onChange={(e) => {
                      const usd = parseFloat(e.target.value) || 0;
                      setSnipeAmountIdr(Math.round(usd * usdIdr));
                    }}
                    className="w-full pl-6 pr-2 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-emerald-300 font-extrabold text-xs"
                    placeholder="1.00"
                  />
                </div>
                <span className="text-[9px] text-slate-500 block">Nominal beli setiap order bot</span>
              </div>

              {/* Parameter 2: Maksimal Posisi Terbuka */}
              <div className="space-y-1 p-2.5 rounded-lg bg-obsidian-900 border border-obsidian-800">
                <label className="text-slate-300 text-[10px] uppercase font-bold flex items-center justify-between">
                  <span>2. Maks Posisi Terbuka</span>
                  <span className="text-cyan-400 font-bold">{maxOpenPositions} Koin</span>
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="1"
                    min="1"
                    max="20"
                    value={maxOpenPositions}
                    onChange={(e) => setMaxOpenPositions(parseInt(e.target.value, 10) || 1)}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-cyan-300 font-extrabold text-xs"
                  />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-500">Slot</span>
                </div>
                <span className="text-[9px] text-slate-500 block">Batas koin di-hold bersamaan</span>
              </div>

              {/* Parameter 3: Toleransi Slippage */}
              <div className="space-y-1 p-2.5 rounded-lg bg-obsidian-900 border border-obsidian-800">
                <label className="text-slate-300 text-[10px] uppercase font-bold flex items-center justify-between">
                  <span>3. Toleransi Slippage (%)</span>
                  <span className="text-amber-400 font-bold">{slippage}%</span>
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="25"
                    value={slippage}
                    onChange={(e) => setSlippage(parseFloat(e.target.value) || 0)}
                    className="w-full px-2.5 pr-6 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-amber-300 font-extrabold text-xs"
                  />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 font-bold">%</span>
                </div>
                <span className="text-[9px] text-slate-500 block">Batas pergeseran harga swap</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-1 text-[10px] text-slate-500">
              <span>* Parameter di atas otomatis diterapkan saat bot memindai &amp; mengeksekusi DEX.</span>
              <button
                type="button"
                onClick={handleSaveConfig}
                className="px-3 py-1 rounded bg-cyan-500/20 hover:bg-cyan-500 text-cyan-300 hover:text-obsidian-950 border border-cyan-500/40 font-extrabold text-[11px] transition"
              >
                💾 Simpan Parameter
              </button>
            </div>
          </div>

          {/* 3 BOT TRADING STRATEGY MODES: SAFE, DEFAULT, AGGRESSIVE */}
          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-[11px] font-mono font-extrabold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <LucideIcon name="zap" className="w-3.5 h-3.5 text-amber-400" />
                Pilih Mode Strategi Bot Trading (Safe, Default, Agresif)
              </span>
              {isRunning ? (
                <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  🔒 Mode Terkunci saat Bot Berjalan (Hentikan Bot untuk mengubah mode)
                </span>
              ) : (
                <span className="text-[10px] font-mono text-slate-400">
                  Klik mode di bawah untuk otomatis menyesuaikan target koin &amp; kecepatan trading
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono">
              {BOT_STRATEGY_MODES.map((m) => {
                const isSelected = strategyMode === m.id;
                const isLockedOther = isRunning && !isSelected;
                const srvStat =
                  configQuery.data?.strategy_stats?.[m.id] ||
                  botQuery.data?.strategy_stats?.[m.id];
                const tradesCount = Number(srvStat?.trades_count ?? 0);
                const winsCount = Number(srvStat?.wins ?? 0);
                const hasTrades = tradesCount > 0 && srvStat?.winrate_pct !== null && srvStat?.winrate_pct !== undefined;
                const displayWinrate = hasTrades ? `${srvStat.winrate_pct}%` : '—';

                return (
                  <button
                    key={m.id}
                    type="button"
                    disabled={isLockedOther}
                    onClick={() => handleSelectStrategyMode(m.id as 'SAFE' | 'DEFAULT' | 'AGGRESSIVE')}
                    className={`text-left p-3.5 rounded-xl border transition flex flex-col justify-between ${
                      isSelected
                        ? m.activeClass
                        : isLockedOther
                        ? 'bg-obsidian-950/50 border-obsidian-800/50 text-slate-500 opacity-50 cursor-not-allowed'
                        : 'bg-obsidian-950 border-obsidian-800 hover:border-obsidian-700 text-slate-300'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold border ${m.badgeClass}`}>
                          {m.badge}
                        </span>
                        {isSelected ? (
                          <span className="text-[10px] font-extrabold uppercase text-white bg-slate-900/80 px-2 py-0.5 rounded">
                            {isRunning ? '🔒 AKTIF & TERKUNCI' : '✓ AKTIF'}
                          </span>
                        ) : isLockedOther ? (
                          <span className="text-[9px] font-mono text-slate-500">🔒 Terkunci</span>
                        ) : null}
                      </div>
                      <div className="flex items-baseline justify-between gap-2 mt-1">
                        <div className="text-sm font-extrabold text-white">{m.title}</div>
                        <span className={`px-2 py-0.5 rounded-md text-[11px] font-extrabold border ${m.winrateBadgeClass}`}>
                          🎯 Winrate: {displayWinrate}
                        </span>
                      </div>
                      <div className="text-[11px] font-bold text-cyan-300 mt-0.5">{m.subtitle}</div>
                      <p className="text-[11px] text-slate-300 mt-1.5 leading-relaxed font-sans">{m.desc}</p>

                      {/* Winrate Progress Bar & Metrics - Strictly Real Data */}
                      {hasTrades ? (
                        <div className="mt-2.5 p-2 rounded-lg bg-obsidian-900/80 border border-obsidian-800/90 space-y-1.5">
                          <div className="flex items-center justify-between text-[10px]">
                            <span className="text-slate-400 font-semibold">
                              Winrate Real (Riwayat Trade)
                            </span>
                            <span className="font-extrabold text-white">
                              {displayWinrate} • {winsCount}W / {tradesCount - winsCount}L
                            </span>
                          </div>
                          <div className="w-full h-1.5 rounded-full bg-obsidian-950 overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-300 ${m.winrateBarClass}`}
                              style={{ width: `${Math.min(100, Math.max(0, Number(srvStat?.winrate_pct ?? 0)))}%` }}
                            />
                          </div>
                          <div className="text-[9px] text-slate-400 flex items-center justify-between pt-0.5">
                            <span>Rekor Mode {m.id}:</span>
                            <span className="text-emerald-300 font-bold">
                              {tradesCount} Trade Selesai
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="mt-2.5 p-2 rounded-lg bg-obsidian-900/80 border border-obsidian-800/90 space-y-1">
                          <div className="flex items-center justify-between text-[10px]">
                            <span className="text-slate-400 font-semibold">Winrate Mode:</span>
                            <span className="text-slate-400 font-medium">Belum ada trade</span>
                          </div>
                          <p className="text-[9px] text-slate-500 font-sans">
                            Winrate dihitung otomatis 100% real saat posisi closed trade tercatat.
                          </p>
                        </div>
                      )}
                    </div>
                    <div className="mt-2.5 pt-2 border-t border-slate-800/80 text-[10px] font-bold text-slate-200">
                      {m.stats}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Live Radar Koin Meme Baru (DexScreener Token Profiles v1 + GMGN.ai Trench) */}
          <div className="p-3 rounded-xl bg-obsidian-950 border border-amber-500/30 space-y-2.5 font-mono text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-extrabold text-[10px]">
                  🔥 DEXSCREENER + GMGN.AI NEW CREATIONS RADAR
                </span>
                <span className="text-[11px] text-slate-300">
                  Koin meme baru muncul (&lt; 3 jam) • Bebas koin lama (BONK/PEPE/WIF diblokir di Mode Agresif)
                </span>
              </div>
              <button
                type="button"
                onClick={() => pulseQuery.refetch()}
                className="px-2.5 py-1 rounded bg-obsidian-900 hover:bg-obsidian-800 border border-obsidian-700 text-cyan-300 text-[10px] font-bold"
              >
                🔄 Refresh DexScreener + GMGN
              </button>
            </div>

            {newCreationsList.length === 0 ? (
              <div className="text-[11px] text-slate-400 py-1">
                Memuat daftar meme coin yang baru rilis dari DexScreener Token Profiles v1 &amp; GMGN.ai...
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                {newCreationsList.slice(0, 4).map((tok: any) => {
                  const isPicked =
                    terminalSymbol === tok.base_symbol ||
                    terminalSymbol === tok.symbol ||
                    (tok.contract && terminalContract === tok.contract);
                  return (
                    <div
                      key={tok.contract || tok.symbol}
                      className={`p-2.5 rounded-lg border transition flex flex-col justify-between gap-1.5 ${
                        isPicked
                          ? 'bg-amber-500/15 border-amber-500/60'
                          : 'bg-obsidian-900/90 border-obsidian-800 hover:border-obsidian-700'
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-1">
                          <span className="font-extrabold text-white text-xs truncate">{tok.symbol}</span>
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[9px] font-bold shrink-0">
                            Umur {tok.age}
                          </span>
                        </div>
                        <div className="text-[10px] text-slate-400 flex items-center justify-between mt-0.5">
                          <span>{tok.launchpad}</span>
                          <span className="text-amber-300 font-bold">
                            MCap ${(Number(tok.market_cap || 0) / 1000).toFixed(1)}K
                          </span>
                        </div>
                        {tok.contract && (
                          <div className="text-[9px] text-slate-500 truncate mt-0.5" title={tok.contract}>
                            CA: {tok.contract.slice(0, 6)}...{tok.contract.slice(-4)}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center justify-between gap-1 pt-1.5 border-t border-obsidian-800/80 text-[9px]">
                        <div className="flex items-center gap-1.5">
                          {tok.gmgn_url && (
                            <a
                              href={tok.gmgn_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-emerald-400 hover:underline font-bold"
                            >
                              GMGN.ai ↗
                            </a>
                          )}
                          {tok.dex_url && (
                            <a
                              href={tok.dex_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-cyan-400 hover:underline"
                            >
                              DexScreener ↗
                            </a>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setTerminalSymbol(tok.base_symbol || tok.symbol);
                            setTerminalContract(tok.contract || '');
                          }}
                          className="px-2 py-0.5 rounded bg-amber-500 hover:bg-amber-400 text-obsidian-950 font-extrabold"
                        >
                          Pilih Target
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 1-Click Terminal Snipe Bar (Inspired by PumpSniper Terminal) */}
          <form
            onSubmit={handleTerminalSnipe}
            className="p-3 rounded-xl bg-obsidian-950 border border-emerald-500/30 flex flex-wrap items-center justify-between gap-3 font-mono text-xs"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 font-extrabold text-[10px]">
                ⚡ 1-CLICK TERMINAL SNIPE
              </span>
              <input
                type="text"
                value={terminalSymbol}
                onChange={(e) => {
                  setTerminalSymbol(e.target.value);
                  setTerminalContract('');
                }}
                placeholder="Paste Mint CA / Simbol Koin Baru DexScreener & GMGN..."
                className="w-56 sm:w-64 px-3 py-1.5 rounded-lg bg-obsidian-900 border border-obsidian-700 text-white font-bold focus:outline-none focus:border-emerald-500"
              />
              {terminalContract && (
                <span className="text-[10px] text-amber-300 bg-amber-500/10 border border-amber-500/30 px-2 py-1 rounded">
                  CA: {terminalContract.slice(0, 6)}...{terminalContract.slice(-4)}
                </span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] text-slate-400">Nominal:</span>
              {QUICK_SNIPE_PRESETS.map((amt) => (
                <button
                  key={amt}
                  type="button"
                  onClick={() => setTerminalAmountIdr(amt)}
                  className={`px-2 py-1 rounded text-[10px] font-bold transition ${
                    terminalAmountIdr === amt
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                      : 'bg-obsidian-900 text-slate-400 border border-obsidian-800 hover:text-white'
                  }`}
                >
                  {formatIdr(amt)}
                </button>
              ))}
              <input
                type="number"
                step="5000"
                value={terminalAmountIdr}
                onChange={(e) => setTerminalAmountIdr(Number(e.target.value))}
                className="w-28 px-2.5 py-1 rounded-lg bg-obsidian-900 border border-obsidian-700 text-emerald-400 font-bold"
              />
            </div>

            <button
              type="submit"
              disabled={isSniping}
              className={`px-4 py-1.5 rounded-lg font-extrabold text-xs transition ${
                isLive
                  ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-glow-rose'
                  : 'bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 shadow-glow-emerald'
              }`}
            >
              {isSniping ? '⏳ Mengeksekusi...' : `⚡ SNIPE SEKARANG [${selectedMode}]`}
            </button>
          </form>

          {/* PumpSniper Pro Parameters Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3 font-mono text-xs">
            {/* Relay Selector */}
            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
              <label className="text-slate-400 block uppercase text-[10px]">
                0-Slot / Anti-MEV Relay Node
              </label>
              <select
                value={relayMode}
                onChange={(e) => setRelayMode(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-cyan-300 font-bold"
              >
                {RELAY_OPTIONS.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
              <span className="text-[10px] text-slate-500 block">
                {RELAY_OPTIONS.find((r) => r.id === relayMode)?.desc}
              </span>
            </div>

            {/* Filter Koin Baru (DexScreener + GMGN.ai) */}
            <div className="p-3 rounded-lg bg-obsidian-950 border border-amber-500/30 space-y-1.5">
              <label className="text-amber-300 block uppercase text-[10px] font-bold">
                Filter Koin Baru (DexScreener / GMGN)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <input
                    type="number"
                    step="15"
                    value={maxTokenAgeMinutes}
                    onChange={(e) => setMaxTokenAgeMinutes(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-amber-300 font-bold"
                  />
                  <span className="text-[9px] text-slate-400">Max Umur (Menit)</span>
                </div>
                <div>
                  <input
                    type="number"
                    step="50000"
                    value={maxMarketCapUsd}
                    onChange={(e) => setMaxMarketCapUsd(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-cyan-300 font-bold"
                  />
                  <span className="text-[9px] text-slate-400">Max MCap ($)</span>
                </div>
              </div>
            </div>

            {/* Jito Tip & Slippage */}
            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
              <label className="text-slate-400 block uppercase text-[10px]">
                Jito Bribe (SOL) &amp; Max Slippage (%)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <input
                    type="number"
                    step="0.001"
                    value={jitoTip}
                    onChange={(e) => setJitoTip(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-cyan-400 font-bold"
                  />
                  <span className="text-[9px] text-slate-500">Bribe (SOL)</span>
                </div>
                <div>
                  <input
                    type="number"
                    step="0.5"
                    value={slippage}
                    onChange={(e) => setSlippage(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-emerald-400 font-bold"
                  />
                  <span className="text-[9px] text-slate-500">Slippage (%)</span>
                </div>
              </div>
            </div>

            {/* Bonding Curve & Dev Holding Filter */}
            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
              <label className="text-slate-400 block uppercase text-[10px]">
                Filter Bonding Curve &amp; Max Dev Hold
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <input
                    type="number"
                    step="5"
                    value={minBondingPct}
                    onChange={(e) => setMinBondingPct(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-amber-300 font-bold"
                  />
                  <span className="text-[9px] text-slate-500">Min Curve (%)</span>
                </div>
                <div>
                  <input
                    type="number"
                    step="1"
                    value={maxDevHoldPct}
                    onChange={(e) => setMaxDevHoldPct(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-emerald-300 font-bold"
                  />
                  <span className="text-[9px] text-slate-500">Max Dev (%)</span>
                </div>
              </div>
            </div>

            {/* Auto Take Profit & Stop Loss */}
            <div className="p-3 rounded-lg bg-obsidian-950 border border-obsidian-800 space-y-1.5">
              <label className="text-slate-400 block uppercase text-[10px]">
                Auto Take-Profit (+%) &amp; Stop-Loss (-%)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <input
                    type="number"
                    step="5"
                    value={autoTpPct}
                    onChange={(e) => setAutoTpPct(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-emerald-400 font-bold"
                  />
                  <span className="text-[9px] text-emerald-400/80">Take Profit +%</span>
                </div>
                <div>
                  <input
                    type="number"
                    step="1"
                    value={autoSlPct}
                    onChange={(e) => setAutoSlPct(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 rounded bg-obsidian-900 border border-obsidian-700 text-rose-400 font-bold"
                  />
                  <span className="text-[9px] text-rose-400/80">Stop Loss -%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Row: Trailing Stop, Multi-Wallet Rotation, Only New Creations, and Save Config Button */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-obsidian-800 font-mono text-xs">
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer text-amber-300">
                <input
                  type="checkbox"
                  checked={onlyNewCreations}
                  onChange={(e) => setOnlyNewCreations(e.target.checked)}
                  className="rounded border-obsidian-700 bg-obsidian-950 text-amber-500"
                />
                <span>🔥 Wajib Koin Baru (Blokir BONK/PEPE/WIF)</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                <input
                  type="checkbox"
                  checked={trailingStop}
                  onChange={(e) => setTrailingStop(e.target.checked)}
                  className="rounded border-obsidian-700 bg-obsidian-950 text-emerald-500"
                />
                <span>📈 Trailing Stop-Loss ({trailingPct}%)</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                <input
                  type="checkbox"
                  checked={multiWalletRot}
                  onChange={(e) => setMultiWalletRot(e.target.checked)}
                  className="rounded border-obsidian-700 bg-obsidian-950 text-cyan-500"
                />
                <span>🔄 Multi-Wallet Anti-Bubble Rotation</span>
              </label>
            </div>

            <button
              type="button"
              onClick={handleSaveConfig}
              className="px-4 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500 text-cyan-300 hover:text-obsidian-950 border border-cyan-500/40 font-extrabold text-xs transition shadow-sm"
            >
              💾 Simpan Konfigurasi Terminal
            </button>
          </div>
        </div>
        );

        const positionsBlock = (
          <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-700/80 space-y-3 shadow-lg">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-obsidian-800 pb-2.5">
            <div className="flex items-center gap-2">
              <LucideIcon name="activity" className="w-4 h-4 text-emerald-400" />
              <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-100 font-mono">
                Posisi Aktif di Terminal ({holdings.length} Koin)
              </h2>
            </div>
            <div className="flex items-center gap-2">
              {holdings.length > 0 && (
                <button
                  type="button"
                  disabled={!!sellingKey}
                  onClick={handlePanicSellAll}
                  className="px-3 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 disabled:opacity-60 text-white font-mono font-extrabold text-[11px] shadow-glow-rose transition"
                >
                  {sellingKey === 'PANIC_ALL' ? '⏳ MELIKUIDASI SEMUA...' : '🚨 PANIC SELL ALL (100% LIKUIDASI)'}
                </button>
              )}
            </div>
          </div>

          {quickExitNotice && (
            <div
              className={`px-3.5 py-2 rounded-lg text-xs font-mono flex items-center justify-between border ${
                quickExitNotice.type === 'ok'
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  : 'bg-rose-500/15 text-rose-300 border-rose-500/30'
              }`}
            >
              <span>{quickExitNotice.text}</span>
              <button
                type="button"
                onClick={() => setQuickExitNotice(null)}
                className="ml-2 text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
          )}

          {holdings.length === 0 ? (
            <div className="py-4 text-center text-xs font-mono text-slate-400">
              Belum ada posisi terbuka. Gunakan <strong>⚡ 1-Click Terminal Snipe</strong> di atas atau nyalakan <strong>Auto-Sniper Bot</strong> untuk mulai membeli koin potensial secara otomatis.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-obsidian-950 text-slate-400 border-b border-obsidian-800 text-[10px] uppercase">
                  <tr>
                    <th className="p-2.5">Token</th>
                    <th className="p-2.5">Qty</th>
                    <th className="p-2.5">Entry</th>
                    <th className="p-2.5">Harga Live</th>
                    <th className="p-2.5">Nilai Posisi</th>
                    <th className="p-2.5">Floating PnL</th>
                    <th className="p-2.5 text-right">Quick Exit ({selectedMode})</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-obsidian-800/60">
                  {holdings.map((h: any) => (
                    <tr key={h.symbol} className="hover:bg-obsidian-850/60">
                      <td className="p-2.5 font-extrabold text-white">${h.symbol}</td>
                      <td className="p-2.5 text-slate-300">{Number(h.quantity).toLocaleString()}</td>
                      <td className="p-2.5 text-slate-300">{formatUsd(h.avg_entry_price)}</td>
                      <td className="p-2.5 text-cyan-300 font-bold">{formatUsd(h.current_price)}</td>
                      <td className="p-2.5">
                        <div className="font-bold text-white">{formatUsd(h.value)}</div>
                        <div className="text-[10px] text-slate-400">≈ {formatIdr(h.value * usdIdr)}</div>
                      </td>
                      <td className="p-2.5">
                        <span className={`font-bold ${h.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {h.pnl >= 0 ? '+' : ''}
                          {formatUsd(h.pnl)} ({h.pnl_pct}%)
                        </span>
                      </td>
                      <td className="p-2.5 text-right">
                        <div className="inline-flex gap-1">
                          {[25, 50, 100].map((pct) => {
                            const isThisSelling = sellingKey === `${h.symbol}-${pct}`;
                            return (
                              <button
                                key={pct}
                                type="button"
                                disabled={!!sellingKey}
                                onClick={() => handleQuickSell(h.symbol, pct)}
                                className={`px-2 py-1 rounded font-bold text-[10px] transition disabled:opacity-60 ${
                                  pct === 100
                                    ? 'bg-rose-600 hover:bg-rose-500 text-white'
                                    : 'bg-obsidian-800 hover:bg-obsidian-700 text-rose-300 border border-rose-500/30'
                                }`}
                              >
                                {isThisSelling ? '⏳ Proses...' : `Jual ${pct}%`}
                              </button>
                            );
                          })}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          </div>
        );

        const botLogsBlock = (
          <BotActivityCard botStatus={botQuery.data?.status} />
        );

        const kpiCardsBlock = (
          <section
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3"
            data-purpose="auto-sniper-kpi-grid"
          >
            {/* CARD 1: TOTAL EKUITAS */}
            <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 transition hover:border-obsidian-600 shadow-md">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-slate-400 font-medium">Total Ekuitas</span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold border ${
                    isLive
                      ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                      : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  }`}
                >
                  {isLive ? 'LIVE ON-CHAIN' : 'PAPER SIMULASI'}
                </span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-extrabold font-mono tracking-tight text-white">
                  {formatUsd(activeEquityUsd)}
                </span>
                <span className="text-xs text-slate-400 font-mono">≈ {formatIdr(activeEquityIdr)}</span>
              </div>
              <div className="mt-2.5 text-[11px] text-slate-400 flex items-center justify-between border-t border-obsidian-800/80 pt-1.5">
                <span>{isLive ? `${liveWallets.length} Dompet On-Chain` : `Modal Awal ${formatIdr(paperInitialIdr)}`}</span>
                {isLive ? (
                  <span className="font-mono text-cyan-400 text-[10px]">
                    Solana Mainnet
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowResetPaperModal(true)}
                    className="font-mono text-cyan-400 hover:text-cyan-300 hover:underline text-[10px] font-bold"
                  >
                    ⚙️ Atur Modal
                  </button>
                )}
              </div>
            </div>
            {/* CARD 2: SALDO KAS TERSEDIA */}
            <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 transition hover:border-obsidian-600 shadow-md">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-slate-400 font-medium">Saldo Kas Tersedia</span>
                <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-bold border ${
                  isLive ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30' : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                }`}>
                  {isLive ? 'TOTAL WALLET TRADING' : 'SIAP SNIPE'}
                </span>
              </div>
              {isLive ? (
                <div className="space-y-2 mt-1">
                  {/* Total Kas Riil di Wallet Trading */}
                  <div>
                    <div className="text-[10px] font-mono uppercase text-slate-400 flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                        <span className="text-slate-300 font-semibold">Total di Wallet Trading</span>
                      </span>
                      <span className="text-[9px] text-slate-500 font-mono">SOL + USDC</span>
                    </div>
                    <div className="flex items-baseline gap-2 mt-0.5">
                      <span className="text-xl font-extrabold font-mono text-emerald-400">
                        {formatUsd(liveCashUsd)}
                      </span>
                      <span className="text-xs text-slate-300 font-mono font-medium">
                        ≈ {formatIdr(liveCashIdr)}
                      </span>
                    </div>
                  </div>

                  {/* Rincian: Kas Belanja (USDC) & Gas Fee (SOL) */}
                  <div className="border-t border-obsidian-800/80 pt-1.5 grid grid-cols-2 gap-2 text-[10px] font-mono">
                    <div className="bg-obsidian-950/60 p-1.5 rounded border border-obsidian-800/50">
                      <div className="text-slate-400 flex items-center gap-1 mb-0.5">
                        <span className="w-1 h-1 rounded-full bg-cyan-400"></span>
                        <span>Kas USDC</span>
                      </div>
                      <div className="font-bold text-cyan-300 truncate">
                        {liveUsdcBal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDC
                      </div>
                      <div className="text-[9px] text-slate-500 truncate">
                        ≈ {formatIdr(liveUsdcIdr)}
                      </div>
                    </div>
                    <div className="bg-obsidian-950/60 p-1.5 rounded border border-obsidian-800/50">
                      <div className="text-slate-400 flex items-center gap-1 mb-0.5">
                        <span className="w-1 h-1 rounded-full bg-amber-400"></span>
                        <span>Gas ({liveGasToken})</span>
                      </div>
                      <div className="font-bold text-amber-300 truncate">
                        {Number(liveGasBal).toFixed(4)} SOL
                      </div>
                      <div className="text-[9px] text-slate-500 truncate">
                        ≈ {formatIdr(liveGasIdr)}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-extrabold font-mono tracking-tight text-white">
                      {formatUsd(activeCashUsd)}
                    </span>
                    <span className="text-xs text-emerald-400 font-mono">≈ {formatIdr(activeCashIdr)}</span>
                  </div>
                  <div className="mt-2.5 text-[11px] text-slate-400 flex items-center justify-between border-t border-obsidian-800/80 pt-1.5">
                    <span>Kas Virtual Bot</span>
                    <span className="font-mono text-slate-300 text-[10px]">IDR Liquid</span>
                  </div>
                </>
              )}
            </div>

            {/* CARD 3: POSISI TERBUKA */}
            <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 transition hover:border-obsidian-600 shadow-md">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-slate-400 font-medium">Posisi Terbuka</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-obsidian-850 text-cyan-300 border border-obsidian-700 font-bold">
                  {holdingsCount}/5 SLOT
                </span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-extrabold font-mono tracking-tight text-cyan-400">
                  {holdingsCount} <span className="text-xs font-normal text-slate-400">Koin</span>
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  Valuasi: {formatIdr(holdingsValIdr)}
                </span>
              </div>
              <div className="mt-2.5 text-[11px] text-slate-400 flex items-center justify-between border-t border-obsidian-800/80 pt-1.5">
                <span>Auto TP +{autoTpPct}% • SL -{autoSlPct}%</span>
                <span className="font-mono text-slate-300 text-[10px]">
                  {holdingsValUsd > 0 ? formatUsd(holdingsValUsd) : '$0.00'}
                </span>
              </div>
            </div>

            {/* CARD 4: PNL PORTFOLIO */}
            <div className="bg-obsidian-900 border border-obsidian-700/80 rounded-xl p-3.5 transition hover:border-obsidian-600 shadow-md">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-slate-400 font-medium">PnL Posisi</span>
                <span
                  className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-bold border ${
                    pnlIsPositive
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                      : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                  }`}
                >
                  {pnlIsPositive ? 'PROFIT' : 'LOSS'}
                </span>
              </div>
              <div className="flex items-baseline gap-2">
                <span
                  className={`text-2xl font-extrabold font-mono tracking-tight ${
                    pnlIsPositive ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {pnlIsPositive ? '+' : ''}
                  {formatIdr(unrealizedPnlIdr)}
                </span>
                <span
                  className={`text-xs font-mono font-bold ${
                    pnlIsPositive ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  ({pnlIsPositive ? '+' : ''}{unrealizedPnlPct.toFixed(2)}%)
                </span>
              </div>
              <div className="mt-2.5 text-[11px] text-slate-400 flex items-center justify-between border-t border-obsidian-800/80 pt-1.5">
                <span>Net Fee &amp; Gas Jaringan</span>
                <span className="font-mono text-slate-300 text-[10px]">
                  {pnlIsPositive ? '+' : ''}{formatUsd(unrealizedPnlUsd)}
                </span>
              </div>

              {/* All-Time Winrate (closed trades in active mode) */}
              {(() => {
                const wr = Number(portfolioQuery.data?.alltime_winrate_pct ?? 0);
                const wins = Number(portfolioQuery.data?.alltime_wins ?? 0);
                const losses = Number(portfolioQuery.data?.alltime_losses ?? 0);
                const total = Number(portfolioQuery.data?.alltime_trades ?? 0);
                const realizedIdr = Number(portfolioQuery.data?.alltime_realized_pnl_idr ?? 0);
                const wrColor = wr >= 60 ? 'text-emerald-400' : wr >= 45 ? 'text-amber-400' : 'text-rose-400';
                const barColor = wr >= 60 ? 'bg-emerald-400' : wr >= 45 ? 'bg-amber-400' : 'bg-rose-400';
                return (
                  <div className="mt-2 pt-1.5 border-t border-obsidian-800/80 space-y-1">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-400">🎯 Winrate All-Time ({selectedMode})</span>
                      <span className={`font-mono font-extrabold ${wrColor}`}>
                        {total > 0 ? `${wr.toFixed(1)}%` : '—'}
                      </span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-obsidian-950 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${barColor}`}
                        style={{ width: `${total > 0 ? Math.min(100, Math.max(3, wr)) : 0}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                      <span>
                        <span className="text-emerald-400 font-bold">{wins}W</span> /{' '}
                        <span className="text-rose-400 font-bold">{losses}L</span> ({total} trade)
                      </span>
                      <span className={realizedIdr >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                        Realized {realizedIdr >= 0 ? '+' : ''}{formatIdr(realizedIdr)}
                      </span>
                    </div>
                  </div>
                );
              })()}
            </div>
          </section>
        );

        return (
          <div className="space-y-4">
            {kpiCardsBlock}
            {isUltrawide ? (
              <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
                {/* Kolom Kiri: Control Switch, Strategy & Snipe Terminal (7 Col) */}
                <div className="xl:col-span-7 space-y-4">
                  {terminalControlsBlock}
                </div>

                {/* Kolom Kanan: Posisi Aktif & Log Stream dipindahkan ke samping! (5 Col) */}
                <div className="xl:col-span-5 space-y-4">
                  {positionsBlock}
                  {botLogsBlock}
                </div>
              </div>
            ) : (
              <>
                {terminalControlsBlock}
                {positionsBlock}
                {botLogsBlock}
              </>
            )}
          </div>
        );
      })()}
      </QueryState>

      <StartBotModal
        isOpen={showStartBotModal}
        onClose={() => setShowStartBotModal(false)}
        onConfirm={handleConfirmStartBot}
        mode={selectedMode}
        strategyMode={strategyMode}
        initialBuyAmountUsd={Number(((configQuery.data?.buy_amount_usd) || (snipeAmountIdr / usdIdr)).toFixed(2)) || 1.0}
        initialMaxPositions={maxOpenPositions || 3}
        initialSlippagePct={slippage || 1.5}
        usdIdr={usdIdr}
        solPrice={liveGasBal > 0.0001 ? Math.round(liveGasUsd / liveGasBal) : 145}
        liveUsdcBal={liveUsdcBal}
        liveGasBal={liveGasBal}
        liveGasToken={liveGasToken}
      />

      <ResetPaperModal
        isOpen={showResetPaperModal}
        onClose={() => setShowResetPaperModal(false)}
        onConfirm={handleConfirmResetPaper}
        currentInitialUsd={paperInitialUsd}
        usdIdr={usdIdr}
      />
    </div>
  );
}
