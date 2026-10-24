'use client';

import React, { useState } from 'react';
import {
  CheckCircle2,
  Clock,
  Loader2,
  XCircle,
  ChevronDown,
  ChevronUp,
  Terminal,
  ShieldCheck,
  Ban,
  RotateCcw,
} from 'lucide-react';
import { Task, TaskStep, TaskStatus } from '../lib/types';

interface TaskProgressProps {
  task: Partial<Task> & {
    id?: string;
    title?: string;
    status?: TaskStatus | string;
    steps?: TaskStep[];
  };
  onApprove?: (taskId: string, stepId: string) => void;
  onCancel?: (taskId: string) => void;
  onReplan?: (taskId: string) => Promise<void>;
  liveStepLogs?: Record<string, string>;
  compact?: boolean;
}

export const TaskProgress: React.FC<TaskProgressProps> = ({
  task,
  onApprove,
  onCancel,
  onReplan,
  liveStepLogs = {},
  compact = false,
}) => {
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({});
  const [isReplanning, setIsReplanning] = useState(false);

  const toggleStep = (stepId: string) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [stepId]: !prev[stepId],
    }));
  };

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            Completed
          </span>
        );
      case 'executing':
      case 'verifying':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/15 text-[#00d2ff] border border-blue-500/30 animate-pulse">
            Executing
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-500/15 text-red-400 border border-red-500/30">
            Failed
          </span>
        );
      case 'cancelled':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-500/15 text-gray-400 border border-gray-500/30">
            Cancelled
          </span>
        );
      case 'planning':
      case 'pending':
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            Pending Approval
          </span>
        );
    }
  };

  const renderStepIcon = (status: Task['steps'][number]['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-[#00d2ff] animate-spin shrink-0" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-rose-400 shrink-0" />;
      case 'skipped':
        return <Ban className="w-5 h-5 text-gray-500 shrink-0" />;
      case 'pending':
      default:
        return <Clock className="w-5 h-5 text-amber-400/80 shrink-0" />;
    }
  };

  const steps = task.steps || [];
  const taskSummary =
    typeof task.results?.summary === 'string' ? task.results.summary : null;
  const memoryUpdate = task.results?.memory_update;
  const memoryUpdateStatus =
    typeof memoryUpdate === 'object' &&
    memoryUpdate !== null &&
    'status' in memoryUpdate &&
    typeof memoryUpdate.status === 'string'
      ? memoryUpdate.status
      : null;
  const completedCount = steps.filter((s) => s.status === 'completed').length;
  const totalCount = steps.length || 1;
  const progressPercent = steps.length ? Math.round((completedCount / steps.length) * 100) : 0;
  const hasRunningStep = steps.some((step) => step.status === 'running');

  return (
    <div className="w-full bg-[#16213e]/90 border border-[#25325c] rounded-2xl p-5 shadow-lg">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h4 className="text-base font-semibold text-white tracking-wide flex items-center gap-2">
            <span>{task.title || 'Agent Autonomous Task'}</span>
          </h4>
          <p className="text-xs text-gray-400 mt-0.5">
            {completedCount} of {totalCount} steps completed ({progressPercent}%)
          </p>
        </div>
        <div className="flex items-center gap-2">
          {getStatusBadge(task.status)}
          {task.status === 'failed' && onReplan && task.id && (
            <button
              onClick={async () => {
                setIsReplanning(true);
                try {
                  await onReplan(task.id!);
                } finally {
                  setIsReplanning(false);
                }
              }}
              disabled={isReplanning}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium bg-[#00d2ff]/10 hover:bg-[#00d2ff]/20 text-[#00d2ff] border border-[#00d2ff]/30 rounded-lg transition-colors disabled:opacity-50"
              title="Generate a revised plan for approval"
            >
              {isReplanning ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RotateCcw className="w-3.5 h-3.5" />
              )}
              Revised plan
            </button>
          )}
          {['pending', 'planning', 'executing', 'verifying'].includes(task.status || '') &&
            onCancel && task.id && !hasRunningStep && (
            <button
              onClick={() => onCancel(task.id!)}
              className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
              title="Cancel task"
            >
              <Ban className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-[#1a1a2e] h-2 rounded-full overflow-hidden mb-5 border border-[#25325c]/50">
        <div
          className="h-full bg-gradient-to-r from-[#00d2ff] to-[#7b2ff7] transition-all duration-500 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Steps List */}
      {steps.length > 0 && (
        <div className="space-y-3">
          {steps.map((step) => {
            const isExpanded = expandedSteps[step.id] || false;
            const inputText = JSON.stringify(step.tool_input || {}, null, 2);
            const verification = step.tool_output?.verification;
            const verificationSummary =
              typeof verification === 'object' &&
              verification !== null &&
              'summary' in verification &&
              typeof verification.summary === 'string'
                ? verification.summary
                : null;
            const verificationStatus =
              typeof verification === 'object' &&
              verification !== null &&
              'status' in verification &&
              typeof verification.status === 'string'
                ? verification.status
                : null;
            const output = step.tool_output?.output;
            const outputText =
              typeof output === 'string'
                ? output
                : output === undefined
                  ? ''
                  : JSON.stringify(output, null, 2);
            const liveOutput = task.id
              ? liveStepLogs[`${task.id}:${step.id}`]
              : undefined;
            return (
              <div
                key={step.id}
                className="rounded-xl border border-[#25325c]/60 bg-[#121b33]/60 overflow-hidden transition-all"
              >
                <div
                  className="flex items-center justify-between p-3.5 cursor-pointer hover:bg-[#1a1a2e]/50 transition-colors"
                  onClick={() => toggleStep(step.id)}
                >
                  <div className="flex items-center space-x-3 min-w-0">
                    {renderStepIcon(step.status)}
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-gray-400">
                          Step {step.step_number}:
                        </span>
                        <p className="text-sm font-medium text-gray-200 truncate">
                          {step.description}
                        </p>
                      </div>
                      {step.tool_name && (
                        <div className="flex items-center text-xs text-[#00d2ff]/80 mt-0.5">
                          <Terminal className="w-3 h-3 mr-1" />
                          Tool: <span className="font-mono ml-1">{step.tool_name}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 shrink-0">
                    <span className="text-gray-400 p-1">
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4" />
                      ) : (
                        <ChevronDown className="w-4 h-4" />
                      )}
                    </span>
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="p-3.5 pt-0 border-t border-[#25325c]/40 text-xs space-y-2 bg-[#0f0f23]/40">
                    {verificationSummary && (
                      <div
                        className={`rounded-lg border px-3 py-2 ${
                          verificationStatus === 'verified'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                            : 'border-rose-500/30 bg-rose-500/10 text-rose-300'
                        }`}
                      >
                        <span className="font-semibold capitalize">
                          {verificationStatus || 'Verification'}:
                        </span>{' '}
                        {verificationSummary}
                      </div>
                    )}
                    <div>
                      <div className="text-gray-400 font-semibold mb-1">Proposed tool input:</div>
                      <pre className="p-2.5 rounded-lg bg-[#0a0a18] text-sky-200 font-mono text-xs overflow-x-auto whitespace-pre-wrap border border-[#25325c]">
                        {inputText}
                      </pre>
                    </div>
                    {step.status === 'pending' && onApprove && task.id && (
                      <button
                        onClick={() => {
                          setExpandedSteps((prev) => ({ ...prev, [step.id]: true }));
                          onApprove(task.id!, step.id);
                        }}
                        className="flex items-center px-2.5 py-1.5 text-xs font-medium bg-[#00d2ff]/10 hover:bg-[#00d2ff]/20 text-[#00d2ff] border border-[#00d2ff]/30 rounded-lg transition-colors"
                      >
                        <ShieldCheck className="w-3.5 h-3.5 mr-1" />
                        Approve this step
                      </button>
                    )}
                    {liveOutput && (
                      <div>
                        <div className="text-gray-400 font-semibold mb-1">Live output:</div>
                        <pre
                          aria-live="polite"
                          className="max-h-64 overflow-auto p-2.5 rounded-lg bg-[#0a0a18] text-emerald-300 font-mono text-xs whitespace-pre-wrap border border-[#25325c]"
                        >
                          {liveOutput}
                        </pre>
                      </div>
                    )}
                    {outputText && (
                      <div>
                        <div className="text-gray-400 font-semibold mb-1">Output:</div>
                        <pre className="p-2.5 rounded-lg bg-[#0a0a18] text-emerald-300 font-mono text-xs overflow-x-auto whitespace-pre-wrap border border-[#25325c]">
                          {outputText}
                        </pre>
                      </div>
                    )}
                    {step.error_message && (
                      <div>
                        <div className="text-red-400 font-semibold mb-1">Error:</div>
                        <pre className="p-2.5 rounded-lg bg-[#0a0a18] text-red-400 font-mono text-xs overflow-x-auto whitespace-pre-wrap border border-red-900/50">
                          {step.error_message}
                        </pre>
                      </div>
                    )}
                    {!outputText && !step.error_message && step.status !== 'pending' && (
                      <p className="text-gray-400 italic">No output recorded for this step yet.</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Task Result if present */}
      {taskSummary && (
        <div className={`mt-4 p-3.5 rounded-xl border ${
          task.status === 'failed'
            ? 'bg-red-950/20 border-red-500/30'
            : 'bg-emerald-950/20 border-emerald-500/30'
        }`}>
          <div className="text-xs font-semibold text-gray-300 mb-1">Execution Summary:</div>
          <p className="text-sm text-gray-200">{taskSummary}</p>
          {memoryUpdateStatus && (
            <p className="mt-2 text-xs text-gray-400">
              Outcome memory: {memoryUpdateStatus}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default TaskProgress;
