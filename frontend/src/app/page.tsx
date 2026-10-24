'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Brain, Loader2 } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuthStore();

  useEffect(() => {
    if (isLoading) return;

    const token = typeof window !== 'undefined' ? localStorage.getItem('cognexa_token') : null;
    const nextRoute = token || isAuthenticated ? '/chat' : '/login';
    router.replace(nextRoute);
  }, [isAuthenticated, isLoading, router]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-[#0f0f23] p-4">
      <div className="relative flex flex-col items-center">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#00d2ff] to-[#7b2ff7] flex items-center justify-center shadow-glow mb-6 animate-pulse">
          <Brain className="w-9 h-9 text-white" />
        </div>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-white via-blue-200 to-[#00d2ff] bg-clip-text text-transparent">
          Cognexa AI
        </h1>
        <p className="text-sm text-gray-400 mt-2">Initializing Cognitive Agent Environment...</p>
        <div className="mt-6 flex items-center text-xs text-[#00d2ff]">
          <Loader2 className="w-4 h-4 animate-spin mr-2" />
          <span>Verifying session security</span>
        </div>
      </div>
    </div>
  );
}
