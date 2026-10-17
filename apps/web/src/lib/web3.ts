import { api } from './api';

export interface ConnectedExtensionWallet {
  providerId: 'phantom' | 'solflare' | 'backpack' | 'metamask' | 'rabby' | 'manual';
  providerName: string;
  address: string;
  chain: 'Solana' | 'Base' | 'Ethereum' | 'BSC';
  token: string;
  walletDbId?: number;
  onchainBalance?: number | null;
  connectedAt: string;
}

const STORAGE_KEY = 'sofia_ext_wallet';

export function getSavedExtensionWallet(): ConnectedExtensionWallet | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function saveExtensionWallet(w: ConnectedExtensionWallet | null) {
  if (typeof window === 'undefined') return;
  if (!w) {
    localStorage.removeItem(STORAGE_KEY);
  } else {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(w));
  }
  window.dispatchEvent(new CustomEvent('sofia-wallet-connected', { detail: w }));
}

export function shortenAddress(addr: string): string {
  if (!addr) return '';
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 5)}...${addr.slice(-4)}`;
}

export interface DetectedExtensions {
  phantom: boolean;
  solflare: boolean;
  backpack: boolean;
  metamask: boolean;
  rabby: boolean;
  anySolana: boolean;
  anyEvm: boolean;
}

export function detectChromeExtensions(): DetectedExtensions {
  if (typeof window === 'undefined') {
    return {
      phantom: false,
      solflare: false,
      backpack: false,
      metamask: false,
      rabby: false,
      anySolana: false,
      anyEvm: false,
    };
  }
  const w = window as any;
  const phantom = Boolean(w.phantom?.solana?.isPhantom || w.solana?.isPhantom);
  const solflare = Boolean(w.solflare?.isSolflare);
  const backpack = Boolean(w.backpack?.isBackpack || w.xnft?.solana);
  const eth = w.ethereum;
  const rabby = Boolean(eth?.isRabby);
  const metamask = Boolean(eth?.isMetaMask);

  return {
    phantom,
    solflare,
    backpack,
    metamask,
    rabby,
    anySolana: Boolean(phantom || solflare || backpack || w.solana),
    anyEvm: Boolean(eth),
  };
}

export async function connectSolanaExtension(
  preferred: 'phantom' | 'solflare' | 'backpack' = 'phantom'
): Promise<ConnectedExtensionWallet> {
  if (typeof window === 'undefined') {
    throw new Error('Browser window tidak tersedia.');
  }
  const w = window as any;
  let provider: any = null;
  let providerName = 'Phantom Chrome';

  if (preferred === 'phantom') {
    provider = w.phantom?.solana || (w.solana?.isPhantom ? w.solana : w.solana);
    providerName = 'Phantom Chrome';
  } else if (preferred === 'solflare') {
    provider = w.solflare || w.solana;
    providerName = 'Solflare Chrome';
  } else if (preferred === 'backpack') {
    provider = w.backpack?.solana || w.backpack || w.solana;
    providerName = 'Backpack Chrome';
  }

  if (!provider) {
    throw new Error(
      `Ekstensi ${providerName} belum terdeteksi di browser Chrome ini. Silakan pasang ekstensi di Chrome Web Store atau gunakan tombol Connect Cepat / Input Alamat di bawah.`
    );
  }

  const resp = await provider.connect();
  const pubKey =
    resp?.publicKey?.toString?.() ||
    provider?.publicKey?.toString?.() ||
    '';

  if (!pubKey) {
    throw new Error('Gagal membaca Public Key dari ekstensi Solana.');
  }

  const extWallet: ConnectedExtensionWallet = {
    providerId: preferred,
    providerName,
    address: pubKey,
    chain: 'Solana',
    token: 'SOL',
    connectedAt: new Date().toISOString(),
  };

  return await syncExtensionWalletWithBackend(extWallet);
}

export async function connectEvmExtension(
  targetChain: 'Base' | 'Ethereum' | 'BSC' = 'Base',
  preferred: 'metamask' | 'rabby' = 'metamask'
): Promise<ConnectedExtensionWallet> {
  if (typeof window === 'undefined') {
    throw new Error('Browser window tidak tersedia.');
  }
  const w = window as any;
  const eth = w.ethereum;
  if (!eth) {
    throw new Error(
      'Ekstensi MetaMask / Rabby (EVM) belum terdeteksi di browser Chrome ini. Silakan pasang MetaMask di Chrome Web Store atau gunakan tombol Connect Cepat di bawah.'
    );
  }

  const accounts: string[] = await eth.request({ method: 'eth_requestAccounts' });
  if (!accounts || accounts.length === 0) {
    throw new Error('Tidak ada akun EVM yang dipilih pada ekstensi Chrome.');
  }

  const CHAIN_HEX: Record<string, string> = {
    Ethereum: '0x1',
    Base: '0x2105',
    BSC: '0x38',
  };

  const targetHex = CHAIN_HEX[targetChain] || '0x2105';
  try {
    await eth.request({
      method: 'wallet_switchEthereumChain',
      params: [{ chainId: targetHex }],
    });
  } catch {
    // Keep current chain if user cancels network switch
  }

  const isRabby = Boolean(eth.isRabby) || preferred === 'rabby';
  const extWallet: ConnectedExtensionWallet = {
    providerId: isRabby ? 'rabby' : 'metamask',
    providerName: isRabby ? 'Rabby Chrome' : 'MetaMask Chrome',
    address: accounts[0],
    chain: targetChain,
    token: targetChain === 'BSC' ? 'BNB' : 'ETH',
    connectedAt: new Date().toISOString(),
  };

  return await syncExtensionWalletWithBackend(extWallet);
}

export async function syncExtensionWalletWithBackend(
  extWallet: ConnectedExtensionWallet
): Promise<ConnectedExtensionWallet> {
  try {
    const walletsData = await api.getWallets();
    const allWallets: any[] = walletsData?.wallets || [];
    const existing = allWallets.find(
      (item) =>
        (item.address || '').toLowerCase() === extWallet.address.toLowerCase()
    );

    let walletDbId: number | undefined;
    if (existing) {
      walletDbId = existing.id;
      await api.updateWallet(existing.id, {
        name: `${extWallet.providerName} (${shortenAddress(extWallet.address)})`,
        address: extWallet.address,
        chain: extWallet.chain,
        gate: 'trading',
      });
    } else {
      const created = await api.createWallet({
        name: `${extWallet.providerName} (${shortenAddress(extWallet.address)})`,
        address: extWallet.address,
        chain: extWallet.chain,
        balance: extWallet.chain === 'Solana' ? 12.5 : 1.25,
        token: extWallet.token,
        gate: 'trading',
      });
      walletDbId = created?.id;
    }

    if (walletDbId) {
      extWallet.walletDbId = walletDbId;
      try {
        const syncRes = await api.syncWalletOnchain(walletDbId, true);
        if (syncRes?.rpc_check?.onchain_balance !== undefined) {
          extWallet.onchainBalance = syncRes.rpc_check.onchain_balance;
        }
      } catch {
        // Ignore RPC timeout
      }
    }
  } catch {
    // Allow frontend connection even before auth token if used on login screen
  }

  saveExtensionWallet(extWallet);
  return extWallet;
}
