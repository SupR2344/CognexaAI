'use client';

import React, { useState } from 'react';
import {
  FileText,
  Presentation,
  Download,
  X,
  Loader2,
  CheckCircle2,
  Sparkles,
  Layers,
} from 'lucide-react';

interface DocumentStudioModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultType?: 'pdf' | 'pptx';
}

export const DocumentStudioModal: React.FC<DocumentStudioModalProps> = ({
  isOpen,
  onClose,
  defaultType = 'pdf',
}) => {
  const [docType, setDocType] = useState<'pdf' | 'pptx'>(defaultType);
  const [topic, setTopic] = useState('');
  const [slideCount, setSlideCount] = useState(5);
  const [isGenerating, setIsGenerating] = useState(false);
  const [downloadInfo, setDownloadInfo] = useState<{
    title: string;
    filename: string;
    url: string;
    size_kb?: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    if (!topic.trim()) return;
    setIsGenerating(true);
    setError(null);
    setDownloadInfo(null);

    try {
      const prompt =
        docType === 'pdf'
          ? `generate a comprehensive official study document in pdf format for: ${topic.trim()}`
          : `generate a ${slideCount} slide presentation in pptx format for: ${topic.trim()}`;

      const token = localStorage.getItem('cognexa_token');
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

      const response = await fetch(`${apiUrl}/chat/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: prompt, use_memory: false }),
      });

      if (!response.ok) {
        throw new Error('Document synthesis failed. Ensure backend server is healthy.');
      }

      const data = await response.json();
      const reply = data.response || '';

      // Extract markdown link with download url
      const downloadMatch = reply.match(/\[Click Here to Download:?\s*([^\]\)]+)\]\((https?:\/\/[^\s\)]+)/i);
      if (downloadMatch && downloadMatch[2]) {
        setDownloadInfo({
          title: topic.trim(),
          filename: downloadMatch[1].trim(),
          url: downloadMatch[2].trim(),
        });
      } else {
        // Search for any download url
        const genericUrl = reply.match(/https?:\/\/[^\s\)]+\.(pdf|pptx)/i);
        if (genericUrl) {
          setDownloadInfo({
            title: topic.trim(),
            filename: `${topic.slice(0, 20)}.${docType}`,
            url: genericUrl[0],
          });
        } else {
          throw new Error('Generated artifact link was not detected in backend response.');
        }
      }
    } catch (err: any) {
      console.error(err);
      setError(err?.message || 'Error compiling publication document.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg p-6 rounded-2xl bg-white dark:bg-[#151624] border border-slate-200 dark:border-[#25283d] shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-2.5 mb-4">
          <div className="p-2.5 rounded-xl bg-purple-100 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
            {docType === 'pdf' ? <FileText className="w-5 h-5" /> : <Presentation className="w-5 h-5" />}
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-white">Publication & Document Studio</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">Compile official PDFs and executive PowerPoint slides</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Artifact Format:
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setDocType('pdf')}
                className={`px-3.5 py-2.5 rounded-xl text-xs font-semibold border flex items-center justify-center gap-2 transition-all ${
                  docType === 'pdf'
                    ? 'bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 border-rose-400 shadow-sm'
                    : 'bg-slate-50 dark:bg-[#0c0d17] text-slate-600 dark:text-slate-400 border-slate-200 dark:border-[#25283d]'
                }`}
              >
                <FileText className="w-4 h-4 text-rose-500" />
                <span>Adobe PDF Document</span>
              </button>
              <button
                type="button"
                onClick={() => setDocType('pptx')}
                className={`px-3.5 py-2.5 rounded-xl text-xs font-semibold border flex items-center justify-center gap-2 transition-all ${
                  docType === 'pptx'
                    ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border-amber-400 shadow-sm'
                    : 'bg-slate-50 dark:bg-[#0c0d17] text-slate-600 dark:text-slate-400 border-slate-200 dark:border-[#25283d]'
                }`}
              >
                <Presentation className="w-4 h-4 text-amber-500" />
                <span>PowerPoint Deck (.pptx)</span>
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Subject, Topic or Questions:
            </label>
            <textarea
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Ethereum DApp integration with MetaMask, or paste Question 1, Question 2..."
              rows={3}
              className="w-full px-3.5 py-2.5 rounded-xl text-sm bg-slate-50 dark:bg-[#0c0d17] border border-slate-200 dark:border-[#25283d] text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 placeholder:text-slate-400"
            />
          </div>

          {docType === 'pptx' && (
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Number of Slides: ({slideCount})
              </label>
              <input
                type="range"
                min={3}
                max={15}
                value={slideCount}
                onChange={(e) => setSlideCount(Number(e.target.value))}
                className="w-full accent-purple-600 cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-400 mt-1">
                <span>3 slides (Brief)</span>
                <span>8 slides (Standard)</span>
                <span>15 slides (Deep)</span>
              </div>
            </div>
          )}

          {error && (
            <p className="text-xs text-rose-500 bg-rose-50 dark:bg-rose-950/30 p-2.5 rounded-lg border border-rose-200 dark:border-rose-900/50">
              {error}
            </p>
          )}

          {downloadInfo && (
            <div className="p-4 rounded-xl bg-purple-50/80 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 flex items-center justify-between">
              <div className="flex items-center space-x-3 truncate">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                <div className="truncate">
                  <div className="text-xs font-bold text-slate-900 dark:text-white truncate">
                    {downloadInfo.title}
                  </div>
                  <div className="text-[11px] text-slate-500 dark:text-slate-400">
                    {downloadInfo.filename}
                  </div>
                </div>
              </div>
              <a
                href={downloadInfo.url}
                download
                target="_blank"
                rel="noreferrer"
                className="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-xs font-bold flex items-center gap-1.5 shrink-0 shadow-sm"
              >
                <Download className="w-3.5 h-3.5" />
                Download
              </a>
            </div>
          )}

          <div className="flex items-center justify-end space-x-2.5 pt-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleGenerate}
              disabled={isGenerating || !topic.trim()}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-xs font-semibold flex items-center gap-2 hover:opacity-95 disabled:opacity-50 shadow-sm transition-all"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Compiling Document...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Generate {docType.toUpperCase()}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
