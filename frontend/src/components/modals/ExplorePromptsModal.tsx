'use client';

import React from 'react';
import {
  Sparkles,
  X,
  ArrowRight,
  TrendingUp,
  Brain,
  Globe2,
  FileCode,
  ShieldCheck,
  Cpu,
} from 'lucide-react';

interface ExplorePromptsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectPrompt: (prompt: string) => void;
}

const CURATED_PROMPTS = [
  {
    category: 'Engineering & Blockchain',
    icon: ShieldCheck,
    color: 'text-purple-600 bg-purple-100 dark:bg-purple-950/60 dark:text-purple-400',
    title: 'DApp & MetaMask Usability Analysis',
    description: 'Importance of connecting smart contracts with front-end apps and MetaMask transaction signing.',
    prompt: 'Question 1: Importance of connecting smart contracts with front-end applications for improving DApp usability.\nQuestion 2: MetaMask integration in DApp development.\nQuestion 3: Role of MetaMask in signing and submitting transactions.\nGive answers for 5 marks each in pdf format.',
  },
  {
    category: 'Distributed Systems',
    icon: TrendingUp,
    color: 'text-indigo-600 bg-indigo-100 dark:bg-indigo-950/60 dark:text-indigo-400',
    title: 'The 5 Vs of Big Data & Ecosystem',
    description: 'Deconstruct Volume, Velocity, Variety, Veracity, Value with Apache Spark & Kafka pipelines.',
    prompt: 'Explain the 5 V\'s of Big Data and architectural comparison between Lambda vs Kappa stream processing in PDF format.',
  },
  {
    category: 'Artificial Intelligence',
    icon: Brain,
    color: 'text-cyan-600 bg-cyan-100 dark:bg-cyan-950/60 dark:text-cyan-400',
    title: 'Autonomous AI (AABAIS) Multi-Agent Swarm',
    description: 'Swarm intelligence, Markov Decision Processes, Q-learning, and Explainable AI (XAI).',
    prompt: 'Provide complete 5-mark solutions for Autonomous AI Based Systems (AABAIS) covering Multi-Agent Swarm and Q-Learning in PDF format.',
  },
  {
    category: 'Presentations & Executive Decks',
    icon: Globe2,
    color: 'text-amber-600 bg-amber-100 dark:bg-amber-950/60 dark:text-amber-400',
    title: 'Cloud Native Microservices Architecture',
    description: 'Multi-slide widescreen PowerPoint deck on Kubernetes, Service Mesh, and Serverless.',
    prompt: 'Create a 6 slide presentation in ppt format about Cloud Native Microservices Architecture and Kubernetes.',
  },
];

export const ExplorePromptsModal: React.FC<ExplorePromptsModalProps> = ({
  isOpen,
  onClose,
  onSelectPrompt,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl p-6 rounded-2xl bg-white dark:bg-[#151624] border border-slate-200 dark:border-[#25283d] shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-2.5 mb-5">
          <div className="p-2.5 rounded-xl bg-purple-100 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-white">Research Prompt Library</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">Select any pre-formulated engineering topic to analyze or synthesize</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[60vh] overflow-y-auto pr-1 custom-scrollbar">
          {CURATED_PROMPTS.map((item, idx) => {
            const Icon = item.icon;
            return (
              <div
                key={idx}
                onClick={() => {
                  onSelectPrompt(item.prompt);
                  onClose();
                }}
                className="p-4 rounded-xl bg-slate-50 dark:bg-[#0e0f1a] border border-slate-200/80 dark:border-[#25283d] hover:border-purple-500/60 dark:hover:border-purple-500/60 hover:shadow-md cursor-pointer transition-all group flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-2.5">
                    <div className={`p-2 rounded-lg ${item.color}`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <span className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                      {item.category}
                    </span>
                  </div>
                  <h3 className="text-xs font-bold text-slate-900 dark:text-white group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                    {item.title}
                  </h3>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">
                    {item.description}
                  </p>
                </div>
                <div className="mt-3.5 pt-2.5 border-t border-slate-200/60 dark:border-slate-800/60 flex items-center justify-between text-xs text-purple-600 dark:text-purple-400 font-semibold">
                  <span>Load prompt</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
