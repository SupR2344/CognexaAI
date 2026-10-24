'use client';

import React from 'react';
import {
  Bell,
  X,
  FileText,
  Presentation,
  Download,
  Image as ImageIcon,
  CheckCircle2,
  ExternalLink,
} from 'lucide-react';

interface NotificationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  recentArtifacts: Array<{
    id: string;
    title: string;
    type: 'pdf' | 'pptx' | 'image' | 'chart';
    filename: string;
    url: string;
    created_at: string;
  }>;
}

export const NotificationDrawer: React.FC<NotificationDrawerProps> = ({
  isOpen,
  onClose,
  recentArtifacts,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-sm h-full bg-white dark:bg-[#151624] border-l border-slate-200 dark:border-[#222438] p-5 flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-[#222438]">
          <div className="flex items-center space-x-2">
            <Bell className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">Artifacts & Downloads</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-4 space-y-3 custom-scrollbar">
          {recentArtifacts.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircle2 className="w-8 h-8 text-slate-300 dark:text-slate-700 mx-auto mb-2" />
              <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">No recent artifacts generated</p>
              <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-1">Generated PDFs, PPTs, and images will appear here for instant re-download.</p>
            </div>
          ) : (
            recentArtifacts.map((art) => {
              const isPdf = art.type === 'pdf';
              const isPpt = art.type === 'pptx';
              return (
                <div
                  key={art.id}
                  className="p-3 rounded-xl bg-slate-50 dark:bg-[#0e0f1a] border border-slate-200/80 dark:border-[#222438] flex items-center justify-between gap-3 group hover:border-purple-400/50 transition-all"
                >
                  <div className="flex items-center space-x-3 min-w-0">
                    <div className="p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shrink-0">
                      {isPdf ? (
                        <FileText className="w-4 h-4 text-rose-500" />
                      ) : isPpt ? (
                        <Presentation className="w-4 h-4 text-amber-500" />
                      ) : (
                        <ImageIcon className="w-4 h-4 text-purple-500" />
                      )}
                    </div>
                    <div className="truncate">
                      <div className="text-xs font-bold text-slate-900 dark:text-white truncate">
                        {art.title}
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono truncate">
                        {art.filename}
                      </div>
                    </div>
                  </div>
                  <a
                    href={art.url}
                    download
                    target="_blank"
                    rel="noreferrer"
                    className="p-1.5 rounded-lg bg-purple-600 text-white hover:bg-purple-700 shrink-0 transition-transform group-hover:scale-105"
                    title="Download file"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </a>
                </div>
              );
            })
          )}
        </div>

        <div className="pt-3 border-t border-slate-200 dark:border-[#222438] text-[11px] text-center text-slate-400">
          Cognexa Autonomous Artifact Engine
        </div>
      </div>
    </div>
  );
};
