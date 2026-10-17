import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  api,
  getToken,
  clearToken,
  formatIdr,
  formatUsd,
  getTradingMode,
  setTradingMode,
} from '@/lib/api';
import {
  ConnectedExtensionWallet,
  getSavedExtensionWallet,
  shortenAddress,
} from '@/lib/web3';
import { LucideIcon } from '@/components/LucideIcon';
import { WalletConnectModal } from '@/components/WalletConnectModal';
import { LoginPortal } from '@/pages/login';

const PRIMARY_NAV = [
  { href: '/', label: 'Command Center', icon: 'layout-dashboard', iconColor: 'text-emerald-400', badge: null, badgeClass: '' },
  {
    href: '/pulse',
    label: 'Trenches & Pulse',
    icon: 'zap',
    iconColor: 'text-amber-400',
    badge: 'LIVE',
    badgeClass: 'bg-amber-500/20 text-amber-300 px-1.5 py-0.5',
  },
  { href: '/trading', label: 'Auto-Sniper Bot', icon: 'crosshair', iconColor: 'text-cyan-400', badge: null, badgeClass: '' },
  {
    href: '/rugcheck',
    label: 'Rug & Bundle Shield',
    icon: 'shield-alert',
    iconColor: 'text-emerald-400',
    badge: '99.8%',
    badgeClass: 'bg-emerald-500/20 text-emerald-300 px-1',
  },
  { href: '/copytrade', label: 'Smart Money Copy', icon: 'copy', iconColor: 'text-purple-400', badge: null, badgeClass: '' },
];

const SECONDARY_NAV = [
  { href: '/portfolio', label: 'Meme Portfolio', icon: 'wallet', iconColor: 'text-blue-400', badge: null, badgeClass: '' },
  {
    href: '/journal',
    label: 'Jurnal Trading Live',
    icon: 'book-open',
    iconColor: 'text-emerald-400',
    badge: 'LIVE',
    badgeClass: 'bg-rose-500/20 text-rose-300 px-1 py-0.2',
  },
  {
    href: '/calendar',
    label: 'Kalender PnL Harian',
    icon: 'calendar',
    iconColor: 'text-amber-400',
    badge: 'PNL',
    badgeClass: 'bg-amber-500/20 text-amber-300 px-1 py-0.2',
  },
  {
    href: '/news',
    label: 'News & Riset Pasar',
    icon: 'newspaper',
    iconColor: 'text-cyan-400',
    badge: 'ID',
    badgeClass: 'bg-cyan-500/20 text-cyan-300 px-1.5 py-0.2',
  },
  { href: '/signals', label: 'Alpha Signals', icon: 'radio', iconColor: 'text-rose-400', badge: null, badgeClass: '' },
  { href: '/agents', label: 'AI Degen Agents', icon: 'bot', iconColor: 'text-emerald-400', badge: null, badgeClass: '' },
  { href: '/risk', label: 'Risk & Slippage', icon: 'sliders', iconColor: 'text-indigo-400', badge: null, badgeClass: '' },
  { href: '/wallets', label: 'Multi-Gate Wallets', icon: 'layers', iconColor: 'text-teal-400', badge: null, badgeClass: '' },
];

const MOBILE_BOTTOM_NAV = [
  { href: '/', label: 'Home', icon: 'layout-dashboard' },
  { href: '/pulse', label: 'Pulse', icon: 'zap' },
  { href: '/trading', label: 'Sniper', icon: 'crosshair' },
  { href: '/news', label: 'News', icon: 'newspaper' },
  { href: '/journal', label: 'Jurnal', icon: 'book-open' },
];

const CHAINS = [
  { id: 'Solana', label: 'Solana', latency: '18ms' },
  { id: 'Base', label: 'Base', latency: null },
  { id: 'Ethereum', label: 'Ethereum', latency: null },
  { id: 'BSC', label: 'BSC', latency: null },
];

