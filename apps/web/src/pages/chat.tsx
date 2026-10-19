import React, { useState, useEffect, useRef } from 'react';
import Head from 'next/head';
import { api } from '@/lib/api';
import { LucideIcon } from '@/components/LucideIcon';

interface ChatSessionItem {
  id: string;
  title: string;
  provider: string;
  model: string;
  updated_at: string;
  created_at: string;
}

interface ChatMessageItem {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  tool_calls?: any[] | null;
  tool_results?: any[] | null;
  created_at: string;
}

interface ChatModelItem {
  id: string;
  name: string;
  provider: string;
  context_length?: number;
  is_free: boolean;
  pricing?: {
    prompt: number;
    completion: number;
  };
  description?: string;
}

interface SofiaToolItem {
  name: string;
  description: string;
  category: string;
  parameters: any;
}

const PROVIDERS = [
  { id: 'openrouter', label: 'OpenRouter', badge: 'AI Hub (200+ Models)' },
  { id: '9router', label: '9Router', badge: 'Multi-Engine Pro' },
  { id: 'gemini', label: 'Google Gemini', badge: 'Google Cloud AI' },
];

const STARTER_PROMPTS = [
  {
    title: 'Analisis Saham BBRI',
    prompt: 'Analisis fundamental dan teknikal saham BBRI hari ini, bagaimana struktur bandarmologi dan support resistance-nya?',
    icon: 'trending-up',
    badge: 'Stock Tool',
  },
  {
    title: 'Deposito Syariah vs Obligasi',
    prompt: 'Simulasikan investasi Rp 50.000.000: bandingkan imbal hasil Deposito Syariah Mudharabah (nisbah 55%) vs Obligasi FR0101 (kupon 6.8%) tenor 1 tahun setelah pajak.',
    icon: 'banknote',
    badge: 'Calculator Tool',
  },
  {
    title: 'Harga Emas & Buyback Antam',
    prompt: 'Berapa harga emas fisik Antam dan UBS hari ini? Hitung potensi buyback jika saya menjual 25 gram emas Antam yang dibeli di harga 1.300.000 per gram.',
    icon: 'coins',
    badge: 'Gold Tool',
  },
  {
    title: 'Analisa On-Chain Kripto (BTC)',
    prompt: 'Bagaimana analisa on-chain, sentimen RSI, dan indikator teknikal Bitcoin (BTC) saat ini? Apakah aman untuk DCA?',
    icon: 'zap',
    badge: 'Crypto Tool',
  },
];

