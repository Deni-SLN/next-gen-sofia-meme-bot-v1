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
  getStrategyMode,
} from '@/lib/api';
import {
  ConnectedExtensionWallet,
  getSavedExtensionWallet,
  shortenAddress,
} from '@/lib/web3';
import { LucideIcon } from '@/components/LucideIcon';
import { WalletConnectModal } from '@/components/WalletConnectModal';
import { LoginPortal } from '@/pages/login';

interface NavItem {
  href: string;
  label: string;
  icon: string;
  badge?: string | null;
  badgeTone?: 'emerald' | 'amber' | 'cyan' | 'slate';
}

const NAV_GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Terminal & Eksekusi',
    items: [
      { href: '/', label: 'Command Center', icon: 'layout-dashboard' },
      { href: '/auto-entry', label: 'Auto Entry Bot', icon: 'crosshair', badge: 'ENTRY', badgeTone: 'cyan' },
      { href: '/pulse', label: 'Trenches & Pulse', icon: 'zap', badge: 'LIVE', badgeTone: 'amber' },
      { href: '/trading', label: 'Auto-Sniper Bot', icon: 'crosshair', badge: '3 MODE', badgeTone: 'emerald' },
      { href: '/rugcheck', label: 'Rug & Bundle Shield', icon: 'shield-alert' },
      { href: '/copytrade', label: 'Smart Money Copy', icon: 'copy' },
    ],
  },
  {
    title: 'Analisa & Riset Pasar',
    items: [
      { href: '/chat', label: 'AI Chat & Research', icon: 'message-square', badge: 'AI TOOLS', badgeTone: 'emerald' },
      { href: '/stocks', label: 'Analisa Saham BEI', icon: 'trending-up', badge: 'IDX', badgeTone: 'emerald' },
      { href: '/crypto', label: 'Analisa Crypto', icon: 'cpu', badge: '24/7', badgeTone: 'cyan' },
      { href: '/gold', label: 'Portofolio Emas', icon: 'coins', badge: 'XAU', badgeTone: 'amber' },
      { href: '/calculator', label: 'Kalkulator Deposito & Obligasi', icon: 'calculator', badge: 'SIMULASI', badgeTone: 'emerald' },
      { href: '/news', label: 'News & Riset', icon: 'newspaper' },
      { href: '/signals', label: 'Alpha Signals', icon: 'radio' },
      { href: '/encyclopedia', label: 'Ensiklopedia Pasar', icon: 'book', badge: 'KAMUS', badgeTone: 'cyan' },
    ],
  },
  {
    title: 'Portofolio & Sistem',
    items: [
      { href: '/portfolio', label: 'Portofolio Meme', icon: 'wallet' },
      { href: '/journal', label: 'Jurnal Trading', icon: 'book-open' },
      { href: '/calendar', label: 'Kalender PnL', icon: 'calendar' },
      { href: '/agents', label: 'AI Degen Agents', icon: 'bot' },
      { href: '/risk', label: 'Risk & Slippage', icon: 'sliders' },
      { href: '/wallets', label: 'Multi-Gate Wallets', icon: 'layers' },
      { href: '/settings', label: 'Pengaturan Sistem', icon: 'sliders', badge: 'CONFIG', badgeTone: 'cyan' },
    ],
  },
];

const MOBILE_BOTTOM_NAV = [
  { href: '/', label: 'Overview', icon: 'layout-dashboard' },
  { href: '/pulse', label: 'Pulse', icon: 'zap' },
  { href: '/trading', label: 'Bot', icon: 'crosshair' },
  { href: '/stocks', label: 'Saham', icon: 'trending-up' },
  { href: '/crypto', label: 'Crypto', icon: 'cpu' },
];

const CHAINS = [
  { id: 'Solana', label: 'Solana' },
  { id: 'Base', label: 'Base' },
  { id: 'Ethereum', label: 'ETH' },
  { id: 'BSC', label: 'BSC' },
];

function getBadgeStyle(tone?: NavItem['badgeTone']) {
  switch (tone) {
    case 'emerald':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    case 'amber':
      return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    case 'cyan':
      return 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20';
    default:
      return 'bg-obsidian-800 text-slate-400 border-obsidian-700';
  }
}