const TP_PRESETS = [
  { label: '+Rp 10k', value: 15000 },
  { label: '+Rp 30k', value: 37500 },
  { label: '+Rp 75k', value: 75000 },
  { label: '+Rp 150k', value: 150000 },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState<boolean>(false);
  const [checking, setChecking] = useState<boolean>(true);
  const [selectedChain, setSelectedChain] = useState<string>('Solana');
  const [quickBuyIdr, setQuickBuyIdr] = useState<number>(15000);
  const [usdIdr, setUsdIdr] = useState<number>(17960);
  const [mode, setMode] = useState<'PAPER' | 'LIVE'>('PAPER');
  const [botRunning, setBotRunning] = useState<boolean>(false);
  const [headerNotice, setHeaderNotice] = useState<string>('');
  const [liveBalanceUsd, setLiveBalanceUsd] = useState<number>(0);
  const [liveBalanceIdr, setLiveBalanceIdr] = useState<number>(0);

  // Mobile Menu & Web3 Extension Modal & PWA Install State
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);
  const [walletModalOpen, setWalletModalOpen] = useState<boolean>(false);
  const [connectedWallet, setConnectedWallet] = useState<ConnectedExtensionWallet | null>(null);
  const [deferredPwaPrompt, setDeferredPwaPrompt] = useState<any>(null);

  const fetchLiveBalances = () => {
    api
      .getWallets()
      .then((res) => {
        if (res?.wallets) {
          const liveWallets = res.wallets.filter((w: any) => !w.name?.includes('Modal Paper'));
          const totalUsd = liveWallets.reduce((acc: number, w: any) => acc + (Number(w.balance_usd) || 0), 0);
          const totalIdr = liveWallets.reduce((acc: number, w: any) => acc + (Number(w.balance_idr) || 0), 0);
          setLiveBalanceUsd(totalUsd);
          setLiveBalanceIdr(totalIdr);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    const hasToken = Boolean(getToken());
    setAuthenticated(hasToken);
    if (typeof window !== 'undefined') {
      const savedPreset = localStorage.getItem('sofia_quickbuy_idr');
      if (savedPreset) setQuickBuyIdr(Number(savedPreset));
      setMode(getTradingMode());
      setConnectedWallet(getSavedExtensionWallet());

      const modeHandler = (e: any) => {
        setMode(e.detail);
        fetchLiveBalances();
      };
      const botHandler = (e: any) => {
        if (typeof e?.detail?.running === 'boolean') {
          setBotRunning(e.detail.running);
        } else {
          api.getBotStatus().then((r) => setBotRunning(r?.status === 'running')).catch(() => {});
        }
        fetchLiveBalances();
      };
      const refreshHandler = () => fetchLiveBalances();
      const walletExtHandler = (e: any) => {
        setConnectedWallet(e.detail || null);
        if (e.detail?.chain) setSelectedChain(e.detail.chain);
        fetchLiveBalances();
      };
      const pwaHandler = (e: any) => {
        e.preventDefault();
        setDeferredPwaPrompt(e);
      };

      window.addEventListener('sofia-mode-change', modeHandler);
      window.addEventListener('sofia-bot-status-change', botHandler);
      window.addEventListener('sofia-bot-trade-executed', refreshHandler);
      window.addEventListener('sofia-paper-reset', refreshHandler);
      window.addEventListener('sofia-wallet-connected', walletExtHandler);
      window.addEventListener('beforeinstallprompt', pwaHandler);
      setChecking(false);
      return () => {
        window.removeEventListener('sofia-mode-change', modeHandler);
        window.removeEventListener('sofia-bot-status-change', botHandler);
        window.removeEventListener('sofia-bot-trade-executed', refreshHandler);
        window.removeEventListener('sofia-paper-reset', refreshHandler);
        window.removeEventListener('sofia-wallet-connected', walletExtHandler);
        window.removeEventListener('beforeinstallprompt', pwaHandler);
      };
    }
    setChecking(false);
  }, []);

  useEffect(() => {
    setMobileMenuOpen(false);
    setAuthenticated(Boolean(getToken()));
  }, [router.pathname]);

  useEffect(() => {
    if (authenticated) {
      api
        .getFx()
        .then((res) => {
          if (res?.usd_idr) setUsdIdr(res.usd_idr);
        })
        .catch(() => {});
      api
        .getBotStatus()
        .then((res) => {
          setBotRunning(res?.status === 'running');
        })
        .catch(() => {});
      fetchLiveBalances();
    }
  }, [authenticated]);

  const handleSelectMode = (nextMode: 'PAPER' | 'LIVE') => {
    setMode(nextMode);
    setTradingMode(nextMode);
  };

  const handlePresetChange = (valIdr: number) => {
    setQuickBuyIdr(valIdr);
    if (typeof window !== 'undefined') {
      localStorage.setItem('sofia_quickbuy_idr', String(valIdr));
      window.dispatchEvent(new CustomEvent('sofia-preset-idr-change', { detail: valIdr }));
    }
  };

  const handleHeaderResetPaper = async () => {
    try {
      const freshOverview = await api.resetPaperAccount();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sofia-paper-reset', { detail: freshOverview }));
      }
      setHeaderNotice('🔄 Paper Reset: Saldo kembali ke Rp 150.000 & semua posisi dihapus.');
      setTimeout(() => setHeaderNotice(''), 3500);
    } catch {
      // handled by page
    }
  };

  const handleHeaderBotToggle = async () => {
    try {
      if (botRunning) {
        await api.stopBot();
        setBotRunning(false);
        setHeaderNotice('🛑 Mesin Sniper Bot berhasil dihentikan.');
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: false } }));
        }
      } else {
        await api.startBot(mode);
        setBotRunning(true);
        setHeaderNotice(`🟢 Mesin Sniper Bot aktif (${mode} Mode).`);
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: true } }));
        }
      }
      setTimeout(() => setHeaderNotice(''), 3500);
    } catch (err: any) {
      if (err?.code === 'BOT_NOT_RUNNING') {
        setBotRunning(false);
        setHeaderNotice('ℹ️ Mesin Sniper Bot sudah dalam kondisi berhenti.');
      } else {
        setHeaderNotice(`⚠️ ${err?.code || 'ERROR'}: ${err?.message || 'Gagal mengubah status bot'}`);
      }
      setTimeout(() => setHeaderNotice(''), 4000);
    }
  };

  const handleInstallPwa = async () => {
    if (deferredPwaPrompt) {
      deferredPwaPrompt.prompt();
      await deferredPwaPrompt.userChoice;
      setDeferredPwaPrompt(null);
    } else {
      setHeaderNotice(
        '📲 Aplikasi PWA Siap! Klik ikon "Install SOFIA PRO" di Address Bar Chrome atau pilih "Add to Home Screen" di HP Anda.'
      );
      setTimeout(() => setHeaderNotice(''), 4500);
    }
  };

  const handleLogout = () => {
    clearToken();
    setAuthenticated(false);
    router.push('/login');
  };

  if (checking) {
    return (
      <div className="min-h-screen bg-obsidian-950 text-slate-300 flex items-center justify-center font-mono text-xs">
        ⚡ Initializing SOFIA TRENCHES v3.8 PRO Command Center...
      </div>
    );
  }

  if (router.pathname === '/login') {
    return <>{children}</>;
  }

  if (!authenticated) {
    return <LoginPortal onSuccess={() => setAuthenticated(true)} />;
  }

  return (
    <div className="bg-obsidian-950 text-slate-200 font-sans antialiased selection:bg-emerald-500/30 selection:text-emerald-300 min-h-screen flex flex-col overflow-x-hidden">
      {/* Web3 Chrome Extension Modal */}
      <WalletConnectModal
        isOpen={walletModalOpen}
        onClose={() => setWalletModalOpen(false)}
        connectedWallet={connectedWallet}
        onConnected={(w) => {
          setConnectedWallet(w);
          setSelectedChain(w.chain);
          setHeaderNotice(
            `🔌 Terhubung ke ${w.providerName}: ${shortenAddress(w.address)} (${w.chain})!`
          );
          setTimeout(() => setHeaderNotice(''), 4000);
        }}
      />

      {/* BEGIN: MainHeader */}
      <header className="border-b border-obsidian-700 bg-obsidian-900/95 backdrop-blur-md sticky top-0 z-50">
        <div className="px-2.5 sm:px-3.5 py-2 flex flex-wrap items-center justify-between gap-2 text-xs">
          {/* Left: Mobile Hamburger + Logo & Network Hub */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Mobile Drawer Toggle Button */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-1.5 rounded-lg bg-obsidian-850 border border-obsidian-700 text-slate-200 hover:text-emerald-400"
              aria-label="Menu Navigasi"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>

            {/* Logo Branding */}
            <Link href="/" className="flex items-center gap-2 pr-2 sm:pr-3 sm:border-r border-obsidian-700">
              <div className="relative flex items-center justify-center w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                <LucideIcon name="crosshair" className="w-4 h-4" />
                <span className="absolute -top-0.5 -right-0.5 flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
              </div>
              <div>
                <div className="font-extrabold tracking-wider text-xs sm:text-sm text-slate-100 flex items-center gap-1 font-mono">
                  SOFIA<span className="text-emerald-400">TRENCHES</span>
                  <span className="text-[9px] uppercase px-1.5 py-0.2 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded font-sans font-semibold">
                    v3.8
                  </span>
                </div>
                <p className="text-[10px] text-slate-400 hidden sm:block">Fast &amp; Low Latency Snipe Engine</p>
              </div>
            </Link>

            {/* Network Selector Pills (Hidden on small mobile, shown in drawer) */}
            <div
              className="hidden sm:flex items-center bg-obsidian-850 p-0.5 rounded-lg border border-obsidian-700"
              data-purpose="network-selector"
            >
              {CHAINS.map((c) => {
                const active = selectedChain === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setSelectedChain(c.id)}
                    className={
                      active
                        ? 'flex items-center gap-1.5 px-2 py-1 rounded-md text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 font-semibold shadow-sm text-[11px] transition'
                        : 'flex items-center gap-1 px-2 py-1 rounded-md text-slate-400 hover:text-slate-200 text-[11px] transition'
                    }
                  >
                    {active && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>}
                    <span>{c.label}</span>
                    {c.latency && <span className="text-[9px] font-mono opacity-70 hidden lg:inline">{c.latency}</span>}
                  </button>
                );
              })}
            </div>

            {/* Exchange Rate USD / IDR Badge */}
            <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded bg-obsidian-850/80 border border-obsidian-700/80 text-[11px] font-mono text-slate-300">
              <LucideIcon name="banknote" className="w-3.5 h-3.5 text-cyan-400" />
              <span>Kurs:</span>
              <span className="text-emerald-400 font-semibold">$1 = {formatIdr(usdIdr)}</span>
            </div>
          </div>

          {/* Right: Controls, Chrome Wallet Connect, Mode Switcher, Bot Power */}
          <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
            {/* Target Profit Presets */}
            <div className="hidden 2xl:flex items-center gap-1 bg-obsidian-850 px-2 py-0.5 rounded-md border border-obsidian-700 font-mono text-[10px]">
              <span className="text-slate-400 uppercase text-[9px] font-sans font-bold pr-1">Target TP:</span>
              {TP_PRESETS.map((p) => {
                const active = quickBuyIdr === p.value;
                return (
                  <button
                    key={p.label}
                    type="button"
                    onClick={() => handlePresetChange(p.value)}
                    className={
                      active
                        ? 'px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 transition border border-emerald-500/30'
                        : 'px-1.5 py-0.5 rounded hover:bg-obsidian-700 text-slate-300 transition'
                    }
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>

            {/* Paper vs Live Mode Toggle */}
            <div
              className="flex items-center bg-obsidian-850 p-0.5 rounded-lg border border-obsidian-700"
              data-purpose="trading-mode-toggle"
            >
              <button
                type="button"
                onClick={() => handleSelectMode('PAPER')}
                className={
                  mode === 'PAPER'
                    ? 'flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-500 text-obsidian-950 font-bold text-[10px] sm:text-[11px] shadow-glow-emerald transition'
                    : 'flex items-center gap-1 px-2 py-1 rounded-md text-slate-400 hover:text-slate-200 text-[10px] sm:text-[11px] font-medium transition'
                }
              >
                <LucideIcon name="shield-check" className="w-3 h-3 hidden sm:inline" />
                <span>PAPER</span>
                <span className="hidden lg:inline">(Rp 150rb)</span>
              </button>
              <button
                type="button"
                onClick={() => handleSelectMode('LIVE')}
                className={
                  mode === 'LIVE'
                    ? 'flex items-center gap-1 px-2 py-1 rounded-md bg-rose-600 text-white font-bold text-[10px] sm:text-[11px] shadow-glow-rose transition'
                    : 'flex items-center gap-1 px-2 py-1 rounded-md text-slate-400 hover:text-slate-200 text-[10px] sm:text-[11px] font-medium transition'
                }
              >
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                <span>LIVE</span>
              </button>
            </div>

            {/* Chrome Extension Wallet Connect Button */}
            <button
              type="button"
              onClick={() => setWalletModalOpen(true)}
              className={
                connectedWallet
                  ? 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/40 text-emerald-300 font-mono font-bold text-[10px] sm:text-[11px] transition'
                  : 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/40 text-purple-200 font-mono font-bold text-[10px] sm:text-[11px] transition'
              }
              title="Hubungkan Ekstensi Wallet Chrome (Phantom / Solflare / MetaMask)"
            >
              <span>{connectedWallet ? '🟢' : '🔌'}</span>
              <span>
                {connectedWallet
                  ? `${shortenAddress(connectedWallet.address)}`
                  : 'Connect Wallet'}
              </span>
            </button>

            {/* Quick Reset Paper Modal */}
            <button
              type="button"
              onClick={handleHeaderResetPaper}
              className="hidden md:flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-obsidian-800 hover:bg-obsidian-700 border border-obsidian-600 text-slate-300 hover:text-white transition font-mono text-[11px]"
              title="Reset Akun Simulasi Paper ke Rp 150.000"
            >
              <LucideIcon name="rotate-ccw" className="w-3.5 h-3.5 text-cyan-400" />
              <span className="hidden xl:inline">Reset Paper</span>
            </button>

            {/* Emergency Kill Switch / Start Bot Button */}
            <button
              type="button"
              onClick={handleHeaderBotToggle}
              className={
                botRunning
                  ? 'flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-400 hover:text-rose-300 border border-rose-500/40 transition font-bold text-[10px] sm:text-[11px] shadow-glow-rose'
                  : 'flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 transition font-bold text-[10px] sm:text-[11px] shadow-glow-emerald'
              }
            >
              <LucideIcon name="octagon-alert" className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">
                {botRunning ? 'HENTIKAN BOT' : `JALANKAN BOT (${mode})`}
              </span>
              <span className="sm:hidden">{botRunning ? 'STOP' : 'START'}</span>
            </button>
          </div>
        </div>
        {headerNotice && (
          <div className="px-3.5 py-1 bg-obsidian-950/90 border-t border-obsidian-800 text-[11px] font-mono text-emerald-300">
            {headerNotice}
          </div>
        )}
      </header>
      {/* END: MainHeader */}

      {/* BEGIN: Mobile Slide-Over Navigation Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-xs"
            onClick={() => setMobileMenuOpen(false)}
          />
          <aside className="relative w-72 max-w-[82vw] bg-obsidian-900 border-r border-obsidian-700 h-full flex flex-col justify-between p-4 overflow-y-auto z-10">
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b border-obsidian-800 pb-3">
                <span className="font-mono font-extrabold text-sm text-emerald-400">
                  ⚡ MENU NAVIGASI SOFIA
                </span>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-2 py-1 rounded bg-obsidian-800 text-slate-300 text-xs"
                >
                  ✕
                </button>
              </div>

              {/* Mobile Network Selector */}
              <div className="grid grid-cols-4 gap-1 bg-obsidian-950 p-1 rounded-lg border border-obsidian-800 text-[10px] font-mono">
                {CHAINS.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setSelectedChain(c.id)}
                    className={
                      selectedChain === c.id
                        ? 'py-1 rounded bg-emerald-500/20 text-emerald-300 font-bold'
                        : 'py-1 rounded text-slate-400'
                    }
                  >
                    {c.label}
                  </button>
                ))}
              </div>

              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5 font-mono">
                  Terminal &amp; Sniping
                </p>
                <nav className="space-y-1">
                  {PRIMARY_NAV.map((item) => {
                    const active = router.pathname === item.href;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={
                          active
                            ? 'flex items-center justify-between px-3 py-2 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-medium text-xs'
                            : 'flex items-center justify-between px-3 py-2 rounded-lg text-slate-300 hover:bg-obsidian-800 text-xs'
                        }
                      >
                        <div className="flex items-center gap-2.5">
                          <LucideIcon name={item.icon} className={`w-4 h-4 ${item.iconColor}`} />
                          <span>{item.label}</span>
                        </div>
                        {item.badge && (
                          <span className={`text-[9px] rounded font-mono ${item.badgeClass}`}>
                            {item.badge}
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </nav>
              </div>

              <div className="pt-2 border-t border-obsidian-800">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5 font-mono">
                  Portofolio &amp; AI Dev
                </p>
                <nav className="space-y-1">
                  {SECONDARY_NAV.map((item) => {
                    const active = router.pathname === item.href;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={
                          active
                            ? 'flex items-center justify-between px-3 py-2 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-medium text-xs'
                            : 'flex items-center justify-between px-3 py-2 rounded-lg text-slate-300 hover:bg-obsidian-800 text-xs'
                        }
                      >
                        <div className="flex items-center gap-2.5">
                          <LucideIcon name={item.icon} className={`w-4 h-4 ${item.iconColor}`} />
                          <span>{item.label}</span>
                        </div>
                        {item.badge && (
                          <span className={`text-[9px] rounded font-mono ${item.badgeClass}`}>
                            {item.badge}
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </nav>
              </div>
            </div>

            <div className="space-y-2 pt-4 border-t border-obsidian-800 font-mono">
              <div className="bg-obsidian-950 p-3 rounded-xl border border-obsidian-800">
                <div className="text-[10px] text-slate-400 font-bold">SALDO REAL LIVE</div>
                <div className="text-sm font-extrabold text-white mt-0.5">
                  {formatUsd(liveBalanceUsd)}
                </div>
                <div className="text-[10px] text-emerald-400">≈ {formatIdr(liveBalanceIdr)}</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setMobileMenuOpen(false);
                  setWalletModalOpen(true);
                }}
                className="w-full py-2 px-3 rounded-lg bg-purple-500/20 text-purple-200 border border-purple-500/40 text-xs font-bold"
              >
                🔌 Connect Ekstensi Chrome
              </button>
              <button
                type="button"
                onClick={handleInstallPwa}
                className="w-full py-2 px-3 rounded-lg bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 text-xs font-bold"
              >
                📲 Install Aplikasi (PWA)
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="w-full py-2 px-3 rounded-lg bg-rose-500/15 text-rose-300 border border-rose-500/30 text-xs font-bold"
              >
                🔒 Logout Operator
              </button>
            </div>
          </aside>
        </div>
      )}
      {/* END: Mobile Slide-Over Navigation Drawer */}

      <div className="flex flex-1 overflow-hidden">
        {/* BEGIN: Desktop LeftSidebarNav (Hidden on mobile so content gets 100% width) */}
        <aside className="hidden md:flex md:w-56 shrink-0 bg-obsidian-900 border-r border-obsidian-700/80 flex-col justify-between py-3 select-none">
          <div className="space-y-4">
            {/* Navigation Category 1 */}
            <div className="px-3">
              <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400 px-2 mb-1.5 font-mono">
                Terminal &amp; Sniping
              </p>
              <nav className="space-y-0.5" data-purpose="sidebar-nav-primary">
                {PRIMARY_NAV.map((item) => {
                  const active = router.pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={
                        active
                          ? 'flex items-center justify-between px-2.5 py-2 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-medium text-xs'
                          : 'flex items-center justify-between px-2.5 py-2 rounded-lg text-slate-300 hover:bg-obsidian-800/80 hover:text-slate-100 transition text-xs'
                      }
                    >
                      <div className="flex items-center gap-2.5 truncate">
                        <LucideIcon
                          name={item.icon}
                          className={`w-4 h-4 ${active ? 'text-emerald-400' : item.iconColor} shrink-0`}
                        />
                        <span className="truncate">{item.label}</span>
                      </div>
                      {item.badge && (
                        <span className={`text-[9px] rounded font-mono ${item.badgeClass}`}>
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </nav>
            </div>

            {/* Navigation Category 2 */}
            <div className="px-3 pt-2 border-t border-obsidian-800">
              <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400 px-2 mb-1.5 font-mono">
                Portofolio &amp; AI Dev
              </p>
              <nav className="space-y-0.5" data-purpose="sidebar-nav-secondary">
                {SECONDARY_NAV.map((item) => {
                  const active = router.pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={
                        active
                          ? 'flex items-center justify-between px-2.5 py-2 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-medium text-xs'
                          : 'flex items-center justify-between px-2.5 py-2 rounded-lg text-slate-300 hover:bg-obsidian-800 hover:text-slate-100 transition text-xs'
                      }
                    >
                      <div className="flex items-center gap-2.5 truncate">
                        <LucideIcon
                          name={item.icon}
                          className={`w-4 h-4 ${active ? 'text-emerald-400' : item.iconColor} shrink-0`}
                        />
                        <span className="truncate">{item.label}</span>
                      </div>
                      {item.badge && (
                        <span className={`text-[9px] rounded font-mono ${item.badgeClass}`}>
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </nav>
            </div>
          </div>

          {/* Bottom Mini Status: Saldo Real Live (USD & IDR), PWA Install & Logout */}
          <div className="px-3 space-y-2">
            <div className="bg-obsidian-950 p-2.5 rounded-xl border border-obsidian-800 font-mono">
              <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
                <span className="flex items-center gap-1.5 text-slate-300 font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  SALDO REAL LIVE
                </span>
                <span className="text-[9px] text-emerald-400 font-bold px-1.5 py-0.2 rounded bg-emerald-500/10 border border-emerald-500/30">
                  ON-CHAIN
                </span>
              </div>
              <div className="space-y-0.5">
                <div className="text-sm font-extrabold text-white tracking-tight">
                  {formatUsd(liveBalanceUsd)}
                </div>
                <div className="text-[10px] text-emerald-400 font-medium">
                  ≈ {formatIdr(liveBalanceIdr)}
                </div>
              </div>
              <div className="flex items-center justify-between text-[9px] text-slate-500 border-t border-obsidian-800/80 pt-1.5 mt-2">
                <span>Engine RPC</span>
                <span className="text-cyan-400">Ultra-Fast 18ms</span>
              </div>
              <div className="w-full bg-obsidian-800 h-1 rounded-full mt-1 overflow-hidden">
                <div className="bg-gradient-to-r from-emerald-500 to-cyan-400 h-full w-[94%]"></div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-1.5 font-mono text-[10px]">
              <button
                type="button"
                onClick={handleInstallPwa}
                className="px-2 py-1.5 rounded-lg bg-obsidian-950 hover:bg-obsidian-850 border border-obsidian-800 text-cyan-300 font-bold text-center transition"
                title="Install aplikasi ke Desktop / HP (PWA)"
              >
                📲 Install PWA
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="px-2 py-1.5 rounded-lg bg-obsidian-950 hover:bg-rose-950/50 border border-obsidian-800 hover:border-rose-500/40 text-slate-400 hover:text-rose-300 font-bold text-center transition"
              >
                🔒 Logout
              </button>
            </div>
          </div>
        </aside>
        {/* END: Desktop LeftSidebarNav */}

        {/* BEGIN: MainContentArea */}
        <main className="flex-1 overflow-y-auto px-2.5 sm:px-3.5 py-3 pb-20 md:pb-3 space-y-3 bg-obsidian-950 grid-bg-overlay">
          {children}
        </main>
        {/* END: MainContentArea */}
      </div>

      {/* BEGIN: Mobile Fixed Bottom Tab Bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-obsidian-900/95 backdrop-blur-md border-t border-obsidian-700 grid grid-cols-5 py-1.5 px-1 font-mono text-[10px]">
        {MOBILE_BOTTOM_NAV.map((tab) => {
          const active = router.pathname === tab.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`flex flex-col items-center justify-center gap-0.5 py-1 rounded-lg transition ${
                active ? 'text-emerald-400 font-bold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <LucideIcon name={tab.icon} className="w-4 h-4" />
              <span>{tab.label}</span>
            </Link>
          );
        })}
      </nav>
      {/* END: Mobile Fixed Bottom Tab Bar */}

      {/* BEGIN: FooterStatusHUD */}
      <footer className="hidden md:flex bg-obsidian-900 border-t border-obsidian-800 px-4 py-1.5 text-[10px] font-mono text-slate-400 flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-slate-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            SOFIA Core Node: <strong className="text-white">Active (Cluster SG-1)</strong>
          </span>
          <span className="hidden md:inline text-slate-600">|</span>
          <span className="hidden md:inline">
            Gas Gwei: <strong className="text-cyan-300">0.000005 SOL</strong>
          </span>
          <span className="hidden md:inline text-slate-600">|</span>
          <span className="hidden md:inline">
            Anti-Rug Guard: <strong className="text-emerald-400">Strict (Score &gt; 80)</strong>
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span>
            Auto-Take Profit: <span className="text-emerald-400">+35%</span> • Stop-Loss:{' '}
            <span className="text-rose-400">-15%</span>
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-300">
            Latency: <span className="text-emerald-400">14ms</span>
          </span>
        </div>
      </footer>
      {/* END: FooterStatusHUD */}
    </div>
  );
}
