import React from 'react';

interface QueryStateProps {
  isLoading: boolean;
  isError: boolean;
  error?: any;
  children?: React.ReactNode;
}

export function QueryState({ isLoading, isError, error, children }: QueryStateProps) {
  if (isLoading) {
    return (
      <div className="p-6 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 animate-pulse">
        Memuat data...
      </div>
    );
  }
  if (isError) {
    return (
      <div className="p-6 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-200">
        <div className="font-semibold">Gagal memuat data</div>
        <div className="text-sm mt-1">{error?.message || 'Terjadi kesalahan saat menghubungi server.'}</div>
        {error?.request_id && (
          <div className="text-xs font-mono text-rose-400 mt-2">request_id: {error.request_id}</div>
        )}
      </div>
    );
  }
  return <>{children}</>;
}
