'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Send,
  Plus,
  Search,
  Trash2,
  Brain,
  Sparkles,
  Loader2,
  MessageSquare,
  ChevronDown,
  ArrowUp,
  Square,
  Paperclip,
  Globe,
  Mic,
  MicOff,
  X,
  FileText,
  Image as ImageIcon,
  CheckCircle2,
  PanelLeftClose,
  PanelLeftOpen,
  Bell,
  Sun,
  Moon,
  TrendingUp,
  Bot,
  Globe2,
  ChevronRight,
  ExternalLink,
  Layers,
  LogOut,
  User as UserIcon,
} from 'lucide-react';

import Sidebar from '../../components/Sidebar';
import ChatMessage from '../../components/ChatMessage';
import { NotificationDrawer } from '../../components/modals/NotificationDrawer';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useThemeStore } from '../../stores/themeStore';
import { isToday, isYesterday, subDays, isAfter } from 'date-fns';

interface AttachedFile {
  file_id: string;
  filename: string;
  file_type: string;
  size_kb: number;
  summary: string;
  extracted_text: string;
  url: string;
}

export default function ChatPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const { user, isAuthenticated, logout } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();

  const {
    conversations,
    currentConversation,
    messages,
    streamingConversations,
    isLoading: chatLoading,
    isStreaming,
    selectConversation,
    createConversation,
    deleteConversation,
    sendMessage,
    stopStreaming,
    uploadAttachment,
  } = useChatStore();

  const [inputMessage, setInputMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [useMemory, setUseMemory] = useState(true);
  const [useWebSearch, setUseWebSearch] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // Model Selector
  const [selectedModel, setSelectedModel] = useState('Cognexa 2.0 Pro');
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);

  // User Profile Dropdown
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  // Notifications Drawer
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);

  // File Attachment State
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Voice Input State
  const [isListening, setIsListening] = useState(false);
  const speechRecognitionRef = useRef<any>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setMounted(true);
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('cognexa_token');
      if (!token) {
        window.location.href = '/login';
      } else {
        useChatStore.getState().fetchConversations();
      }

      // Listen for custom prompts dispatched from Explore / Prompts modal
      const handleSetPrompt = (e: any) => {
        if (e.detail) {
          setInputMessage(e.detail);
          if (textareaRef.current) {
            textareaRef.current.focus();
          }
        }
      };
      window.addEventListener('cognexa_set_prompt', handleSetPrompt);
      return () => {
        window.removeEventListener('cognexa_set_prompt', handleSetPrompt);
      };
    }
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        220
      )}px`;
    }
  }, [inputMessage]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isStreaming]);

  // Safe date parser to handle UTC strings from backend without Z
  const parseSafeDate = (dateStr?: string | null): Date => {
    if (!dateStr) return new Date();
    let str = String(dateStr).trim();
    if (str.includes(' ') && !str.includes('T')) {
      str = str.replace(' ', 'T');
    }
    if (!str.endsWith('Z') && !str.includes('+') && !/-\d\d:\d\d$/.test(str)) {
      str = str + 'Z';
    }
    const parsed = new Date(str);
    return isNaN(parsed.getTime()) ? new Date() : parsed;
  };

  // Group conversations by date (TODAY, YESTERDAY, PREVIOUS 7 DAYS, OLDER)
  const groupedConversations = useMemo(() => {
    const today: typeof conversations = [];
    const yesterday: typeof conversations = [];
    const previous7Days: typeof conversations = [];
    const older: typeof conversations = [];

    const now = new Date();
    const sevenDaysAgo = subDays(now, 7);

    // Sort newest updated/created first
    const sorted = [...conversations].sort((a, b) => {
      const timeB = parseSafeDate(b.updated_at || b.created_at).getTime();
      const timeA = parseSafeDate(a.updated_at || a.created_at).getTime();
      return timeB - timeA;
    });

    const filtered = sorted.filter((c) =>
      (c.title || '').toLowerCase().includes(searchQuery.toLowerCase())
    );

    filtered.forEach((conv) => {
      const d = parseSafeDate(conv.updated_at || conv.created_at);
      if (isToday(d)) {
        today.push(conv);
      } else if (isYesterday(d)) {
        yesterday.push(conv);
      } else if (isAfter(d, sevenDaysAgo)) {
        previous7Days.push(conv);
      } else {
        older.push(conv);
      }
    });

    return { today, yesterday, previous7Days, older };
  }, [conversations, searchQuery]);

  // Extract generated download artifacts for Notification Drawer
  const recentArtifacts = useMemo(() => {
    const list: Array<{
      id: string;
      title: string;
      type: 'pdf' | 'pptx' | 'image' | 'chart';
      filename: string;
      url: string;
      created_at: string;
    }> = [];

    messages.forEach((m) => {
      const content = String((m as any)?.content || '');
      const regex = /\[Click Here to Download:?\s*([^\]\)]+)\]\((https?:\/\/[^\s\)]+)/gi;
      let match: RegExpExecArray | null;
      let idx = 0;
      while ((match = regex.exec(content)) !== null) {
        const fn = match[1].trim();
        const url = match[2].trim();
        let type: 'pdf' | 'pptx' | 'image' | 'chart' = 'pdf';
        if (url.endsWith('.pptx')) type = 'pptx';
        else if (url.endsWith('.zip')) type = 'chart';
        else if (url.match(/\.(png|jpg|jpeg|webp)/i)) type = 'image';

        list.push({
          id: `${m.id}-${idx}`,
          title: fn.replace(/\.[^/.]+$/, '').replace(/_/g, ' '),
          filename: fn,
          type,
          url,
          created_at: m.created_at,
        });
        idx++;
      }
    });

    return list.reverse();
  }, [messages]);

  // File Attachment Handling
  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setIsUploading(true);

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        const uploaded = await uploadAttachment(file);
        if (uploaded) {
          setAttachedFiles((prev) => [...prev, uploaded]);
        }
      } catch (err) {
        console.error('File upload failed:', err);
      }
    }
    setIsUploading(false);
  };

  const removeAttachedFile = (fileId: string) => {
    setAttachedFiles((prev) => prev.filter((f) => f.file_id !== fileId));
  };

  // Voice Recognition
  const toggleVoiceInput = () => {
    if (typeof window === 'undefined') return;
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser.');
      return;
    }

    if (isListening) {
      if (speechRecognitionRef.current) {
        speechRecognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setInputMessage((prev) => (prev ? `${prev} ${transcript}` : transcript));
      setIsListening(false);
    };

    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);

    speechRecognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  };

  // Submit Handler
  const handleSendMessage = async (customPrompt?: string) => {
    const textToSend = (customPrompt || inputMessage).trim();
    if (!textToSend || isStreaming) return;

    setInputMessage('');
    const filesToSend = [...attachedFiles];
    setAttachedFiles([]);

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    let finalPrompt = textToSend;
    if (useWebSearch) {
      finalPrompt = `[Web Search Active] ${finalPrompt}`;
    }

    let attachmentContext = '';
    if (filesToSend.length > 0) {
      attachmentContext = filesToSend
        .map(
          (f) =>
            `[Attached File: ${f.filename} (${f.file_type}, ${f.size_kb} KB)]\n` +
            `Summary: ${f.summary}\n` +
            `Content Excerpt:\n${f.extracted_text.slice(0, 25000)}`
        )
        .join('\n\n---\n\n');
    }

    await sendMessage(
      finalPrompt,
      useMemory,
      attachmentContext || undefined,
      selectedModel
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (!mounted) return null;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#f8f9fc] dark:bg-[#0b0c14] text-slate-800 dark:text-slate-100 font-sans transition-colors duration-200">
      {/* 1. Leftmost Icon Rail */}
      <Sidebar />

      {/* 2. Second Panel: Collapsible Chat History (Matching Screenshot) */}
      <aside
        className={`${
          isSidebarCollapsed ? 'w-0 -ml-1 opacity-0 pointer-events-none' : 'w-72'
        } shrink-0 h-screen bg-white dark:bg-[#13141f] border-r border-slate-200/90 dark:border-[#222438] flex flex-col transition-all duration-300 z-20 overflow-hidden`}
      >
        {/* Chat History Header */}
        <div className="p-4 pb-3 flex items-center justify-between border-b border-slate-100 dark:border-[#1d1f30]">
          <h2 className="text-sm font-bold text-slate-800 dark:text-slate-200 tracking-tight">
            Chat History
          </h2>
          <button
            onClick={() => setIsSidebarCollapsed(true)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Collapse Sidebar"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>

        {/* Primary Action Button: [+ New Chat] in purple gradient matching image */}
        <div className="p-3">
          <button
            onClick={() => createConversation()}
            className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-purple-600 via-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold text-xs flex items-center justify-center space-x-2 shadow-sm hover:shadow-md transition-all active:scale-[0.98]"
          >
            <Plus className="w-4 h-4" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Search bar within conversations */}
        {conversations.length > 4 && (
          <div className="px-3 pb-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search history..."
                className="w-full pl-8 pr-3 py-1.5 rounded-lg text-xs bg-slate-50 dark:bg-[#0c0d17] border border-slate-200 dark:border-[#25283d] text-slate-700 dark:text-slate-300 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-purple-500"
              />
            </div>
          </div>
        )}

        {/* Grouped Conversations List */}
        <div className="flex-1 overflow-y-auto px-2 space-y-4 custom-scrollbar pb-6 text-xs">
          {/* Section: TODAY */}
          {groupedConversations.today.length > 0 && (
            <div>
              <div className="px-3 py-1 text-[10px] font-bold tracking-wider text-slate-400 dark:text-slate-500 uppercase">
                Today
              </div>
              <div className="space-y-0.5 mt-1">
                {groupedConversations.today.map((conv) => {
                  const isActive = currentConversation?.id === conv.id;
                  return (
                    <div
                      key={conv.id}
                      onClick={() => selectConversation(conv.id)}
                      className={`group relative flex items-center justify-between px-3 py-2 rounded-xl cursor-pointer transition-all ${
                        isActive
                          ? 'bg-purple-50 dark:bg-purple-950/40 text-purple-900 dark:text-purple-200 font-semibold shadow-xs'
                          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-100'
                      }`}
                    >
                      <span className="truncate pr-5">{conv.title || 'New chat'}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm('Delete this conversation?')) {
                            deleteConversation(conv.id);
                          }
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-rose-100 dark:hover:bg-rose-950/50 text-rose-500 transition-opacity"
                        title="Delete chat"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Section: YESTERDAY */}
          {groupedConversations.yesterday.length > 0 && (
            <div>
              <div className="px-3 py-1 text-[10px] font-bold tracking-wider text-slate-400 dark:text-slate-500 uppercase">
                Yesterday
              </div>
              <div className="space-y-0.5 mt-1">
                {groupedConversations.yesterday.map((conv) => {
                  const isActive = currentConversation?.id === conv.id;
                  return (
                    <div
                      key={conv.id}
                      onClick={() => selectConversation(conv.id)}
                      className={`group relative flex items-center justify-between px-3 py-2 rounded-xl cursor-pointer transition-all ${
                        isActive
                          ? 'bg-purple-50 dark:bg-purple-950/40 text-purple-900 dark:text-purple-200 font-semibold'
                          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-100'
                      }`}
                    >
                      <span className="truncate pr-5">{conv.title}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm('Delete this conversation?')) {
                            deleteConversation(conv.id);
                          }
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-rose-100 dark:hover:bg-rose-950/50 text-rose-500 transition-opacity"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Section: PREVIOUS 7 DAYS */}
          {groupedConversations.previous7Days.length > 0 && (
            <div>
              <div className="px-3 py-1 text-[10px] font-bold tracking-wider text-slate-400 dark:text-slate-500 uppercase">
                Previous 7 Days
              </div>
              <div className="space-y-0.5 mt-1">
                {groupedConversations.previous7Days.map((conv) => {
                  const isActive = currentConversation?.id === conv.id;
                  return (
                    <div
                      key={conv.id}
                      onClick={() => selectConversation(conv.id)}
                      className={`group relative flex items-center justify-between px-3 py-2 rounded-xl cursor-pointer transition-all ${
                        isActive
                          ? 'bg-purple-50 dark:bg-purple-950/40 text-purple-900 dark:text-purple-200 font-semibold'
                          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-100'
                      }`}
                    >
                      <span className="truncate pr-5">{conv.title}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm('Delete this conversation?')) {
                            deleteConversation(conv.id);
                          }
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-rose-100 dark:hover:bg-rose-950/50 text-rose-500 transition-opacity"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Section: OLDER */}
          {groupedConversations.older.length > 0 && (
            <div>
              <div className="px-3 py-1 text-[10px] font-bold tracking-wider text-slate-400 dark:text-slate-500 uppercase">
                Older
              </div>
              <div className="space-y-0.5 mt-1">
                {groupedConversations.older.map((conv) => {
                  const isActive = currentConversation?.id === conv.id;
                  return (
                    <div
                      key={conv.id}
                      onClick={() => selectConversation(conv.id)}
                      className={`group relative flex items-center justify-between px-3 py-2 rounded-xl cursor-pointer transition-all ${
                        isActive
                          ? 'bg-purple-50 dark:bg-purple-950/40 text-purple-900 dark:text-purple-200 font-semibold'
                          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-100'
                      }`}
                    >
                      <span className="truncate pr-5">{conv.title}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm('Delete this conversation?')) {
                            deleteConversation(conv.id);
                          }
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-rose-100 dark:hover:bg-rose-950/50 text-rose-500 transition-opacity"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {conversations.length === 0 && (
            <div className="text-center py-8 text-slate-400">
              <p className="text-xs">No conversations yet</p>
            </div>
          )}
        </div>
      </aside>

      {/* 3. Main Workspace Area */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden relative">
        {/* Top Header Bar (Matching LUMIQ / Screenshot) */}
        <header className="h-16 shrink-0 flex items-center justify-between px-6 border-b border-slate-200/80 dark:border-[#222438] bg-white/70 dark:bg-[#13141f]/70 backdrop-blur-md z-10">
          <div className="flex items-center space-x-3">
            {isSidebarCollapsed && (
              <button
                onClick={() => setIsSidebarCollapsed(false)}
                className="p-2 rounded-xl text-slate-500 hover:text-slate-800 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                title="Open Chat History"
              >
                <PanelLeftOpen className="w-5 h-5" />
              </button>
            )}

            {/* Model Selector Dropdown */}
            <div className="relative">
              <button
                onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
                className="flex items-center space-x-2 px-3 py-1.5 rounded-xl bg-slate-50 dark:bg-[#1a1c2b] border border-slate-200/80 dark:border-[#292c42] text-xs font-bold text-slate-800 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
              >
                <span>{selectedModel}</span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>

              {isModelDropdownOpen && (
                <div className="absolute top-full left-0 mt-1.5 w-56 rounded-xl bg-white dark:bg-[#161726] border border-slate-200 dark:border-[#26283d] shadow-xl p-1 z-30 animate-in fade-in zoom-in-95 duration-150">
                  {[
                    { id: 'Cognexa 2.0 Pro', badge: 'Fastest + RAG' },
                    { id: 'Qwen 2.5 7B Core', badge: 'Local Reasoning' },
                    { id: 'Deep Research Mode', badge: 'Web + Citations' },
                    { id: 'Multi-Agent Swarm', badge: 'Autonomous Dev' },
                  ].map((m) => (
                    <button
                      key={m.id}
                      onClick={() => {
                        setSelectedModel(m.id);
                        setIsModelDropdownOpen(false);
                      }}
                      className={`w-full text-left px-3 py-2 rounded-lg text-xs flex items-center justify-between transition-colors ${
                        selectedModel === m.id
                          ? 'bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 font-bold'
                          : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                      }`}
                    >
                      <span>{m.id}</span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {m.badge}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center space-x-3">
            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-xl text-slate-500 dark:text-slate-400 hover:text-amber-500 dark:hover:text-amber-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} theme`}
            >
              {theme === 'light' ? (
                <Moon className="w-4 h-4 text-purple-600" />
              ) : (
                <Sun className="w-4 h-4 text-amber-400" />
              )}
            </button>

            {/* Notification Bell */}
            <button
              onClick={() => setIsNotificationsOpen(true)}
              className="relative p-2 rounded-xl text-slate-500 dark:text-slate-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              title="Recent Downloads & Artifacts"
            >
              <Bell className="w-4 h-4" />
              {recentArtifacts.length > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-purple-600 animate-pulse" />
              )}
            </button>

            {/* User Profile Avatar */}
            <div className="relative">
              <button
                onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-600 via-indigo-600 to-cyan-500 text-white flex items-center justify-center font-bold text-xs shadow-sm hover:scale-105 transition-transform"
                title="Account"
              >
                {user?.username ? user.username.charAt(0).toUpperCase() : 'S'}
              </button>

              {isUserMenuOpen && (
                <div className="absolute top-full right-0 mt-2 w-48 rounded-xl bg-white dark:bg-[#161726] border border-slate-200 dark:border-[#26283d] shadow-xl p-2 z-30 animate-in fade-in zoom-in-95 duration-150">
                  <div className="px-3 py-2 border-b border-slate-100 dark:border-[#222438] mb-1">
                    <p className="text-xs font-bold text-slate-900 dark:text-white truncate">
                      {user?.username || 'Supriya'}
                    </p>
                    <p className="text-[11px] text-slate-400 truncate">
                      {user?.email || 'admin@cognexa.ai'}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      logout();
                      router.push('/login');
                    }}
                    className="w-full flex items-center space-x-2 px-3 py-2 rounded-lg text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors font-medium"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* 4. Chat View Container */}
        <div
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto px-4 md:px-8 py-6 custom-scrollbar"
        >
          {messages.length === 0 ? (
            /* HERO EMPTY STATE - EXACT MATCH TO USER'S SCREENSHOT */
            <div className="max-w-3xl mx-auto flex flex-col items-center justify-center min-h-[75vh] text-center pt-8">
              {/* Main Headline */}
              <h1 className="text-3xl sm:text-4xl md:text-[42px] font-bold tracking-tight text-slate-900 dark:text-white mb-2.5">
                What will you discover today?
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 max-w-xl mx-auto mb-8 font-normal leading-relaxed">
                Your personal AI research partner, explore insights, analyze data, and uncover knowledge faster than ever.
              </p>

              {/* Floating Input Card (Hero version) */}
              <div className="w-full max-w-2xl bg-white dark:bg-[#151624] border border-slate-200/90 dark:border-[#26283d] rounded-2xl shadow-card dark:shadow-card-dark p-3.5 mb-8 text-left transition-all hover:border-purple-300 dark:hover:border-purple-800">
                {/* Attached file badges */}
                {attachedFiles.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2 p-1">
                    {attachedFiles.map((f) => (
                      <span
                        key={f.file_id}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-purple-50 dark:bg-purple-950/50 border border-purple-200 dark:border-purple-800/60 text-purple-700 dark:text-purple-300 text-xs"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        <span className="truncate max-w-[150px]">{f.filename}</span>
                        <button
                          onClick={() => removeAttachedFile(f.file_id)}
                          className="hover:text-rose-500 ml-0.5"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                <textarea
                  ref={textareaRef}
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask Anything... (e.g. create a PDF for smart contracts, generate presentation, solve question bank)"
                  rows={2}
                  className="w-full resize-none bg-transparent text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none px-2 py-1"
                />

                {/* Bottom toolbar inside input card */}
                <div className="flex items-center justify-between pt-2 px-1 border-t border-slate-100 dark:border-[#1e2033] mt-2">
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
                      className="px-2.5 py-1 rounded-lg bg-slate-50 dark:bg-[#1c1d2e] border border-slate-200/80 dark:border-[#26283d] text-[11px] font-semibold text-slate-600 dark:text-slate-300 flex items-center space-x-1 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      <span>{selectedModel}</span>
                      <ChevronDown className="w-3 h-3 text-slate-400" />
                    </button>
                  </div>

                  <div className="flex items-center space-x-2">
                    {/* Live Web Search Toggle */}
                    <button
                      type="button"
                      onClick={() => setUseWebSearch(!useWebSearch)}
                      className={`p-2 rounded-xl text-xs transition-all ${
                        useWebSearch
                          ? 'bg-cyan-100 dark:bg-cyan-950/60 text-cyan-600 dark:text-cyan-400 border border-cyan-300 dark:border-cyan-800'
                          : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                      }`}
                      title={useWebSearch ? 'Live Web Search: Active' : 'Enable Real-time Web Search'}
                    >
                      <Globe className="w-4 h-4" />
                    </button>

                    {/* File Attachment */}
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      accept=".pdf,.txt,.docx,.md"
                      onChange={(e) => handleFileUpload(e.target.files)}
                      className="hidden"
                    />
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading}
                      className="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                      title="Attach Syllabus, Textbook or PDF"
                    >
                      {isUploading ? (
                        <Loader2 className="w-4 h-4 animate-spin text-purple-600" />
                      ) : (
                        <Paperclip className="w-4 h-4" />
                      )}
                    </button>

                    {/* Send Button */}
                    <button
                      type="button"
                      onClick={() => handleSendMessage()}
                      disabled={!inputMessage.trim() || isStreaming}
                      className="w-8 h-8 rounded-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white flex items-center justify-center shadow-sm transition-transform active:scale-95"
                    >
                      <ArrowUp className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* 3 Quick Starter Cards (Matching Screenshot Grid) */}
              <div className="w-full max-w-2xl grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                {/* Card 1: Trending Topics */}
                <div
                  onClick={() =>
                    handleSendMessage(
                      'What are the top trending topics and emerging discussions in technology, science, and global innovation today?'
                    )
                  }
                  className="p-4 rounded-2xl bg-white dark:bg-[#151624] border border-slate-200/80 dark:border-[#26283d] shadow-sm hover:shadow-md hover:border-purple-300 dark:hover:border-purple-800/80 cursor-pointer text-left transition-all group"
                >
                  <div className="w-8 h-8 rounded-xl bg-purple-100 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 flex items-center justify-center mb-3">
                    <TrendingUp className="w-4 h-4" />
                  </div>
                  <h3 className="text-xs font-bold text-slate-900 dark:text-white group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                    Trending Topics
                  </h3>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 leading-snug line-clamp-2">
                    Stay ahead with the most discussed subjects in tech, science, and innovation.
                  </p>
                </div>

                {/* Card 2: AI Discoveries */}
                <div
                  onClick={() =>
                    handleSendMessage(
                      'What are the most significant recent breakthroughs in Artificial Intelligence, LLMs, and autonomous agents in 2026?'
                    )
                  }
                  className="p-4 rounded-2xl bg-white dark:bg-[#151624] border border-slate-200/80 dark:border-[#26283d] shadow-sm hover:shadow-md hover:border-purple-300 dark:hover:border-purple-800/80 cursor-pointer text-left transition-all group"
                >
                  <div className="w-8 h-8 rounded-xl bg-indigo-100 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mb-3">
                    <Bot className="w-4 h-4" />
                  </div>
                  <h3 className="text-xs font-bold text-slate-900 dark:text-white group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                    AI Discoveries
                  </h3>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 leading-snug line-clamp-2">
                    Dive into the latest breakthroughs in machine learning and automation.
                  </p>
                </div>

                {/* Card 3: Global Insights */}
                <div
                  onClick={() =>
                    handleSendMessage(
                      'Provide a strategic overview of the key technological, economic, and digital transformation trends shaping our future in 2026.'
                    )
                  }
                  className="p-4 rounded-2xl bg-white dark:bg-[#151624] border border-slate-200/80 dark:border-[#26283d] shadow-sm hover:shadow-md hover:border-purple-300 dark:hover:border-purple-800/80 cursor-pointer text-left transition-all group"
                >
                  <div className="w-8 h-8 rounded-xl bg-cyan-100 dark:bg-cyan-950/60 text-cyan-600 dark:text-cyan-400 flex items-center justify-center mb-3">
                    <Globe2 className="w-4 h-4" />
                  </div>
                  <h3 className="text-xs font-bold text-slate-900 dark:text-white group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                    Global Insights
                  </h3>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 leading-snug line-clamp-2">
                    Explore reports and trends shaping the digital future.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            /* ACTIVE MESSAGES STREAM */
            <div className="max-w-3xl mx-auto pb-32">
              {messages.map((m) => (
                <ChatMessage key={m.id} message={m} />
              ))}

              {isStreaming && (
                <div className="flex items-center space-x-3 text-xs text-purple-600 dark:text-purple-400 py-3 animate-pulse">
                  <Brain className="w-4 h-4 animate-spin" />
                  <span>Cognexa is researching and synthesizing response...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* 5. Sticky Bottom Input Box (When Messages Are Present) */}
        {messages.length > 0 && (
          <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-[#f8f9fc] via-[#f8f9fc] to-transparent dark:from-[#0b0c14] dark:via-[#0b0c14] dark:to-transparent z-10">
            <div className="max-w-3xl mx-auto bg-white dark:bg-[#151624] border border-slate-200/90 dark:border-[#26283d] rounded-2xl shadow-lg p-3 text-left">
              {/* Attached file badges */}
              {attachedFiles.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2 p-1">
                  {attachedFiles.map((f) => (
                    <span
                      key={f.file_id}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-purple-50 dark:bg-purple-950/50 border border-purple-200 dark:border-purple-800/60 text-purple-700 dark:text-purple-300 text-xs"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      <span className="truncate max-w-[150px]">{f.filename}</span>
                      <button
                        onClick={() => removeAttachedFile(f.file_id)}
                        className="hover:text-rose-500 ml-0.5"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}

              <textarea
                ref={textareaRef}
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask Anything... (e.g. generate in PDF format, create PPT, analyze data)"
                rows={1}
                className="w-full resize-none bg-transparent text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none px-2 py-1 max-h-36 custom-scrollbar"
              />

              <div className="flex items-center justify-between pt-2 px-1 border-t border-slate-100 dark:border-[#1e2033] mt-2">
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
                    className="px-2.5 py-1 rounded-lg bg-slate-50 dark:bg-[#1c1d2e] border border-slate-200/80 dark:border-[#26283d] text-[11px] font-semibold text-slate-600 dark:text-slate-300 flex items-center space-x-1 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    <span>{selectedModel}</span>
                    <ChevronDown className="w-3 h-3 text-slate-400" />
                  </button>
                </div>

                <div className="flex items-center space-x-2">
                  {/* Live Web Search */}
                  <button
                    type="button"
                    onClick={() => setUseWebSearch(!useWebSearch)}
                    className={`p-2 rounded-xl text-xs transition-all ${
                      useWebSearch
                        ? 'bg-cyan-100 dark:bg-cyan-950/60 text-cyan-600 dark:text-cyan-400 border border-cyan-300 dark:border-cyan-800'
                        : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                    title={useWebSearch ? 'Live Web Search: Active' : 'Enable Real-time Web Search'}
                  >
                    <Globe className="w-4 h-4" />
                  </button>

                  {/* Attachment */}
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.txt,.docx,.md"
                    onChange={(e) => handleFileUpload(e.target.files)}
                    className="hidden"
                    id="bottom-file-picker"
                  />
                  <button
                    type="button"
                    onClick={() => document.getElementById('bottom-file-picker')?.click()}
                    disabled={isUploading}
                    className="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                    title="Attach File"
                  >
                    {isUploading ? (
                      <Loader2 className="w-4 h-4 animate-spin text-purple-600" />
                    ) : (
                      <Paperclip className="w-4 h-4" />
                    )}
                  </button>

                  {/* Send or Stop button */}
                  {isStreaming ? (
                    <button
                      type="button"
                      onClick={() => stopStreaming()}
                      className="w-8 h-8 rounded-full bg-rose-600 hover:bg-rose-700 text-white flex items-center justify-center shadow-sm animate-pulse"
                      title="Stop Response"
                    >
                      <Square className="w-3.5 h-3.5 fill-current" />
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleSendMessage()}
                      disabled={!inputMessage.trim()}
                      className="w-8 h-8 rounded-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white flex items-center justify-center shadow-sm transition-transform active:scale-95"
                      title="Send Prompt"
                    >
                      <ArrowUp className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Real Notification Drawer */}
        <NotificationDrawer
          isOpen={isNotificationsOpen}
          onClose={() => setIsNotificationsOpen(false)}
          recentArtifacts={recentArtifacts}
        />
      </main>
    </div>
  );
}
