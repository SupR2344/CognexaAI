import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import {
  AuthResponse,
  User,
  Conversation,
  Message,
  ChatRequest,
  ChatResponse,
  Memory,
  MemoryCreateInput,
  MemoryUpdateInput,
  Task,
  DashboardStats,
  ActivityItem,
  ExecutionLog,
  UsedMemory,
} from './types';

const API_BASE_URL =
  (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001').replace(/\/$/, '');

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 300000,
});

// Request Interceptor: Attach JWT bearer token from localStorage
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('cognexa_token');
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response Interceptor: Handle 401 Unauthorized by clearing session and redirecting
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      const currentPath = window.location.pathname;
      if (currentPath !== '/login' && currentPath !== '/register') {
        localStorage.removeItem('cognexa_token');
        localStorage.removeItem('cognexa_user');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// API Service Endpoints

export const authApi = {
  login: async (credentials: { email?: string; username?: string; password?: string }): Promise<AuthResponse> => {
    // Support OAuth2 password request form or JSON body
    const response = await apiClient.post<AuthResponse>('/api/auth/login', credentials);
    return response.data;
  },

  register: async (data: { username: string; email: string; password: string }): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/api/auth/register', data);
    return response.data;
  },

  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/api/auth/me');
    return response.data;
  },
};

export const chatApi = {
  getConversations: async (): Promise<Conversation[]> => {
    const response = await apiClient.get<Conversation[]>('/api/chat/conversations');
    return response.data;
  },

  getConversation: async (id: string): Promise<Conversation> => {
    const response = await apiClient.get<Conversation>(`/api/chat/conversations/${id}`);
    return response.data;
  },

  createConversation: async (title?: string): Promise<Conversation> => {
    const response = await apiClient.post<Conversation>('/api/chat/conversations', {
      title: title || 'New Conversation',
    });
    return response.data;
  },

  deleteConversation: async (id: string): Promise<{ success: boolean }> => {
    const response = await apiClient.delete<{ success: boolean }>(`/api/chat/conversations/${id}`);
    return response.data;
  },

  sendMessage: async (data: ChatRequest): Promise<ChatResponse> => {
    const response = await apiClient.post<ChatResponse>('/api/chat/messages', data);
    return response.data;
  },

  uploadFile: async (file: File): Promise<{
    file_id: string;
    filename: string;
    file_type: string;
    size_kb: number;
    summary: string;
    extracted_text: string;
    url: string;
  }> => {
    const formData = new FormData();
    formData.append('file', file);
    const token = typeof window !== 'undefined' ? localStorage.getItem('cognexa_token') : null;
    const response = await apiClient.post('/api/chat/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    return response.data;
  },

  streamMessage: async (
    data: ChatRequest,
    onChunk: (chunk: string) => void,
    externalSignal?: AbortSignal
  ): Promise<{
    conversation_id: string;
    task_created?: boolean;
    task_id?: string | null;
    memories_used?: UsedMemory[];
  }> => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 600000);
    const token = localStorage.getItem('cognexa_token');

    // Combine external signal if provided
    if (externalSignal) {
      externalSignal.addEventListener('abort', () => controller.abort());
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(data),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        const detail = await response.text();
        throw new Error(detail || `Chat request failed (${response.status}).`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      const result: {
        value: {
          conversation_id: string;
          task_created?: boolean;
          task_id?: string | null;
          memories_used?: UsedMemory[];
        } | null;
      } = { value: null };

      const processEvent = (event: string) => {
        const data = event
          .split('\n')
          .filter((line) => line.startsWith('data: '))
          .map((line) => line.slice(6))
          .join('\n');
        if (!data) return;

        const payload = JSON.parse(data);
        if (typeof payload.chunk === 'string') onChunk(payload.chunk);
        if (typeof payload.error === 'string') throw new Error(payload.error);
        if (payload.done) result.value = payload;
      };

      try {
        while (true) {
          const { done, value } = await reader.read();
          buffer += decoder.decode(value, { stream: !done });
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';
          events.forEach(processEvent);
          if (done) break;
        }
        if (buffer.trim()) processEvent(buffer);
      } finally {
        reader.releaseLock();
      }

      if (controller.signal.aborted) {
        return result.value || { conversation_id: data.conversation_id || '' };
      }

      if (!result.value?.conversation_id) {
        return { conversation_id: data.conversation_id || '' };
      }
      return result.value;
    } catch (err: any) {
      if (controller.signal.aborted || err.name === 'AbortError') {
        return { conversation_id: data.conversation_id || '' };
      }
      throw err;
    } finally {
      window.clearTimeout(timeout);
    }
  },

  getMessages: async (conversationId: string): Promise<Message[]> => {
    const response = await apiClient.get<Message[]>(`/api/chat/conversations/${conversationId}/messages`);
    return response.data;
  },
};

