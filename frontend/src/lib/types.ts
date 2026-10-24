/**
 * Cognexa AI - Type Definitions
 * Complete TypeScript interfaces for users, chats, memory, tasks, and API models.
 */

export interface User {
  id: string;
  username: string;
  email: string;
  created_at?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export type MemoryType =
  | 'user_preference'
  | 'project'
  | 'decision'
  | 'episodic'
  | 'error'
  | 'task'
  | 'verified_knowledge';

export interface Memory {
  id: string;
  user_id?: string;
  type: MemoryType | string;
  content: string;
  confidence: number;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at?: string;
}

export interface MemoryCreateInput {
  content: string;
  type: MemoryType | string;
  confidence?: number;
  metadata?: Record<string, any>;
}

export interface MemoryUpdateInput {
  content?: string;
  type?: MemoryType | string;
  confidence?: number;
  metadata?: Record<string, any>;
}

export interface MemorySearchRequest {
  query: string;
  type?: string;
  limit?: number;
  threshold?: number;
}

export type TaskStatus =
  | 'pending'
  | 'planning'
  | 'executing'
  | 'verifying'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type TaskStepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

export interface TaskStep {
  id: string;
  step_number: number;
  description: string;
  tool_name?: string | null;
  tool_input?: Record<string, unknown> | null;
  tool_output?: Record<string, unknown> | null;
  status: TaskStepStatus;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface Task {
  id: string;
  conversation_id?: string | null;
  title: string;
  description?: string | null;
  status: TaskStatus;
  plan?: Array<Record<string, unknown>> | null;
  results?: Record<string, unknown> | null;
  created_at: string;
  updated_at?: string;
  steps: TaskStep[];
}

export interface TaskInfo {
  task_id?: string;
  title?: string;
  status?: TaskStatus | string;
  steps_completed?: number;
  total_steps?: number;
  current_step?: string;
}

export interface UsedMemory {
  id: string;
  memory_type?: string;
  type?: string;
  content: string;
  confidence?: number;
  similarity?: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  memories_used?: UsedMemory[] | number | null;
  task_info?: TaskInfo | null;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: Message[];
}

export interface ChatRequest {
  conversation_id?: string;
  message: string;
  use_memory?: boolean;
  stream?: boolean;
  model?: string;
}

export interface ChatResponse {
  response: string;
  reply?: string | null;
  conversation_id: string;
  task_created: boolean;
  task_id?: string | null;
  memories_used?: UsedMemory[];
}

export interface DashboardStats {
  total_conversations: number;
  memories_stored: number;
  tasks_completed: number;
  success_rate: number;
  conversations_change?: number;
  memories_change?: number;
  tasks_change?: number;
  success_rate_change?: number;
}

export interface ActivityItem {
  id: string;
  type: 'chat' | 'memory' | 'task' | 'system';
  title: string;
  description: string;
  timestamp: string;
  status?: string;
}

export interface ExecutionLog {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  module: string;
  message: string;
  details?: Record<string, any>;
}
