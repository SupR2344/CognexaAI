'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Brain, Lock, Mail, ArrowRight, Loader2, Sparkles, Sun, Moon } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useThemeStore } from '../../stores/themeStore';

export default function LoginPage() {
  const router = useRouter();
  const { login, isLoading, error } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!email || !password) {
      setFormError('Please enter both email and password.');
      return;
    }

    const success = await login(email.trim(), password);
    if (success) {
      router.push('/chat');
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 bg-[#f8f9fc] dark:bg-[#0b0c14] text-slate-800 dark:text-slate-100 transition-colors relative">
      {/* Theme toggle top-right */}
      <button
        onClick={toggleTheme}
        className="absolute top-5 right-5 p-2.5 rounded-xl bg-white dark:bg-[#151624] border border-slate-200 dark:border-[#222438] text-slate-500 dark:text-slate-400 hover:text-purple-600 dark:hover:text-purple-400 shadow-sm transition-all"
        title="Toggle Theme"
      >
        {theme === 'light' ? <Moon className="w-4 h-4 text-purple-600" /> : <Sun className="w-4 h-4 text-amber-400" />}
      </button>

      <div className="relative w-full max-w-md bg-white dark:bg-[#13141f] border border-slate-200/90 dark:border-[#222438] rounded-3xl p-8 shadow-xl dark:shadow-2xl">
        <div className="text-center mb-7">
          <div className="inline-flex w-12 h-12 rounded-2xl bg-gradient-to-tr from-purple-600 via-indigo-600 to-cyan-500 items-center justify-center mb-3 shadow-md">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
            Sign in to <span className="bg-gradient-to-r from-purple-600 to-indigo-600 bg-clip-text text-transparent">Cognexa AI</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Autonomous cognitive research engine & artifact synthesis
          </p>
        </div>

        {(formError || error) && (
          <div className="mb-5 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/50 text-rose-600 dark:text-rose-400 text-xs">
            {formError || error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Username or Email
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@cognexa.ai or admin"
                required
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 dark:bg-[#0c0d17] border border-slate-200 dark:border-[#25283d] rounded-xl text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm transition-all"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="admin123"
                required
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 dark:bg-[#0c0d17] border border-slate-200 dark:border-[#25283d] rounded-xl text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm transition-all"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 px-4 rounded-xl font-semibold text-white bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-md transition-all flex items-center justify-center space-x-2 disabled:opacity-60 text-xs mt-3 active:scale-[0.99]"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Authenticating...</span>
              </>
            ) : (
              <>
                <span>Sign In</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-slate-100 dark:border-[#222438] text-center text-xs text-slate-500 dark:text-slate-400 space-y-2">
          <div>
            Default Account: <span className="font-semibold text-purple-600 dark:text-purple-400">admin@cognexa.ai</span> / <span className="font-semibold text-purple-600 dark:text-purple-400">admin123</span>
          </div>
          <div>
            Don&apos;t have an account?{' '}
            <Link href="/register" className="font-semibold text-purple-600 dark:text-purple-400 hover:underline">
              Create an account
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
