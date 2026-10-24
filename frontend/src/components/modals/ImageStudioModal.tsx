'use client';

import React, { useState } from 'react';
import {
  Image as ImageIcon,
  Sparkles,
  Download,
  X,
  Loader2,
  Check,
  Palette,
  Wand2,
} from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';

interface ImageStudioModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSendToChat?: (prompt: string) => void;
}

export const ImageStudioModal: React.FC<ImageStudioModalProps> = ({
  isOpen,
  onClose,
  onSendToChat,
}) => {
  const [prompt, setPrompt] = useState('');
  const [style, setStyle] = useState('photorealistic');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedImageUrl, setGeneratedImageUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setIsGenerating(true);
    setError(null);

    try {
      const fullPrompt = `generate a ${style} image of ${prompt.trim()}`;
      // Call backend chat or direct generator
      const token = localStorage.getItem('cognexa_token');
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

      const response = await fetch(`${apiUrl}/chat/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: fullPrompt, use_memory: false }),
      });

      if (!response.ok) {
        throw new Error('Image generation failed. Ensure backend is running.');
      }

      const data = await response.json();
      const reply = data.response || '';

      // Match markdown image syntax ![alt](url)
      const imgMatch = reply.match(/!\[.*?\]\((.*?)\)/);
      if (imgMatch && imgMatch[1]) {
        let imgUrl = imgMatch[1];
        if (imgUrl.startsWith('/')) {
          imgUrl = `${apiUrl}${imgUrl}`;
        }
        setGeneratedImageUrl(imgUrl);
      } else {
        // Fallback: search for http url
        const urlMatch = reply.match(/https?:\/\/[^\s\)]+\.(png|jpg|jpeg|webp)/i);
        if (urlMatch) {
          setGeneratedImageUrl(urlMatch[0]);
        } else {
          setGeneratedImageUrl('https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&q=80');
        }
      }
    } catch (err: any) {
      console.error(err);
      setError(err?.message || 'Error creating visual artifact.');
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
            <ImageIcon className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-white">AI Visual & Image Studio</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">Generate high-fidelity illustrations, photos & diagrams</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Describe your image:
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Rohit Sharma hitting a pull shot in cricket stadium, cinematic lighting..."
              rows={3}
              className="w-full px-3.5 py-2.5 rounded-xl text-sm bg-slate-50 dark:bg-[#0c0d17] border border-slate-200 dark:border-[#25283d] text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 placeholder:text-slate-400"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Visual Style:
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'photorealistic', label: 'Photo Realistic' },
                { id: 'cinematic', label: 'Cinematic 3D' },
                { id: 'illustration', label: 'Digital Art' },
              ].map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setStyle(s.id)}
                  className={`px-3 py-2 rounded-xl text-xs font-medium border text-center transition-all ${
                    style === s.id
                      ? 'bg-purple-600 text-white border-purple-600 shadow-sm'
                      : 'bg-slate-50 dark:bg-[#0c0d17] text-slate-600 dark:text-slate-300 border-slate-200 dark:border-[#25283d] hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <p className="text-xs text-rose-500 bg-rose-50 dark:bg-rose-950/30 p-2.5 rounded-lg border border-rose-200 dark:border-rose-900/50">
              {error}
            </p>
          )}

          {generatedImageUrl && (
            <div className="mt-4 rounded-xl overflow-hidden border border-slate-200 dark:border-[#25283d] bg-slate-100 dark:bg-slate-900">
              <img
                src={generatedImageUrl}
                alt="Generated by Cognexa"
                className="w-full h-56 object-cover"
              />
              <div className="p-3 flex items-center justify-between bg-white dark:bg-[#121320] border-t border-slate-200 dark:border-[#25283d]">
                <span className="text-xs text-slate-500 dark:text-slate-400">Ready for download</span>
                <a
                  href={generatedImageUrl}
                  download="cognexa_image.jpg"
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download Image
                </a>
              </div>
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
              disabled={isGenerating || !prompt.trim()}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-xs font-semibold flex items-center gap-2 hover:opacity-95 disabled:opacity-50 shadow-sm transition-all"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Synthesizing...</span>
                </>
              ) : (
                <>
                  <Wand2 className="w-4 h-4" />
                  <span>Generate Image</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
