import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { api, setToken, getToken } from '@/lib/api';
import {
  detectChromeExtensions,
  connectSolanaExtension,
  connectEvmExtension,
  shortenAddress,
} from '@/lib/web3';
import { LucideIcon } from '@/components/LucideIcon';

interface LoginPortalProps {
  onSuccess?: () => void;
}

export function LoginPortal({ onSuccess }: LoginPortalProps) {
  const router = useRouter();
  const [password, setPassword] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [loginError, setLoginError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [extDetected, setExtDetected] = useState({ anySolana: false, anyEvm: false });

  useEffect(() => {
    const det = detectChromeExtensions();
    setExtDetected({ anySolana: det.anySolana, anyEvm: det.anyEvm });
  }, []);

  const completeLogin = (token: string) => {
    setToken(token);
    if (onSuccess) {
      onSuccess();
    } else {
      router.push('/');
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    setLoading(true);
    try {
      const res = await api.login(password || 'changeme');
      completeLogin(res.token);
    } catch (err: any) {
      setLoginError(err?.message || 'Password operator tidak sesuai');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickDemoLogin = async () => {
    setPassword('changeme');
    setLoginError('');
    setLoading(true);
    try {
      const res = await api.login('changeme');
      completeLogin(res.token);
    } catch (err: any) {
      setLoginError(err?.message || 'Gagal login cepat');
    } finally {
      setLoading(false);
    }
  };

  const handleWeb3ExtensionLogin = async (type: 'solana' | 'evm') => {
    setLoginError('');
    setLoading(true);
    try {
      const authRes = await api.login(password || 'changeme');
      setToken(authRes.token);
      if (type === 'solana') {
        await connectSolanaExtension('phantom');
      } else {
        await connectEvmExtension('Base', 'metamask');
      }
      completeLogin(authRes.token);
    } catch (err: any) {
      setLoginError(
        err?.message ||
          'Pastikan ekstensi Phantom / MetaMask aktif di Chrome atau gunakan Login Password Operator di atas.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-obsidian-950 grid-bg-overlay flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md bg-obsidian-900/95 backdrop-blur-xl border border-obsidian-700 rounded-2xl p-6 sm:p-7 space-y-5 shadow-glow-emerald relative z-10">
        {/* Brand Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              <LucideIcon name="crosshair" className="w-5 h-5" />
              <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
            </div>
            <div>
              <div className="font-extrabold tracking-wider text-base text-slate-100 flex items-center gap-1.5 font-mono">
                SOFIA<span className="text-emerald-400">TRENCHES</span>
                <span className="text-[9px] uppercase px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded font-sans font-semibold">
                  v3.8 PRO
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Dual-Engine Paper &amp; Live On-Chain Meme Sniper
              </p>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-[10px] font-mono font-bold">
            PWA READY
          </span>
        </div>

        <p className="text-xs text-slate-400 leading-relaxed">
          Masuk ke <strong>Sniper Command Center</strong> menggunakan Password Operator (default:{' '}
          <code className="text-emerald-400 font-mono font-bold">changeme</code>) atau hubungkan langsung dengan ekstensi dompet Chrome Anda.
        </p>

        {loginError && (
          <div className="p-3 rounded-xl bg-rose-950/70 border border-rose-500/40 text-rose-200 text-xs font-mono">
            ⚠️ {loginError}
          </div>
        )}

        {/* Password Login Form */}
        <form onSubmit={handleLogin} className="space-y-3.5">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-bold">
                Operator Password
              </label>
              <button
                type="button"
                onClick={handleQuickDemoLogin}
                className="text-[10px] font-mono text-emerald-400 hover:underline"
              >
                ⚡ Masuk Cepat (Default: changeme)
              </button>
            </div>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Masukkan password operator (changeme)..."
                className="w-full px-3.5 py-2.5 pr-16 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs font-mono focus:outline-none focus:border-emerald-500"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2.5 top-2 px-2 py-0.5 rounded bg-obsidian-800 text-[10px] font-mono text-slate-400 hover:text-white"
              >
                {showPassword ? 'HIDE' : 'SHOW'}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-400 via-teal-400 to-cyan-400 hover:from-emerald-300 hover:to-cyan-300 text-obsidian-950 font-extrabold text-xs uppercase tracking-wider shadow-glow-emerald transition"
          >
            {loading ? '⏳ Memverifikasi Akses...' : '⚡ Unlock Sniper Command Center'}
          </button>
        </form>

        {/* Divider */}
        <div className="relative flex py-1 items-center">
          <div className="flex-grow border-t border-obsidian-800"></div>
          <span className="flex-shrink mx-3 text-[10px] font-mono uppercase text-slate-500">
            Atau Login + Connect Ekstensi Chrome
          </span>
          <div className="flex-grow border-t border-obsidian-800"></div>
        </div>

        {/* Web3 Chrome Extension Login Buttons */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 font-mono text-xs">
          <button
            type="button"
            onClick={() => handleWeb3ExtensionLogin('solana')}
            className="py-2.5 px-3 rounded-xl bg-obsidian-950 hover:bg-obsidian-800 border border-obsidian-700 hover:border-purple-500/50 text-purple-300 font-bold flex items-center justify-center gap-2 transition"
          >
            <span>👻 Phantom / Solflare</span>
            {extDetected.anySolana && (
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            )}
          </button>
          <button
            type="button"
            onClick={() => handleWeb3ExtensionLogin('evm')}
            className="py-2.5 px-3 rounded-xl bg-obsidian-950 hover:bg-obsidian-800 border border-obsidian-700 hover:border-orange-500/50 text-orange-300 font-bold flex items-center justify-center gap-2 transition"
          >
            <span>🦊 MetaMask / Rabby</span>
            {extDetected.anyEvm && (
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            )}
          </button>
        </div>

        {/* System Status Footer */}
        <div className="pt-2 border-t border-obsidian-800 flex items-center justify-between text-[10px] font-mono text-slate-500">
          <span className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
            Neonbase Cloud Connected
          </span>
          <span>Mode Paper &amp; Live 100% Aktif</span>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  const router = useRouter();

  useEffect(() => {
    if (getToken()) {
      router.replace('/');
    }
  }, [router]);

  return <LoginPortal onSuccess={() => router.replace('/')} />;
}