export default function ChatPage() {
  // Navigation & Sessions State
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [loadingSessions, setLoadingSessions] = useState<boolean>(true);
  const [loadingMessages, setLoadingMessages] = useState<boolean>(false);

  // Model & Provider State
  const [selectedProvider, setSelectedProvider] = useState<string>('openrouter');
  const [models, setModels] = useState<ChatModelItem[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('google/gemini-2.0-flash-exp:free');
  const [freeOnly, setFreeOnly] = useState<boolean>(true);
  const [searchModelQuery, setSearchModelQuery] = useState<string>('');
  const [importingModels, setImportingModels] = useState<boolean>(false);
  const [modelsNotice, setModelsNotice] = useState<string>('');

  // Tools Modal
  const [tools, setTools] = useState<SofiaToolItem[]>([]);
  const [toolsModalOpen, setToolsModalOpen] = useState<boolean>(false);

  // API Key Settings Modal
  const [apiKeyModalOpen, setApiKeyModalOpen] = useState<boolean>(false);
  const [openrouterApiKey, setOpenrouterApiKey] = useState<string>('');
  const [nineRouterApiKey, setNineRouterApiKey] = useState<string>('');
  const [geminiApiKey, setGeminiApiKey] = useState<string>('');
  const [apiKeySavedNotice, setApiKeySavedNotice] = useState<string>('');

  // Editing session title inline
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>('');

  // Message Sending
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isSending, setIsSending] = useState<boolean>(false);
  const [expandedToolMsgId, setExpandedToolMsgId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load saved API keys from localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setOpenrouterApiKey(localStorage.getItem('sofia_apikey_openrouter') || '');
      setNineRouterApiKey(localStorage.getItem('sofia_apikey_9router') || '');
      setGeminiApiKey(localStorage.getItem('sofia_apikey_gemini') || '');
    }
  }, []);

  // Fetch Sessions list on mount
  const fetchSessions = async () => {
    try {
      setLoadingSessions(true);
      const res = await api.getChatSessions();
      if (res?.sessions) {
        setSessions(res.sessions);
        if (res.sessions.length > 0 && !activeSessionId) {
          setActiveSessionId(res.sessions[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to load chat sessions:', err);
    } finally {
      setLoadingSessions(false);
    }
  };

  useEffect(() => {
    fetchSessions();
    fetchTools();
  }, []);

  // Fetch Tools catalog
  const fetchTools = async () => {
    try {
      const res = await api.getChatTools();
      if (res?.tools) {
        setTools(res.tools);
      }
    } catch (err) {
      console.error('Failed to fetch tools:', err);
    }
  };

  // Fetch Models when provider or freeOnly changes
  const fetchModels = async (refresh: boolean = false) => {
    try {
      setImportingModels(true);
      setModelsNotice('');
      const res = await api.getChatModels(selectedProvider, freeOnly, refresh);
      if (res?.models) {
        setModels(res.models);
        if (refresh) {
          setModelsNotice(`✅ Berhasil import & perbarui ${res.models.length} model dari ${selectedProvider.toUpperCase()}`);
          setTimeout(() => setModelsNotice(''), 4000);
        }
        // Set default model if not matching
        const exists = res.models.some((m: ChatModelItem) => m.id === selectedModel);
        if (!exists && res.models.length > 0) {
          setSelectedModel(res.models[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to load models:', err);
      setModelsNotice('⚠️ Gagal mengambil model dari provider.');
    } finally {
      setImportingModels(false);
    }
  };

  useEffect(() => {
    fetchModels(false);
  }, [selectedProvider, freeOnly]);

  // Load Messages when activeSessionId changes
  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    const loadSession = async () => {
      try {
        setLoadingMessages(true);
        const res = await api.getChatSession(activeSessionId);
        if (res?.session) {
          if (res.session.provider) setSelectedProvider(res.session.provider);
          if (res.session.model) setSelectedModel(res.session.model);
        }
        if (res?.messages) {
          setMessages(res.messages);
        }
      } catch (err) {
        console.error('Failed to load session messages:', err);
      } finally {
        setLoadingMessages(false);
      }
    };
    loadSession();
  }, [activeSessionId]);

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSending]);

  // Handle Save API Keys
  const handleSaveApiKeys = () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('sofia_apikey_openrouter', openrouterApiKey.trim());
      localStorage.setItem('sofia_apikey_9router', nineRouterApiKey.trim());
      localStorage.setItem('sofia_apikey_gemini', geminiApiKey.trim());
      setApiKeySavedNotice('✅ Kunci API berhasil disimpan secara lokal di browser!');
      setTimeout(() => {
        setApiKeySavedNotice('');
        setApiKeyModalOpen(false);
      }, 1500);
    }
  };

  const getActiveApiKey = () => {
    if (selectedProvider === 'openrouter') return openrouterApiKey;
    if (selectedProvider === '9router') return nineRouterApiKey;
    if (selectedProvider === 'gemini') return geminiApiKey;
    return '';
  };

  // Create New Session
  const handleCreateNewSession = async () => {
    try {
      const res = await api.createChatSession({
        title: 'Sesi Riset Baru',
        provider: selectedProvider,
        model: selectedModel,
      });
      if (res?.session) {
        setSessions([res.session, ...sessions]);
        setActiveSessionId(res.session.id);
        setMessages([]);
        if (inputRef.current) inputRef.current.focus();
      }
    } catch (err) {
      console.error('Failed to create new chat session:', err);
    }
  };

  // Delete Session
  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Hapus sesi chat ini beserta seluruh riwayatnya?')) return;
    try {
      await api.deleteChatSession(sessionId);
      const remaining = sessions.filter((s) => s.id !== sessionId);
      setSessions(remaining);
      if (activeSessionId === sessionId) {
        if (remaining.length > 0) {
          setActiveSessionId(remaining[0].id);
        } else {
          setActiveSessionId('');
          setMessages([]);
        }
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  // Save Session Title inline
  const handleSaveTitle = async (sessionId: string) => {
    if (!editingTitle.trim()) {
      setEditingSessionId(null);
      return;
    }
    try {
      await api.updateChatSession(sessionId, { title: editingTitle.trim() });
      setSessions(
        sessions.map((s) => (s.id === sessionId ? { ...s, title: editingTitle.trim() } : s))
      );
    } catch (err) {
      console.error('Failed to update title:', err);
    } finally {
      setEditingSessionId(null);
    }
  };

  // Send message
  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend !== undefined ? textToSend : inputMessage).trim();
    if (!text || isSending) return;

    setInputMessage('');
    setIsSending(true);

    // Optimistic user message
    const tempUserMsg: ChatMessageItem = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const apiKey = getActiveApiKey();
      const payload: any = {
        message: text,
        provider: selectedProvider,
        model: selectedModel,
      };
      if (activeSessionId) {
        payload.session_id = activeSessionId;
      }
      if (apiKey) {
        payload.api_key = apiKey;
      }

      const res = await api.sendChatMessage(payload);

      if (res?.session_id && res.session_id !== activeSessionId) {
        setActiveSessionId(res.session_id);
        fetchSessions();
      }

      if (res?.message) {
        const assistantMsg: ChatMessageItem = {
          id: res.message.id || `ai-${Date.now()}`,
          role: 'assistant',
          content: res.message.content || '',
          tool_calls: res.message.tool_calls || null,
          tool_results: res.message.tool_results || null,
          created_at: res.message.created_at || new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      }
    } catch (err: any) {
      console.error('Chat error:', err);
      const errorMsg: ChatMessageItem = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `⚠️ **Terjadi Kesalahan Komunikasi dengan AI**\n\n${
          err?.message || 'Tidak dapat terhubung ke model AI. Pastikan API key Anda valid atau gunakan model gratis.'
        }`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Filter models based on search query
  const filteredModels = models.filter((m) =>
    m.name.toLowerCase().includes(searchModelQuery.toLowerCase()) ||
    m.id.toLowerCase().includes(searchModelQuery.toLowerCase())
  );

  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const currentModelObj = models.find((m) => m.id === selectedModel);

  return (
    <>
      <Head>
        <title>AI Chat & Research Assistant | SOFIA Trading System</title>
      </Head>

      <div className="flex flex-col h-[calc(100vh-4.5rem)] min-h-[600px] -m-4 md:-m-6 overflow-hidden">
        {/* TOP STATUS BAR */}
        <div className="bg-obsidian-900 border-b border-obsidian-750 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0">
              <LucideIcon name="sparkles" className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-sm text-slate-100 truncate">
                  {activeSession ? activeSession.title : 'SOFIA AI Financial Analyst'}
                </h1>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 uppercase shrink-0">
                  {selectedProvider}
                </span>
                {currentModelObj?.is_free && (
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                    FREE TIER
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 truncate">
                Model: <span className="font-mono text-slate-300">{selectedModel}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* View Available Tools Button */}
            <button
              type="button"
              onClick={() => setToolsModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-obsidian-850 hover:bg-obsidian-800 border border-obsidian-700 text-slate-300 hover:text-white text-xs font-medium transition"
              title="Daftar tools internal SOFIA yang dapat dibaca dan dieksekusi AI"
            >
              <LucideIcon name="wrench" className="w-3.5 h-3.5 text-amber-400" />
              <span>Tools Aktif ({tools.length || 7})</span>
            </button>

            {/* API Keys Configuration Button */}
            <button
              type="button"
              onClick={() => setApiKeyModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-obsidian-850 hover:bg-obsidian-800 border border-obsidian-700 text-slate-300 hover:text-white text-xs font-medium transition"
              title="Konfigurasi API Key kustom untuk OpenRouter, 9Router, atau Gemini"
            >
              <LucideIcon name="key" className="w-3.5 h-3.5 text-cyan-400" />
              <span className="hidden sm:inline">Kunci API</span>
            </button>
          </div>
        </div>

        {/* DUAL PANE WORKSPACE */}
        <div className="flex-1 flex overflow-hidden">
          {/* LEFT SIDEBAR: SESSIONS & MODEL CONTROLS */}
          <aside className="w-72 sm:w-80 border-r border-obsidian-750 bg-obsidian-950/60 flex flex-col shrink-0">
            {/* Session Actions */}
            <div className="p-3 border-b border-obsidian-750 space-y-2.5">
              <button
                type="button"
                onClick={handleCreateNewSession}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs shadow-md transition"
              >
                <LucideIcon name="plus" className="w-4 h-4" />
                <span>+ Chat Baru (Sesi Baru)</span>
              </button>

              {/* Provider Selector Tabs */}
              <div className="grid grid-cols-3 gap-1 p-1 bg-obsidian-900 rounded-lg border border-obsidian-750 text-center">
                {PROVIDERS.map((p) => {
                  const active = selectedProvider === p.id;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setSelectedProvider(p.id)}
                      className={`px-1.5 py-1 rounded text-[11px] font-medium transition ${
                        active
                          ? 'bg-obsidian-800 text-white font-bold shadow-xs'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {p.label}
                    </button>
                  );
                })}
              </div>

              {/* Model Selector & Free Filter */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-400 font-medium">Pilih Model:</span>
                  <label className="flex items-center gap-1.5 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={freeOnly}
                      onChange={(e) => setFreeOnly(e.target.checked)}
                      className="rounded accent-emerald-500 w-3.5 h-3.5"
                    />
                    <span className="text-[10px] text-emerald-400 font-bold bg-emerald-500/10 px-1 rounded border border-emerald-500/20">
                      Hanya Free
                    </span>
                  </label>
                </div>

                {/* Model dropdown */}
                <div className="relative">
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="w-full text-xs font-mono bg-obsidian-900 border border-obsidian-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500 truncate"
                  >
                    {filteredModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.is_free ? '🟢 [FREE] ' : ''}
                        {m.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Import / Refresh Model Button */}
                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    onClick={() => fetchModels(true)}
                    disabled={importingModels}
                    className="flex items-center gap-1 text-[11px] text-cyan-400 hover:text-cyan-300 font-medium disabled:opacity-50"
                  >
                    <LucideIcon
                      name="refresh-cw"
                      className={`w-3 h-3 ${importingModels ? 'animate-spin' : ''}`}
                    />
                    <span>Import Model Otomatis</span>
                  </button>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {models.length} model
                  </span>
                </div>

                {modelsNotice && (
                  <p className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded p-1 text-center font-mono animate-fade-in">
                    {modelsNotice}
                  </p>
                )}
              </div>
            </div>

            {/* Sessions History List */}
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Riwayat Sesi Chat ({sessions.length})
              </div>

              {loadingSessions ? (
                <div className="p-4 text-center text-xs text-slate-500">Memuat riwayat sesi...</div>
              ) : sessions.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-500">
                  Belum ada sesi chat. Klik tombol <strong>+ Chat Baru</strong> di atas.
                </div>
              ) : (
                sessions.map((sess) => {
                  const isActive = sess.id === activeSessionId;
                  const isEditing = editingSessionId === sess.id;
                  return (
                    <div
                      key={sess.id}
                      onClick={() => setActiveSessionId(sess.id)}
                      className={`group flex items-center justify-between gap-2 p-2.5 rounded-xl border text-xs cursor-pointer transition ${
                        isActive
                          ? 'bg-obsidian-850 text-white border-emerald-500/40 shadow-xs'
                          : 'bg-obsidian-900/40 hover:bg-obsidian-900 text-slate-400 hover:text-slate-200 border-transparent hover:border-obsidian-750'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <LucideIcon
                          name="message-square"
                          className={`w-3.5 h-3.5 shrink-0 ${
                            isActive ? 'text-emerald-400' : 'text-slate-500'
                          }`}
                        />
                        {isEditing ? (
                          <input
                            type="text"
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            onBlur={() => handleSaveTitle(sess.id)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleSaveTitle(sess.id);
                              if (e.key === 'Escape') setEditingSessionId(null);
                            }}
                            autoFocus
                            onClick={(e) => e.stopPropagation()}
                            className="bg-obsidian-950 border border-emerald-500 rounded px-1.5 py-0.5 text-xs text-white w-full"
                          />
                        ) : (
                          <div className="truncate">
                            <span className="font-medium truncate block">{sess.title}</span>
                            <span className="text-[10px] text-slate-500 block font-mono">
                              {sess.provider} • {sess.updated_at ? sess.updated_at.slice(11, 16) : ''}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Action buttons on hover/active */}
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition shrink-0">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingSessionId(sess.id);
                            setEditingTitle(sess.title);
                          }}
                          className="p-1 hover:text-white text-slate-400 rounded"
                          title="Ubah judul sesi"
                        >
                          <LucideIcon name="edit" className="w-3 h-3" />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => handleDeleteSession(sess.id, e)}
                          className="p-1 hover:text-rose-400 text-slate-400 rounded"
                          title="Hapus sesi"
                        >
                          <LucideIcon name="trash-2" className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </aside>

          {/* RIGHT CHAT ARENA */}
          <main className="flex-1 flex flex-col bg-obsidian-950 overflow-hidden">
            {/* Messages Feed */}
            <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
              {loadingMessages ? (
                <div className="flex items-center justify-center h-full text-slate-500 text-xs gap-2">
                  <LucideIcon name="refresh-cw" className="w-4 h-4 animate-spin text-emerald-400" />
                  <span>Memuat percakapan...</span>
                </div>
              ) : messages.length === 0 ? (
                /* EMPTY STATE / STARTER CARDS */
                <div className="max-w-3xl mx-auto h-full flex flex-col items-center justify-center text-center py-8">
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-500/20 via-cyan-500/20 to-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-xl mb-4">
                    <LucideIcon name="bot" className="w-8 h-8" />
                  </div>
                  <h2 className="text-xl font-bold text-slate-100 mb-2">
                    SOFIA AI Multi-Tool Financial Assistant
                  </h2>
                  <p className="text-slate-400 text-xs md:text-sm max-w-lg mb-6 leading-relaxed">
                    Ajukan pertanyaan seputar saham BEI, koin kripto global, simulasi obligasi &amp; deposito, harga emas, hingga berita finansial. AI ini terintegrasi langsung dengan <strong>7 tools internal</strong> untuk mengambil data real-time.
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full text-left">
                    {STARTER_PROMPTS.map((sp, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleSendMessage(sp.prompt)}
                        className="p-3.5 rounded-xl bg-obsidian-900/70 hover:bg-obsidian-900 border border-obsidian-750 hover:border-emerald-500/40 text-left transition group shadow-sm"
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="font-semibold text-xs text-slate-200 group-hover:text-emerald-400 transition flex items-center gap-1.5">
                            <LucideIcon name={sp.icon} className="w-3.5 h-3.5 text-cyan-400" />
                            {sp.title}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-obsidian-800 text-slate-400 border border-obsidian-700">
                            {sp.badge}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                          {sp.prompt}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                /* MESSAGE STREAM */
                <div className="max-w-3xl mx-auto space-y-4">
                  {messages.map((msg) => {
                    const isUser = msg.role === 'user';
                    const hasTools = (msg.tool_calls && msg.tool_calls.length > 0) || (msg.tool_results && msg.tool_results.length > 0);
                    const isExpanded = expandedToolMsgId === msg.id;

                    return (
                      <div
                        key={msg.id}
                        className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
                      >
                        {!isUser && (
                          <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
                            <LucideIcon name="bot" className="w-4 h-4" />
                          </div>
                        )}

                        <div
                          className={`max-w-[85%] sm:max-w-[80%] rounded-2xl p-4 text-xs leading-relaxed space-y-2.5 ${
                            isUser
                              ? 'bg-emerald-600 text-white shadow-md rounded-tr-xs'
                              : 'bg-obsidian-900 border border-obsidian-750 text-slate-200 shadow-sm rounded-tl-xs'
                          }`}
                        >
                          {/* Tool execution indicator card if present */}
                          {hasTools && (
                            <div className="rounded-lg bg-obsidian-950 border border-obsidian-700 p-2 text-[11px] font-mono space-y-1.5">
                              <div
                                onClick={() => setExpandedToolMsgId(isExpanded ? null : msg.id)}
                                className="flex items-center justify-between cursor-pointer text-amber-400 hover:text-amber-300 font-bold"
                              >
                                <span className="flex items-center gap-1.5">
                                  <LucideIcon name="wrench" className="w-3 h-3 text-amber-400" />
                                  <span>Tools Internal SOFIA Dijalankan</span>
                                </span>
                                <LucideIcon
                                  name={isExpanded ? 'chevron-up' : 'chevron-down'}
                                  className="w-3 h-3 text-slate-400"
                                />
                              </div>

                              {isExpanded && (
                                <div className="pt-2 border-t border-obsidian-800 space-y-2 text-[10px] text-slate-400">
                                  {msg.tool_calls && msg.tool_calls.length > 0 && (
                                    <div>
                                      <span className="text-slate-500 block mb-0.5">Panggilan Tool:</span>
                                      <pre className="bg-obsidian-900 p-2 rounded border border-obsidian-800 overflow-x-auto text-cyan-300">
                                        {JSON.stringify(msg.tool_calls, null, 2)}
                                      </pre>
                                    </div>
                                  )}
                                  {msg.tool_results && msg.tool_results.length > 0 && (
                                    <div>
                                      <span className="text-slate-500 block mb-0.5">Data Hasil Tool:</span>
                                      <pre className="bg-obsidian-900 p-2 rounded border border-obsidian-800 overflow-x-auto text-emerald-300 max-h-48">
                                        {JSON.stringify(msg.tool_results, null, 2)}
                                      </pre>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Message Content formatted */}
                          <div className="whitespace-pre-wrap font-sans text-xs sm:text-[13px] leading-relaxed break-words">
                            {msg.content}
                          </div>

                          <div
                            className={`text-[9px] font-mono flex items-center justify-end ${
                              isUser ? 'text-emerald-200' : 'text-slate-500'
                            }`}
                          >
                            {msg.created_at ? msg.created_at.slice(11, 16) : ''}
                          </div>
                        </div>

                        {isUser && (
                          <div className="w-8 h-8 rounded-lg bg-obsidian-850 border border-obsidian-750 text-slate-300 flex items-center justify-center shrink-0 mt-0.5">
                            <span className="text-xs font-bold font-mono">U</span>
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {/* Thinking / Running Tools State */}
                  {isSending && (
                    <div className="flex gap-3 justify-start">
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0 animate-pulse">
                        <LucideIcon name="bot" className="w-4 h-4" />
                      </div>
                      <div className="bg-obsidian-900 border border-obsidian-750 rounded-2xl rounded-tl-xs p-3 text-xs text-slate-400 flex items-center gap-2 shadow-xs">
                        <LucideIcon name="refresh-cw" className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                        <span>SOFIA sedang membaca tools &amp; merumuskan analisa pasar...</span>
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* MESSAGE INPUT BAR */}
            <div className="p-3 md:p-4 bg-obsidian-900 border-t border-obsidian-750 shrink-0">
              <div className="max-w-3xl mx-auto space-y-2">
                <div className="flex items-end gap-2 bg-obsidian-950 rounded-xl border border-obsidian-750 p-2 focus-within:border-emerald-500 transition">
                  <textarea
                    ref={inputRef}
                    rows={2}
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Tanyakan analisis saham, kripto, obligasi, emas, atau minta AI jalankan tools... (Enter untuk kirim, Shift+Enter untuk baris baru)"
                    className="flex-1 bg-transparent border-0 text-slate-200 text-xs sm:text-sm placeholder-slate-500 focus:outline-none resize-none min-h-[38px] max-h-32"
                  />
                  <button
                    type="button"
                    onClick={() => handleSendMessage()}
                    disabled={!inputMessage.trim() || isSending}
                    className="p-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 text-white transition shrink-0"
                    title="Kirim pesan"
                  >
                    <LucideIcon name="send" className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 px-1">
                  <span>
                    Provider: <strong className="text-slate-400 font-mono">{selectedProvider}</strong> • Model:{' '}
                    <strong className="text-slate-400 font-mono truncate">{selectedModel}</strong>
                  </span>
                  <span>7 Tools Otomatis Aktif</span>
                </div>
              </div>
            </div>
          </main>
        </div>

        {/* MODAL 1: SOFIA INTERNAL TOOLS CATALOG */}
        {toolsModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs">
            <div className="bg-obsidian-900 border border-obsidian-700 rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl animate-fade-in">
              <div className="p-4 border-b border-obsidian-750 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-400 flex items-center justify-center">
                    <LucideIcon name="wrench" className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-slate-100">Daftar Tools Internal SOFIA</h3>
                    <p className="text-[11px] text-slate-400">
                      AI dapat memanggil fungsi ini secara otonom untuk menarik data real-time aplikasi
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setToolsModalOpen(false)}
                  className="p-1 text-slate-400 hover:text-white rounded"
                >
                  <LucideIcon name="x" className="w-5 h-5" />
                </button>
              </div>

              <div className="p-4 overflow-y-auto space-y-3 flex-1 text-xs">
                {tools.length === 0 ? (
                  <div className="p-4 text-center text-slate-500">Memuat spesifikasi tool...</div>
                ) : (
                  tools.map((t) => (
                    <div
                      key={t.name}
                      className="p-3 rounded-xl bg-obsidian-950 border border-obsidian-800 space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-emerald-400 text-[12px]">
                          {t.name}()
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-obsidian-850 text-slate-400 border border-obsidian-750 uppercase">
                          {t.category}
                        </span>
                      </div>
                      <p className="text-slate-300 text-[11px] leading-relaxed">{t.description}</p>
                      {t.parameters?.properties && (
                        <div className="pt-1 text-[10px] text-slate-500 font-mono">
                          Parameter:{' '}
                          <span className="text-cyan-300">
                            {Object.keys(t.parameters.properties).join(', ')}
                          </span>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>

              <div className="p-3 border-t border-obsidian-750 flex justify-end bg-obsidian-950/40 rounded-b-2xl">
                <button
                  type="button"
                  onClick={() => setToolsModalOpen(false)}
                  className="px-4 py-1.5 rounded-lg bg-obsidian-800 hover:bg-obsidian-750 text-slate-300 hover:text-white text-xs font-medium transition"
                >
                  Tutup
                </button>
              </div>
            </div>
          </div>
        )}

        {/* MODAL 2: API KEY CONFIGURATION */}
        {apiKeyModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs">
            <div className="bg-obsidian-900 border border-obsidian-700 rounded-2xl w-full max-w-lg shadow-2xl animate-fade-in space-y-4 p-5">
              <div className="flex items-center justify-between border-b border-obsidian-750 pb-3">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 flex items-center justify-center">
                    <LucideIcon name="key" className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-slate-100">Konfigurasi Kunci API AI</h3>
                    <p className="text-[11px] text-slate-400">
                      Kunci disimpan secara privat di browser lokal Anda
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setApiKeyModalOpen(false)}
                  className="p-1 text-slate-400 hover:text-white rounded"
                >
                  <LucideIcon name="x" className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-3.5 text-xs">
                <div>
                  <label className="block text-slate-300 font-medium mb-1">
                    OpenRouter API Key (sk-or-v1-...)
                  </label>
                  <input
                    type="password"
                    value={openrouterApiKey}
                    onChange={(e) => setOpenrouterApiKey(e.target.value)}
                    placeholder="Biarkan kosong untuk memakai kunci default sistem"
                    className="w-full bg-obsidian-950 border border-obsidian-700 rounded-lg px-3 py-2 text-slate-200 text-xs font-mono focus:outline-none focus:border-cyan-500"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">
                    Dapatkan di <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer" className="text-cyan-400 underline">openrouter.ai/keys</a> (tersedia ratusan model gratis &amp; berbayar).
                  </p>
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">
                    9Router API Key (9r-...)
                  </label>
                  <input
                    type="password"
                    value={nineRouterApiKey}
                    onChange={(e) => setNineRouterApiKey(e.target.value)}
                    placeholder="Biarkan kosong untuk memakai kunci default sistem"
                    className="w-full bg-obsidian-950 border border-obsidian-700 rounded-lg px-3 py-2 text-slate-200 text-xs font-mono focus:outline-none focus:border-cyan-500"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">
                    Dapatkan di <a href="https://9router.com" target="_blank" rel="noreferrer" className="text-cyan-400 underline">9router.com</a>.
                  </p>
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">
                    Google Gemini API Key (AIzaSy...)
                  </label>
                  <input
                    type="password"
                    value={geminiApiKey}
                    onChange={(e) => setGeminiApiKey(e.target.value)}
                    placeholder="Biarkan kosong untuk memakai kunci default sistem"
                    className="w-full bg-obsidian-950 border border-obsidian-700 rounded-lg px-3 py-2 text-slate-200 text-xs font-mono focus:outline-none focus:border-cyan-500"
                  />
                  <p className="text-[10px] text-slate-500 mt-1">
                    Dapatkan di <a href="https://aistudio.google.com" target="_blank" rel="noreferrer" className="text-cyan-400 underline">Google AI Studio</a> (Free tier tersedia).
                  </p>
                </div>

                {apiKeySavedNotice && (
                  <p className="text-xs text-emerald-400 font-medium bg-emerald-500/10 border border-emerald-500/20 rounded p-2 text-center">
                    {apiKeySavedNotice}
                  </p>
                )}
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-obsidian-750">
                <button
                  type="button"
                  onClick={() => setApiKeyModalOpen(false)}
                  className="px-3.5 py-1.5 rounded-lg bg-obsidian-800 hover:bg-obsidian-750 text-slate-300 text-xs font-medium"
                >
                  Batal
                </button>
                <button
                  type="button"
                  onClick={handleSaveApiKeys}
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium shadow-sm"
                >
                  Simpan Kunci
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
