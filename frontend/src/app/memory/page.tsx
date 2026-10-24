'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Database,
  Plus,
  Search,
  Filter,
  Sparkles,
  Loader2,
  RefreshCw,
  FolderTree,
  Check,
} from 'lucide-react';
import Sidebar from '../../components/Sidebar';
import MemoryCard, { MEMORY_TYPE_CONFIG } from '../../components/MemoryCard';
import Modal from '../../components/Modal';
import { useAuthStore } from '../../stores/authStore';
import { useMemoryStore } from '../../stores/memoryStore';
import { Memory, MemoryType } from '../../lib/types';

const MEMORY_TYPES: { key: string; label: string }[] = [
  { key: '', label: 'All Types' },
  { key: 'user_preference', label: 'User Preference' },
  { key: 'project', label: 'Project' },
  { key: 'decision', label: 'Decision' },
  { key: 'episodic', label: 'Episodic' },
  { key: 'error', label: 'Error' },
  { key: 'task', label: 'Task' },
  { key: 'verified_knowledge', label: 'Verified Knowledge' },
];

export default function MemoryPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuthStore();
  const {
    memories,
    searchResults,
    isLoading,
    isSearching,
    fetchMemories,
    searchMemories,
    createMemory,
    updateMemory,
    deleteMemory,
    clearSearchResults,
  } = useMemoryStore();

  const [selectedType, setSelectedType] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingMemory, setEditingMemory] = useState<Memory | null>(null);

  // Modal Form State
  const [formContent, setFormContent] = useState('');
  const [formType, setFormType] = useState<MemoryType>('user_preference');
  const [formConfidence, setFormConfidence] = useState(0.95);
  const [formMetadataKey, setFormMetadataKey] = useState('');
  const [formMetadataValue, setFormMetadataValue] = useState('');

  // Protect route
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  // Initial fetch
  useEffect(() => {
    if (isAuthenticated) {
      fetchMemories(selectedType || undefined);
    }
  }, [isAuthenticated, selectedType, fetchMemories]);

  // Search handler
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      searchMemories(searchQuery, selectedType || undefined);
    } else {
      clearSearchResults();
    }
  };

  const handleClearSearch = () => {
    setSearchQuery('');
    clearSearchResults();
  };

  const openCreateModal = () => {
    setEditingMemory(null);
    setFormContent('');
    setFormType('user_preference');
    setFormConfidence(0.95);
    setFormMetadataKey('');
    setFormMetadataValue('');
    setIsModalOpen(true);
  };

  const openEditModal = (mem: Memory) => {
    setEditingMemory(mem);
    setFormContent(mem.content);
    setFormType(mem.type as MemoryType);
    setFormConfidence(mem.confidence ?? 0.95);
    setIsModalOpen(true);
  };

  const handleSaveMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formContent.trim()) return;

    const metadata: Record<string, any> = editingMemory?.metadata ? { ...editingMemory.metadata } : {};
    if (formMetadataKey.trim() && formMetadataValue.trim()) {
      metadata[formMetadataKey.trim()] = formMetadataValue.trim();
    }

    if (editingMemory) {
      await updateMemory(editingMemory.id, {
        content: formContent.trim(),
        type: formType,
        confidence: formConfidence,
        metadata,
      });
    } else {
      await createMemory({
        content: formContent.trim(),
        type: formType,
        confidence: formConfidence,
        metadata,
      });
    }

    setIsModalOpen(false);
  };

  const displayedMemories = searchQuery.trim() ? searchResults : memories;

  return (
    <div className="flex h-screen bg-[#0f0f23] text-gray-100 overflow-hidden">
      <Sidebar />

      <main className="flex-1 flex flex-col h-full overflow-y-auto custom-scrollbar p-6 lg:p-8">
        <div className="max-w-7xl mx-auto w-full space-y-6">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#25325c]">
            <div>
              <div className="flex items-center space-x-3">
                <div className="p-2.5 rounded-xl bg-gradient-to-tr from-[#00d2ff]/20 to-[#7b2ff7]/20 border border-[#00d2ff]/30 text-[#00d2ff]">
                  <Database className="w-6 h-6" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-white tracking-tight">
                    Hierarchical Memory Engine
                  </h1>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Explore and curate knowledge, user preferences, and episodic reflections.
                  </p>
                </div>
              </div>
            </div>

            <button
              onClick={openCreateModal}
              className="flex items-center justify-center space-x-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-[#7b2ff7] hover:from-blue-500 hover:to-[#8c46f7] text-white text-sm font-semibold shadow-lg shadow-blue-600/20 transition-all shrink-0"
            >
              <Plus className="w-4 h-4" />
              <span>Add Memory</span>
            </button>
          </div>

          {/* Search & Filters */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-[#16213e]/60 p-3 rounded-2xl border border-[#25325c]">
            {/* Search Input */}
            <form onSubmit={handleSearch} className="relative flex-1">
              <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-3 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Semantic vector search across memory storage..."
                className="w-full pl-10 pr-24 py-2 bg-[#121b33] border border-[#25325c] rounded-xl text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#00d2ff]"
              />
              <button
                type="submit"
                className="absolute right-1.5 top-1 px-3 py-1 bg-[#25325c] hover:bg-[#32437b] text-white text-xs rounded-lg transition-colors"
              >
                Search
              </button>
            </form>

            {/* Type Filter Dropdown */}
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-gray-400 ml-1" />
              <select
                value={selectedType}
                onChange={(e) => {
                  setSelectedType(e.target.value);
                  if (searchQuery.trim()) {
                    searchMemories(searchQuery, e.target.value || undefined);
                  }
                }}
                className="bg-[#121b33] border border-[#25325c] text-white text-xs rounded-xl px-3 py-2.5 focus:outline-none focus:border-[#00d2ff]"
              >
                {MEMORY_TYPES.map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.label}
                  </option>
                ))}
              </select>

              {searchQuery && (
                <button
                  onClick={handleClearSearch}
                  className="px-3 py-2 text-xs text-gray-400 hover:text-white bg-[#121b33] border border-[#25325c] rounded-xl transition-colors"
                >
                  Reset
                </button>
              )}
            </div>
          </div>

          {/* Memory Cards Grid */}
          {isLoading || isSearching ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <Loader2 className="w-8 h-8 text-[#00d2ff] animate-spin mb-3" />
              <p className="text-sm">Querying cognitive vector index...</p>
            </div>
          ) : displayedMemories.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center bg-[#16213e]/30 border border-dashed border-[#25325c] rounded-2xl p-8">
              <Database className="w-12 h-12 text-gray-600 mb-3" />
              <h3 className="text-base font-semibold text-gray-300">
                No memories found
              </h3>
              <p className="text-xs text-gray-500 mt-1 max-w-sm">
                {searchQuery
                  ? 'No vector matches found for your search query. Try alternative keywords or clear the filter.'
                  : 'Start training Cognexa AI by storing user preferences, technical constraints, or verified facts.'}
              </p>
              <button
                onClick={openCreateModal}
                className="mt-4 px-4 py-2 bg-[#1a1a2e] border border-[#25325c] text-[#00d2ff] text-xs rounded-xl hover:bg-[#25325c] transition-colors"
              >
                Create First Memory
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {displayedMemories.map((mem) => (
                <MemoryCard
                  key={mem.id}
                  memory={mem}
                  onEdit={openEditModal}
                  onDelete={deleteMemory}
                />
              ))}
            </div>
          )}
        </div>

        {/* Add / Edit Memory Modal */}
        <Modal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          title={editingMemory ? 'Edit Memory Entry' : 'Store New Memory Entry'}
          maxWidth="lg"
        >
          <form onSubmit={handleSaveMemory} className="space-y-4 text-sm">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5 uppercase tracking-wider">
                Memory Category
              </label>
              <select
                value={formType}
                onChange={(e) => setFormType(e.target.value as MemoryType)}
                className="w-full bg-[#121b33] border border-[#25325c] rounded-xl px-3 py-2.5 text-white focus:outline-none focus:border-[#00d2ff]"
              >
                <option value="user_preference">User Preference (Green)</option>
                <option value="project">Project (Blue)</option>
                <option value="decision">Decision (Purple)</option>
                <option value="episodic">Episodic (Orange)</option>
                <option value="error">Error (Red)</option>
                <option value="task">Task (Yellow)</option>
                <option value="verified_knowledge">Verified Knowledge (Emerald)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5 uppercase tracking-wider">
                Content / Knowledge Expression
              </label>
              <textarea
                value={formContent}
                onChange={(e) => setFormContent(e.target.value)}
                rows={4}
                required
                placeholder="e.g. Always use TypeScript strict mode with Next.js App Router for frontend development."
                className="w-full bg-[#121b33] border border-[#25325c] rounded-xl p-3 text-white placeholder-gray-500 focus:outline-none focus:border-[#00d2ff] custom-scrollbar text-sm"
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
                  Confidence Score
                </label>
                <span className="text-xs font-mono text-[#00d2ff]">
                  {Math.round(formConfidence * 100)}%
                </span>
              </div>
              <input
                type="range"
                min="0.1"
                max="1.0"
                step="0.05"
                value={formConfidence}
                onChange={(e) => setFormConfidence(parseFloat(e.target.value))}
                className="w-full accent-[#00d2ff] cursor-pointer"
              />
            </div>

            {/* Optional Metadata tag */}
            <div className="pt-2 border-t border-[#25325c]">
              <label className="block text-xs font-semibold text-gray-400 mb-1.5">
                Metadata Tag (Optional)
              </label>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  placeholder="Key (e.g. topic)"
                  value={formMetadataKey}
                  onChange={(e) => setFormMetadataKey(e.target.value)}
                  className="bg-[#121b33] border border-[#25325c] rounded-xl px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#00d2ff]"
                />
                <input
                  type="text"
                  placeholder="Value (e.g. architecture)"
                  value={formMetadataValue}
                  onChange={(e) => setFormMetadataValue(e.target.value)}
                  className="bg-[#121b33] border border-[#25325c] rounded-xl px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#00d2ff]"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 pt-4 border-t border-[#25325c]">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 rounded-xl text-gray-400 hover:text-white bg-[#1a1a2e] text-xs transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-[#7b2ff7] hover:from-blue-500 hover:to-[#8c46f7] text-white text-xs font-semibold transition-all shadow-md"
              >
                {editingMemory ? 'Update Memory' : 'Save Memory'}
              </button>
            </div>
          </form>
        </Modal>
      </main>
    </div>
  );
}
