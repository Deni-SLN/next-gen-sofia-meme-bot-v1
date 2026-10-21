import React, { useState, useEffect } from 'react';
import { api, useApiQuery, formatIdr, formatUsd } from '@/lib/api';
import { QueryState } from '@/components/QueryState';
import { LucideIcon } from '@/components/LucideIcon';
import { WalletConnectModal } from '@/components/WalletConnectModal';
import {
  ConnectedExtensionWallet,
  getSavedExtensionWallet,
  shortenAddress,
} from '@/lib/web3';
import { useUltrawide, toggleUltrawide } from '@/lib/useUltrawide';

const CHAINS = ['Solana', 'Base', 'Ethereum', 'BSC'];
const GATES = ['trading', 'main', 'reserve'];

export default function WalletsPage() {
  const isUltrawide = useUltrawide();
  const walletsQuery = useApiQuery(() => api.getWallets(), []);
  const usdIdr = walletsQuery.data?.usd_idr || 17960;

  // Inline editing state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState<string>('');
  const [editAddress, setEditAddress] = useState<string>('');
  const [editChain, setEditChain] = useState<string>('Solana');
  const [editBalance, setEditBalance] = useState<number>(0);
  const [editToken, setEditToken] = useState<string>('SOL');
  const [editGate, setEditGate] = useState<string>('trading');

  // Add new wallet state
  const [showAddForm, setShowAddForm] = useState<boolean>(false);
  const [showConnectModal, setShowConnectModal] = useState<boolean>(false);
  const [extWallet, setExtWallet] = useState<ConnectedExtensionWallet | null>(null);
  const [newName, setNewName] = useState<string>('');
  const [newAddress, setNewAddress] = useState<string>('');
  const [newChain, setNewChain] = useState<string>('Solana');
  const [newBalance, setNewBalance] = useState<number>(0);
  const [newToken, setNewToken] = useState<string>('SOL');
  const [newGate, setNewGate] = useState<string>('trading');

  const [msg, setMsg] = useState<string>('');
  const [err, setErr] = useState<string>('');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setExtWallet(getSavedExtensionWallet());
      const resetHandler = () => walletsQuery.refetch();
      const tradeHandler = () => walletsQuery.refetch();
      const extHandler = (e: any) => {
        setExtWallet(e.detail || null);
        walletsQuery.refetch();
      };
      window.addEventListener('sofia-paper-reset', resetHandler);
      window.addEventListener('sofia-bot-trade-executed', tradeHandler);
      window.addEventListener('sofia-wallet-connected', extHandler);
      return () => {
        window.removeEventListener('sofia-paper-reset', resetHandler);
        window.removeEventListener('sofia-bot-trade-executed', tradeHandler);
        window.removeEventListener('sofia-wallet-connected', extHandler);
      };
    }
  }, []);

  const startEdit = (w: any) => {
    setMsg('');
    setErr('');
    setEditingId(w.id);
    setEditName(w.name || '');
    setEditAddress(w.address || '');
    setEditChain(w.chain || 'Solana');
    setEditBalance(Number(w.balance ?? 0));
    setEditToken(w.token || 'SOL');
    setEditGate(w.gate || 'trading');
  };

  const handleSaveEdit = async (walletId: number) => {
    setMsg('');
    setErr('');
    try {
      await api.updateWallet(walletId, {
        name: editName.trim(),
        address: editAddress.trim(),
        chain: editChain,
        balance: Number(editBalance),
        token: editToken.trim(),
        gate: editGate,
      });
      setEditingId(null);
      setMsg(`✅ Alamat & konfigurasi dompet "${editName}" berhasil diperbarui!`);
      walletsQuery.refetch();
    } catch (e: any) {
      setErr(e?.message || 'Gagal memperbarui dompet');
    }
  };

  const handleCreateWallet = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg('');
    setErr('');
    try {
      await api.createWallet({
        name: newName.trim(),
        address: newAddress.trim(),
        chain: newChain,
        balance: Number(newBalance),
        token: newToken.trim(),
        gate: newGate,
      });
      setNewName('');
      setNewAddress('');
      setNewBalance(0);
      setShowAddForm(false);
      setMsg(`✅ Dompet baru "${newName}" berhasil ditambahkan!`);
      walletsQuery.refetch();
    } catch (e: any) {
      setErr(e?.message || 'Gagal menambahkan dompet baru');
    }
  };

  const handleDeleteWallet = async (w: any) => {
    setMsg('');
    setErr('');
    try {
      await api.deleteWallet(w.id);
      setMsg(`🗑️ Dompet "${w.name}" berhasil dihapus.`);
      walletsQuery.refetch();
    } catch (e: any) {
      setErr(e?.message || 'Gagal menghapus dompet');
    }
  };

  const handleSyncOnchain = async (w: any) => {
    setMsg('');
    setErr('');
    try {
      const res = await api.syncWalletOnchain(w.id, false);
      const rpc = res.rpc_check || {};
      const wal = res.wallet || w;
      if (rpc.rpc_connected && rpc.valid_address) {
        setMsg(
          `🌐 [MAINNET RPC VERIFIED • ${rpc.latency_ms}ms] Dompet "${w.name}" (${w.chain}) terhubung ke ${rpc.rpc_endpoint} • Saldo On-Chain publik: ${rpc.onchain_balance ?? 0} ${rpc.token || ''} • Saldo Vault Bot: ${formatUsd(wal.balance_usd)} (${formatIdr(wal.balance_idr)})`
        );
      } else {
        setMsg(
          `ℹ️ Cek RPC "${w.name}" (${w.chain} • ${rpc.latency_ms ?? 0}ms): ${rpc.note || 'Format alamat kustom / simulasi vault'} • Saldo Vault Aktif: ${formatUsd(wal.balance_usd)} (${formatIdr(wal.balance_idr)})`
        );
      }
      walletsQuery.refetch();
    } catch (e: any) {
      setErr(e?.message || 'Gagal mengecek RPC on-chain');
    }
  };

  return (
    <div className="space-y-3">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-3.5 py-2.5 rounded-xl bg-obsidian-900 border border-obsidian-700/80">
        <div>
          <div className="flex items-center gap-2">
            <LucideIcon name="layers" className="w-4 h-4 text-teal-400" />
            <h1 className="text-sm font-extrabold text-slate-100 uppercase tracking-wide font-mono">
              Multi-Gate Wallets (Paper Rp 150rb &amp; Live Vaults)
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Klik tombol <strong>✏️ Ubah Alamat / Edit</strong> pada baris mana pun untuk mengganti alamat wallet, nama, chain, saldo, atau gate • Kurs Hari Ini: $1 ={' '}
            <span className="text-emerald-400 font-mono font-bold">{formatIdr(usdIdr)}</span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowConnectModal(true)}
            className="px-3.5 py-1.5 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-200 border border-purple-500/40 font-extrabold text-xs font-mono transition flex items-center gap-1.5"
          >
            <span>🔌 {extWallet ? `${extWallet.providerName}: ${shortenAddress(extWallet.address)}` : 'Connect Ekstensi Chrome'}</span>
          </button>
          <button
            type="button"
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 font-extrabold text-xs font-mono shadow-glow-emerald transition"
          >
            {showAddForm ? '✕ Tutup Form' : '+ Tambah Wallet Baru'}
          </button>
        </div>
      </div>

      <WalletConnectModal
        isOpen={showConnectModal}
        onClose={() => setShowConnectModal(false)}
        connectedWallet={extWallet}
        onConnected={(w) => {
          setExtWallet(w);
          setMsg(`🔌 Berhasil menghubungkan ${w.providerName} (${w.address}) ke daftar Multi-Gate Wallets!`);
          walletsQuery.refetch();
        }}
      />

      {msg && (
        <div className="p-3 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 text-xs font-mono">
          {msg}
        </div>
      )}
      {err && (
        <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-500/40 text-rose-200 text-xs font-mono">
          ⚠️ {err}
        </div>
      )}

      {/* Add New Wallet Form */}
      {showAddForm && (
        <form
          onSubmit={handleCreateWallet}
          className="p-4 rounded-xl bg-obsidian-900 border border-emerald-500/40 space-y-3 font-mono text-xs"
        >
          <div className="text-xs font-bold text-emerald-400 uppercase">
            + Tambah Dompet Multi-Gate Baru
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
            <div>
              <label className="block text-[10px] text-slate-400 mb-1">NAMA DOMPET</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Phantom Sniper #2"
                className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
                required
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-[10px] text-slate-400 mb-1">ALAMAT WALLET (SOL / EVM)</label>
              <input
                type="text"
                value={newAddress}
                onChange={(e) => setNewAddress(e.target.value)}
                placeholder="Masukkan alamat publik Solana / 0x..."
                className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-emerald-300"
                required
              />
            </div>
            <div>
              <label className="block text-[10px] text-slate-400 mb-1">CHAIN</label>
              <select
                value={newChain}
                onChange={(e) => setNewChain(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
              >
                {CHAINS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] text-slate-400 mb-1">SALDO &amp; TOKEN</label>
              <div className="flex gap-1">
                <input
                  type="number"
                  step="any"
                  value={newBalance}
                  onChange={(e) => setNewBalance(Number(e.target.value))}
                  className="w-2/3 px-2 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
                />
                <input
                  type="text"
                  value={newToken}
                  onChange={(e) => setNewToken(e.target.value)}
                  className="w-1/3 px-2 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-cyan-300"
                />
              </div>
            </div>
            <div>
              <label className="block text-[10px] text-slate-400 mb-1">GATE</label>
              <div className="flex gap-1.5">
                <select
                  value={newGate}
                  onChange={(e) => setNewGate(e.target.value)}
                  className="w-full px-2 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white"
                >
                  {GATES.map((g) => (
                    <option key={g} value={g}>
                      {g.toUpperCase()}
                    </option>
                  ))}
                </select>
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 font-extrabold shrink-0"
                >
                  Simpan
                </button>
              </div>
            </div>
          </div>
        </form>
      )}

      <QueryState isLoading={walletsQuery.isLoading} isError={walletsQuery.isError} error={walletsQuery.error}>
        {(() => {
          const walletsTableBlock = (
            <div className="rounded-xl bg-obsidian-900 border border-obsidian-700/80 overflow-hidden shadow-lg">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-obsidian-950 text-slate-400 border-b border-obsidian-800 text-[10px] uppercase">
                <tr>
                  <th className="p-3.5">Nama Dompet</th>
                  <th className="p-3.5">Alamat Wallet (Bisa Diubah)</th>
                  <th className="p-3.5">Chain</th>
                  <th className="p-3.5">Saldo (USD &amp; Rupiah Hari Ini)</th>
                  <th className="p-3.5">Gate</th>
                  <th className="p-3.5 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-obsidian-800/60">
                {(walletsQuery.data?.wallets || []).map((w: any) => {
                  const isEditing = editingId === w.id;
                  const isPaperWallet = w.name?.includes('Modal Paper');

                  if (isEditing) {
                    return (
                      <tr key={w.id} className="bg-emerald-950/20">
                        <td className="p-3">
                          <input
                            type="text"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            className="w-full px-2.5 py-1.5 rounded bg-obsidian-950 border border-emerald-500/60 text-white text-xs"
                          />
                        </td>
                        <td className="p-3">
                          <input
                            type="text"
                            value={editAddress}
                            onChange={(e) => setEditAddress(e.target.value)}
                            placeholder="Masukkan alamat wallet baru..."
                            className="w-full min-w-[240px] px-2.5 py-1.5 rounded bg-obsidian-950 border border-emerald-500 text-emerald-300 font-bold text-xs"
                          />
                        </td>
                        <td className="p-3">
                          <select
                            value={editChain}
                            onChange={(e) => setEditChain(e.target.value)}
                            className="px-2 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white text-xs"
                          >
                            {CHAINS.map((c) => (
                              <option key={c} value={c}>
                                {c}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="p-3">
                          <div className="flex items-center gap-1.5">
                            <input
                              type="number"
                              step="any"
                              value={editBalance}
                              onChange={(e) => setEditBalance(Number(e.target.value))}
                              className="w-24 px-2 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-white text-xs"
                            />
                            <input
                              type="text"
                              value={editToken}
                              onChange={(e) => setEditToken(e.target.value)}
                              className="w-24 px-2 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-cyan-300 text-xs"
                            />
                          </div>
                        </td>
                        <td className="p-3">
                          <select
                            value={editGate}
                            onChange={(e) => setEditGate(e.target.value)}
                            className="px-2 py-1.5 rounded bg-obsidian-950 border border-obsidian-700 text-cyan-400 text-xs uppercase font-bold"
                          >
                            {GATES.map((g) => (
                              <option key={g} value={g}>
                                {g.toUpperCase()}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="p-3 text-right">
                          <div className="inline-flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleSaveEdit(w.id)}
                              className="px-2.5 py-1 rounded bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 font-extrabold text-[11px]"
                            >
                              💾 Simpan
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingId(null)}
                              className="px-2.5 py-1 rounded bg-obsidian-800 hover:bg-obsidian-700 text-slate-300 text-[11px]"
                            >
                              Batal
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  }

                  return (
                    <tr key={w.id} className="hover:bg-obsidian-850/70 transition">
                      <td className="p-3.5 font-bold text-slate-100">
                        <div className="flex items-center gap-2">
                          <span>{w.name}</span>
                          {isPaperWallet && (
                            <span className="px-1.5 py-0.5 text-[9px] rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                              PAPER DEFAULT
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="p-3.5">
                        <div className="flex items-center gap-2">
                          <code className="px-2 py-0.5 rounded bg-obsidian-950 border border-obsidian-800 text-cyan-300 text-[11px] break-all">
                            {w.address}
                          </code>
                          <button
                            type="button"
                            onClick={() => startEdit(w)}
                            className="text-[10px] text-slate-400 hover:text-emerald-400 underline shrink-0"
                          >
                            Ubah
                          </button>
                        </div>
                      </td>
                      <td className="p-3.5 text-slate-300">{w.chain}</td>
                      <td className="p-3.5">
                        <div className="font-bold text-slate-100">
                          {Number(w.balance).toLocaleString()} {w.token} ({formatUsd(w.balance_usd ?? w.balance)})
                        </div>
                        <div className="text-[10px] text-emerald-400">
                          ≈ {formatIdr(w.balance_idr ?? w.balance * usdIdr)}
                        </div>
                        {Array.isArray(w.spl_tokens) && w.spl_tokens.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {w.spl_tokens.map((spl: any) => (
                              <span
                                key={spl.mint}
                                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-obsidian-950 border border-obsidian-700 text-[10px] font-mono text-cyan-300"
                              >
                                <span className="font-bold">{spl.symbol}:</span>
                                <span>{Number(spl.amount).toLocaleString(undefined, { maximumFractionDigits: 4 })}</span>
                                <span className="text-slate-400">({formatUsd(spl.usd_val)})</span>
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="p-3.5">
                        <span className="px-2 py-0.5 rounded bg-obsidian-850 border border-obsidian-700 uppercase text-[10px] font-bold text-cyan-400">
                          {w.gate}
                        </span>
                      </td>
                      <td className="p-3.5 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          {!isPaperWallet && (
                            <button
                              type="button"
                              onClick={() => handleSyncOnchain(w)}
                              className="px-2 py-1 rounded bg-cyan-500/15 hover:bg-cyan-500 text-cyan-300 hover:text-obsidian-950 border border-cyan-500/30 font-bold text-[10px] transition"
                              title="Cek Koneksi & Saldo Mainnet RPC (Solana / Base)"
                            >
                              🌐 Cek RPC
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => startEdit(w)}
                            className="px-2.5 py-1 rounded bg-emerald-500/15 hover:bg-emerald-500 text-emerald-300 hover:text-obsidian-950 border border-emerald-500/30 font-bold text-[10px] transition"
                          >
                            ✏️ Ubah Alamat / Edit
                          </button>
                          {!isPaperWallet && (
                            <button
                              type="button"
                              onClick={() => handleDeleteWallet(w)}
                              className="px-2 py-1 rounded bg-rose-500/15 hover:bg-rose-600 text-rose-300 hover:text-white border border-rose-500/30 font-bold text-[10px] transition"
                              title="Hapus dompet"
                            >
                              🗑️
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
        );

        const treasuryBlock = walletsQuery.data?.treasury ? (
          <div className="bg-obsidian-900 border border-obsidian-700 rounded-xl p-4 space-y-4 shadow-lg">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-obsidian-800">
              <div className="flex items-center gap-2">
                <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                  <LucideIcon name="banknote" className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                    Auto Top-Up Gas Fee &amp; Bagi Hasil 05:00 WIB
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 font-mono">
                      Rule 40% Main / 60% Modal
                    </span>
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Otomatis top up saldo gas jika &lt; Rp 3.000, serta transfer 40% keuntungan bersih ke Wallet Utama jika profit &gt; 40% pada jam 05:00 pagi WIB.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={async () => {
                    setMsg('');
                    setErr('');
                    try {
                      await api.topupGasReserve(5000);
                      setMsg('⚡ Gas Reserve berhasil di-top up sebesar Rp 5.000 dari saldo trading!');
                      walletsQuery.refetch();
                    } catch (e: any) {
                      setErr(e?.message || 'Gagal top up gas');
                    }
                  }}
                  className="px-2.5 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500 text-emerald-300 hover:text-obsidian-950 border border-emerald-500/30 font-bold text-xs transition"
                >
                  ⚡ Top Up Gas (+Rp 5.000)
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    setMsg('');
                    setErr('');
                    try {
                      await api.triggerSettlement();
                      setMsg('⚡ Pengecekan Settlement 05:00 WIB selesai dijalankan.');
                      walletsQuery.refetch();
                    } catch (e: any) {
                      setErr(e?.message || 'Gagal mengeksekusi settlement');
                    }
                  }}
                  className="px-2.5 py-1.5 rounded-lg bg-cyan-500/15 hover:bg-cyan-500 text-cyan-300 hover:text-obsidian-950 border border-cyan-500/30 font-bold text-xs transition"
                >
                  ⚡ Cek Settlement 05:00 WIB
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    setMsg('');
                    setErr('');
                    try {
                      await api.triggerSettlement(65000); // Simulate +Rp 65.000 profit (>40% of 150k)
                      setMsg('🧪 Simulasi Profit >40% (+Rp 65.000): 40% ditransfer ke Wallet Utama, 60% diakumulasi ke Modal & Gas!');
                      walletsQuery.refetch();
                    } catch (e: any) {
                      setErr(e?.message || 'Gagal simulasi');
                    }
                  }}
                  className="px-2.5 py-1.5 rounded-lg bg-purple-500/15 hover:bg-purple-500 text-purple-300 hover:text-obsidian-950 border border-purple-500/30 font-bold text-xs transition"
                  title="Simulasikan skenario profit >40% untuk menguji transfer otomatis ke Wallet Utama"
                >
                  🧪 Test Run (&gt;40%)
                </button>
              </div>
            </div>

            {/* Treasury KPI Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-obsidian-950 p-3 rounded-lg border border-obsidian-800">
                <div className="text-[10px] font-mono text-slate-400 uppercase">Cadangan Gas (Gas Reserve)</div>
                <div className="text-lg font-bold font-mono text-emerald-400 mt-1">
                  {formatIdr(walletsQuery.data.treasury.gas_reserve_idr)}
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  {formatUsd(walletsQuery.data.treasury.gas_reserve_usd)} • Target Rp {walletsQuery.data.treasury.gas_target_idr.toLocaleString('id-ID')}
                </div>
                <div className="text-[9px] text-emerald-400 mt-1">
                  ✓ Auto Top-Up Aktif (&lt; Rp {walletsQuery.data.treasury.gas_min_idr.toLocaleString('id-ID')})
                </div>
              </div>

              <div className="bg-obsidian-950 p-3 rounded-lg border border-obsidian-800">
                <div className="text-[10px] font-mono text-slate-400 uppercase">Total Biaya Gas &amp; DEX</div>
                <div className="text-lg font-bold font-mono text-amber-400 mt-1">
                  {formatIdr(walletsQuery.data.treasury.total_gas_spent_idr + walletsQuery.data.treasury.total_dex_fees_idr)}
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  Gas: {formatIdr(walletsQuery.data.treasury.total_gas_spent_idr)} • Swap Fee: {formatIdr(walletsQuery.data.treasury.total_dex_fees_idr)}
                </div>
                <div className="text-[9px] text-slate-400 mt-1">100% dipotong dari perhitungan profit</div>
              </div>

              <div className="bg-obsidian-950 p-3 rounded-lg border border-obsidian-800">
                <div className="text-[10px] font-mono text-slate-400 uppercase">Keuntungan Bersih (Net Profit)</div>
                <div
                  className={`text-lg font-bold font-mono mt-1 ${
                    walletsQuery.data.treasury.net_profit_pct > 40
                      ? 'text-emerald-400'
                      : walletsQuery.data.treasury.net_profit_pct > 0
                      ? 'text-cyan-400'
                      : 'text-slate-300'
                  }`}
                >
                  {walletsQuery.data.treasury.net_profit_pct > 0 ? '+' : ''}
                  {walletsQuery.data.treasury.net_profit_pct}%
                </div>
                <div className="text-[10px] text-slate-400 font-mono">
                  {formatIdr(walletsQuery.data.treasury.net_profit_idr)} (Modal Acuan: {formatIdr(walletsQuery.data.treasury.baseline_equity_idr)})
                </div>
                <div className="text-[9px] text-slate-500 mt-1">
                  Ambang batas transfer: &gt; 40% ({formatIdr(walletsQuery.data.treasury.baseline_equity_idr * 0.4)})
                </div>
              </div>

              <div className="bg-obsidian-950 p-3 rounded-lg border border-obsidian-800">
                <div className="text-[10px] font-mono text-slate-400 uppercase">Jadwal &amp; Status 05:00 WIB</div>
                <div className="text-sm font-bold font-mono text-slate-200 mt-1">
                  {walletsQuery.data.treasury.settlement_status_preview === 'READY_TO_TRANSFER' ? (
                    <span className="text-emerald-400">SIAP TRANSFER (&gt;40%)</span>
                  ) : (
                    <span className="text-amber-400">PENDING (&le;40%)</span>
                  )}
                </div>
                <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                  Setiap Hari 05:00 WIB
                </div>
                <div className="text-[9px] text-slate-500 mt-1 truncate">
                  Tujuan: {walletsQuery.data.treasury.main_wallet?.name || 'Main Treasury Vault'}
                </div>
              </div>
            </div>

            {/* Recent Settlement Logs */}
            {walletsQuery.data.treasury.settlements && walletsQuery.data.treasury.settlements.length > 0 && (
              <div className="bg-obsidian-950 p-3 rounded-lg border border-obsidian-800 space-y-2">
                <div className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between">
                  <span>Riwayat Settlement 05:00 WIB</span>
                  <span className="text-[10px] font-normal text-slate-500">
                    Otomatis dieksekusi di background pada node SOFIA
                  </span>
                </div>
                <div className="space-y-1.5 max-h-40 overflow-y-auto font-mono text-[11px]">
                  {walletsQuery.data.treasury.settlements.map((s: any) => (
                    <div
                      key={s.id}
                      className="p-2 rounded bg-obsidian-900 border border-obsidian-800 flex flex-col sm:flex-row sm:items-center justify-between gap-1"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-[9px] font-bold px-1.5 py-0.2 rounded uppercase ${
                            s.status === 'transferred'
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                              : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          }`}
                        >
                          {s.status}
                        </span>
                        <span className="text-slate-300 font-bold">{s.settlement_date}</span>
                        <span className="text-slate-400 text-[10px]">({s.trigger})</span>
                      </div>
                      <div className="text-slate-300 text-[10px]">
                        {s.note}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            </div>
          ) : null;

          return isUltrawide ? (
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
              {/* Kolom Kiri: Tabel Multi-Gate Wallets (7 Col) */}
              <div className="xl:col-span-7 space-y-4">
                {walletsTableBlock}
              </div>

              {/* Kolom Kanan: Aturan Gas & 05:00 WIB Settlement dipindahkan ke samping! (5 Col) */}
              <div className="xl:col-span-5 space-y-4">
                {treasuryBlock}
              </div>
            </div>
          ) : (
            <>
              {walletsTableBlock}
              {treasuryBlock}
            </>
          );
        })()}
      </QueryState>
    </div>
  );
}