export const memoryApi = {
  getMemories: async (type?: string): Promise<Memory[]> => {
    const params = type ? { type } : {};
    const response = await apiClient.get<Memory[]>('/api/memory', { params });
    return response.data;
  },

  searchMemories: async (query: string, type?: string, limit: number = 20): Promise<Memory[]> => {
    const response = await apiClient.post<any>('/api/memory/search', {
      query,
      type: type || undefined,
      limit,
    });
    if (response.data && Array.isArray(response.data.memories)) {
      return response.data.memories;
    }
    if (Array.isArray(response.data)) {
      return response.data;
    }
    return [];
  },

  createMemory: async (data: MemoryCreateInput): Promise<Memory> => {
    const response = await apiClient.post<Memory>('/api/memory', data);
    return response.data;
  },

  updateMemory: async (id: string, data: MemoryUpdateInput): Promise<Memory> => {
    const response = await apiClient.put<Memory>(`/api/memory/${id}`, data);
    return response.data;
  },

  deleteMemory: async (id: string): Promise<{ success: boolean }> => {
    const response = await apiClient.delete<{ success: boolean }>(`/api/memory/${id}`);
    return response.data;
  },
};

export const taskApi = {
  getTasks: async (status?: string): Promise<Task[]> => {
    const params = status ? { status } : {};
    const response = await apiClient.get<Task[]>('/api/tasks', { params });
    return response.data;
  },

  getTask: async (id: string): Promise<Task> => {
    const response = await apiClient.get<Task>(`/api/tasks/${id}`);
    return response.data;
  },

  approveStep: async (
    taskId: string,
    stepId: string,
    onLog: (stream: string, chunk: string) => void
  ): Promise<Task> => {
    const controller = new AbortController();
    const token = typeof window === 'undefined'
      ? null
      : localStorage.getItem('cognexa_token');
    const logsResponse = await fetch(
      `${API_BASE_URL}/api/tasks/${taskId}/steps/${stepId}/logs`,
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: controller.signal,
      }
    );
    if (!logsResponse.ok || !logsResponse.body) {
      throw new Error(`Could not open task log stream (${logsResponse.status}).`);
    }

    const readLogs = async () => {
      const reader = logsResponse.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      try {
        while (true) {
          const { done, value } = await reader.read();
          buffer += decoder.decode(value, { stream: !done });
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';
          for (const event of events) {
            for (const line of event.split('\n')) {
              if (!line.startsWith('data: ')) continue;
              try {
                const payload = JSON.parse(line.slice(6));
                if (payload.type === 'output' && typeof payload.chunk === 'string') {
                  onLog(
                    typeof payload.stream === 'string' ? payload.stream : 'output',
                    payload.chunk
                  );
                }
                if (payload.type === 'complete') return;
              } catch (error) {
                if (error instanceof SyntaxError) {
                  console.error('Invalid task log event received:', error);
                } else {
                  throw error;
                }
              }
            }
          }
          if (done) return;
        }
      } finally {
        reader.releaseLock();
      }
    };

    try {
      const approval = apiClient.post<Task>(
        `/api/tasks/${taskId}/steps/${stepId}/approve`,
        undefined,
        { timeout: 240000 }
      );
      const [, response] = await Promise.all([readLogs(), approval]);
      return response.data;
    } catch (error) {
      controller.abort();
      throw error;
    }
  },

  replanTask: async (taskId: string): Promise<Task> => {
    const response = await apiClient.post<Task>(`/api/tasks/${taskId}/replan`);
    return response.data;
  },

  cancelTask: async (taskId: string): Promise<Task> => {
    const response = await apiClient.post<Task>(`/api/tasks/${taskId}/cancel`);
    return response.data;
  },
};

export const dashboardApi = {
  getStats: async (): Promise<DashboardStats> => {
    const response = await apiClient.get<DashboardStats>('/api/dashboard/stats');
    return response.data;
  },

  getActivity: async (limit: number = 20): Promise<ActivityItem[]> => {
    const response = await apiClient.get<ActivityItem[]>('/api/dashboard/activity', {
      params: { limit },
    });
    return response.data;
  },

  getExecutionLogs: async (limit: number = 50): Promise<ExecutionLog[]> => {
    const response = await apiClient.get<ExecutionLog[]>('/api/dashboard/logs', {
      params: { limit },
    });
    return response.data;
  },
};

export default apiClient;
