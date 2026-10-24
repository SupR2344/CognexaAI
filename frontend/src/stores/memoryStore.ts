import { create } from 'zustand';
import { Memory, MemoryCreateInput, MemoryUpdateInput } from '../lib/types';
import { memoryApi } from '../lib/api';

interface MemoryState {
  memories: Memory[];
  searchResults: Memory[];
  isLoading: boolean;
  isSearching: boolean;
  error: string | null;

  fetchMemories: (type?: string) => Promise<void>;
  searchMemories: (query: string, type?: string) => Promise<void>;
  createMemory: (data: MemoryCreateInput) => Promise<Memory | null>;
  updateMemory: (id: string, data: MemoryUpdateInput) => Promise<Memory | null>;
  deleteMemory: (id: string) => Promise<boolean>;
  clearSearchResults: () => void;
}

export const useMemoryStore = create<MemoryState>((set, get) => ({
  memories: [],
  searchResults: [],
  isLoading: false,
  isSearching: false,
  error: null,

  clearSearchResults: () => set({ searchResults: [], isSearching: false }),

  fetchMemories: async (type?: string) => {
    set({ isLoading: true, error: null });
    try {
      const data = await memoryApi.getMemories(type);
      set({ memories: data, isLoading: false });
    } catch (err: any) {
      console.error('Failed to load memories:', err);
      set({
        error: err.response?.data?.detail || 'Failed to fetch memory records',
        isLoading: false,
      });
    }
  },

  searchMemories: async (query: string, type?: string) => {
    if (!query.trim()) {
      set({ searchResults: [], isSearching: false });
      return;
    }

    set({ isSearching: true, error: null });
    try {
      const results = await memoryApi.searchMemories(query.trim(), type);
      set({ searchResults: results, isSearching: false });
    } catch (err: any) {
      console.error('Memory search error:', err);
      // Fallback: local filter if backend search endpoint fails
      const fallbackResults = get().memories.filter((m) => {
        const matchesQuery = m.content.toLowerCase().includes(query.toLowerCase());
        const matchesType = type ? m.type === type : true;
        return matchesQuery && matchesType;
      });
      set({
        searchResults: fallbackResults,
        isSearching: false,
        error: err.response?.data?.detail || null,
      });
    }
  },

  createMemory: async (data: MemoryCreateInput): Promise<Memory | null> => {
    set({ isLoading: true, error: null });
    try {
      const created = await memoryApi.createMemory(data);
      set((state) => ({
        memories: [created, ...state.memories],
        isLoading: false,
      }));
      return created;
    } catch (err: any) {
      console.error('Create memory error:', err);
      // Local optimistic creation if server is unreachable
      const localMemory: Memory = {
        id: 'mem-' + Date.now(),
        content: data.content,
        type: data.type,
        confidence: data.confidence ?? 0.95,
        metadata: data.metadata || {},
        created_at: new Date().toISOString(),
      };
      set((state) => ({
        memories: [localMemory, ...state.memories],
        isLoading: false,
        error: err.response?.data?.detail || 'Saved locally (offline mode)',
      }));
      return localMemory;
    }
  },

  updateMemory: async (id: string, data: MemoryUpdateInput): Promise<Memory | null> => {
    set({ isLoading: true, error: null });
    try {
      const updated = await memoryApi.updateMemory(id, data);
      set((state) => ({
        memories: state.memories.map((m) => (m.id === id ? updated : m)),
        searchResults: state.searchResults.map((m) => (m.id === id ? updated : m)),
        isLoading: false,
      }));
      return updated;
    } catch (err: any) {
      console.error('Update memory error:', err);
      set((state) => ({
        memories: state.memories.map((m) =>
          m.id === id
            ? {
                ...m,
                ...data,
                updated_at: new Date().toISOString(),
              }
            : m
        ),
        isLoading: false,
        error: err.response?.data?.detail || 'Updated locally',
      }));
      return null;
    }
  },

  deleteMemory: async (id: string): Promise<boolean> => {
    try {
      await memoryApi.deleteMemory(id);
      set((state) => ({
        memories: state.memories.filter((m) => m.id !== id),
        searchResults: state.searchResults.filter((m) => m.id !== id),
      }));
      return true;
    } catch (err: any) {
      console.error('Delete memory error:', err);
      // Remove locally
      set((state) => ({
        memories: state.memories.filter((m) => m.id !== id),
        searchResults: state.searchResults.filter((m) => m.id !== id),
      }));
      return true;
    }
  },
}));
