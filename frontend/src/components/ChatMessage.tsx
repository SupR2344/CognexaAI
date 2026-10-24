'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  Brain,
  Check,
  Copy,
  Clock,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Workflow,
  Presentation,
  FileText,
  FolderArchive,
  Download,
  ExternalLink,
  Image as ImageIcon,
  Volume2,
  VolumeX,
} from 'lucide-react';

import { format } from 'date-fns';
import { Message, UsedMemory } from '../lib/types';
import TaskProgress from './TaskProgress';
import { useThemeStore } from '../stores/themeStore';

interface ChatMessageProps {
  message: Message;
}

// Code Block with Copy Button
const CodeBlock: React.FC<{ language: string; value: string }> = ({
  language,
  value,
}) => {
  const [copied, setCopied] = useState(false);
  const theme = useThemeStore((s) => s.theme);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  return (
    <div className="relative group my-3 rounded-xl overflow-hidden border border-slate-200 dark:border-[#25283d] bg-slate-900 dark:bg-[#0a0a14] shadow-sm">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800/80 dark:bg-[#121320] border-b border-slate-700/50 dark:border-[#25283d] text-xs text-slate-300">
        <span className="font-mono lowercase text-purple-400 font-semibold">{language || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center space-x-1 hover:text-white transition-colors px-2 py-1 rounded bg-slate-700/60 hover:bg-slate-700"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5 text-slate-400" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <div className="overflow-x-auto text-xs">
        <SyntaxHighlighter
          language={language || 'text'}
          style={oneDark}
          customStyle={{
            margin: 0,
            padding: '1rem',
            background: 'transparent',
            fontSize: '0.825rem',
            lineHeight: '1.5',
          }}
          wrapLongLines={true}
        >
          {value}
        </SyntaxHighlighter>
      </div>
    </div>
  );
};

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const [showMemoryDetails, setShowMemoryDetails] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [copiedMessage, setCopiedMessage] = useState(false);

  const handleSpeak = () => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    if (isPlayingAudio) {
      window.speechSynthesis.cancel();
      setIsPlayingAudio(false);
      return;
    }

    window.speechSynthesis.cancel();
    const raw = (message as any)?.content || '';
    const cleanSpeech = String(raw)
      .replace(/\[.*?\]\(.*?\)/g, '')
      .replace(/```[\s\S]*?```/g, 'Code block omitted.')
      .replace(/[*_#`]/g, '');

    const utterance = new SpeechSynthesisUtterance(cleanSpeech.slice(0, 500));
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find(
      (v) => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google'))
    );
    if (preferredVoice) utterance.voice = preferredVoice;

    utterance.onend = () => setIsPlayingAudio(false);
    utterance.onerror = () => setIsPlayingAudio(false);

    setIsPlayingAudio(true);
    window.speechSynthesis.speak(utterance);
  };

  const handleCopyMessage = async () => {
    try {
      const raw = (message as any)?.content || '';
      await navigator.clipboard.writeText(String(raw));
      setCopiedMessage(true);
      setTimeout(() => setCopiedMessage(false), 2000);
    } catch (err) {
      console.warn('Failed to copy message:', err);
    }
  };

  const isUser = message.role === 'user';

  const renderableContent = React.useMemo(() => {
    const raw = (message as any)?.content;
    if (typeof raw === 'string') return raw;
    if (raw === null || raw === undefined) return '';
    if (typeof raw === 'object') {
      if (typeof raw.content === 'string') return raw.content;
      if (typeof raw.text === 'string') return raw.text;
      if (typeof raw.message === 'string') return raw.message;
      if (typeof raw.response === 'string') return raw.response;
      if (typeof raw.reply === 'string') return raw.reply;
      try {
        return JSON.stringify(raw, null, 2);
      } catch {
        return String(raw);
      }
    }
    return String(raw);
  }, [message?.content]);

  const formattedTime = (() => {
    try {
      return format(new Date(message.created_at), 'HH:mm');
    } catch {
      return '';
    }
  })();

  const memoriesCount = Array.isArray(message.memories_used)
    ? message.memories_used.length
    : typeof message.memories_used === 'number'
    ? message.memories_used
    : 0;

  const usedMemoriesList = Array.isArray(message.memories_used)
    ? (message.memories_used as UsedMemory[])
    : [];

  return (
    <div className={`flex w-full mb-6 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex max-w-[90%] md:max-w-[78%] ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start gap-3`}>
        {/* Avatar */}
        <div
          className={`shrink-0 w-8 h-8 rounded-xl flex items-center justify-center shadow-sm ${
            isUser
              ? 'bg-gradient-to-tr from-purple-600 to-indigo-600 text-white'
              : 'bg-gradient-to-tr from-purple-600 via-indigo-600 to-cyan-500 text-white'
          }`}
        >
          {isUser ? (
            <span className="text-xs font-bold">U</span>
          ) : (
            <Brain className="w-4 h-4 text-white" />
          )}
        </div>

        {/* Message Bubble Container */}
        <div className="flex flex-col min-w-0">
          <div
            className={`rounded-2xl px-5 py-4 text-sm leading-relaxed shadow-sm transition-all ${
              isUser
                ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-tr-sm'
                : 'bg-white dark:bg-[#151624] border border-slate-200/90 dark:border-[#222438] text-slate-800 dark:text-slate-100 rounded-tl-sm'
            }`}
          >
            {/* Markdown rendered text */}
            <div className={`markdown-body ${isUser ? 'text-white' : 'text-slate-800 dark:text-slate-100'} max-w-none text-sm break-words`}>
              <ReactMarkdown
                components={{
                  code({ node, inline, className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline && match ? (
                      <CodeBlock
                        language={match[1]}
                        value={String(children).replace(/\n$/, '')}
                      />
                    ) : (
                      <code
                        className={`px-1.5 py-0.5 rounded text-xs font-mono ${
                          isUser
                            ? 'bg-purple-800 text-purple-100'
                            : 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border border-purple-200/60 dark:border-purple-800/40'
                        }`}
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  },
                  p: ({ children }) => <p className="mb-2.5 last:mb-0">{children}</p>,
                  ul: ({ children }) => (
                    <ul className="list-disc pl-5 my-2.5 space-y-1">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal pl-5 my-2.5 space-y-1">{children}</ol>
                  ),
                  li: ({ children }) => <li className="my-0.5">{children}</li>,
                  h1: ({ children }) => (
                    <h1 className={`text-xl font-bold my-3 ${isUser ? 'text-white' : 'text-slate-900 dark:text-white'}`}>{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className={`text-lg font-bold my-2.5 ${isUser ? 'text-white' : 'text-slate-900 dark:text-white'}`}>{children}</h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className={`text-base font-semibold my-2 ${isUser ? 'text-white' : 'text-slate-900 dark:text-white'}`}>{children}</h3>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-purple-500 pl-3 italic opacity-90 my-2">
                      {children}
                    </blockquote>
                  ),
                  a: ({ href, children }: any) => {
                    if (!href) return <a>{children}</a>;
                    const lowerHref = href.toLowerCase();
                    const isDownload =
                      lowerHref.includes('/downloads/') ||
                      lowerHref.endsWith('.pptx') ||
                      lowerHref.endsWith('.pdf') ||
                      lowerHref.endsWith('.zip');

                    if (isDownload) {
                      let icon = <Download className="w-5 h-5 text-purple-600 dark:text-purple-400" />;
                      let badge = 'Download Artifact';
                      let cardBg =
                        'bg-purple-50/80 dark:bg-purple-950/20 border-purple-200 dark:border-purple-800/50 text-purple-900 dark:text-purple-200';
                      let btnStyle =
                        'bg-purple-600 text-white hover:bg-purple-700 shadow-sm';

                      if (lowerHref.endsWith('.pptx')) {
                        icon = <Presentation className="w-5 h-5 text-amber-500" />;
                        badge = 'PowerPoint Presentation (.pptx)';
                        cardBg =
                          'bg-amber-50/80 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800/50 text-amber-900 dark:text-amber-200';
                        btnStyle =
                          'bg-amber-500 text-slate-950 hover:bg-amber-400 font-bold';
                      } else if (lowerHref.endsWith('.pdf')) {
                        icon = <FileText className="w-5 h-5 text-rose-500" />;
                        badge = 'Official Document (.pdf)';
                        cardBg =
                          'bg-rose-50/80 dark:bg-rose-950/20 border-rose-200 dark:border-rose-800/50 text-rose-900 dark:text-rose-200';
                        btnStyle =
                          'bg-rose-500 text-white hover:bg-rose-600 font-bold';
                      } else if (lowerHref.endsWith('.zip')) {
                        icon = <FolderArchive className="w-5 h-5 text-indigo-500" />;
                        badge = 'Project Source Code (.zip)';
                        cardBg =
                          'bg-indigo-50/80 dark:bg-indigo-950/20 border-indigo-200 dark:border-indigo-800/50 text-indigo-900 dark:text-indigo-200';
                        btnStyle =
                          'bg-indigo-600 text-white hover:bg-indigo-700 font-bold';
                      }

                      return (
                        <a
                          href={href}
                          download
                          target="_blank"
                          rel="noopener noreferrer"
                          className={`my-3 flex flex-col sm:flex-row sm:items-center justify-between p-3.5 rounded-xl ${cardBg} border shadow-sm hover:shadow transition-all no-underline group block gap-3`}
                        >
                          <div className="flex items-center space-x-3 min-w-0">
                            <div className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shrink-0 shadow-sm">
                              {icon}
                            </div>
                            <div className="truncate">
                              <div className="text-xs font-bold truncate group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                                {children}
                              </div>
                              <div className="text-[11px] opacity-75 font-mono mt-0.5">
                                {badge}
                              </div>
                            </div>
                          </div>
                          <span
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold shrink-0 flex items-center justify-center space-x-1 transition-transform group-hover:scale-105 ${btnStyle}`}
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>Download</span>
                          </span>
                        </a>
                      );
                    }

                    // Render inline images nicely
                    if (lowerHref.match(/\.(png|jpg|jpeg|gif|webp)$/) || lowerHref.includes('/images/')) {
                      return (
                        <div className="my-3 rounded-xl overflow-hidden border border-slate-200 dark:border-[#222438] bg-slate-100 dark:bg-slate-900 shadow-sm max-w-md">
                          <img
                            src={href}
                            alt="Generated Artifact"
                            className="w-full h-auto object-cover max-h-80 hover:scale-105 transition-transform duration-300"
                            loading="lazy"
                          />
                          <div className="p-2.5 flex items-center justify-between bg-white dark:bg-[#121320] border-t border-slate-200 dark:border-slate-800 text-xs">
                            <span className="text-purple-600 dark:text-purple-400 font-medium flex items-center gap-1.5">
                              <ImageIcon className="w-3.5 h-3.5" />
                              Generated Visualization
                            </span>
                            <a
                              href={href}
                              download
                              target="_blank"
                              rel="noreferrer"
                              className="px-2.5 py-1 rounded-md bg-purple-600 hover:bg-purple-700 text-white font-medium flex items-center gap-1 text-[11px]"
                            >
                              <Download className="w-3 h-3" />
                              Save
                            </a>
                          </div>
                        </div>
                      );
                    }

                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-purple-600 dark:text-purple-400 hover:underline inline-flex items-center gap-0.5 font-medium"
                      >
                        {children}
                        <ExternalLink className="w-3 h-3 inline ml-0.5 opacity-70" />
                      </a>
                    );
                  },
                }}
              >
                {renderableContent}
              </ReactMarkdown>
            </div>

            {/* Task Execution Progress Card if present */}
            {message.task_info && (
              <div className="mt-4 pt-3 border-t border-slate-200/80 dark:border-[#222438]">
                <TaskProgress
                  task={{
                    id: (message.task_info as any)?.task_id || (message.task_info as any)?.id,
                    title: message.task_info.title || 'Autonomous Task Execution',
                    status: (message.task_info.status as any) || 'completed',
                  }}
                />
              </div>
            )}
          </div>

          {/* Action Row & Provenance Toolbar */}
          <div
            className={`flex items-center space-x-2 mt-1.5 text-[11px] text-slate-400 dark:text-slate-500 px-1 ${
              isUser ? 'justify-end' : 'justify-start'
            }`}
          >
            <span>{formattedTime}</span>

            {!isUser && (
              <>
                <span>•</span>
                <button
                  onClick={handleCopyMessage}
                  className="hover:text-purple-600 dark:hover:text-purple-400 transition-colors flex items-center space-x-1"
                  title="Copy full message"
                >
                  {copiedMessage ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-500" />
                      <span className="text-emerald-500">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy</span>
                    </>
                  )}
                </button>

                <span>•</span>
                <button
                  onClick={handleSpeak}
                  className="hover:text-purple-600 dark:hover:text-purple-400 transition-colors flex items-center space-x-1"
                  title={isPlayingAudio ? 'Stop audio' : 'Listen with voice'}
                >
                  {isPlayingAudio ? (
                    <>
                      <VolumeX className="w-3 h-3 text-rose-500 animate-pulse" />
                      <span className="text-rose-500">Stop</span>
                    </>
                  ) : (
                    <>
                      <Volume2 className="w-3 h-3" />
                      <span>Listen</span>
                    </>
                  )}
                </button>

                {memoriesCount > 0 && (
                  <>
                    <span>•</span>
                    <button
                      onClick={() => setShowMemoryDetails(!showMemoryDetails)}
                      className="hover:text-purple-600 dark:hover:text-purple-400 transition-colors flex items-center space-x-1 text-purple-600 dark:text-purple-400 font-medium"
                    >
                      <Sparkles className="w-3 h-3" />
                      <span>{memoriesCount} memories used</span>
                      {showMemoryDetails ? (
                        <ChevronUp className="w-3 h-3" />
                      ) : (
                        <ChevronDown className="w-3 h-3" />
                      )}
                    </button>
                  </>
                )}
              </>
            )}
          </div>

          {/* Memory Drawer Collapsible */}
          {showMemoryDetails && usedMemoriesList.length > 0 && (
            <div className="mt-2 p-3 rounded-xl bg-purple-50/70 dark:bg-[#121322] border border-purple-200/70 dark:border-purple-900/30 text-xs space-y-2">
              <div className="font-semibold text-purple-900 dark:text-purple-300 flex items-center space-x-1.5">
                <Workflow className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
                <span>Episodic & Vector Memory Context</span>
              </div>
              <div className="space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar">
                {usedMemoriesList.map((mem, i) => (
                  <div
                    key={i}
                    className="p-2 rounded-lg bg-white dark:bg-[#18192a] border border-purple-100 dark:border-purple-900/40 text-slate-700 dark:text-slate-300"
                  >
                    <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
                      <span className="uppercase font-mono text-purple-600 dark:text-purple-400">
                        {mem.memory_type}
                      </span>
                      {mem.similarity && (
                        <span>{Math.round(mem.similarity * 100)}% match</span>
                      )}
                    </div>
                    <p className="line-clamp-2 text-xs">{mem.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
