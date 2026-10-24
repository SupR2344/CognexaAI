'use client';

import React, { useState } from 'react';
import NextLink from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Brain,
  MessageSquare,
  Database,
  CheckSquare,
  LayoutDashboard,
  LogOut,
  Sparkles,
  Image as ImageIcon,
  Presentation,
  Code2,
  Sun,
  Moon,
  HelpCircle,
  Settings,
  Folder,
  Layers,
} from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { useThemeStore } from '../stores/themeStore';
import { ImageStudioModal } from './modals/ImageStudioModal';
import { DocumentStudioModal } from './modals/DocumentStudioModal';
import { ExplorePromptsModal } from './modals/ExplorePromptsModal';
import { SettingsModal } from './modals/SettingsModal';

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();

  // Studio Modals state
  const [isImageStudioOpen, setIsImageStudioOpen] = useState(false);
  const [isDocStudioOpen, setIsDocStudioOpen] = useState(false);
  const [docStudioType, setDocStudioType] = useState<'pdf' | 'pptx'>('pdf');
  const [isExploreOpen, setIsExploreOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  const isChat = pathname === '/chat' || pathname === '/';
  const isDashboard = pathname === '/dashboard';
  const isMemory = pathname === '/memory';
  const isTasks = pathname === '/tasks';

  return (
    <>
      {/* Leftmost Narrow Icon Rail - Matches LUMIQ / Screenshot */}
      <aside className="w-16 shrink-0 h-screen sticky top-0 flex flex-col items-center justify-between py-4 bg-white dark:bg-[#12131f] border-r border-slate-200/90 dark:border-[#222438] z-30 transition-colors">
        {/* Top Brand Logo */}
        <div className="flex flex-col items-center space-y-4">
          <NextLink
            href="/chat"
            className="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-600 to-cyan-500 flex items-center justify-center text-white shadow-md hover:scale-105 transition-transform"
            title="Cognexa AI"
          >
            <Brain className="w-5 h-5 text-white" />
          </NextLink>

          {/* Group 1: Exploration & Analytics */}
          <div className="flex flex-col items-center space-y-1.5 pt-2">
            <button
              onClick={() => setIsExploreOpen(true)}
              className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/40 transition-all"
              title="Prompt Library & Explore"
            >
              <Sparkles className="w-5 h-5" />
            </button>

            <NextLink
              href="/dashboard"
              className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                isDashboard
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-500 dark:text-slate-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/40'
              }`}
              title="Executive Dashboard"
            >
              <LayoutDashboard className="w-5 h-5" />
            </NextLink>

            <NextLink
              href="/memory"
              className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                isMemory
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-500 dark:text-slate-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/40'
              }`}
              title="Vector Memory Engine"
            >
              <Database className="w-5 h-5" />
            </NextLink>

            <NextLink
              href="/tasks"
              className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                isTasks
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-500 dark:text-slate-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/40'
              }`}
              title="Autonomous Tasks & Plans"
            >
              <CheckSquare className="w-5 h-5" />
            </NextLink>
          </div>

          <div className="w-6 h-[1px] bg-slate-200 dark:bg-[#25283d] my-1" />

          {/* Group 2: Generative Studios */}
          <div className="flex flex-col items-center space-y-1.5">
            <NextLink
              href="/chat"
              className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                isChat
                  ? 'bg-purple-600 text-white shadow-md'
                  : 'text-slate-500 dark:text-slate-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/40'
              }`}
              title="AI Chat"
            >
              <MessageSquare className="w-5 h-5" />
            </NextLink>

            <button
              onClick={() => setIsImageStudioOpen(true)}
              className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/40 transition-all"
              title="AI Image Studio"
            >
              <ImageIcon className="w-5 h-5" />
            </button>

            <button
              onClick={() => {
                setDocStudioType('pptx');
                setIsDocStudioOpen(true);
              }}
              className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-amber-600 dark:hover:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/40 transition-all"
              title="PowerPoint Presentation (.pptx) Studio"
            >
              <Presentation className="w-5 h-5" />
            </button>

            <button
              onClick={() => {
                setDocStudioType('pdf');
                setIsDocStudioOpen(true);
              }}
              className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-all"
              title="Document & PDF Studio"
            >
              <Layers className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Bottom Utility Cluster */}
        <div className="flex flex-col items-center space-y-2 pt-2 border-t border-slate-200/90 dark:border-[#222438] w-full">
          {/* Light / Dark Theme Switcher Button */}
          <button
            onClick={toggleTheme}
            className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-amber-500 dark:hover:text-amber-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
            title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}
          >
            {theme === 'light' ? (
              <Moon className="w-5 h-5 text-purple-600" />
            ) : (
              <Sun className="w-5 h-5 text-amber-400" />
            )}
          </button>

          {/* Help & Guide */}
          <button
            onClick={() => setIsHelpOpen(true)}
            className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
            title="Help & Shortcuts"
          >
            <HelpCircle className="w-5 h-5" />
          </button>

          {/* Settings */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-purple-600 dark:hover:text-purple-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
            title="System Settings"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </aside>

      {/* Real Working Studio Modals */}
      <ImageStudioModal
        isOpen={isImageStudioOpen}
        onClose={() => setIsImageStudioOpen(false)}
      />

      <DocumentStudioModal
        isOpen={isDocStudioOpen}
        onClose={() => setIsDocStudioOpen(false)}
        defaultType={docStudioType}
      />

      <ExplorePromptsModal
        isOpen={isExploreOpen}
        onClose={() => setIsExploreOpen(false)}
        onSelectPrompt={(p) => {
          if (pathname !== '/chat') {
            router.push('/chat');
          }
          // Dispatch custom event to auto-populate chat input
          window.dispatchEvent(new CustomEvent('cognexa_set_prompt', { detail: p }));
        }}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />

      {/* Help Modal */}
      {isHelpOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative w-full max-w-md p-6 rounded-2xl bg-white dark:bg-[#151624] border border-slate-200 dark:border-[#25283d] shadow-2xl">
            <button
              onClick={() => setIsHelpOpen(false)}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              ✕
            </button>
            <div className="flex items-center space-x-2.5 mb-4">
              <div className="p-2.5 rounded-xl bg-purple-100 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
                <HelpCircle className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900 dark:text-white">Quick Reference Guide</h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">How to use Cognexa AI features</p>
              </div>
            </div>
            <div className="space-y-3 text-xs text-slate-600 dark:text-slate-300">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-[#0c0d17] border border-slate-200/80 dark:border-[#25283d]">
                <strong className="text-purple-600 dark:text-purple-400 block mb-1">📄 PDF Generation:</strong>
                Type: <em>&quot;give answers in pdf format&quot;</em> or paste your question bank to instantly synthesize official multi-page PDF documents.
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-[#0c0d17] border border-slate-200/80 dark:border-[#25283d]">
                <strong className="text-amber-500 block mb-1">🎯 PowerPoint Decks:</strong>
                Type: <em>&quot;make a 6 slide presentation in ppt format about X&quot;</em> to compile editable 16:9 .pptx presentations.
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-[#0c0d17] border border-slate-200/80 dark:border-[#25283d]">
                <strong className="text-cyan-500 block mb-1">🌐 Real-time Web Search:</strong>
                Toggle the globe icon in the prompt bar to verify live facts, latest sports scores, and real-time news.
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-[#0c0d17] border border-slate-200/80 dark:border-[#25283d]">
                <strong className="text-emerald-500 block mb-1">📎 Document RAG:</strong>
                Attach any syllabus PDF or textbook using the paperclip icon to index and answer with exact page citations.
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default Sidebar;
