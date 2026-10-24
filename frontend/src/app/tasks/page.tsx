'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  CheckSquare,
  Filter,
  RefreshCw,
  Loader2,
  Workflow,
  Clock,
  Play,
  XCircle,
  ShieldAlert,
} from 'lucide-react';
import Sidebar from '../../components/Sidebar';
import TaskProgress from '../../components/TaskProgress';
import { useAuthStore } from '../../stores/authStore';
import { useTaskStore } from '../../stores/taskStore';
import { Task, TaskStatus } from '../../lib/types';

export default function TasksPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuthStore();
  const {
    tasks,
    liveStepLogs,
    isLoading,
    error,
    fetchTasks,
    approveStep,
    cancelTask,
    replanTask,
  } = useTaskStore();

  const [selectedStatus, setSelectedStatus] = useState<string>('all');

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchTasks(selectedStatus === 'all' ? undefined : selectedStatus);
    }
  }, [isAuthenticated, selectedStatus, fetchTasks]);

  const handleRefresh = () => {
    fetchTasks(selectedStatus === 'all' ? undefined : selectedStatus);
  };

  const handleReplan = async (taskId: string) => {
    const revisedTask = await replanTask(taskId);
    if (revisedTask) {
      setSelectedStatus('all');
    }
  };

  const filteredTasks = tasks.filter((task) => {
    if (selectedStatus === 'all') return true;
    return task.status === selectedStatus;
  });

  const pendingCount = tasks.filter((t) => t.status === 'pending' || t.status === 'planning').length;
  const executingCount = tasks.filter((t) => t.status === 'executing').length;

  return (
    <div className="flex h-screen bg-[#0f0f23] text-gray-100 overflow-hidden">
      <Sidebar />

      <main className="flex-1 flex flex-col h-full overflow-y-auto custom-scrollbar p-6 lg:p-8">
        <div className="max-w-7xl mx-auto w-full space-y-6">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#25325c]">
            <div className="flex items-center space-x-3">
              <div className="p-2.5 rounded-xl bg-gradient-to-tr from-[#00d2ff]/20 to-[#7b2ff7]/20 border border-[#00d2ff]/30 text-[#00d2ff]">
                <Workflow className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white tracking-tight">
                  Autonomous Task Execution
                </h1>
                <p className="text-xs text-gray-400 mt-0.5">
                  Inspect multi-step plans, review safety policies, and approve agent actions.
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              {pendingCount > 0 && (
                <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-semibold">
                  <ShieldAlert className="w-4 h-4" />
                  <span>{pendingCount} Pending Approvals</span>
                </div>
              )}

              <button
                onClick={handleRefresh}
                disabled={isLoading}
                className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-[#16213e] hover:bg-[#1f2d5a] border border-[#25325c] text-xs font-medium text-gray-300 hover:text-white transition-all disabled:opacity-50"
                title="Refresh task list"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-[#00d2ff]' : ''}`} />
                <span>Refresh</span>
              </button>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="flex flex-wrap items-center gap-2 bg-[#16213e]/60 p-2 rounded-2xl border border-[#25325c]">
            {['all', 'pending', 'planning', 'executing', 'completed', 'failed', 'cancelled'].map((status) => {
              const isActive = selectedStatus === status;
              return (
                <button
                  key={status}
                  onClick={() => setSelectedStatus(status)}
                  className={`px-4 py-2 rounded-xl text-xs font-medium capitalize transition-all ${
                    isActive
                      ? 'bg-gradient-to-r from-blue-600 to-[#7b2ff7] text-white shadow-md font-semibold'
                      : 'text-gray-400 hover:text-white hover:bg-[#1a1a2e]'
                  }`}
                >
                  {status === 'all' ? 'All Tasks' : status}
                </button>
              );
            })}
          </div>

          {error && (
            <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {/* Tasks List */}
          {isLoading && tasks.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <Loader2 className="w-8 h-8 text-[#00d2ff] animate-spin mb-3" />
              <p className="text-sm">Fetching agent workflows...</p>
            </div>
          ) : filteredTasks.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center bg-[#16213e]/30 border border-dashed border-[#25325c] rounded-2xl p-8">
              <CheckSquare className="w-12 h-12 text-gray-600 mb-3" />
              <h3 className="text-base font-semibold text-gray-300">
                No tasks found
              </h3>
              <p className="text-xs text-gray-500 mt-1 max-w-sm">
                There are currently no tasks with status &ldquo;{selectedStatus}&rdquo;. As Cognexa AI executes complex multi-step workflows, their step progress will be tracked here.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredTasks.map((task) => (
                <TaskProgress
                  key={task.id}
                  task={task}
                  liveStepLogs={liveStepLogs}
                  onApprove={approveStep}
                  onCancel={cancelTask}
                  onReplan={handleReplan}
                />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
