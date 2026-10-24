'use client';

import { useEffect } from 'react';
import { useThemeStore } from '../stores/themeStore';
import { useAuthStore } from '../stores/authStore';

export default function ClientInitializer() {
  const setTheme = useThemeStore((s) => s.setTheme);
  const loadUser = useAuthStore((s) => s.loadUser);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedTheme = localStorage.getItem('cognexa_theme') as 'light' | 'dark' | null;
      if (savedTheme === 'dark') {
        document.documentElement.classList.add('dark');
        document.documentElement.classList.remove('light');
        setTheme('dark');
      } else {
        document.documentElement.classList.remove('dark');
        document.documentElement.classList.add('light');
        setTheme('light');
      }
      loadUser();
    }
  }, [setTheme, loadUser]);

  return null;
}
