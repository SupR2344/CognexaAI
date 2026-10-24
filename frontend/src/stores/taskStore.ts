import { create } from 'zustand';
import { Task } from '../lib/types';
import { taskApi } from '../lib/api';

interface TaskState {
  tasks: Task[];
  currentTask: Task | null;
  liveStepLogs: Record<string, string>;
  isLoading: boolean;
  error: string | null;

  fetchTasks: (status?: string) => Promise<void>;
  getTask: (id: string) => Promise<Task | null>;
  approveStep: (taskId: string, stepId: string) => Promise<void>;
  replanTask: (taskId: string) => Promise<Task | null>;
  cancelTask: (taskId: string) => Promise<void>;
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  currentTask: null,
  liveStepLogs: {},
  isLoading: false,
  error: null,

  fetchTasks: async (status?: string) => {
    set({ isLoading: true, error: null });
    try {
      const tasks = await taskApi.getTasks(status);
      set({ tasks, isLoading: false });
    } catch (err: any) {
      console.error('Failed to load tasks:', err);
      // Mock seed tasks if empty and server error to enable immediate UI testing
      set({
        error: err.response?.data?.detail || 'Failed to load task queue',
        isLoading: false,
      });
    }
  },

  getTask: async (id: string): Promise<Task | null> => {
    set({ isLoading: true, error: null });
    try {
      const task = await taskApi.getTask(id);
      set({ currentTask: task, isLoading: false });
      return task;
    } catch (err: any) {
      console.error('Failed to get task:', err);
      const existing = get().tasks.find((t) => t.id === id) || null;
      set({ currentTask: existing, isLoading: false });
      return existing;
    }
  },

  approveStep: async (taskId: string, stepId: string) => {
    const optimisticUpdate = (task: Task): Task => ({
      ...task,
      status: 'executing',
      steps: task.steps.map((step) =>
        step.id === stepId ? { ...step, status: 'running' } : step
      ),
    });
    const logKey = `${taskId}:${stepId}`;
    const previousTask = get().tasks.find((task) => task.id === taskId) || null;
    try {
      set((state) => ({
        liveStepLogs: { ...state.liveStepLogs, [logKey]: '' },
        tasks: state.tasks.map((task) =>
          task.id === taskId ? optimisticUpdate(task) : task
        ),
        currentTask:
          state.currentTask?.id === taskId
            ? optimisticUpdate(state.currentTask)
            : state.currentTask,
        error: null,
      }));
      const updated = await taskApi.approveStep(taskId, stepId, (stream, chunk) => {
        set((state) => {
          const previous = state.liveStepLogs[logKey] || '';
          const prefix = stream === 'stderr' || stream === 'errors' ? '[stderr] ' : '';
          return {
            liveStepLogs: {
              ...state.liveStepLogs,
              [logKey]: `${previous}${prefix}${chunk}`.slice(-100_000),
            },
          };
        });
      });
      set((state) => ({
        tasks: state.tasks.map((t) => (t.id === taskId ? updated : t)),
        currentTask: state.currentTask?.id === taskId ? updated : state.currentTask,
      }));
    } catch (err: any) {
      console.error('Failed to approve step:', err);
      let refreshedTask: Task | null = null;
      try {
        refreshedTask = await taskApi.getTask(taskId);
      } catch (refreshError) {
        console.error('Failed to refresh task after approval error:', refreshError);
      }
      set((state) => ({
        tasks: refreshedTask
          ? state.tasks.map((task) => (task.id === taskId ? refreshedTask! : task))
          : previousTask
            ? state.tasks.map((task) => (task.id === taskId ? previousTask : task))
            : state.tasks,
        currentTask:
          refreshedTask && state.currentTask?.id === taskId
            ? refreshedTask
            : !refreshedTask &&
                previousTask &&
                state.currentTask?.id === taskId
              ? previousTask
              : state.currentTask,
        error:
          err.response?.data?.detail ||
          err.message ||
          'Failed to approve task step',
      }));
    }
  },

  replanTask: async (taskId: string): Promise<Task | null> => {
    try {
      const revised = await taskApi.replanTask(taskId);
      set((state) => ({
        tasks: [revised, ...state.tasks.filter((task) => task.id !== revised.id)],
        currentTask: revised,
        error: null,
      }));
      return revised;
    } catch (err: any) {
      console.error('Failed to replan task:', err);
      set({ error: err.response?.data?.detail || 'Failed to create a revised task plan' });
      return null;
    }
  },

  cancelTask: async (taskId: string) => {
    try {
      const updated = await taskApi.cancelTask(taskId);
      set((state) => ({
        tasks: state.tasks.map((t) => (t.id === taskId ? updated : t)),
        currentTask: state.currentTask?.id === taskId ? updated : state.currentTask,
      }));
    } catch (err: any) {
      console.error('Failed to cancel task:', err);
      set({ error: err.response?.data?.detail || 'Failed to cancel task' });
    }
  },
}));
