'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  MessageSquare,
  Database,
  CheckCircle2,
  Activity,
  Calendar,
  Clock,
  Terminal,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Info,
  Check,
  RefreshCw,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { format } from 'date-fns';
import Sidebar from '../../components/Sidebar';
import StatsCard from '../../components/StatsCard';
import { useAuthStore } from '../../stores/authStore';
import { dashboardApi, taskApi } from '../../lib/api';
import {
  DashboardStats,
  ActivityItem,
  ExecutionLog,
  Task,
} from '../../lib/types';

export default function DashboardPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuthStore();

  const [stats, setStats] = useState<DashboardStats>({
    total_conversations: 0,
    memories_stored: 0,
    tasks_completed: 0,
    success_rate: 100,
  });


  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const [fetchedStats, fetchedActivity, fetchedLogs, fetchedTasks] =
        await Promise.allSettled([
          dashboardApi.getStats(),
          dashboardApi.getActivity(10),
          dashboardApi.getExecutionLogs(15),
          taskApi.getTasks(),
        ]);

      if (fetchedStats.status === 'fulfilled' && fetchedStats.value) {
        const val = fetchedStats.value as any;
        setStats({
          total_conversations: val.total_conversations ?? 0,
          memories_stored: val.memories_stored ?? val.total_memories ?? 0,
          tasks_completed: val.tasks_completed ?? val.completed_tasks ?? 0,
          success_rate: val.success_rate ?? 100,
        });
      }

      if (fetchedActivity.status === 'fulfilled' && Array.isArray(fetchedActivity.value)) {
        setActivities(fetchedActivity.value);
      } else {
        setActivities([]);
      }

      if (fetchedTasks.status === 'fulfilled' && Array.isArray(fetchedTasks.value)) {
        setTasks(fetchedTasks.value);
      } else {
        setTasks([]);
      }

      if (fetchedLogs.status === 'fulfilled' && Array.isArray(fetchedLogs.value)) {
        setLogs(fetchedLogs.value);
      } else {
        setLogs([]);
      }

    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadDashboardData();
    }
  }, [isAuthenticated]);

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'chat':
        return <MessageSquare className="w-4 h-4 text-[#00d2ff]" />;
      case 'memory':
        return <Database className="w-4 h-4 text-[#7b2ff7]" />;
      case 'task':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'system':
      default:
        return <Activity className="w-4 h-4 text-blue-400" />;
    }
  };

  const getLogLevelBadge = (level: string) => {
    switch (level.toLowerCase()) {
      case 'error':
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-red-500/15 text-red-400 border border-red-500/30">
            ERROR
          </span>
        );
      case 'warn':
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            WARN
          </span>
        );
      case 'debug':
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-purple-500/15 text-purple-400 border border-purple-500/30">
            DEBUG
          </span>
        );
      case 'info':
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-blue-500/15 text-blue-400 border border-blue-500/30">
            INFO
          </span>
        );
    }
  };

  const formatTimestamp = (ts: string) => {
    try {
      return format(new Date(ts), 'MMM d, HH:mm:ss');
    } catch {
      return ts;
    }
  };

  return (
    <div className="flex h-screen bg-[#0f0f23] text-gray-100 overflow-hidden">
      <Sidebar />

      <main className="flex-1 flex flex-col h-full overflow-y-auto custom-scrollbar p-6 lg:p-8">
        <div className="max-w-7xl mx-auto w-full space-y-8">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#25325c]">
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                <span>Cognexa AI Mission Control</span>
                <Sparkles className="w-5 h-5 text-[#00d2ff]" />
              </h1>
              <p className="text-xs text-gray-400 mt-1">
                Real-time operational metrics, agent cognitive health, and audit logs.
              </p>
            </div>

            <button
              onClick={loadDashboardData}
              disabled={isLoading}
              className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-[#16213e] hover:bg-[#1f2d5a] border border-[#25325c] text-xs font-medium text-gray-300 hover:text-white transition-all disabled:opacity-50 shrink-0"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-[#00d2ff]' : ''}`} />
              <span>Refresh Metrics</span>
            </button>
          </div>

          {/* Top Stats Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <StatsCard
              label="Total Conversations"
              value={stats.total_conversations}
              icon={MessageSquare}
              change={stats.conversations_change}
              gradient="from-blue-600/30 to-[#00d2ff]/30"
            />
            <StatsCard
              label="Memories Stored"
              value={stats.memories_stored}
              icon={Database}
              change={stats.memories_change}
              gradient="from-[#7b2ff7]/30 to-[#00d2ff]/30"
            />
            <StatsCard
              label="Tasks Completed"
              value={stats.tasks_completed}
              icon={CheckCircle2}
              change={stats.tasks_change}
              gradient="from-emerald-500/30 to-blue-500/30"
            />
            <StatsCard
              label="Success Rate"
              value={stats.success_rate}
              suffix="%"
              icon={Activity}
              change={stats.success_rate_change}
              gradient="from-[#00d2ff]/30 to-emerald-400/30"
            />
          </div>

          {/* Middle Section: Timeline & Task History */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Recent Activity Timeline (5 cols) */}
            <div className="lg:col-span-5 bg-[#16213e]/90 border border-[#25325c] rounded-2xl p-6 shadow-xl flex flex-col justify-between">
              <div>
                <h3 className="text-base font-semibold text-white tracking-wide mb-4 flex items-center justify-between">
                  <span>Recent Activity Stream</span>
                  <span className="text-xs font-normal text-gray-400">Live events</span>
                </h3>

                {activities.length === 0 ? (
                  <div className="py-10 flex flex-col items-center justify-center text-center">
                    <Activity className="w-8 h-8 text-gray-500 mb-2 opacity-40" />
                    <p className="text-xs font-medium text-gray-300">No activity recorded yet</p>
                    <p className="text-[11px] text-gray-500 mt-1 max-w-xs">
                      Conversations, memory creations, and agent actions will appear here live as they occur.
                    </p>
                  </div>
                ) : (
                  <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-[2px] before:bg-[#25325c]">
                    {activities.map((item) => (
                      <div key={item.id} className="relative group">
                        {/* Node point */}
                        <div className="absolute -left-6 top-1 w-5 h-5 rounded-full bg-[#121b33] border-2 border-[#00d2ff] flex items-center justify-center shrink-0">
                          <div className="w-1.5 h-1.5 rounded-full bg-[#00d2ff]" />
                        </div>

                        <div className="bg-[#121b33]/80 p-3.5 rounded-xl border border-[#25325c]/60 hover:border-[#00d2ff]/40 transition-colors">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-semibold text-white truncate pr-2">
                              {item.title}
                            </span>
                            <span className="text-[10px] text-gray-400 shrink-0 font-mono">
                              {formatTimestamp(item.timestamp)}
                            </span>
                          </div>
                          <p className="text-xs text-gray-400 leading-relaxed">
                            {item.description}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Task History Table (7 cols) */}
            <div className="lg:col-span-7 bg-[#16213e]/90 border border-[#25325c] rounded-2xl p-6 shadow-xl flex flex-col justify-between">
              <div>
                <h3 className="text-base font-semibold text-white tracking-wide mb-4 flex items-center justify-between">
                  <span>Task Execution Log</span>
                  <span className="text-xs font-normal text-gray-400">{tasks.length} total tasks</span>
                </h3>

                {tasks.length === 0 ? (
                  <div className="py-10 flex flex-col items-center justify-center text-center">
                    <CheckCircle2 className="w-8 h-8 text-gray-500 mb-2 opacity-40" />
                    <p className="text-xs font-medium text-gray-300">No tasks executed yet</p>
                    <p className="text-[11px] text-gray-500 mt-1 max-w-xs">
                      Issue an actionable prompt in Chat (e.g. generate code, run tests) to trigger multi-step tasks.
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-[#25325c] text-gray-400 uppercase tracking-wider font-semibold">
                          <th className="pb-3 px-2">Task Name</th>
                          <th className="pb-3 px-2">Status</th>
                          <th className="pb-3 px-2">Steps</th>
                          <th className="pb-3 px-2">Timestamp</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#25325c]/50 text-gray-300">
                        {tasks.map((task) => {
                          const completedSteps = (task.steps || []).filter(
                            (s) => s.status === 'completed'
                          ).length;
                          const totalSteps = task.steps?.length || 1;

                          return (
                            <tr key={task.id} className="hover:bg-[#1a1a2e]/60 transition-colors">
                              <td className="py-3 px-2 font-medium text-white max-w-[200px] truncate">
                                {task.title}
                              </td>
                              <td className="py-3 px-2">
                                {task.status === 'completed' && (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                                    Completed
                                  </span>
                                )}
                                {task.status === 'executing' && (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/15 text-[#00d2ff] border border-blue-500/30 animate-pulse">
                                    Executing
                                  </span>
                                )}
                                {task.status === 'pending' && (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
                                    Pending
                                  </span>
                                )}
                                {task.status === 'failed' && (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-red-500/15 text-red-400 border border-red-500/30">
                                    Failed
                                  </span>
                                )}
                              </td>
                              <td className="py-3 px-2 font-mono text-gray-400">
                                {completedSteps}/{totalSteps}
                              </td>
                              <td className="py-3 px-2 text-gray-400 whitespace-nowrap">
                                {formatTimestamp(task.created_at)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Execution Logs Accordion Section */}
          <div className="bg-[#16213e]/90 border border-[#25325c] rounded-2xl p-6 shadow-xl">
            <div className="flex items-center justify-between pb-4 border-b border-[#25325c]">
              <div className="flex items-center space-x-2">
                <Terminal className="w-5 h-5 text-[#00d2ff]" />
                <h3 className="text-base font-semibold text-white tracking-wide">
                  Agent Kernel Diagnostics & Execution Traces
                </h3>
              </div>
              <span className="text-xs text-gray-400 font-mono">
                {logs.length} logged entries
              </span>
            </div>

            {logs.length === 0 ? (
              <div className="py-8 flex flex-col items-center justify-center text-center">
                <Terminal className="w-8 h-8 text-gray-500 mb-2 opacity-40" />
                <p className="text-xs font-medium text-gray-300">No execution traces yet</p>
                <p className="text-[11px] text-gray-500 mt-1 max-w-xs">
                  Tool invocations, shell executions, and verification audits will stream here when tasks run.
                </p>
              </div>
            ) : (
              <div className="mt-4 space-y-2">
                {logs.map((log) => {
                  const isExpanded = expandedLogId === log.id;
                  return (
                    <div
                      key={log.id}
                      className="rounded-xl border border-[#25325c]/70 bg-[#121b33] overflow-hidden"
                    >
                      <div
                        onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                        className="p-3 flex items-center justify-between text-xs cursor-pointer hover:bg-[#1a1a2e] transition-colors"
                      >
                        <div className="flex items-center space-x-3 min-w-0">
                          {getLogLevelBadge(log.level)}
                          <span className="text-gray-400 font-mono text-[11px] shrink-0">
                            {formatTimestamp(log.timestamp)}
                          </span>
                          <span className="text-[#00d2ff] font-mono text-[11px] shrink-0 font-semibold">
                            [{log.module}]
                          </span>
                          <span className="text-gray-200 truncate">{log.message}</span>
                        </div>

                        <div className="text-gray-400 pl-2">
                          {isExpanded ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </div>
                      </div>

                      {isExpanded && log.details && (
                        <div className="p-3 border-t border-[#25325c]/50 bg-[#0a0a18] text-xs font-mono text-emerald-300">
                          <pre className="overflow-x-auto whitespace-pre-wrap">
                            {JSON.stringify(log.details, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

          </div>
        </div>
      </main>
    </div>
  );
}
