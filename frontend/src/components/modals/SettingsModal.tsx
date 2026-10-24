'use client';

import React, { useState, useEffect } from 'react';
import {
  Settings,
  X,
  Moon,
  Sun,
  Server,
  User,
  Trash2,
  Check,
  Shield,
  Sparkles,
} from 'lucide-react';
import { useThemeStore } from '../../stores/themeStore';
import { useAuthStore } from '../../stores/authStore';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const { theme, setTheme } = useThemeStore();
  const { user, logout } = useAuthStore();
  const [apiUrl, setApiUrl] = useState('http://localhost:8001');
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('cognexa_api_url') || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
      setApiUrl(stored);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSaveApiUrl = () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('cognexa_api_url', apiUrl.trim());
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2000);
    }
  };

  const handleClearHistory = () => {
    if (confirm('Clear all local conversation cache?')) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('cognexa_conversations');
        window.location.reload();
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-md p-6 rounded-2xl bg-white dark:bg-[#151624] border border-slate-200 dark:border-[#25283d] shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-2.5 mb-5">
          <div className="p-2.5 rounded-xl bg-purple-100 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
            <Settings className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-white">System Settings</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">Configure theme, API endpoints, and workspace</p>
          </div>
        </div>

        <div className="space-y-4">
          {/* Appearance / Theme */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Interface Theme:
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setTheme('light')}
                className={`px-3.5 py-2.5 rounded-xl text-xs font-semibold border flex items-center justify-center gap-2 transition-all ${
                  theme === 'light'
                    ? 'bg-purple-50 text-purple-900 border-purple-500 shadow-sm'
                    : 'bg-slate-50 dark:bg-[#0c0d17] text-slate-600 dark:text-slate-400 border-slate-200 dark:border-[#25283d]'
                }`}
              >
                <Sun className="w-4 h-4 text-amber-500" />
                <span>Light Mode</span>
              </button>
              <button
                type="button"
                onClick={() => setTheme('dark')}
                className={`px-3.5 py-2.5 rounded-xl text-xs font-semibold border flex items-center justify-center gap-2 transition-all ${
                  theme === 'dark'
                    ? 'bg-purple-950/40 text-purple-200 border-purple-500 shadow-sm'
                    : 'bg-slate-50 dark:bg-[#0c0d17] text-slate-600 dark:text-slate-400 border-slate-200 dark:border-[#25283d]'
                }`}
              >
                <Moon className="w-4 h-4 text-purple-400" />
                <span>Dark Mode</span>
              </button>
            </div>
          </div>

          {/* Backend API Endpoint */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center justify-between">
              <span>Backend API Server:</span>
              {savedSuccess && <span className="text-emerald-500 flex items-center gap-1 text-[11px]"><Check className="w-3 h-3" /> Saved</span>}
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Server className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
                <input
                  type="text"
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  placeholder="http://localhost:8001"
                  className="w-full pl-9 pr-3 py-2 rounded-xl text-xs bg-slate-50 dark:bg-[#0c0d17] border border-slate-200 dark:border-[#25283d] text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono"
                />
              </div>
              <button
                onClick={handleSaveApiUrl}
                className="px-3 py-2 bg-purple-600 text-white rounded-xl text-xs font-semibold hover:bg-purple-700"
              >
                Save
              </button>
            </div>
          </div>

          {/* User Account Info */}
          <div className="p-3 rounded-xl bg-slate-50 dark:bg-[#0c0d17] border border-slate-200/80 dark:border-[#25283d]">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 text-white flex items-center justify-center font-bold text-xs">
                  {user?.username ? user.username.charAt(0).toUpperCase() : 'U'}
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900 dark:text-white">
                    {user?.username || 'Active Engineer'}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    {user?.email || 'admin@cognexa.ai'}
                  </div>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">
                Online
              </span>
            </div>
          </div>

          {/* Danger zone */}
          <div className="pt-2">
            <button
              onClick={handleClearHistory}
              className="w-full py-2.5 px-3 rounded-xl border border-rose-200 dark:border-rose-900/40 text-rose-600 dark:text-rose-400 text-xs font-medium hover:bg-rose-50 dark:hover:bg-rose-950/20 flex items-center justify-center gap-1.5 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Reset Local Cache & Re-sync</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
