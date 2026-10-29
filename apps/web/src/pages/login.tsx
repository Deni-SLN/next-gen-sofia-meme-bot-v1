import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import { api, setToken, getToken } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';

const MAX_FAILED_ATTEMPTS = 5;
const LOCKOUT_DURATION_MS = 15 * 60 * 1000; // 15 menit
const STORAGE_KEY_ATTEMPTS = 'sofia_login_failed_attempts';
const STORAGE_KEY_LOCKOUT = 'sofia_login_locked_until';

interface LoginPortalProps {
  onSuccess?: () => void;
}

export function LoginPortal({ onSuccess }: LoginPortalProps) {
  const router = useRouter();
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [loginError, setLoginError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [lockRemainingSec, setLockRemainingSec] = useState<number>(0);

  // Cek status lockout dari localStorage saat load
  const checkLockoutStatus = () => {
    if (typeof window === 'undefined') return 0;
    const lockedUntilStr = localStorage.getItem(STORAGE_KEY_LOCKOUT);
    if (lockedUntilStr) {
      const lockedUntil = parseInt(lockedUntilStr, 10);
      const remainingMs = lockedUntil - Date.now();
      if (remainingMs > 0) {
        const remainingSec = Math.ceil(remainingMs / 1000);
        setLockRemainingSec(remainingSec);
        return remainingSec;
      } else {
        // Lockout berakhir, bersihkan
        localStorage.removeItem(STORAGE_KEY_LOCKOUT);
        localStorage.removeItem(STORAGE_KEY_ATTEMPTS);
        setLockRemainingSec(0);
        return 0;
      }
    }
    return 0;
  };

  useEffect(() => {
    checkLockoutStatus();
    const interval = setInterval(() => {
      checkLockoutStatus();
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const completeLogin = (token: string) => {
    // Reset counter gagal login jika berhasil
    if (typeof window !== 'undefined') {
      localStorage.removeItem(STORAGE_KEY_ATTEMPTS);
      localStorage.removeItem(STORAGE_KEY_LOCKOUT);
    }
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

    // Periksa apakah sedang terkunci
    const remaining = checkLockoutStatus();
    if (remaining > 0) {
      const minutes = Math.floor(remaining / 60);
      const seconds = remaining % 60;
      setLoginError(
        `Akses terkunci karena 5x kesalahan login berturut-turut. Silakan tunggu ${minutes} menit ${seconds} detik.`
      );
      return;
    }

    if (!username.trim()) {
      setLoginError('Username wajib diisi.');
      return;
    }

    if (!password.trim()) {
      setLoginError('Password wajib diisi.');
      return;
    }

    setLoading(true);
    try {
      const res = await api.login(password.trim(), username.trim());
      completeLogin(res.token);
    } catch (err: any) {
      // Catat percobaan gagal
      let currentAttempts = 1;
      if (typeof window !== 'undefined') {
        const savedAttempts = parseInt(localStorage.getItem(STORAGE_KEY_ATTEMPTS) || '0', 10);
        currentAttempts = savedAttempts + 1;
        localStorage.setItem(STORAGE_KEY_ATTEMPTS, currentAttempts.toString());

        if (currentAttempts >= MAX_FAILED_ATTEMPTS) {
          const lockTime = Date.now() + LOCKOUT_DURATION_MS;
          localStorage.setItem(STORAGE_KEY_LOCKOUT, lockTime.toString());
          setLockRemainingSec(Math.ceil(LOCKOUT_DURATION_MS / 1000));
          setLoginError(
            `Akses terkunci! Anda telah 5 kali salah memasukkan informasi login. Harap tunggu 15 menit sebelum mencoba kembali.`
          );
          setLoading(false);
          return;
        }
      }

      const sisa = MAX_FAILED_ATTEMPTS - currentAttempts;
      setLoginError(
        `${err?.message || 'Username atau Password tidak sesuai.'} (Sisa percobaan: ${sisa}x sebelum terkunci 15 menit)`
      );
    } finally {
      setLoading(false);
    }
  };

  const isLocked = lockRemainingSec > 0;
  const lockMinutes = Math.floor(lockRemainingSec / 60);
  const lockSeconds = lockRemainingSec % 60;

  return (
    <>
      <Head>
        <title>Login — Sofia Market 4.1.3 (SFIA 4.1.3)</title>
      </Head>
      <div className="min-h-screen bg-obsidian-950 grid-bg-overlay flex items-center justify-center p-4 relative overflow-hidden">
        {/* Glow ambient background */}
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="w-full max-w-md bg-obsidian-900/95 backdrop-blur-xl border border-obsidian-800 rounded-2xl p-7 sm:p-8 space-y-6 shadow-2xl relative z-10">
          {/* Brand Header Clean */}
          <div className="text-center space-y-2">
            <div className="relative inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-emerald-500/20 via-teal-500/20 to-cyan-500/20 border border-emerald-500/40 text-emerald-400 mb-1 shadow-glow-emerald">
              <svg viewBox="0 0 48 48" className="w-10 h-10" fill="none">
                {/* Candle 1 (Awal) */}
                <line x1="11" y1="26" x2="11" y2="40" stroke="#34d399" strokeWidth="1.5" strokeLinecap="round" />
                <rect x="8.5" y="29" width="5" height="8" rx="1" fill="#10b981" stroke="#34d399" strokeWidth="1" />

                {/* Candle 2 (Akumulasi Rebound) */}
                <line x1="22" y1="18" x2="22" y2="34" stroke="#34d399" strokeWidth="1.5" strokeLinecap="round" />
                <rect x="19.5" y="21" width="5" height="10" rx="1" fill="#10b981" stroke="#34d399" strokeWidth="1" />

                {/* Candle 3 (Impulsif Bullish Breakout) */}
                <line x1="33" y1="9" x2="33" y2="28" stroke="#34d399" strokeWidth="1.5" strokeLinecap="round" />
                <rect x="30.5" y="12" width="5" height="12" rx="1" fill="#10b981" stroke="#34d399" strokeWidth="1" />

                {/* Bullish Trend Curve & Arrow */}
                <path
                  d="M6 38 C 15 35, 23 26, 40 9"
                  stroke="#22d3ee"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
                <polyline
                  points="32,9 41,9 41,18"
                  stroke="#22d3ee"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />

                {/* Glowing Spark at Target Peak */}
                <circle cx="41" cy="9" r="2.5" fill="#38bdf8" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center justify-center gap-2">
              Sofia Market 4.1.3
            </h1>
            <p className="text-xs text-slate-400 font-mono tracking-wide">
              by <span className="text-emerald-400 font-semibold">deni sln</span>
            </p>
          </div>

          {/* Lockout Notice */}
          {isLocked && (
            <div className="p-4 rounded-xl bg-rose-950/70 border border-rose-500/50 text-rose-200 text-xs font-mono space-y-1">
              <div className="font-bold flex items-center gap-1.5 text-rose-300">
                <LucideIcon name="shield-alert" className="w-4 h-4" />
                AKUN TERKUNCI (SECURITY LOCKOUT)
              </div>
              <p>
                Terdeteksi 5 kali kegagalan login. Sistem mengunci akses selama 15 menit demi keamanan.
              </p>
              <div className="pt-2 text-rose-300 font-bold text-sm">
                Waktu tunggu:{' '}
                <span className="text-amber-400 font-mono">
                  {String(lockMinutes).padStart(2, '0')}:{String(lockSeconds).padStart(2, '0')}
                </span>
              </div>
            </div>
          )}

          {/* Regular Error Notification */}
          {!isLocked && loginError && (
            <div className="p-3.5 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-200 text-xs font-mono flex items-start gap-2">
              <span className="text-rose-400 font-bold text-sm">⚠️</span>
              <div>{loginError}</div>
            </div>
          )}

          {/* Clean User & Password Login Form */}
          <form onSubmit={handleLogin} className="space-y-4">
            {/* Username Input */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5 font-mono">
                Username
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-3 text-slate-500">
                  <LucideIcon name="user" className="w-4 h-4" />
                </span>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Masukkan username..."
                  disabled={isLocked || loading}
                  className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs font-mono focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:opacity-50 transition"
                  autoComplete="username"
                />
              </div>
            </div>

            {/* Password Input */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-slate-300 font-mono">
                  Password
                </label>
              </div>
              <div className="relative">
                <span className="absolute left-3.5 top-3 text-slate-500">
                  <LucideIcon name="lock" className="w-4 h-4" />
                </span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Masukkan password..."
                  disabled={isLocked || loading}
                  className="w-full pl-10 pr-16 py-2.5 rounded-xl bg-obsidian-950 border border-obsidian-700 text-slate-100 text-xs font-mono focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:opacity-50 transition"
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={isLocked || loading}
                  className="absolute right-2.5 top-2 px-2 py-0.5 rounded bg-obsidian-800 text-[10px] font-mono text-slate-400 hover:text-white transition"
                >
                  {showPassword ? 'HIDE' : 'SHOW'}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLocked || loading}
              className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 text-obsidian-950 font-bold text-xs uppercase tracking-wider shadow-lg shadow-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition duration-200 mt-2"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-obsidian-950 border-t-transparent rounded-full animate-spin" />
                  Memverifikasi...
                </span>
              ) : isLocked ? (
                `Terkunci (${String(lockMinutes).padStart(2, '0')}:${String(lockSeconds).padStart(2, '0')})`
              ) : (
                'Masuk ke Sistem'
              )}
            </button>
          </form>

          {/* System Footer Note */}
          <div className="pt-3 border-t border-obsidian-800 flex items-center justify-between text-[11px] text-slate-500 font-mono">
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Sistem Aktif
            </span>
            <span>Sofia Market 4.1.3 © {new Date().getFullYear()}</span>
          </div>
        </div>
      </div>
    </>
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
