import { create } from 'zustand';
import { User } from '../lib/types';
import { authApi } from '../lib/api';

interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<boolean>;
  register: (username: string, email: string, password: string) => Promise<boolean>;
  logout: () => void;
  loadUser: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  clearError: () => set({ error: null }),

  loadUser: async () => {
    if (typeof window === 'undefined') {
      set({ isLoading: false });
      return;
    }

    try {
      const token = localStorage.getItem('cognexa_token');
      const storedUser = localStorage.getItem('cognexa_user');

      if (!token) {
        localStorage.removeItem('cognexa_token');
        localStorage.removeItem('cognexa_user');
        set({ token: null, user: null, isAuthenticated: false, isLoading: false, error: null });
        return;
      }

      let initialUser: User | null = null;
      if (storedUser) {
        try {
          initialUser = JSON.parse(storedUser);
        } catch {
          localStorage.removeItem('cognexa_user');
        }
      }

      if (initialUser) {
        set({
          token,
          user: initialUser,
          isAuthenticated: true,
          isLoading: false,
        });
      }

      try {
        const user = await authApi.getMe();
        localStorage.setItem('cognexa_user', JSON.stringify(user));
        set({ token, user, isAuthenticated: true, isLoading: false, error: null });
      } catch {
        // If /me fails with invalid/expired token, clear cleanly without crashing
        localStorage.removeItem('cognexa_token');
        localStorage.removeItem('cognexa_user');
        set({ token: null, user: null, isAuthenticated: false, isLoading: false, error: null });
      }
    } catch {
      set({ token: null, user: null, isAuthenticated: false, isLoading: false, error: null });
    }
  },

  login: async (email: string, password: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const response = await authApi.login({ email, password });
      const { access_token, user } = response;

      if (typeof window !== 'undefined') {
        localStorage.setItem('cognexa_token', access_token);
        localStorage.setItem('cognexa_user', JSON.stringify(user));
      }

      set({
        token: access_token,
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      return true;
    } catch (err: any) {
      const message =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        'Failed to log in. Please check your credentials.';
      set({ error: message, isLoading: false });
      return false;
    }
  },

  register: async (username: string, email: string, password: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const response = await authApi.register({ username, email, password });
      const { access_token, user } = response;

      if (typeof window !== 'undefined') {
        localStorage.setItem('cognexa_token', access_token);
        localStorage.setItem('cognexa_user', JSON.stringify(user));
      }

      set({
        token: access_token,
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      return true;
    } catch (err: any) {
      const message =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        'Failed to register account. Please try again.';
      set({ error: message, isLoading: false });
      return false;
    }
  },

  logout: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('cognexa_token');
      localStorage.removeItem('cognexa_user');
    }
    set({
      token: null,
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  },
}));
