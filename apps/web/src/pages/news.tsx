import React, { useState, useEffect, useCallback } from 'react';
import Head from 'next/head';
import { api } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';

interface NewsArticle {
  id: string;
  title: string;
  summary: string;
  url: string;
  image_url: string;
  has_native_thumbnail?: boolean;
  publisher: string;
  publisher_url: string;
  category: string;
  category_label: string;
  sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  published_at: string;
  published_ts: number;
  formatted_date?: string;
  relative_time: string;
}

const CATEGORY_TABS = [
  { id: 'all', label: 'Semua Kategori', badge: 'TERKINI', icon: 'newspaper', color: 'cyan' },
  { id: 'crypto', label: 'Crypto', badge: 'WEB3 & KOIN', icon: 'zap', color: 'amber' },
  { id: 'saham', label: 'Saham', badge: 'IHSG & BEI', icon: 'trending-up', color: 'emerald' },
  { id: 'emas', label: 'Emas', badge: 'ANTAM & XAU', icon: 'layers', color: 'yellow' },
  { id: 'ekonomi', label: 'Ekonomi', badge: 'MAKRO & BI', icon: 'banknote', color: 'blue' },
  { id: 'teknologi', label: 'Teknologi', badge: 'AI & DIGITAL', icon: 'bot', color: 'purple' },
];

const FALLBACK_THUMBS: Record<string, string> = {
  crypto: 'https://images.unsplash.com/photo-1518546305927-5a555bb7020d?auto=format&fit=crop&w=800&q=80',
  saham: 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=800&q=80',
  emas: 'https://images.unsplash.com/photo-1610375461246-83df859d849d?auto=format&fit=crop&w=800&q=80',
  ekonomi: 'https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=800&q=80',
  teknologi: 'https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=800&q=80',
};

