import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { LucideIcon } from '@/components/LucideIcon';
import { useUltrawide, toggleUltrawide } from '@/lib/useUltrawide';

export default function SettingsPage() {
  const router = useRouter();
  const isUltrawide = useUltrawide();

  const [activeTab, setActiveTab] = useState<'ai-api' | 'market-api' | 'display' | 'wallet' | 'account'>('ai-api');
  const [saveNotice, setSaveNotice] = useState<string>('');

  // 1. AI APIs State (Terpisah Khusus AI)
  const [openrouterApiKey, setOpenrouterApiKey] = useState<string>('');
  const [nineRouterApiKey, setNineRouterApiKey] = useState<string>('');
  const [geminiApiKey, setGeminiApiKey] = useState<string>('');
  const [aiApiKey, setAiApiKey] = useState<string>('');
  const [defaultAiProvider, setDefaultAiProvider] = useState<string>('openrouter');
  const [defaultAiFreeOnly, setDefaultAiFreeOnly] = useState<boolean>(true);

  // 2. Market & Feed APIs State (Terpisah Non-AI)
  const [binanceApiKey, setBinanceApiKey] = useState<string>('');
  const [binanceApiSecret, setBinanceApiSecret] = useState<string>('');
  const [dexscreenerEndpoint, setDexscreenerEndpoint] = useState<string>('https://api.dexscreener.com/latest/dex');
  const [gmgnEndpoint, setGmgnEndpoint] = useState<string>('https://gmgn.ai/defi/quotation/v1/rank/sol');
  const [telegramToken, setTelegramToken] = useState<string>('');
  const [telegramChatId, setTelegramChatId] = useState<string>('');

  // 3. Wallet Settings State
  const [solanaAddress, setSolanaAddress] = useState<string>('');
  const [evmAddress, setEvmAddress] = useState<string>('');
  const [solanaRpc, setSolanaRpc] = useState<string>('https://api.mainnet-beta.solana.com');
  const [baseRpc, setBaseRpc] = useState<string>('https://mainnet.base.org');
  const [slippagePct, setSlippagePct] = useState<number>(1.5);
  const [gasThresholdIdr, setGasThresholdIdr] = useState<number>(10000);

  // 4. Display Settings
  const [defaultTimeframe, setDefaultTimeframe] = useState<string>('1d');
  const [soundAlerts, setSoundAlerts] = useState<boolean>(true);

  // Load saved settings from localStorage on mount
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // AI Keys
    setOpenrouterApiKey(localStorage.getItem('sofia_apikey_openrouter') || '');
    setNineRouterApiKey(localStorage.getItem('sofia_apikey_9router') || '');
    setGeminiApiKey(localStorage.getItem('sofia_apikey_gemini') || '');
    setAiApiKey(localStorage.getItem('sofia_ai_key') || 'SOFIA_BUILTIN_ALGORITHMIC_ENGINE');
    setDefaultAiProvider(localStorage.getItem('sofia_default_ai_provider') || 'openrouter');
    setDefaultAiFreeOnly(localStorage.getItem('sofia_default_ai_free_only') !== 'false');

    // Market APIs
    setBinanceApiKey(localStorage.getItem('sofia_binance_key') || 'https://data-api.binance.vision/api/v3');
    setBinanceApiSecret(localStorage.getItem('sofia_binance_secret') || 'PUBLIC_FREE_GATEWAY');
    setDexscreenerEndpoint(localStorage.getItem('sofia_dexscreener_url') || 'https://api.dexscreener.com/latest/dex');
    setGmgnEndpoint(localStorage.getItem('sofia_gmgn_url') || 'https://gmgn.ai/defi/quotation/v1/rank/sol');
    setTelegramToken(localStorage.getItem('sofia_tg_token') || '');
    setTelegramChatId(localStorage.getItem('sofia_tg_chat_id') || '');

    // Wallet & RPC
    setSolanaAddress(localStorage.getItem('sofia_sol_addr') || '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R');
    setEvmAddress(localStorage.getItem('sofia_evm_addr') || '0x71C7656EC7ab88b098defB751B7401B5f6d8976F');
    setSolanaRpc(localStorage.getItem('sofia_sol_rpc') || 'https://api.mainnet-beta.solana.com');
    setBaseRpc(localStorage.getItem('sofia_base_rpc') || 'https://mainnet.base.org');
    setSlippagePct(parseFloat(localStorage.getItem('sofia_slippage') || '1.5'));
    setGasThresholdIdr(parseInt(localStorage.getItem('sofia_gas_thresh') || '10000', 10));

    // Display
    setDefaultTimeframe(localStorage.getItem('sofia_default_tf') || '1d');
    setSoundAlerts(localStorage.getItem('sofia_sound_alerts') !== 'false');
  }, []);

  const handleFillFreeMarketApis = () => {
    setBinanceApiKey('https://data-api.binance.vision/api/v3');
    setBinanceApiSecret('PUBLIC_FREE_GATEWAY');
    setDexscreenerEndpoint('https://api.dexscreener.com/latest/dex');
    setGmgnEndpoint('https://gmgn.ai/defi/quotation/v1/rank/sol');
    setSolanaRpc('https://api.mainnet-beta.solana.com');
    setBaseRpc('https://mainnet.base.org');
    if (!solanaAddress) setSolanaAddress('4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R');
    if (!evmAddress) setEvmAddress('0x71C7656EC7ab88b098defB751B7401B5f6d8976F');
    setSaveNotice('Semua API Pasar berhasil diisi dengan Free Public Gateway!');
    setTimeout(() => setSaveNotice(''), 3500);
  };

  const handleSave = () => {
    if (typeof window === 'undefined') return;

    // Save AI APIs
    localStorage.setItem('sofia_apikey_openrouter', openrouterApiKey.trim());
    localStorage.setItem('sofia_apikey_9router', nineRouterApiKey.trim());
    localStorage.setItem('sofia_apikey_gemini', geminiApiKey.trim());
    localStorage.setItem('sofia_ai_key', aiApiKey.trim());
    localStorage.setItem('sofia_default_ai_provider', defaultAiProvider);
    localStorage.setItem('sofia_default_ai_free_only', defaultAiFreeOnly.toString());

    // Save Market APIs
    localStorage.setItem('sofia_binance_key', binanceApiKey.trim());
    localStorage.setItem('sofia_binance_secret', binanceApiSecret.trim());
    localStorage.setItem('sofia_dexscreener_url', dexscreenerEndpoint.trim());
    localStorage.setItem('sofia_gmgn_url', gmgnEndpoint.trim());
    localStorage.setItem('sofia_tg_token', telegramToken.trim());
    localStorage.setItem('sofia_tg_chat_id', telegramChatId.trim());

    // Save Wallet & RPC
    localStorage.setItem('sofia_sol_addr', solanaAddress.trim());
    localStorage.setItem('sofia_evm_addr', evmAddress.trim());
    localStorage.setItem('sofia_sol_rpc', solanaRpc.trim());
    localStorage.setItem('sofia_base_rpc', baseRpc.trim());
    localStorage.setItem('sofia_slippage', slippagePct.toString());
    localStorage.setItem('sofia_gas_thresh', gasThresholdIdr.toString());

    // Save Display
    localStorage.setItem('sofia_default_tf', defaultTimeframe);
    localStorage.setItem('sofia_sound_alerts', soundAlerts.toString());

    setSaveNotice('Seluruh konfigurasi pengaturan berhasil disimpan!');
    setTimeout(() => setSaveNotice(''), 3500);
  };

  const handleResetDefaults = () => {
    if (!confirm('Kembalikan semua pengaturan ke nilai default bawaan sistem?')) return;
    handleFillFreeMarketApis();
    setOpenrouterApiKey('');
    setNineRouterApiKey('');
    setGeminiApiKey('');
    setAiApiKey('SOFIA_BUILTIN_ALGORITHMIC_ENGINE');
    setDefaultTimeframe('1d');
    setSoundAlerts(true);
    setSaveNotice('Pengaturan telah di-reset ke nilai bawaan.');
    setTimeout(() => setSaveNotice(''), 3500);
  };

  const NAV_TABS = [
    {
      id: 'ai-api' as const,
      label: 'API AI & Model LLM',
      desc: 'OpenRouter, 9Router, Google Gemini & Fallback Key',
      icon: 'sparkles',
      badge: 'AI ENGINE',
      tone: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
    },
    {
      id: 'market-api' as const,
      label: 'API Pasar & Feed Kripto',
      desc: 'Binance Vision, DexScreener, GMGN & Telegram Alert',
      icon: 'zap',
      badge: 'MARKET FEED',
      tone: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    },
    {
      id: 'display' as const,
      label: 'Layar & Tampilan UI',
      desc: 'Mode Layar Lebar Ultrawide, Timeframe & Audio',
      icon: 'sliders',
      badge: 'DISPLAY',
      tone: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30',
    },
    {
      id: 'wallet' as const,
      label: 'Wallet & Node RPC Web3',
      desc: 'Solana Mainnet, Base Node, Address & Slippage',
      icon: 'wallet',
      badge: 'ON-CHAIN',
      tone: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    },
    {
      id: 'account' as const,
      label: 'Akun & Keamanan Data',
      desc: 'Sesi Deni26, Cache Browser & Reset Sistem',
      icon: 'user',
      badge: 'SECURITY',
      tone: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    },
  ];

  return (
    <>
      <Head>
        <title>Pengaturan Sistem &amp; Kredensial API — Sofia Trading System</title>
      </Head>

      <div className="space-y-5 pb-12">
        {/* HEADER HERO BANNER (DITENGAH LAYAR SEPERTI MENU LAINNYA) */}
        <div className="bg-gradient-to-r from-obsidian-900 via-obsidian-900 to-obsidian-850 border border-obsidian-750 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
              <h1 className="text-xl sm:text-2xl font-black text-slate-100 tracking-tight flex items-center gap-2.5">
                <LucideIcon name="sliders" className="w-6 h-6 text-cyan-400" />
                Pengaturan Sistem &amp; Kredensial
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                SOFIA v3.8
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 max-w-2xl leading-relaxed">
              Konfigurasi terpusat untuk API AI multi-provider, public feed pasar &amp; kripto, node RPC Web3, preferensi tampilan layar, dan sesi akun Deni26.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            {saveNotice && (
              <div className="px-3.5 py-2 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs font-mono font-medium flex items-center gap-1.5 animate-fade-in shadow-sm">
                <LucideIcon name="check" className="w-4 h-4 text-emerald-400" />
                <span>{saveNotice}</span>
              </div>
            )}

            <button
              type="button"
              onClick={handleFillFreeMarketApis}
              className="px-3.5 py-2 rounded-xl bg-obsidian-800 hover:bg-obsidian-750 text-cyan-400 border border-obsidian-700 text-xs font-mono font-medium transition flex items-center gap-1.5"
              title="Isi otomatis seluruh feed dengan Public Gateway gratis"
            >
              <LucideIcon name="refresh-cw" className="w-3.5 h-3.5" />
              <span>⚡ Isi Free API</span>
            </button>

            <button
              type="button"
              onClick={handleSave}
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs shadow-md transition flex items-center gap-1.5"
            >
              <LucideIcon name="check" className="w-4 h-4" />
              <span>Simpan Pengaturan</span>
            </button>
          </div>
        </div>

        {/* DUAL PANE WORKSPACE (DITENGAH KONTEN UTAMA) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* LEFT SIDEBAR: KATEGORI PENGATURAN */}
          <div className="lg:col-span-4 xl:col-span-3 space-y-2">
            <div className="bg-obsidian-900 border border-obsidian-750 rounded-2xl p-3 shadow-md space-y-1.5">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 px-3 py-1.5">
                Kategori Pengaturan
              </div>

              {NAV_TABS.map((tab) => {
                const active = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className={`w-full text-left p-3 rounded-xl border transition group flex items-start gap-3 ${
                      active
                        ? 'bg-obsidian-850 text-white border-cyan-500/50 shadow-sm'
                        : 'bg-obsidian-900/60 hover:bg-obsidian-850/80 text-slate-400 hover:text-slate-200 border-transparent hover:border-obsidian-750'
                    }`}
                  >
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border transition ${
                        active
                          ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                          : 'bg-obsidian-800 text-slate-400 border-obsidian-700 group-hover:text-slate-200'
                      }`}
                    >
                      <LucideIcon name={tab.icon} className="w-4 h-4" />
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-1 mb-0.5">
                        <span className={`font-bold text-xs truncate ${active ? 'text-white' : 'text-slate-200'}`}>
                          {tab.label}
                        </span>
                        <span className={`px-1.5 py-0.2 rounded text-[9px] font-mono font-bold uppercase border ${tab.tone}`}>
                          {tab.badge}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-1 leading-snug">
                        {tab.desc}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Quick Helper Box */}
            <div className="p-4 rounded-2xl bg-obsidian-900/50 border border-obsidian-800 text-slate-400 text-xs space-y-2 shadow-xs">
              <div className="flex items-center gap-1.5 text-slate-200 font-bold text-xs">
                <LucideIcon name="shield-check" className="w-4 h-4 text-emerald-400" />
                <span>Penyimpanan Lokal Aman</span>
              </div>
              <p className="text-[11px] leading-relaxed text-slate-400 font-sans">
                Seluruh kunci API, token notifikasi, dan preferensi tersimpan di peramban browser Anda tanpa dipublikasikan ke server eksternal.
              </p>
              <button
                type="button"
                onClick={handleResetDefaults}
                className="w-full py-2 px-3 rounded-lg border border-obsidian-750 hover:border-rose-500/40 text-slate-400 hover:text-rose-400 text-xs font-mono transition flex items-center justify-center gap-1.5"
              >
                <LucideIcon name="rotate-ccw" className="w-3.5 h-3.5" />
                <span>Reset ke Nilai Bawaan</span>
              </button>
            </div>
          </div>

          {/* RIGHT CONTENT PANE: LEMBAR KONFIGURASI SESUAI TAB */}
          <div className="lg:col-span-8 xl:col-span-9 space-y-5">
            {/* TAB 1: PENGATURAN API AI & MODEL LLM (TERPISAH KHUSUS AI) */}
            {activeTab === 'ai-api' && (
              <div className="space-y-5 animate-fade-in">
                {/* Header Card AI */}
                <div className="p-5 rounded-2xl bg-gradient-to-r from-purple-950/40 via-obsidian-900 to-obsidian-900 border border-purple-500/30 shadow-lg">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-purple-500/20 text-purple-300 border border-purple-500/40">
                          AI ENGINE &amp; MULTI-MODEL
                        </span>
                        <span className="text-xs font-mono text-emerald-400 font-bold">
                          ⚡ 7 Tools SOFIA Terintegrasi
                        </span>
                      </div>
                      <h2 className="text-base sm:text-lg font-bold text-slate-100">
                        Integrasi API AI (OpenRouter, 9Router, Google Gemini)
                      </h2>
                      <p className="text-xs text-slate-400 max-w-2xl leading-relaxed">
                        Model AI pada SOFIA dapat membaca dan mengeksekusi langsung 7 tools internal: analisa saham BEI, koin crypto 24/7, simulasi deposito &amp; obligasi, harga emas, serta sentimen berita pasar.
                      </p>
                    </div>

                    <Link
                      href="/chat"
                      className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-medium text-xs shrink-0 shadow-md transition flex items-center gap-1.5 self-start sm:self-auto"
                    >
                      <LucideIcon name="message-square" className="w-4 h-4" />
                      <span>Buka AI Chat ↗</span>
                    </Link>
                  </div>
                </div>

                {/* Provider 1: OpenRouter */}
                <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 flex items-center justify-center font-bold font-mono text-xs">
                        OR
                      </div>
                      <div>
                        <h3 className="font-bold text-sm text-slate-100">OpenRouter API Key</h3>
                        <p className="text-[11px] text-slate-400">Akses 200+ Model AI termasuk DeepSeek V3, Llama 3.3, Claude, &amp; Gemini</p>
                      </div>
                    </div>
                    <a
                      href="https://openrouter.ai/keys"
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-cyan-400 hover:text-cyan-300 font-mono font-medium flex items-center gap-1 underline"
                    >
                      <span>Dapatkan Kunci</span>
                      <LucideIcon name="external-link" className="w-3 h-3" />
                    </a>
                  </div>

                  <div>
                    <input
                      type="password"
                      value={openrouterApiKey}
                      onChange={(e) => setOpenrouterApiKey(e.target.value)}
                      placeholder="sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (Kosongkan untuk free server fallback)"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 font-mono text-xs focus:outline-none focus:border-cyan-500 transition"
                    />
                    <div className="flex items-center justify-between mt-1.5 text-[11px] text-slate-500">
                      <span>Model gratis bawaan: <code className="text-emerald-400">google/gemini-2.0-flash-exp:free</code></span>
                      <span className={openrouterApiKey ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
                        {openrouterApiKey ? '🟢 Kunci Pribadi Tersimpan' : '⚪ Memakai Kunci Server Default'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Provider 2: 9Router */}
                <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-purple-500/15 border border-purple-500/30 text-purple-400 flex items-center justify-center font-bold font-mono text-xs">
                        9R
                      </div>
                      <div>
                        <h3 className="font-bold text-sm text-slate-100">9Router API Key</h3>
                        <p className="text-[11px] text-slate-400">Multi-Engine Aggregator dengan routing cerdas dan failover instan</p>
                      </div>
                    </div>
                    <a
                      href="https://9router.com"
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-purple-400 hover:text-purple-300 font-mono font-medium flex items-center gap-1 underline"
                    >
                      <span>Dapatkan Kunci</span>
                      <LucideIcon name="external-link" className="w-3 h-3" />
                    </a>
                  </div>

                  <div>
                    <input
                      type="password"
                      value={nineRouterApiKey}
                      onChange={(e) => setNineRouterApiKey(e.target.value)}
                      placeholder="9r-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (Kosongkan untuk free server fallback)"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 font-mono text-xs focus:outline-none focus:border-purple-500 transition"
                    />
                    <div className="flex items-center justify-between mt-1.5 text-[11px] text-slate-500">
                      <span>Endpoint kompatibel OpenAI: <code className="text-purple-400">https://api.9router.com/v1</code></span>
                      <span className={nineRouterApiKey ? 'text-purple-400 font-bold' : 'text-slate-500'}>
                        {nineRouterApiKey ? '🟣 Kunci Pribadi Tersimpan' : '⚪ Memakai Kunci Server Default'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Provider 3: Google Gemini Direct */}
                <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center font-bold font-mono text-xs">
                        G
                      </div>
                      <div>
                        <h3 className="font-bold text-sm text-slate-100">Google Gemini API Key (AI Studio)</h3>
                        <p className="text-[11px] text-slate-400">Koneksi langsung ke Google Gemini 2.0 Flash &amp; Pro (Free tier di Google AI Studio)</p>
                      </div>
                    </div>
                    <a
                      href="https://aistudio.google.com"
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-emerald-400 hover:text-emerald-300 font-mono font-medium flex items-center gap-1 underline"
                    >
                      <span>Google AI Studio Free</span>
                      <LucideIcon name="external-link" className="w-3 h-3" />
                    </a>
                  </div>

                  <div>
                    <input
                      type="password"
                      value={geminiApiKey}
                      onChange={(e) => setGeminiApiKey(e.target.value)}
                      placeholder="AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (Free Tier Google AI Studio)"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 font-mono text-xs focus:outline-none focus:border-emerald-500 transition"
                    />
                    <div className="flex items-center justify-between mt-1.5 text-[11px] text-slate-500">
                      <span>Konteks panjang 1M token &amp; respon kilat</span>
                      <span className={geminiApiKey ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
                        {geminiApiKey ? '🟢 Kunci Gemini Tersimpan' : '⚪ Memakai Kunci Server Default'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Fallback & Defaults */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 space-y-2">
                    <label className="block text-xs font-bold text-slate-300">
                      Provider AI Default Saat Memulai Chat
                    </label>
                    <select
                      value={defaultAiProvider}
                      onChange={(e) => setDefaultAiProvider(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-200 text-xs font-mono focus:outline-none focus:border-cyan-500"
                    >
                      <option value="openrouter">OpenRouter (AI Hub 200+ Model)</option>
                      <option value="9router">9Router (Multi-Engine Pro)</option>
                      <option value="gemini">Google Gemini (Google Cloud)</option>
                    </select>
                  </div>

                  <div className="p-4 rounded-xl bg-obsidian-900 border border-obsidian-750 flex items-center justify-between">
                    <div>
                      <span className="font-bold text-xs text-slate-300 block">
                        Prioritaskan Model Gratis (Free Tier)
                      </span>
                      <span className="text-[11px] text-slate-500">
                        Otomatis aktifkan filter model bebas biaya
                      </span>
                    </div>
                    <input
                      type="checkbox"
                      checked={defaultAiFreeOnly}
                      onChange={(e) => setDefaultAiFreeOnly(e.target.checked)}
                      className="rounded accent-emerald-500 w-4 h-4 cursor-pointer"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: PENGATURAN API PASAR & FEED (TERPISAH NON-AI) */}
            {activeTab === 'market-api' && (
              <div className="space-y-5 animate-fade-in">
                {/* Header Banner Market API */}
                <div className="p-4 rounded-2xl bg-gradient-to-r from-cyan-950/50 via-emerald-950/40 to-obsidian-900 border border-cyan-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-md">
                  <div className="space-y-0.5">
                    <div className="text-sm font-bold text-white flex items-center gap-2">
                      <span className="text-cyan-400">⚡</span> Mode Free Public Market Gateway Aktif
                    </div>
                    <p className="text-xs text-slate-300 max-w-xl leading-relaxed">
                      Binance Public Vision Gateway, DexScreener Latest DEX API, dan GMGN.ai Radar terhubung gratis tanpa perlu akun berbayar.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleFillFreeMarketApis}
                    className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-obsidian-950 font-mono text-xs font-bold shrink-0 transition shadow-sm flex items-center gap-1.5 self-start sm:self-auto"
                  >
                    <LucideIcon name="refresh-cw" className="w-3.5 h-3.5" />
                    <span>⚡ Reset Free Public Feed</span>
                  </button>
                </div>

                {/* Binance Gateway */}
                <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-400 flex items-center justify-center font-bold text-xs font-mono">
                      BN
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-slate-100">Binance Market Gateway (Spot &amp; Orderbook)</h3>
                      <p className="text-[11px] text-slate-400">Feed harga spot global bebas blokir internet positif</p>
                    </div>
                  </div>

                  <div className="space-y-3 font-mono text-xs">
                    <div>
                      <label className="block text-slate-400 font-bold mb-1">
                        Gateway Endpoint URL
                      </label>
                      <input
                        type="text"
                        value={binanceApiKey}
                        onChange={(e) => setBinanceApiKey(e.target.value)}
                        placeholder="https://data-api.binance.vision/api/v3"
                        className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-amber-500"
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 font-bold mb-1">
                        Binance API Secret (Opsional untuk Trading Live)
                      </label>
                      <input
                        type="password"
                        value={binanceApiSecret}
                        onChange={(e) => setBinanceApiSecret(e.target.value)}
                        placeholder="PUBLIC_FREE_GATEWAY"
                        className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-amber-500"
                      />
                    </div>
                  </div>
                </div>

                {/* DexScreener & GMGN */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-2 font-mono text-xs">
                    <h4 className="font-bold text-slate-200">DexScreener API Endpoint</h4>
                    <p className="text-[11px] text-slate-400 font-sans">Scanning likuiditas token baru Solana, BSC, &amp; Base</p>
                    <input
                      type="text"
                      value={dexscreenerEndpoint}
                      onChange={(e) => setDexscreenerEndpoint(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-2 font-mono text-xs">
                    <h4 className="font-bold text-slate-200">GMGN.ai Meme Feed Endpoint</h4>
                    <p className="text-[11px] text-slate-400 font-sans">Radar tren meme &amp; volume orderflow real-time</p>
                    <input
                      type="text"
                      value={gmgnEndpoint}
                      onChange={(e) => setGmgnEndpoint(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                </div>

                {/* Telegram Alerts */}
                <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-3 font-mono text-xs">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-sky-500/15 border border-sky-500/30 text-sky-400 flex items-center justify-center font-bold text-xs">
                      TG
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-slate-100">Telegram Bot Notifications (Alerts Eksekusi)</h3>
                      <p className="text-[11px] text-slate-400 font-sans">Notifikasi real-time saat bot membeli token baru atau mencapai Take Profit</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    <div>
                      <label className="block text-slate-400 font-bold mb-1">
                        Telegram Bot Token
                      </label>
                      <input
                        type="text"
                        value={telegramToken}
                        onChange={(e) => setTelegramToken(e.target.value)}
                        placeholder="123456789:ABCDefGHIjkLM..."
                        className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-sky-500"
                      />
                    </div>

                    <div>
                      <label className="block text-slate-400 font-bold mb-1">
                        Telegram Chat ID
                      </label>
                      <input
                        type="text"
                        value={telegramChatId}
                        onChange={(e) => setTelegramChatId(e.target.value)}
                        placeholder="987654321"
                        className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-sky-500"
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: LAYAR & TAMPILAN UI */}
            {activeTab === 'display' && (
              <div className="space-y-5 animate-fade-in font-mono">
                <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-base font-bold text-slate-100">
                        Mode Layar Lebar Penuh (Ultrawide Desktop Mode)
                      </h3>
                      <p className="text-xs text-slate-400 mt-1 font-sans leading-relaxed max-w-xl">
                        Memanfaatkan 100% lebar layar monitor (1080p, 2K, 4K, 21:9 ultrawide). Tabel, kartu perbandingan, dan radar orderflow akan melebar secara proporsional.
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => toggleUltrawide()}
                      className={`relative inline-flex h-7 w-12 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                        isUltrawide ? 'bg-cyan-500' : 'bg-obsidian-800'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-6 w-6 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          isUltrawide ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>

                  <div className="text-xs text-cyan-400 bg-cyan-500/10 p-3 rounded-xl border border-cyan-500/20 flex items-center justify-between">
                    <span>Status Layar Lebar: <strong>{isUltrawide ? 'AKTIF (100% Tepi Layar Penuh)' : 'STANDAR (Centered Fixed Container)'}</strong></span>
                    <span className="text-[10px] bg-obsidian-900 px-2 py-0.5 rounded border border-cyan-500/30">
                      Shortcut: Tombol Maximize di Header
                    </span>
                  </div>
                </div>

                <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-3">
                  <label className="block text-sm font-bold text-slate-200">
                    Default Timeframe Grafik Saham &amp; Kripto
                  </label>
                  <p className="text-xs text-slate-400 font-sans">
                    Timeframe default yang akan dibuka pertama kali saat memuat chart analisa teknikal
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 pt-1">
                    {[
                      { id: '15m', label: '15 Menit', desc: 'Scalping' },
                      { id: '1h', label: '1 Jam', desc: 'Intraday' },
                      { id: '4h', label: '4 Jam', desc: 'Swing' },
                      { id: '1d', label: '1 Hari', desc: 'Standar Daily' },
                      { id: '1w', label: '1 Minggu', desc: 'Macro Cycle' },
                    ].map((tf) => (
                      <button
                        key={tf.id}
                        type="button"
                        onClick={() => setDefaultTimeframe(tf.id)}
                        className={`p-3 rounded-xl border text-center transition ${
                          defaultTimeframe === tf.id
                            ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-bold shadow-xs'
                            : 'bg-obsidian-950 hover:bg-obsidian-850 text-slate-400 border-obsidian-750'
                        }`}
                      >
                        <span className="block text-xs font-bold">{tf.label}</span>
                        <span className="text-[10px] text-slate-500 block font-sans">{tf.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm flex items-center justify-between">
                  <div>
                    <h4 className="font-bold text-sm text-slate-200">Suara Notifikasi Audio Bot</h4>
                    <p className="text-xs text-slate-400 font-sans mt-0.5">
                      Bunyikan nada audio saat sniper berhasil membeli koin atau saat sinyal breakout terdeteksi
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={soundAlerts}
                    onChange={(e) => setSoundAlerts(e.target.checked)}
                    className="rounded accent-cyan-500 w-4 h-4 cursor-pointer"
                  />
                </div>
              </div>
            )}

            {/* TAB 4: WALLET & RPC */}
            {activeTab === 'wallet' && (
              <div className="space-y-5 animate-fade-in font-mono text-xs">
                <div className="p-4 rounded-2xl bg-gradient-to-r from-emerald-950/50 to-cyan-950/40 border border-emerald-500/30 flex items-center justify-between gap-4 shadow-md">
                  <div>
                    <div className="text-sm font-bold text-white flex items-center gap-2">
                      <span className="text-emerald-400">🌐</span> Public Mainnet RPC Terkoneksi
                    </div>
                    <p className="text-xs text-slate-300 font-sans mt-0.5">
                      Solana Foundation Beta Node &amp; Base Official Mainnet RPC aktif secara default tanpa perlu biaya node berbayar.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleFillFreeMarketApis}
                    className="px-3.5 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 font-bold shrink-0 transition"
                  >
                    ⚡ Reset Free RPC
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-2">
                    <label className="block text-slate-300 font-bold">Solana Public RPC Node</label>
                    <input
                      type="text"
                      value={solanaRpc}
                      onChange={(e) => setSolanaRpc(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-emerald-500"
                    />
                    <span className="text-[10px] text-slate-500 block">Default: https://api.mainnet-beta.solana.com</span>
                  </div>

                  <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-2">
                    <label className="block text-slate-300 font-bold">Base EVM Official RPC Node</label>
                    <input
                      type="text"
                      value={baseRpc}
                      onChange={(e) => setBaseRpc(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-emerald-500"
                    />
                    <span className="text-[10px] text-slate-500 block">Default: https://mainnet.base.org</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-2">
                    <label className="block text-slate-300 font-bold">Solana Public Address</label>
                    <input
                      type="text"
                      value={solanaAddress}
                      onChange={(e) => setSolanaAddress(e.target.value)}
                      placeholder="Base58 Solana Address..."
                      className="w-full px-3.5 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-2">
                    <label className="block text-slate-300 font-bold">EVM Public Address (Base / ETH)</label>
                    <input
                      type="text"
                      value={evmAddress}
                      onChange={(e) => setEvmAddress(e.target.value)}
                      placeholder="0x..."
                      className="w-full px-3.5 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-2">
                    <label className="block text-slate-300 font-bold">Default Slippage Tolerance (%)</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0.1"
                      max="50"
                      value={slippagePct}
                      onChange={(e) => setSlippagePct(parseFloat(e.target.value) || 1.5)}
                      className="w-full px-3.5 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-amber-500"
                    />
                  </div>

                  <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-2">
                    <label className="block text-slate-300 font-bold">Gas Fee Threshold (Rupiah)</label>
                    <input
                      type="number"
                      step="1000"
                      value={gasThresholdIdr}
                      onChange={(e) => setGasThresholdIdr(parseInt(e.target.value, 10) || 10000)}
                      className="w-full px-3.5 py-2 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs focus:outline-none focus:border-amber-500"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* TAB 5: AKUN & KEAMANAN */}
            {activeTab === 'account' && (
              <div className="space-y-5 animate-fade-in font-mono text-xs">
                <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-base">
                      D26
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-slate-100">Deni26 (SOFIA Trade Master)</h3>
                      <p className="text-[11px] text-slate-400 font-sans">Role: Administrator • Hak Akses Penuh ke Sistem &amp; Eksekusi Bot</p>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-obsidian-950 border border-obsidian-800 text-slate-400 space-y-1 font-sans text-xs">
                    <p>• Status Autentikasi: <span className="text-emerald-400 font-mono font-bold">AKTIF / LOCAL SESSION</span></p>
                    <p>• Database Sync: <span className="text-cyan-400 font-mono font-bold">PostgreSQL / Neon Cloud Sync Ready</span></p>
                  </div>
                </div>

                <div className="p-5 rounded-2xl bg-obsidian-900 border border-obsidian-750 shadow-sm space-y-3">
                  <h4 className="font-bold text-slate-200">Manajemen Cache &amp; Reset Data</h4>
                  <p className="text-slate-400 font-sans leading-relaxed">
                    Jika Anda mengalami kendala tampilan atau ingin membersihkan seluruh kredensial lokal dari peramban ini:
                  </p>
                  <div className="flex flex-wrap items-center gap-3 pt-2">
                    <button
                      type="button"
                      onClick={handleResetDefaults}
                      className="px-4 py-2 rounded-xl bg-obsidian-800 hover:bg-obsidian-750 text-slate-200 border border-obsidian-700 transition"
                    >
                      Reset Konfigurasi ke Bawaan
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (!confirm('Hapus seluruh sesi token dan reload halaman?')) return;
                        localStorage.clear();
                        window.location.reload();
                      }}
                      className="px-4 py-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 transition"
                    >
                      Hapus Seluruh Cache &amp; Logout
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
