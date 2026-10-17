import React, { useState, useEffect } from 'react';
import {
  ConnectedExtensionWallet,
  DetectedExtensions,
  detectChromeExtensions,
  connectSolanaExtension,
  connectEvmExtension,
  syncExtensionWalletWithBackend,
  saveExtensionWallet,
  shortenAddress,
} from '@/lib/web3';

interface WalletConnectModalProps {
  isOpen: boolean;
  onClose: () => void;
  connectedWallet: ConnectedExtensionWallet | null;
  onConnected?: (wallet: ConnectedExtensionWallet) => void;
}

export function WalletConnectModal({
  isOpen,
  onClose,
  connectedWallet,
  onConnected,
}: WalletConnectModalProps) {
  const [detected, setDetected] = useState<DetectedExtensions>({
    phantom: false,
    solflare: false,
    backpack: false,
    metamask: false,
    rabby: false,
    anySolana: false,
    anyEvm: false,
  });
  const [evmChain, setEvmChain] = useState<'Base' | 'Ethereum' | 'BSC'>('Base');
  const [customAddr, setCustomAddr] = useState<string>('');
  const [customChain, setCustomChain] = useState<'Solana' | 'Base' | 'Ethereum' | 'BSC'>('Solana');
  const [loading, setLoading] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [successMsg, setSuccessMsg] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      setDetected(detectChromeExtensions());
      setErrorMsg('');
      setSuccessMsg('');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleConnectSolana = async (provider: 'phantom' | 'solflare' | 'backpack') => {
    setErrorMsg('');
    setSuccessMsg('');
    setLoading(provider);
    try {
      const w = await connectSolanaExtension(provider);
      setSuccessMsg(
        `✅ Berhasil terhubung ke ${w.providerName}: ${shortenAddress(w.address)} (Solana Mainnet)`
      );
      onConnected?.(w);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Gagal menghubungkan ekstensi Solana');
    } finally {
      setLoading('');
    }
  };

  const handleConnectEvm = async (provider: 'metamask' | 'rabby') => {
    setErrorMsg('');
    setSuccessMsg('');
    setLoading(provider);
    try {
      const w = await connectEvmExtension(evmChain, provider);
      setSuccessMsg(
        `✅ Berhasil terhubung ke ${w.providerName}: ${shortenAddress(w.address)} (${w.chain})`
      );
      onConnected?.(w);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Gagal menghubungkan ekstensi EVM');
    } finally {
      setLoading('');
    }
  };

  const handleInstantExtensionBridge = async (
    presetProvider: 'phantom' | 'metamask',
    addr: string,
    chain: 'Solana' | 'Base'
  ) => {
    setErrorMsg('');
    setSuccessMsg('');
    setLoading('instant');
    try {
      const extWallet: ConnectedExtensionWallet = {
        providerId: presetProvider,
        providerName: presetProvider === 'phantom' ? 'Phantom Chrome' : 'MetaMask Chrome',
        address: addr,
        chain,
        token: chain === 'Solana' ? 'SOL' : 'ETH',
        connectedAt: new Date().toISOString(),
      };
      const synced = await syncExtensionWalletWithBackend(extWallet);
      setSuccessMsg(
        `✅ Terhubung ke ${synced.providerName} (${shortenAddress(synced.address)}) & disinkronkan ke Hot Wallet Neonbase!`
      );
      onConnected?.(synced);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Gagal menghubungkan dompet');
    } finally {
      setLoading('');
    }
  };

  const handleManualAddressConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customAddr.trim()) return;
    setErrorMsg('');
    setSuccessMsg('');
    setLoading('manual');
    try {
      const addr = customAddr.trim();
      const isEvm = addr.startsWith('0x');
      const resolvedChain = isEvm && customChain === 'Solana' ? 'Base' : customChain;
      const extWallet: ConnectedExtensionWallet = {
        providerId: isEvm ? 'metamask' : 'phantom',
        providerName: isEvm ? 'MetaMask / EVM Direct' : 'Phantom / Solana Direct',
        address: addr,
        chain: resolvedChain,
        token: resolvedChain === 'Solana' ? 'SOL' : resolvedChain === 'BSC' ? 'BNB' : 'ETH',
        connectedAt: new Date().toISOString(),
      };
      const synced = await syncExtensionWalletWithBackend(extWallet);
      setCustomAddr('');
      setSuccessMsg(
        `✅ Alamat ${shortenAddress(synced.address)} (${synced.chain}) berhasil dihubungkan & disinkronkan ke RPC Mainnet!`
      );
      onConnected?.(synced);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Gagal menghubungkan alamat');
    } finally {
      setLoading('');
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-obsidian-900 border border-obsidian-700 rounded-2xl shadow-2xl overflow-hidden font-mono text-xs max-h-[92vh] flex flex-col">
        {/* Modal Header */}
        <div className="px-4 py-3.5 bg-obsidian-950 border-b border-obsidian-800 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-extrabold text-white uppercase tracking-wider flex items-center gap-2">
              <span>🔌 Hubungkan Ekstensi Wallet Chrome</span>
              <span className="px-1.5 py-0.5 text-[9px] rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                WEB3 PROVIDER
              </span>
            </h2>
            <p className="text-[11px] text-slate-400 font-sans mt-0.5">
              Hubungkan langsung ke ekstensi Phantom, Solflare, MetaMask, atau Rabby di Google Chrome.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-7 h-7 rounded-lg bg-obsidian-800 hover:bg-obsidian-700 text-slate-300 hover:text-white flex items-center justify-center font-bold"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 space-y-4 overflow-y-auto">
          {successMsg && (
            <div className="p-3 rounded-xl bg-emerald-950/70 border border-emerald-500/40 text-emerald-200 text-xs">
              {successMsg}
            </div>
          )}
          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-950/70 border border-rose-500/40 text-rose-200 text-xs">
              ⚠️ {errorMsg}
            </div>
          )}

          {/* Active Connected Banner */}
          {connectedWallet && (
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-[10px] text-emerald-400 font-bold uppercase">
                  ✓ EKSTENSI TERHUBUNG SAAT INI
                </div>
                <div className="text-xs font-extrabold text-white mt-0.5">
                  {connectedWallet.providerName} • {connectedWallet.chain}
                </div>
                <div className="text-[11px] text-cyan-300 break-all">{connectedWallet.address}</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  saveExtensionWallet(null);
                  setSuccessMsg('🔌 Koneksi ekstensi wallet telah diputuskan.');
                }}
                className="px-2.5 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-600 text-rose-300 hover:text-white border border-rose-500/40 font-bold text-[10px] transition"
              >
                Putuskan
              </button>
            </div>
          )}

          {/* Section 1: Solana Chrome Extensions */}
          <div className="space-y-2">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
              <span>1. Ekstensi Solana (window.solana / Phantom / Solflare)</span>
              <span className={detected.anySolana ? 'text-emerald-400' : 'text-amber-400'}>
                {detected.anySolana ? '● Ekstensi Terdeteksi' : '○ Siap Hubungkan'}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => handleConnectSolana('phantom')}
                disabled={loading === 'phantom'}
                className="p-3 rounded-xl bg-obsidian-950 hover:bg-obsidian-800 border border-obsidian-700 hover:border-purple-500/60 text-left transition flex flex-col justify-between gap-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-extrabold text-purple-300">👻 Phantom</span>
                  <span
                    className={`text-[9px] px-1.5 py-0.2 rounded ${
                      detected.phantom
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-obsidian-800 text-slate-400'
                    }`}
                  >
                    {detected.phantom ? 'INSTALLED' : 'CHROME'}
                  </span>
                </div>
                <span className="text-[10px] text-slate-400 font-sans">
                  Connect langsung via window.phantom.solana
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleConnectSolana('solflare')}
                disabled={loading === 'solflare'}
                className="p-3 rounded-xl bg-obsidian-950 hover:bg-obsidian-800 border border-obsidian-700 hover:border-amber-500/60 text-left transition flex flex-col justify-between gap-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-extrabold text-amber-300">☀️ Solflare</span>
                  <span
                    className={`text-[9px] px-1.5 py-0.2 rounded ${
                      detected.solflare
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-obsidian-800 text-slate-400'
                    }`}
                  >
                    {detected.solflare ? 'INSTALLED' : 'CHROME'}
                  </span>
                </div>
                <span className="text-[10px] text-slate-400 font-sans">
                  Connect langsung via window.solflare
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleConnectSolana('backpack')}
                disabled={loading === 'backpack'}
                className="p-3 rounded-xl bg-obsidian-950 hover:bg-obsidian-800 border border-obsidian-700 hover:border-rose-500/60 text-left transition flex flex-col justify-between gap-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-extrabold text-rose-300">🎒 Backpack</span>
                  <span
                    className={`text-[9px] px-1.5 py-0.2 rounded ${
                      detected.backpack
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-obsidian-800 text-slate-400'
                    }`}
                  >
                    {detected.backpack ? 'INSTALLED' : 'CHROME'}
                  </span>
                </div>
                <span className="text-[10px] text-slate-400 font-sans">
                  Connect langsung via window.backpack
                </span>
              </button>
            </div>
          </div>

          {/* Section 2: EVM Chrome Extensions (MetaMask / Rabby) */}
          <div className="space-y-2 pt-2 border-t border-obsidian-800">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                2. Ekstensi EVM (window.ethereum / MetaMask / Rabby)
              </span>
              <div className="flex items-center gap-1">
                {(['Base', 'Ethereum', 'BSC'] as const).map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setEvmChain(c)}
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      evmChain === c
                        ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                        : 'bg-obsidian-950 text-slate-400 border border-obsidian-800'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleConnectEvm('metamask')}
                disabled={loading === 'metamask'}
                className="p-3 rounded-xl bg-obsidian-950 hover:bg-obsidian-800 border border-obsidian-700 hover:border-orange-500/60 text-left transition flex flex-col justify-between gap-1"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-extrabold text-orange-300">🦊 MetaMask Chrome</span>
                  <span
                    className={`text-[9px] px-1.5 py-0.2 rounded ${
                      detected.metamask
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-obsidian-800 text-slate-400'
                    }`}
                  >
                    {detected.metamask ? 'INSTALLED' : evmChain.toUpperCase()}
                  </span>
                </div>
                <span className="text-[10px] text-slate-400 font-sans">
                  eth_requestAccounts ({evmChain} Mainnet)
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleConnectEvm('rabby')}
                disabled={loading === 'rabby'}
                className="p-3 rounded-xl bg-obsidian-950 hover:bg-obsidian-800 border border-obsidian-700 hover:border-cyan-500/60 text-left transition flex flex-col justify-between gap-1"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-extrabold text-cyan-300">🐰 Rabby / Coinbase</span>
                  <span
                    className={`text-[9px] px-1.5 py-0.2 rounded ${
                      detected.rabby || detected.anyEvm
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-obsidian-800 text-slate-400'
                    }`}
                  >
                    {detected.rabby || detected.anyEvm ? 'INSTALLED' : evmChain.toUpperCase()}
                  </span>
                </div>
                <span className="text-[10px] text-slate-400 font-sans">
                  Connect multi-chain EVM via window.ethereum
                </span>
              </button>
            </div>
          </div>

          {/* Section 3: Direct Public Key / Address Bridge (Works even on mobile or without extension installed) */}
          <form
            onSubmit={handleManualAddressConnect}
            className="space-y-2 pt-2 border-t border-obsidian-800"
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                3. Direct Wallet Bridge / Paste Public Address Asli Anda
              </span>
              <span className="text-[10px] text-emerald-400">Auto-Sync Mainnet RPC</span>
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <select
                value={customChain}
                onChange={(e) => setCustomChain(e.target.value as any)}
                className="px-2.5 py-2 rounded-lg bg-obsidian-950 border border-obsidian-700 text-white"
              >
                <option value="Solana">Solana</option>
                <option value="Base">Base</option>
                <option value="Ethereum">Ethereum</option>
                <option value="BSC">BSC</option>
              </select>
              <input
                type="text"
                value={customAddr}
                onChange={(e) => setCustomAddr(e.target.value)}
                placeholder="Tempel alamat publik Solana / 0x..."
                className="flex-1 px-3 py-2 rounded-lg bg-obsidian-950 border border-obsidian-700 text-emerald-300 focus:outline-none focus:border-emerald-500"
              />
              <button
                type="submit"
                disabled={loading === 'manual'}
                className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 font-extrabold shrink-0 transition"
              >
                Hubungkan
              </button>
            </div>
          </form>
        </div>

        {/* Modal Footer */}
        <div className="px-4 py-2.5 bg-obsidian-950 border-t border-obsidian-800 flex flex-wrap items-center justify-between gap-2 text-[10px] text-slate-400">
          <span>Belum punya ekstensi? Unduh resmi di Chrome Web Store:</span>
          <div className="flex items-center gap-2.5">
            <a
              href="https://phantom.app/download"
              target="_blank"
              rel="noreferrer"
              className="text-purple-400 hover:underline"
            >
              Phantom ↗
            </a>
            <a
              href="https://metamask.io/download/"
              target="_blank"
              rel="noreferrer"
              className="text-orange-400 hover:underline"
            >
              MetaMask ↗
            </a>
            <a
              href="https://solflare.com/"
              target="_blank"
              rel="noreferrer"
              className="text-amber-400 hover:underline"
            >
              Solflare ↗
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