export default function NewsPage() {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchInput, setSearchInput] = useState<string>('');
  const [activeQuery, setActiveQuery] = useState<string>('');
  const [sentimentFilter, setSentimentFilter] = useState<'ALL' | 'BULLISH' | 'BEARISH' | 'NEUTRAL'>('ALL');
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadNews = useCallback(
    async (cat: string, query: string, forceRefresh: boolean = false) => {
      if (forceRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setErrorMsg(null);
      try {
        const res = await api.getNews(cat, query || undefined, forceRefresh, 30);
        const list: NewsArticle[] = Array.isArray(res?.articles) ? res.articles : [];
        // Pastikan diurutkan dari yang paling baru ke yang paling lama
        list.sort((a, b) => (b.published_ts || 0) - (a.published_ts || 0));
        setArticles(list);
        if (res?.updated_at) {
          const dt = new Date(res.updated_at);
          setLastUpdated(
            dt.toLocaleTimeString('id-ID', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            })
          );
        }
      } catch (err: any) {
        setErrorMsg(err?.message || 'Gagal memuat berita pasar Indonesia.');
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    []
  );

  useEffect(() => {
    loadNews(selectedCategory, activeQuery, false);
  }, [selectedCategory, activeQuery, loadNews]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setActiveQuery(searchInput.trim());
  };

  const filteredArticles = articles.filter((a) => {
    if (sentimentFilter !== 'ALL' && a.sentiment !== sentimentFilter) return false;
    return true;
  });

  const bullishCount = articles.filter((a) => a.sentiment === 'BULLISH').length;
  const bearishCount = articles.filter((a) => a.sentiment === 'BEARISH').length;
  const neutralCount = articles.filter((a) => a.sentiment === 'NEUTRAL').length;

  const getCategoryBadgeStyle = (cat: string) => {
    switch (cat) {
      case 'crypto':
        return 'bg-amber-500/90 text-slate-950 border-amber-400';
      case 'saham':
        return 'bg-emerald-500/90 text-slate-950 border-emerald-400';
      case 'emas':
        return 'bg-yellow-400/95 text-slate-950 border-yellow-300';
      case 'ekonomi':
        return 'bg-blue-500/90 text-white border-blue-400';
      case 'teknologi':
        return 'bg-purple-500/90 text-white border-purple-400';
      default:
        return 'bg-cyan-500/90 text-slate-950 border-cyan-400';
    }
  };

  const getSentimentBadge = (sentiment: string) => {
    if (sentiment === 'BULLISH') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          ▲ POSITIF
        </span>
      );
    }
    if (sentiment === 'BEARISH') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
          ▼ NEGATIF
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
        ● NETRAL
      </span>
    );
  };

  return (
    <>
      <Head>
        <title>News & Riset Pasar Indonesia | SOFIA Trenches v3.8 PRO</title>
      </Head>

      <div className="p-4 lg:p-6 space-y-5 max-w-[1600px] mx-auto">
        {/* Top Header */}
        <div className="rounded-2xl border border-slate-800/90 bg-gradient-to-r from-[#0b101d] via-[#0f172a] to-[#0b101d] p-5 shadow-xl">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                  <LucideIcon name="newspaper" className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="text-lg sm:text-xl font-black tracking-tight text-white">
                      NEWS & RISET PASAR INDONESIA
                    </h1>
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                      TERBARU → TERLAMA
                    </span>
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      MAKS 7 HARI TERAKHIR
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Berita finansial, komoditas & teknologi Bahasa Indonesia (maksimal 1 minggu terakhir) • Klik berita untuk langsung membuka sumber artikel asli
                  </p>
                </div>
              </div>
            </div>

            {/* Search & Refresh Controls */}
            <div className="flex flex-wrap items-center gap-2.5">
              <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1 sm:flex-initial">
                <input
                  type="text"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder="Cari topik (cth: Bitcoin, Antam, IHSG, BI)..."
                  className="w-full sm:w-64 bg-slate-950/90 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/60"
                />
                <button
                  type="submit"
                  className="px-3.5 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/30 text-xs font-bold transition"
                >
                  Cari
                </button>
                {activeQuery && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchInput('');
                      setActiveQuery('');
                    }}
                    className="px-2.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
                  >
                    Reset
                  </button>
                )}
              </form>

              <button
                type="button"
                onClick={() => loadNews(selectedCategory, activeQuery, true)}
                disabled={refreshing || loading}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-xs font-bold transition disabled:opacity-50"
              >
                <LucideIcon name="rotate-ccw" className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                {refreshing ? 'Memperbarui...' : 'Refresh Berita'}
              </button>
            </div>
          </div>

          {/* Category Filter Tabs */}
          <div className="mt-5 pt-4 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar">
              {CATEGORY_TABS.map((tab) => {
                const active = selectedCategory === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setSelectedCategory(tab.id)}
                    className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition whitespace-nowrap border ${
                      active
                        ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-lg shadow-cyan-950/50'
                        : 'bg-slate-900/80 text-slate-400 border-slate-800 hover:bg-slate-800/70 hover:text-slate-200'
                    }`}
                  >
                    <LucideIcon name={tab.icon} className="w-3.5 h-3.5" />
                    <span>{tab.label}</span>
                    <span
                      className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                        active ? 'bg-cyan-400/20 text-cyan-200' : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {tab.badge}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Sentiment Quick Filter */}
            <div className="flex items-center gap-1.5 text-[11px]">
              <button
                type="button"
                onClick={() => setSentimentFilter('ALL')}
                className={`px-2.5 py-1 rounded-lg font-semibold border transition ${
                  sentimentFilter === 'ALL'
                    ? 'bg-slate-800 text-white border-slate-600'
                    : 'bg-slate-950/60 text-slate-400 border-slate-800/80 hover:text-slate-200'
                }`}
              >
                Semua ({articles.length})
              </button>
              <button
                type="button"
                onClick={() => setSentimentFilter('BULLISH')}
                className={`px-2.5 py-1 rounded-lg font-semibold border transition ${
                  sentimentFilter === 'BULLISH'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    : 'bg-slate-950/60 text-emerald-400/70 border-slate-800/80 hover:text-emerald-300'
                }`}
              >
                ▲ Positif ({bullishCount})
              </button>
              <button
                type="button"
                onClick={() => setSentimentFilter('BEARISH')}
                className={`px-2.5 py-1 rounded-lg font-semibold border transition ${
                  sentimentFilter === 'BEARISH'
                    ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                    : 'bg-slate-950/60 text-rose-400/70 border-slate-800/80 hover:text-rose-300'
                }`}
              >
                ▼ Negatif ({bearishCount})
              </button>
              <button
                type="button"
                onClick={() => setSentimentFilter('NEUTRAL')}
                className={`px-2.5 py-1 rounded-lg font-semibold border transition ${
                  sentimentFilter === 'NEUTRAL'
                    ? 'bg-slate-700/60 text-slate-200 border-slate-500'
                    : 'bg-slate-950/60 text-slate-400 border-slate-800/80 hover:text-slate-300'
                }`}
              >
                ● Netral ({neutralCount})
              </button>
            </div>
          </div>
        </div>

        {/* Status Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>
              Menampilkan <strong className="text-slate-200">{filteredArticles.length}</strong> berita terbaru (maks. 7 hari terakhir) untuk kategori{' '}
              <strong className="text-cyan-400">
                {CATEGORY_TABS.find((t) => t.id === selectedCategory)?.label || 'Semua'}
              </strong>
              {activeQuery ? ` dengan kata kunci "${activeQuery}"` : ''} • Diurutkan dari paling baru ke paling lama
            </span>
          </div>
          {lastUpdated && (
            <span className="font-mono text-[11px] text-slate-500">
              Pembaruan terakhir: {lastUpdated} WIB
            </span>
          )}
        </div>

        {/* Error Alert */}
        {errorMsg && (
          <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300 text-xs flex items-center justify-between">
            <span>⚠️ {errorMsg}</span>
            <button
              type="button"
              onClick={() => loadNews(selectedCategory, activeQuery, true)}
              className="px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 font-bold"
            >
              Coba Lagi
            </button>
          </div>
        )}

        {/* Loading Skeleton */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {Array.from({ length: 9 }).map((_, idx) => (
              <div
                key={idx}
                className="rounded-2xl border border-slate-800/80 bg-[#0b101d] overflow-hidden animate-pulse"
              >
                <div className="h-44 w-full bg-slate-800/80" />
                <div className="p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="h-4 w-24 bg-slate-800 rounded" />
                    <div className="h-4 w-20 bg-slate-800 rounded" />
                  </div>
                  <div className="h-5 w-full bg-slate-800 rounded" />
                  <div className="h-5 w-4/5 bg-slate-800 rounded" />
                  <div className="h-10 w-full bg-slate-900 rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : filteredArticles.length === 0 ? (
          <div className="rounded-2xl border border-slate-800 bg-[#0b101d] p-10 text-center space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto text-slate-400">
              <LucideIcon name="newspaper" className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-slate-200">Tidak Ada Artikel dalam 7 Hari Terakhir</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              Belum ada berita untuk filter atau kata kunci ini dalam 1 minggu terakhir. Coba ganti kategori atau reset filter sentimen.
            </p>
            <button
              type="button"
              onClick={() => {
                setSentimentFilter('ALL');
                setSearchInput('');
                setActiveQuery('');
                loadNews(selectedCategory, '', true);
              }}
              className="px-4 py-2 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs font-bold"
            >
              Tampilkan Semua Berita
            </button>
          </div>
        ) : (
          /* News Grid with Visual Thumbnail - Ordered Newest to Oldest (Max 7 Days) */
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {filteredArticles.map((article, index) => {
              const fallbackThumb = FALLBACK_THUMBS[article.category] || FALLBACK_THUMBS.ekonomi;
              return (
                <a
                  key={article.id}
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group rounded-2xl border border-slate-800/90 hover:border-cyan-500/50 bg-[#0b101d]/95 hover:bg-[#0f172a] overflow-hidden flex flex-col justify-between transition-all duration-200 shadow-lg hover:shadow-cyan-950/40"
                >
                  <div>
                    {/* Article Thumbnail Image */}
                    <div className="relative h-44 w-full overflow-hidden bg-slate-900">
                      <img
                        src={article.image_url || fallbackThumb}
                        alt={article.title}
                        loading="lazy"
                        onError={(e) => {
                          const target = e.currentTarget;
                          if (target.src !== fallbackThumb) {
                            target.src = fallbackThumb;
                          }
                        }}
                        className="w-full h-full object-cover object-center group-hover:scale-105 transition-transform duration-500"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-[#0b101d] via-transparent to-black/30" />

                      {/* Top Left Overlay: Category Badge + Rank #1..N */}
                      <div className="absolute top-3 left-3 flex items-center gap-1.5">
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-black font-mono bg-slate-950/85 text-cyan-300 border border-slate-700/80 backdrop-blur-sm">
                          #{index + 1}
                        </span>
                        <span
                          className={`px-2.5 py-0.5 rounded-md text-[10px] font-extrabold uppercase border shadow-sm ${getCategoryBadgeStyle(
                            article.category
                          )}`}
                        >
                          {article.category_label}
                        </span>
                      </div>

                      {/* Top Right Overlay: Relative Time Badge */}
                      <div className="absolute top-3 right-3">
                        <span className="px-2.5 py-1 rounded-md text-[10px] font-bold font-mono bg-slate-950/85 text-emerald-300 border border-slate-700/80 backdrop-blur-sm">
                          🕒 {article.relative_time}
                        </span>
                      </div>
                    </div>

                    {/* Content Body */}
                    <div className="p-4 sm:p-5 space-y-2.5">
                      {/* Date WIB + Sentiment Row */}
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-mono text-slate-400">
                          {article.formatted_date || article.relative_time}
                        </span>
                        {getSentimentBadge(article.sentiment)}
                      </div>

                      {/* Headline */}
                      <h2 className="text-sm sm:text-[15px] font-bold text-slate-100 group-hover:text-cyan-300 leading-snug transition-colors line-clamp-2">
                        {article.title}
                      </h2>

                      {/* Summary Snippet */}
                      <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
                        {article.summary}
                      </p>
                    </div>
                  </div>

                  {/* Footer: Publisher Source & Direct Link CTA */}
                  <div className="px-4 sm:px-5 py-3 border-t border-slate-800/80 bg-slate-950/40 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 shrink-0" />
                      <span className="text-xs font-semibold text-slate-300 truncate">
                        {article.publisher}
                      </span>
                    </div>
                    <span className="inline-flex items-center gap-1 text-[11px] font-bold text-cyan-400 group-hover:text-cyan-300 shrink-0">
                      <span>Buka Artikel</span>
                      <LucideIcon name="external-link" className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </a>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
