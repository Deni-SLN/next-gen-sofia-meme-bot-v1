import { useState, useEffect } from 'react';

/**
 * Hook to detect and listen for Ultrawide / Mode Layar Lebar state.
 * When enabled, pages rearrange cards horizontally (side-by-side)
 * allowing users to view more than 3 cards side-by-side on wide monitors
 * without needing to scroll down.
 */
export function toggleUltrawide(nextState?: boolean): boolean {
  if (typeof window !== 'undefined') {
    const raw = localStorage.getItem('sofia_ultrawide');
    const current = raw === null ? true : raw === 'true';
    const next = typeof nextState === 'boolean' ? nextState : !current;
    localStorage.setItem('sofia_ultrawide', next ? 'true' : 'false');
    window.dispatchEvent(new CustomEvent('sofia-ultrawide-toggle', { detail: next }));
    return next;
  }
  return true;
}

export function useUltrawide(): boolean {
  const [isUltrawide, setIsUltrawide] = useState<boolean>(true);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const raw = localStorage.getItem('sofia_ultrawide');
      setIsUltrawide(raw === null ? true : raw === 'true');

      const handler = (e: any) => {
        setIsUltrawide(Boolean(e?.detail));
      };

      window.addEventListener('sofia-ultrawide-toggle', handler);
      return () => window.removeEventListener('sofia-ultrawide-toggle', handler);
    }
  }, []);

  return isUltrawide;
}
