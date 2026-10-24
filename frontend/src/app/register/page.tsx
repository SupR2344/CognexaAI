'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Brain, Lock, Mail, User, ArrowRight, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';

export default function RegisterPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const authError = useAuthStore((s) => s.error);
  const register = useAuthStore((s) => s.register);

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && isAuthenticated) {
      router.replace('/chat');
    }
  }, [mounted, isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!username.trim() || !email.trim() || !password) {
      setFormError('Please fill in all required fields.');
      return;
    }

    if (password.length < 6) {
      setFormError('Password must be at least 6 characters in length.');
      return;
    }

    if (password !== confirmPassword) {
      setFormError('Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    const success = await register(username.trim(), email.trim(), password);
    setIsSubmitting(false);

    if (success) {
      router.push('/chat');
    }
  };

  if (!mounted) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center p-4 bg-[#0f0f23]">
        <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-[#00d2ff] to-[#7b2ff7] flex items-center justify-center shadow-glow animate-pulse">
          <Brain className="w-5 h-5 text-white" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 bg-[#0f0f23] relative overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-gradient-to-tr from-[#00d2ff]/15 to-[#7b2ff7]/15 rounded-full blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-md my-8">
        {/* Card */}
        <div className="bg-[#16213e]/90 backdrop-blur-xl border border-[#25325c] rounded-3xl p-8 shadow-2xl">
          {/* Brand Header */}
          <div className="text-center mb-8">
            <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#00d2ff] to-[#7b2ff7] items-center justify-center shadow-glow mb-4">
              <Brain className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Join <span className="bg-gradient-to-r from-[#00d2ff] to-[#7b2ff7] bg-clip-text text-transparent">Cognexa AI</span>
            </h1>
            <p className="text-sm text-gray-400 mt-2">
              Create an account to deploy intelligent autonomous systems
            </p>
          </div>

          {/* Error Banner */}
          {(formError || authError) && (
            <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-start space-x-3 text-red-300 text-sm">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-red-400" />
              <span>{formError || authError}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-2">
                Operator Username
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                  <User className="w-5 h-5" />
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="cognexa_operator"
                  required
                  className="w-full pl-11 pr-4 py-3 bg-[#1a1a2e] border border-[#25325c] rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-[#00d2ff] focus:ring-1 focus:ring-[#00d2ff] text-sm transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-2">
                Email Address
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                  <Mail className="w-5 h-5" />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="operator@cognexa.ai"
                  required
                  className="w-full pl-11 pr-4 py-3 bg-[#1a1a2e] border border-[#25325c] rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-[#00d2ff] focus:ring-1 focus:ring-[#00d2ff] text-sm transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-2">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                  <Lock className="w-5 h-5" />
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 6 characters"
                  required
                  className="w-full pl-11 pr-4 py-3 bg-[#1a1a2e] border border-[#25325c] rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-[#00d2ff] focus:ring-1 focus:ring-[#00d2ff] text-sm transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-2">
                Confirm Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                  <Lock className="w-5 h-5" />
                </div>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
                  required
                  className="w-full pl-11 pr-4 py-3 bg-[#1a1a2e] border border-[#25325c] rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-[#00d2ff] focus:ring-1 focus:ring-[#00d2ff] text-sm transition-all"
                />
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3.5 px-4 rounded-xl font-semibold text-white bg-gradient-to-r from-blue-600 via-[#3b82f6] to-[#7b2ff7] hover:from-blue-500 hover:to-[#8c46f7] shadow-lg shadow-blue-600/30 active:scale-[0.99] transition-all flex items-center justify-center space-x-2 disabled:opacity-60 disabled:cursor-not-allowed pt-3"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Registering...</span>
                </>
              ) : (
                <>
                  <span>Create Account</span>
                  <ArrowRight className="w-4 h-4 ml-1" />
                </>
              )}
            </button>
          </form>

          {/* Footer Link */}
          <div className="mt-8 pt-6 border-t border-[#25325c]/70 text-center text-sm text-gray-400">
            Already registered?{' '}
            <Link
              href="/login"
              className="font-medium text-[#00d2ff] hover:text-[#00d2ff]/80 transition-colors"
            >
              Sign In Instead
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
