'use client';

import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';

interface StatsCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  change?: number;
  suffix?: string;
  gradient?: string;
}

export const StatsCard: React.FC<StatsCardProps> = ({
  label,
  value,
  icon: Icon,
  change,
  suffix = '',
  gradient = 'from-[#00d2ff]/20 to-[#7b2ff7]/20',
}) => {
  const isPositive = (change ?? 0) >= 0;

  return (
    <div className="relative group rounded-2xl p-[1px] bg-gradient-to-r from-[#00d2ff]/30 via-[#7b2ff7]/20 to-transparent hover:from-[#00d2ff] hover:to-[#7b2ff7] transition-all duration-300">
      <div className="relative h-full bg-[#16213e]/90 backdrop-blur-xl rounded-2xl p-6 flex flex-col justify-between overflow-hidden">
        {/* Glow ambient background effect */}
        <div
          className={`absolute -right-6 -bottom-6 w-28 h-28 bg-gradient-to-br ${gradient} rounded-full blur-2xl opacity-40 group-hover:opacity-75 transition-opacity duration-300 pointer-events-none`}
        />

        <div className="flex items-center justify-between mb-4">
          <span className="text-sm font-medium text-gray-400 tracking-wide">{label}</span>
          <div className="p-2.5 rounded-xl bg-[#1a1a2e] border border-[#25325c] text-[#00d2ff] group-hover:scale-110 transition-transform duration-200">
            <Icon className="w-5 h-5" />
          </div>
        </div>

        <div className="flex items-baseline justify-between mt-1">
          <div className="text-3xl font-bold text-white tracking-tight">
            {value}
            {suffix && <span className="text-xl text-gray-400 font-normal ml-1">{suffix}</span>}
          </div>

          {change !== undefined && (
            <div
              className={`flex items-center text-xs font-semibold px-2 py-1 rounded-full ${
                isPositive
                  ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
                  : 'text-rose-400 bg-rose-500/10 border border-rose-500/20'
              }`}
            >
              {isPositive ? (
                <TrendingUp className="w-3.5 h-3.5 mr-1" />
              ) : (
                <TrendingDown className="w-3.5 h-3.5 mr-1" />
              )}
              {isPositive ? `+${change}%` : `${change}%`}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default StatsCard;