export function Layout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState<boolean>(false);
  const [checking, setChecking] = useState<boolean>(true);
  const [selectedChain, setSelectedChain] = useState<string>('Solana');
  const [usdIdr, setUsdIdr] = useState<number>(17960);
  const [mode, setMode] = useState<'PAPER' | 'LIVE'>('PAPER');
  const [botRunning, setBotRunning] = useState<boolean>(false);
  const [headerNotice, setHeaderNotice] = useState<string>('');
  const [liveBalanceUsd, setLiveBalanceUsd] = useState<number>(0);
  const [liveBalanceIdr, setLiveBalanceIdr] = useState<number>(0);

  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);
  const [walletModalOpen, setWalletModalOpen] = useState<boolean>(false);
  const [isUltrawide, setIsUltrawide] = useState<boolean>(false);
  const [connectedWallet, setConnectedWallet] = useState<ConnectedExtensionWallet | null>(null);
  const [deferredPwaPrompt, setDeferredPwaPrompt] = useState<any>(null);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [timeWIB, setTimeWIB] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeWIB(
        now.toLocaleTimeString('id-ID', {
          timeZone: 'Asia/Jakarta',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        })
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsUltrawide(localStorage.getItem('sofia_ultrawide') === 'true');
      const ultHandler = (e: any) => {
        setIsUltrawide(Boolean(e?.detail));
      };
      window.addEventListener('sofia-ultrawide-toggle', ultHandler);
      return () => window.removeEventListener('sofia-ultrawide-toggle', ultHandler);
    }
  }, []);

  const handleToggleUltrawide = (enabled: boolean) => {
    setIsUltrawide(enabled);
    if (typeof window !== 'undefined') {
      localStorage.setItem('sofia_ultrawide', enabled ? 'true' : 'false');
      window.dispatchEvent(new CustomEvent('sofia-ultrawide-toggle', { detail: enabled }));
    }
  };

  const handleToggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    if (typeof window !== 'undefined') {
      localStorage.setItem('sofia_theme', next);
      document.documentElement.classList.toggle('light-theme', next === 'light');
      window.dispatchEvent(new CustomEvent('sofia-theme-change', { detail: next }));
    }
  };

  const fetchLiveBalances = () => {
    api
      .getLiveWalletStatus()
      .then((res: any) => {
        if (res) {
          const cashUsd = Number(res.live_cash_usd ?? res.live_total_equity_usd ?? 0);
          const cashIdr = Number(res.live_cash_idr ?? res.live_total_equity_idr ?? 0);
          setLiveBalanceUsd(cashUsd);
          setLiveBalanceIdr(cashIdr);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    const hasToken = Boolean(getToken());
    setAuthenticated(hasToken);
    if (typeof window !== 'undefined') {
      const savedTheme = localStorage.getItem('sofia_theme') === 'light' ? 'light' : 'dark';
      setTheme(savedTheme);
      document.documentElement.classList.toggle('light-theme', savedTheme === 'light');
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
    const hasAuth = Boolean(getToken());
    setAuthenticated(hasAuth);
    if (hasAuth) {
      api
        .getBotStatus()
        .then((res) => {
          const running = res?.status === 'running';
          setBotRunning(running);
          if (running && (res?.mode === 'LIVE' || res?.mode === 'PAPER')) {
            setMode(res.mode);
            setTradingMode(res.mode);
          }
        })
        .catch(() => {});
    }
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
          const running = res?.status === 'running';
          setBotRunning(running);
          if (running && (res?.mode === 'LIVE' || res?.mode === 'PAPER')) {
            setMode(res.mode);
            setTradingMode(res.mode);
          }
        })
        .catch(() => {});
      fetchLiveBalances();
    }
  }, [authenticated]);

  // Global background bot heartbeat: ensures bot keeps running & UI stays synced even when navigating away from '/' or '/trading'
  useEffect(() => {
    if (!authenticated || !botRunning) return;
    const isBotCardMountedPage = router.pathname === '/' || router.pathname === '/trading';
    const interval = setInterval(() => {
      // On pages where BotActivityCard is not mounted, trigger background tick & sync state
      api
        .getBotActivity(!isBotCardMountedPage, false)
        .then((res) => {
          if (res?.status) {
            setBotRunning(res.status === 'running');
          }
          if (res?.trade_executed && typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('sofia-bot-trade-executed', { detail: res.trade_action }));
            fetchLiveBalances();
          }
        })
        .catch(() => {});
    }, 3500);

    return () => clearInterval(interval);
  }, [authenticated, botRunning, router.pathname]);

  const handleSelectMode = (nextMode: 'PAPER' | 'LIVE') => {
    if (botRunning && nextMode !== mode) {
      setHeaderNotice('🔒 Mode tidak dapat diubah selama Bot sedang berjalan. Hentikan Bot terlebih dahulu.');
      setTimeout(() => setHeaderNotice(''), 4000);
      return;
    }
    setMode(nextMode);
    setTradingMode(nextMode);
  };

  const handleHeaderResetPaper = async () => {
    try {
      const freshOverview = await api.resetPaperAccount();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('sofia-paper-reset', { detail: freshOverview }));
      }
      setHeaderNotice('Akun Paper direset kembali ke Rp 150.000.');
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
        setHeaderNotice('Auto-Sniper Bot dihentikan.');
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: false } }));
        }
      } else {
        await api.startBot(mode, getStrategyMode());
        setBotRunning(true);
        setHeaderNotice(`Auto-Sniper Bot diaktifkan (${mode} Mode).`);
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('sofia-bot-status-change', { detail: { running: true } }));
        }
      }
      setTimeout(() => setHeaderNotice(''), 3500);
    } catch (err: any) {
      if (err?.code === 'BOT_NOT_RUNNING') {
        setBotRunning(false);
        setHeaderNotice('Auto-Sniper Bot sudah berhenti.');
      } else {
        setHeaderNotice(`${err?.code || 'ERROR'}: ${err?.message || 'Gagal mengubah status bot'}`);
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
        'Aplikasi Web Siap: Klik ikon Install di Address Bar browser atau pilih Add to Home Screen.'
      );
      setTimeout(() => setHeaderNotice(''), 4500);
    }
  };

  const handleLogout = () => {
    clearToken();
    setAuthenticated(false);
    router.push('/login');
  };

  const handleMenuNavigation = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    setMobileMenuOpen(false);
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
      return;
    }
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('sofia-nav-start', { detail: href }));
      if (window.location.pathname === href) {
        return;
      }
      e.preventDefault();
      router.push(href).catch(() => {
        window.location.href = href;
      });
      setTimeout(() => {
        if (window.location.pathname !== href) {
          window.location.href = href;
        }
      }, 450);
    }
  };

  if (checking) {
    return (
      <div className="min-h-screen bg-obsidian-950 text-slate-400 flex items-center justify-center font-sans text-xs tracking-wide">
        Memuat ruang kerja Sofia Market 3.9...
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
    <div className="bg-obsidian-950 text-slate-200 font-sans antialiased selection:bg-emerald-500/20 selection:text-emerald-300 min-h-screen md:h-screen flex flex-col overflow-x-hidden md:overflow-hidden">
      <WalletConnectModal
        isOpen={walletModalOpen}
        onClose={() => setWalletModalOpen(false)}
        connectedWallet={connectedWallet}
        onConnected={(w) => {
          setConnectedWallet(w);
          setSelectedChain(w.chain);
          setHeaderNotice(
            `Terhubung ke ${w.providerName}: ${shortenAddress(w.address)} (${w.chain})`
          );
          setTimeout(() => setHeaderNotice(''), 4000);
        }}
      />

      {/* BEGIN: Clean AnalisMarket-Style Topbar */}
      <header className="border-b border-obsidian-700/70 bg-obsidian-950/90 backdrop-blur-md sticky top-0 z-50 shrink-0">
        <div className="px-3 sm:px-5 h-14 flex items-center justify-between gap-3 text-xs">
          {/* Left: Hamburger + Brand + Clean Chain Switcher */}
          <div className="flex items-center gap-3 sm:gap-4">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-1.5 rounded-lg bg-obsidian-900 border border-obsidian-700 text-slate-300 hover:text-white transition"
              aria-label="Menu Navigasi"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>

            {/* Brand Identity */}
            <Link
              href="/"
              onClick={(e) => handleMenuNavigation(e, '/')}
              className="flex items-center gap-2.5 pr-3 sm:border-r border-obsidian-700/70"
            >
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-obsidian-900 border border-obsidian-700 text-amber-400">
                <LucideIcon name="trending-up" className="w-4 h-4" />
              </div>
              <div className="leading-tight">
                <div className="font-semibold tracking-tight text-sm text-white flex items-center gap-1.5">
                  <span>SOFIA</span>
                  <span className="text-slate-400 font-normal">Market</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-obsidian-850 text-slate-400 border border-obsidian-700 font-mono">
                    3.9
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 hidden sm:block">
                  Multi-Asset Quantitative Terminal
                </p>
              </div>
            </Link>

            {/* Network Switcher */}
            <div
              className="hidden lg:flex items-center bg-obsidian-900 p-0.5 rounded-lg border border-obsidian-700/80"
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
                        ? 'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-white bg-obsidian-800 border border-obsidian-600 font-medium text-[11px] transition'
                        : 'flex items-center gap-1 px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200 text-[11px] transition'
                    }
                  >
                    {active && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>}
                    <span>{c.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Clean FX Indicator */}
            <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-obsidian-900 border border-obsidian-700/70 text-[11px] text-slate-400">
              <span>USD/IDR</span>
              <span className="text-slate-200 font-mono font-medium">{formatIdr(usdIdr)}</span>
            </div>

            {/* Live Clock WIB / Depok */}
            <div
              className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-obsidian-900 border border-obsidian-700/70 text-[11px] text-slate-300 font-mono shadow-xs"
              title="Waktu Indonesia Barat (WIB) — Depok / Jakarta (UTC+7)"
            >
              <LucideIcon name="clock" className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span className="text-white font-medium tracking-wide">{timeWIB || '--:--:--'}</span>
              <span className="text-cyan-400 text-[10px] font-bold">WIB</span>
            </div>
          </div>

          {/* Right: Clean Unified Controls */}
          <div className="flex items-center gap-2">
            {/* Paper vs Live Segmented Switch */}
            <div
              className="flex items-center bg-obsidian-900 p-0.5 rounded-lg border border-obsidian-700/80"
              data-purpose="trading-mode-toggle"
            >
              <button
                type="button"
                onClick={() => handleSelectMode('PAPER')}
                className={
                  mode === 'PAPER'
                    ? 'px-2.5 py-1 rounded-md bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-medium text-[11px] transition'
                    : 'px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200 text-[11px] transition'
                }
              >
                Paper
              </button>
              <button
                type="button"
                onClick={() => handleSelectMode('LIVE')}
                className={
                  mode === 'LIVE'
                    ? 'flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-500/15 text-rose-400 border border-rose-500/30 font-medium text-[11px] transition'
                    : 'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200 text-[11px] transition'
                }
              >
                <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
                <span>Live</span>
              </button>
            </div>

            {/* Reset Paper Button */}
            {mode === 'PAPER' && (
              <button
                type="button"
                onClick={handleHeaderResetPaper}
                className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-obsidian-900 hover:bg-obsidian-850 border border-obsidian-700/80 text-slate-400 hover:text-slate-200 transition text-[11px]"
                title="Reset Saldo Simulasi Paper ke Rp 150.000"
              >
                <LucideIcon name="rotate-ccw" className="w-3.5 h-3.5" />
                <span className="hidden xl:inline">Reset</span>
              </button>
            )}

            {/* Wallet Button */}
            <button
              type="button"
              onClick={() => setWalletModalOpen(true)}
              className={
                connectedWallet
                  ? 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-obsidian-900 hover:bg-obsidian-850 border border-emerald-500/30 text-emerald-400 font-mono text-[11px] transition'
                  : 'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-obsidian-900 hover:bg-obsidian-850 border border-obsidian-700/80 text-slate-300 hover:text-white text-[11px] font-medium transition'
              }
              title="Hubungkan Wallet Web3 (Phantom / Solflare / MetaMask)"
            >
              <LucideIcon name="wallet" className="w-3.5 h-3.5" />
              <span>
                {connectedWallet ? shortenAddress(connectedWallet.address) : 'Wallet'}
              </span>
            </button>

            {/* Ultrawide / Layar Lebar Toggle Button */}
            <button
              type="button"
              onClick={() => handleToggleUltrawide(!isUltrawide)}
              className={`flex items-center justify-center w-8 h-8 rounded-lg border transition ${
                isUltrawide
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-sm'
                  : 'bg-obsidian-900 hover:bg-obsidian-850 text-slate-400 hover:text-slate-200 border-obsidian-700/80'
              }`}
              title={
                isUltrawide
                  ? 'Mode Layar Lebar Aktif (Klik untuk Mode Standar)'
                  : 'Aktifkan Mode Layar Lebar (Maksimalkan Monitor)'
              }
            >
              <LucideIcon name={isUltrawide ? 'minimize' : 'maximize'} className="w-3.5 h-3.5" />
            </button>

            {/* Settings Link to /settings page */}
            <Link
              href="/settings"
              onClick={(e) => handleMenuNavigation(e, '/settings')}
              className={`flex items-center justify-center w-8 h-8 rounded-lg border transition ${
                router.pathname === '/settings'
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-sm'
                  : 'bg-obsidian-900 hover:bg-obsidian-850 border border-obsidian-700/80 text-slate-400 hover:text-slate-200'
              }`}
              title="Buka Pengaturan Sistem (API, Wallet, Tampilan)"
            >
              <LucideIcon name="sliders" className="w-3.5 h-3.5" />
            </Link>

            {/* Theme Toggle */}
            <button
              type="button"
              onClick={handleToggleTheme}
              className="flex items-center justify-center w-8 h-8 rounded-lg bg-obsidian-900 hover:bg-obsidian-850 border border-obsidian-700/80 text-slate-400 hover:text-slate-200 transition"
              title={theme === 'dark' ? 'Beralih ke Mode Terang' : 'Beralih ke Mode Gelap'}
              data-purpose="theme-toggle"
            >
              <LucideIcon
                name={theme === 'dark' ? 'sun' : 'moon'}
                className="w-3.5 h-3.5"
              />
            </button>

            {/* Auto-Sniper Bot Status / Toggle */}
            <button
              type="button"
              onClick={handleHeaderBotToggle}
              className={
                botRunning
                  ? 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 transition font-medium text-[11px]'
                  : 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 transition font-medium text-[11px]'
              }
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  botRunning ? 'bg-rose-400 animate-pulse' : 'bg-emerald-400'
                }`}
              />
              <span className="hidden sm:inline">
                {botRunning ? 'Stop Bot' : `Jalankan Bot`}
              </span>
              <span className="sm:hidden">{botRunning ? 'Stop' : 'Bot'}</span>
            </button>
          </div>
        </div>
        {headerNotice && (
          <div className="px-5 py-1.5 bg-obsidian-900 border-t border-obsidian-800 text-[11px] text-emerald-400 flex items-center justify-between">
            <span>{headerNotice}</span>
            <button
              type="button"
              onClick={() => setHeaderNotice('')}
              className="text-slate-500 hover:text-slate-300"
            >
              ✕
            </button>
          </div>
        )}
      </header>
      {/* END: Clean AnalisMarket-Style Topbar */}

      {/* BEGIN: Mobile Slide-Over Navigation Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs"
            onClick={() => setMobileMenuOpen(false)}
          />
          <aside className="relative w-64 max-w-[82vw] bg-obsidian-900 border-r border-obsidian-700 h-full flex flex-col justify-between p-4 overflow-y-auto z-10">
            <div className="space-y-5">
              <div className="flex items-center justify-between border-b border-obsidian-800 pb-3">
                <span className="font-semibold text-sm text-white">Navigasi Sofia Market 3.9</span>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-2 py-1 rounded bg-obsidian-850 text-slate-400 text-xs"
                >
                  ✕
                </button>
              </div>

              {NAV_GROUPS.map((group) => (
                <div key={group.title} className="space-y-1">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 px-2 mb-1">
                    {group.title}
                  </p>
                  <nav className="space-y-0.5">
                    {group.items.map((item) => {
                      const active = router.pathname === item.href;
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          onClick={(e) => handleMenuNavigation(e, item.href)}
                          className={
                            active
                              ? 'flex items-center justify-between px-2.5 py-2 rounded-lg bg-obsidian-800 text-white border border-obsidian-700 font-medium text-xs cursor-pointer'
                              : 'flex items-center justify-between px-2.5 py-2 rounded-lg text-slate-400 hover:bg-obsidian-850 hover:text-slate-200 text-xs cursor-pointer'
                          }
                        >
                          <div className="flex items-center gap-2.5">
                            <LucideIcon
                              name={item.icon}
                              className={`w-4 h-4 ${active ? 'text-emerald-400' : 'text-slate-400'}`}
                            />
                            <span>{item.label}</span>
                          </div>
                          {item.badge && (
                            <span
                              className={`text-[9px] px-1.5 py-0.2 rounded border font-mono ${getBadgeStyle(
                                item.badgeTone
                              )}`}
                            >
                              {item.badge}
                            </span>
                          )}
                        </Link>
                      );
                    })}
                  </nav>
                </div>
              ))}
            </div>

            <div className="space-y-2 pt-4 border-t border-obsidian-800">
              <div className="bg-obsidian-950 p-3 rounded-xl border border-obsidian-800">
                <div className="text-[10px] text-slate-500 font-medium uppercase">Saldo On-Chain</div>
                <div className="text-sm font-semibold text-white mt-0.5 font-mono">
                  {formatUsd(liveBalanceUsd)}
                </div>
                <div className="text-[11px] text-slate-400 font-mono">≈ {formatIdr(liveBalanceIdr)}</div>
              </div>
              <div className="grid grid-cols-2 gap-1.5 text-xs">
                <button
                  type="button"
                  onClick={handleInstallPwa}
                  className="py-2 px-2.5 rounded-lg bg-obsidian-850 text-slate-300 border border-obsidian-700 font-medium"
                >
                  Install App
                </button>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="py-2 px-2.5 rounded-lg bg-obsidian-850 text-rose-400 border border-obsidian-700 font-medium"
                >
                  Keluar
                </button>
              </div>
            </div>
          </aside>
        </div>
      )}
      {/* END: Mobile Slide-Over Navigation Drawer */}

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* BEGIN: Clean AnalisMarket-Style Left Sidebar */}
        <aside className="relative z-30 pointer-events-auto hidden md:flex md:w-56 shrink-0 h-full overflow-y-auto bg-obsidian-900/70 border-r border-obsidian-700/70 flex-col justify-between py-4 select-none">
          <div className="space-y-5 px-3">
            {NAV_GROUPS.map((group) => (
              <div key={group.title}>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 px-2.5 mb-1.5">
                  {group.title}
                </p>
                <nav className="space-y-0.5">
                  {group.items.map((item) => {
                    const active = router.pathname === item.href;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={(e) => handleMenuNavigation(e, item.href)}
                        className={
                          active
                            ? 'flex items-center justify-between px-2.5 py-2 rounded-lg bg-obsidian-800 text-white border border-obsidian-700 font-medium text-xs transition cursor-pointer'
                            : 'flex items-center justify-between px-2.5 py-2 rounded-lg text-slate-400 hover:bg-obsidian-850/80 hover:text-slate-200 transition text-xs cursor-pointer'
                        }
                      >
                        <div className="flex items-center gap-2.5 truncate">
                          <LucideIcon
                            name={item.icon}
                            className={`w-4 h-4 shrink-0 ${
                              active ? 'text-emerald-400' : 'text-slate-400'
                            }`}
                          />
                          <span className="truncate">{item.label}</span>
                        </div>
                        {item.badge && (
                          <span
                            className={`text-[9px] px-1.5 py-0.2 rounded border font-mono ${getBadgeStyle(
                              item.badgeTone
                            )}`}
                          >
                            {item.badge}
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </nav>
              </div>
            ))}
          </div>

          {/* Bottom Account Card */}
          <div className="px-3 space-y-2 pt-4 border-t border-obsidian-800/80">
            <div className="bg-obsidian-950/80 p-3 rounded-xl border border-obsidian-800">
              <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
                <span className="font-medium text-slate-400">Saldo Live Wallet</span>
                <span className="flex items-center gap-1 text-[9px] text-emerald-400 font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                  On-Chain
                </span>
              </div>
              <div className="text-sm font-semibold text-white font-mono tracking-tight">
                {formatUsd(liveBalanceUsd)}
              </div>
              <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                ≈ {formatIdr(liveBalanceIdr)}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-1.5 text-[11px]">
              <button
                type="button"
                onClick={handleInstallPwa}
                className="px-2 py-1.5 rounded-lg bg-obsidian-950 hover:bg-obsidian-850 border border-obsidian-800 text-slate-400 hover:text-slate-200 font-medium text-center transition"
                title="Install Aplikasi Web"
              >
                Install App
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="px-2 py-1.5 rounded-lg bg-obsidian-950 hover:bg-rose-950/30 border border-obsidian-800 hover:border-rose-500/30 text-slate-400 hover:text-rose-300 font-medium text-center transition"
              >
                Keluar
              </button>
            </div>
          </div>
        </aside>
        {/* END: Clean AnalisMarket-Style Left Sidebar */}

        {/* BEGIN: MainContentArea */}
        <main className="flex-1 min-h-0 overflow-y-auto px-2 sm:px-5 py-4 pb-20 md:pb-5 space-y-4 bg-obsidian-950 grid-bg-overlay">
          <div
            className={
              isUltrawide
                ? 'w-full max-w-none px-1 sm:px-3 space-y-4 transition-all duration-300'
                : 'max-w-[1440px] mx-auto space-y-4 transition-all duration-300'
            }
          >
            {children}
          </div>
        </main>
        {/* END: MainContentArea */}
      </div>

      {/* BEGIN: Mobile Fixed Bottom Tab Bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-obsidian-900/95 backdrop-blur-md border-t border-obsidian-700 grid grid-cols-6 py-1.5 px-1 text-[10px]">
        {MOBILE_BOTTOM_NAV.map((tab) => {
          const active = router.pathname === tab.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              onClick={(e) => handleMenuNavigation(e, tab.href)}
              className={`flex flex-col items-center justify-center gap-0.5 py-1 rounded-lg transition cursor-pointer ${
                active ? 'text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <LucideIcon name={tab.icon} className="w-4 h-4" />
              <span>{tab.label}</span>
            </Link>
          );
        })}
        <button
          type="button"
          onClick={() => setMobileMenuOpen((prev) => !prev)}
          className={`flex flex-col items-center justify-center gap-0.5 py-1 rounded-lg transition cursor-pointer ${
            mobileMenuOpen ? 'text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <LucideIcon name="layers" className="w-4 h-4" />
          <span>Lainnya</span>
        </button>
      </nav>
      {/* END: Mobile Fixed Bottom Tab Bar */}

      {/* BEGIN: Minimalist Status Bar */}
      <footer className="hidden md:flex shrink-0 bg-obsidian-950 border-t border-obsidian-800/80 px-5 py-1.5 text-[11px] text-slate-500 items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-slate-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            <span>DexScreener &amp; Yahoo Finance Feed</span>
          </span>
          <span>•</span>
          <span>Rug Shield: Active</span>
        </div>
        <div className="flex items-center gap-4 font-mono text-[10px]">
          <span>Mode: {mode}</span>
          <span>•</span>
          <span className="text-slate-400">Latency 14ms</span>
        </div>
      </footer>
      {/* END: Minimalist Status Bar */}
    </div>
  );
}
