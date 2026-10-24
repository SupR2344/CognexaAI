'use client';

import React, { useState } from 'react';
import {
  Calendar,
  Sparkles,
  Edit2,
  Trash2,
  ChevronDown,
  ChevronUp,
  Tag,
  CheckCircle,
} from 'lucide-react';
import { format } from 'date-fns';
import { Memory, MemoryType } from '../lib/types';

interface MemoryCardProps {
  memory: Memory;
  onEdit?: (memory: Memory) => void;
  onDelete?: (id: string) => void;
}

export const MEMORY_TYPE_CONFIG: Record<
  string,
  { label: string; bg: string; text: string; border: string }
> = {
  user_preference: {
    label: 'User Preference',
    bg: 'bg-green-500/15',
    text: 'text-green-400',
    border: 'border-green-500/30',
  },
  project: {
    label: 'Project',
    bg: 'bg-blue-500/15',
    text: 'text-blue-400',
    border: 'border-blue-500/30',
  },
  decision: {
    label: 'Decision',
    bg: 'bg-purple-500/15',
    text: 'text-purple-400',
    border: 'border-purple-500/30',
  },
  episodic: {
    label: 'Episodic',
    bg: 'bg-orange-500/15',
    text: 'text-orange-400',
    border: 'border-orange-500/30',
  },
  error: {
    label: 'Error',
    bg: 'bg-red-500/15',
    text: 'text-red-400',
    border: 'border-red-500/30',
  },
  task: {
    label: 'Task',
    bg: 'bg-yellow-500/15',
    text: 'text-yellow-400',
    border: 'border-yellow-500/30',
  },
  verified_knowledge: {
    label: 'Verified Knowledge',
    bg: 'bg-emerald-500/15',
    text: 'text-emerald-400',
    border: 'border-emerald-500/30',
  },
};

export const MemoryCard: React.FC<MemoryCardProps> = ({
  memory,
  onEdit,
  onDelete,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const typeConfig = MEMORY_TYPE_CONFIG[memory.type] || {
    label: memory.type || 'General',
    bg: 'bg-gray-500/15',
    text: 'text-gray-300',
    border: 'border-gray-500/30',
  };

  const confidenceScore = Math.round((memory.confidence ?? 0.95) * 100);

  const formattedDate = (() => {
    try {
      return format(new Date(memory.created_at), 'MMM d, yyyy HH:mm');
    } catch {
      return memory.created_at;
    }
  })();

  const isLongContent = memory.content.length > 220;

  const handleDelete = () => {
    if (onDelete) {
      setIsDeleting(true);
      onDelete(memory.id);
    }
  };

  return (
    <div className="group relative rounded-2xl bg-[#16213e]/90 border border-[#25325c] hover:border-[#00d2ff]/40 p-5 transition-all duration-200 shadow-lg flex flex-col justify-between">
      <div>
        {/* Top bar: Type badge & Confidence */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <span
            className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ${typeConfig.bg} ${typeConfig.text} ${typeConfig.border}`}
          >
            <Tag className="w-3 h-3 mr-1" />
            {typeConfig.label}
          </span>

          <div className="flex items-center space-x-1.5 text-xs text-gray-300 bg-[#121b33] px-2.5 py-1 rounded-full border border-[#25325c]">
            <Sparkles className="w-3 h-3 text-[#00d2ff]" />
            <span>{confidenceScore}% confidence</span>
          </div>
        </div>

        {/* Memory Content */}
        <div className="text-gray-200 text-sm leading-relaxed mb-4">
          <p className={!isExpanded && isLongContent ? 'line-clamp-4' : ''}>
            {memory.content}
          </p>
          {isLongContent && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="mt-1 text-xs text-[#00d2ff] hover:underline flex items-center gap-1 focus:outline-none"
            >
              {isExpanded ? (
                <>
                  Show less <ChevronUp className="w-3 h-3" />
                </>
              ) : (
                <>
                  Read more <ChevronDown className="w-3 h-3" />
                </>
              )}
            </button>
          )}
        </div>

        {/* Metadata section if present */}
        {memory.metadata && Object.keys(memory.metadata).length > 0 && (
          <div className="mb-4 pt-3 border-t border-[#25325c]/50">
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(memory.metadata).map(([key, val]) => (
                <span
                  key={key}
                  className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-[#1a1a2e] text-gray-300 border border-[#25325c]"
                >
                  <span className="text-gray-400 mr-1">{key}:</span>
                  <span className="truncate max-w-[120px]">
                    {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer: Date and Action Buttons */}
      <div className="pt-3 border-t border-[#25325c]/60 flex items-center justify-between text-xs text-gray-400">
        <div className="flex items-center space-x-1">
          <Calendar className="w-3.5 h-3.5 text-gray-400" />
          <span>{formattedDate}</span>
        </div>

        <div className="flex items-center space-x-1">
          {onEdit && (
            <button
              onClick={() => onEdit(memory)}
              className="p-1.5 text-gray-400 hover:text-[#00d2ff] hover:bg-[#1a1a2e] rounded-lg transition-colors"
              title="Edit memory"
            >
              <Edit2 className="w-3.5 h-3.5" />
            </button>
          )}
          {onDelete && (
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors disabled:opacity-50"
              title="Delete memory"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default MemoryCard;
