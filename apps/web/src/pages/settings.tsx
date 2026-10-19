import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { SettingsDrawer } from '@/components/SettingsDrawer';
import { LucideIcon } from '@/components/LucideIcon';

export default function SettingsPage() {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [isUltrawide, setIsUltrawide] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsUltrawide(localStorage.getItem('sofia_ultrawide') === 'true');
    }
  }, []);

  const handleToggleUltrawide = (enabled: boolean) => {
    setIsUltrawide(enabled);
    if (typeof window !== 'undefined') {
      localStorage.setItem('sofia_ultrawide', enabled ? 'true' : 'false');
      window.dispatchEvent(new CustomEvent('sofia-ultrawide-toggle', { detail: enabled }));
    }
  };

  const handleClose = () => {
    setIsOpen(false);
    if (typeof window !== 'undefined') {
      if (window.history.length > 1) {
        router.back();
      } else {
        router.push('/');
      }
    }
  };

  return (
    <>
      <Head>
        <title>Pengaturan Sistem — Sofia Market Analyst</title>
      </Head>
      <div className="space-y-5">
        <div className="bg-obsidian-900 border border-obsidian-800 rounded-2xl p-6 shadow-xl flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
              <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2">
                <LucideIcon name="sliders" className="w-6 h-6 text-cyan-400" />
                Pengaturan Sistem &amp; Kredensial
              </h1>
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Kelola API Keys, integrasi Wallet on-chain, mode layar lebar, dan akun Deni26.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {!isOpen && (
              <button
                type="button"
                onClick={() => setIsOpen(true)}
                className="px-3.5 py-2 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-xs font-mono font-bold hover:bg-cyan-500/30 transition flex items-center gap-1.5"
              >
                <LucideIcon name="sliders" className="w-3.5 h-3.5" />
                <span>Buka Panel Pengaturan</span>
              </button>
            )}
            <button
              type="button"
              onClick={handleClose}
              className="px-3.5 py-2 rounded-xl bg-obsidian-800 text-slate-300 border border-obsidian-700 text-xs font-mono font-bold hover:bg-rose-500/20 hover:text-rose-300 hover:border-rose-500/40 transition flex items-center gap-1.5"
              title="Tutup pengaturan dan kembali ke halaman sebelumnya"
            >
              <LucideIcon name="arrow-left" className="w-3.5 h-3.5" />
              <span>Kembali ke Halaman Sebelumnya</span>
            </button>
          </div>
        </div>

        {/* Embedded Settings Drawer Body */}
        <SettingsDrawer
          isOpen={isOpen}
          onClose={handleClose}
          isUltrawide={isUltrawide}
          onToggleUltrawide={handleToggleUltrawide}
        />
      </div>
    </>
  );
}
