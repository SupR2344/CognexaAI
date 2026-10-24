import { create } from 'zustand';
import { Conversation, Message, UsedMemory, TaskInfo } from '../lib/types';
import { chatApi } from '../lib/api';

// In-memory registry of active AbortControllers per conversation
const activeControllers: Record<string, AbortController> = {};

interface ChatState {
  conversations: Conversation[];
  currentConversation: Conversation | null;
  messages: Message[];
  conversationsMessages: Record<string, Message[]>;
  streamingConversations: Record<string, boolean>;
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;

  fetchConversations: () => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  createConversation: (title?: string) => Promise<Conversation>;
  deleteConversation: (id: string) => Promise<void>;
  sendMessage: (content: string, useMemory?: boolean, attachmentContext?: string, model?: string) => Promise<void>;
  stopStreaming: (conversationId?: string) => void;
  clearCurrentConversation: () => void;
  uploadAttachment: (file: File) => Promise<{
    file_id: string;
    filename: string;
    file_type: string;
    size_kb: number;
    summary: string;
    extracted_text: string;
    url: string;
  }>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversation: null,
  messages: [],
  conversationsMessages: {},
  streamingConversations: {},
  isLoading: false,
  isStreaming: false,
  error: null,

  clearCurrentConversation: () => {
    set({ currentConversation: null, messages: [], isStreaming: false });
  },

  stopStreaming: (conversationId?: string) => {
    const targetId = conversationId || get().currentConversation?.id;
    if (!targetId) return;

    if (activeControllers[targetId]) {
      try {
        activeControllers[targetId].abort();
      } catch (err) {
        console.warn('Error aborting stream:', err);
      }
      delete activeControllers[targetId];
    }

    set((state) => {
      const updatedStreaming = { ...state.streamingConversations, [targetId]: false };
      const isCurrentStreaming = state.currentConversation?.id === targetId ? false : state.isStreaming;
      return {
        streamingConversations: updatedStreaming,
        isStreaming: isCurrentStreaming,
      };
    });
  },

  uploadAttachment: async (file: File) => {
    set({ error: null });
    try {
      const data = await chatApi.uploadFile(file);
      return data;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'File upload failed';
      set({ error: errorMsg });
      throw new Error(errorMsg);
    }
  },

  fetchConversations: async () => {
    set({ isLoading: true, error: null });
    try {
      const conversations = await chatApi.getConversations();
      set({ conversations, isLoading: false });
    } catch (err: any) {
      console.error('Failed to fetch conversations:', err);
      set({
        error: err.response?.data?.detail || 'Failed to load conversations',
        isLoading: false,
      });
    }
  },

  selectConversation: async (id: string) => {
    const { conversationsMessages, streamingConversations } = get();
    const isConvStreaming = !!streamingConversations[id];

    // Check if we already have messages in memory
    const cachedMessages = conversationsMessages[id];
    if (cachedMessages) {
      const conv = get().conversations.find((c) => c.id === id) || {
        id,
        title: 'Conversation',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      set({
        currentConversation: conv,
        messages: cachedMessages,
        isStreaming: isConvStreaming,
        isLoading: false,
        error: null,
      });
      return;
    }

    set({ isLoading: true, error: null });
    try {
      const conv = await chatApi.getConversation(id);
      let loadedMessages: Message[] = [];
      if (conv.messages && conv.messages.length > 0) {
        loadedMessages = conv.messages;
      } else {
        try {
          loadedMessages = await chatApi.getMessages(id);
        } catch {
          loadedMessages = [];
        }
      }

      set((state) => ({
        currentConversation: conv,
        messages: loadedMessages,
        conversationsMessages: {
          ...state.conversationsMessages,
          [id]: loadedMessages,
        },
        isStreaming: !!state.streamingConversations[id],
        isLoading: false,
      }));
    } catch (err: any) {
      console.error('Failed to select conversation:', err);
      const existing = get().conversations.find((c) => c.id === id);
      if (existing) {
        set({
          currentConversation: existing,
          messages: existing.messages || [],
          isStreaming: isConvStreaming,
          isLoading: false,
        });
      } else {
        set({
          error: err.response?.data?.detail || 'Failed to load conversation details',
          isLoading: false,
        });
      }
    }
  },

  createConversation: async (title?: string): Promise<Conversation> => {
    set({ isLoading: true, error: null });
    try {
      const newConv = await chatApi.createConversation(title || 'New Chat');
      set((state) => ({
        conversations: [newConv, ...state.conversations],
        currentConversation: newConv,
        messages: [],
        conversationsMessages: {
          ...state.conversationsMessages,
          [newConv.id]: [],
        },
        isStreaming: false,
        isLoading: false,
      }));
      return newConv;
    } catch (err: any) {
      const localConv: Conversation = {
        id: 'local-' + Date.now(),
        title: title || 'New Conversation',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [],
      };
      set((state) => ({
        conversations: [localConv, ...state.conversations],
        currentConversation: localConv,
        messages: [],
        conversationsMessages: {
          ...state.conversationsMessages,
          [localConv.id]: [],
        },
        isStreaming: false,
        isLoading: false,
      }));
      return localConv;
    }
  },

  deleteConversation: async (id: string) => {
    // If active stream on this conversation, abort it
    if (activeControllers[id]) {
      try {
        activeControllers[id].abort();
      } catch {}
      delete activeControllers[id];
    }

    try {
      await chatApi.deleteConversation(id);
      set((state) => {
        const remaining = state.conversations.filter((c) => c.id !== id);
        const isCurrent = state.currentConversation?.id === id;
        const nextConv = isCurrent ? remaining[0] || null : state.currentConversation;
        const nextMessages = nextConv ? state.conversationsMessages[nextConv.id] || [] : [];
        return {
          conversations: remaining,
          currentConversation: nextConv,
          messages: nextMessages,
          isStreaming: nextConv ? !!state.streamingConversations[nextConv.id] : false,
        };
      });
    } catch (err: any) {
      console.error('Failed to delete conversation:', err);
      set((state) => ({
        conversations: state.conversations.filter((c) => c.id !== id),
        currentConversation: state.currentConversation?.id === id ? null : state.currentConversation,
        messages: state.currentConversation?.id === id ? [] : state.messages,
        isStreaming: false,
      }));
    }
  },

  sendMessage: async (
    content: string,
    useMemory: boolean = true,
    attachmentContext?: string,
    model?: string
  ) => {
    if (!content.trim() && !attachmentContext) return;

    let { currentConversation } = get();

    if (!currentConversation) {
      try {
        currentConversation = await get().createConversation(
          content.slice(0, 30) + (content.length > 30 ? '...' : '')
        );
      } catch (err) {
        currentConversation = {
          id: 'temp-' + Date.now(),
          title: content.slice(0, 30),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        set({ currentConversation });
      }
    }

    const conversationId = currentConversation.id;

    // Create abort controller for this specific conversation stream
    const controller = new AbortController();
    activeControllers[conversationId] = controller;

    // Build message with attached file context if provided
    let finalPrompt = content.trim();
    if (attachmentContext) {
      finalPrompt = `${attachmentContext}\n\nUser Question/Instruction:\n${finalPrompt || 'Please inspect and analyze this attached document.'}`;
    }

    // Create optimistic user message
    const userMessage: Message = {
      id: 'usr-' + Date.now(),
      conversation_id: conversationId,
      role: 'user',
      content: content.trim() || 'Attached file for analysis',
      created_at: new Date().toISOString(),
    };

    const assistantMessageId = 'asst-' + Date.now();
    const assistantMessage: Message = {
      id: assistantMessageId,
      conversation_id: conversationId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    };

    set((state) => {
      const prevList = state.conversationsMessages[conversationId] || state.messages || [];
      const updatedList = [...prevList, userMessage, assistantMessage];
      const isCurrent = state.currentConversation?.id === conversationId;
      return {
        conversationsMessages: {
          ...state.conversationsMessages,
          [conversationId]: updatedList,
        },
        messages: isCurrent ? updatedList : state.messages,
        streamingConversations: {
          ...state.streamingConversations,
          [conversationId]: true,
        },
        isStreaming: isCurrent ? true : state.isStreaming,
        error: null,
      };
    });

    try {
      const response = await chatApi.streamMessage(
        {
          conversation_id: conversationId,
          message: finalPrompt,
          use_memory: useMemory,
          model: model || 'Cognexa 2.0 Pro',
        },
        (chunk) => {
          set((state) => {
            const currentList = state.conversationsMessages[conversationId] || [];
            const updatedList = currentList.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: msg.content + chunk }
                : msg
            );
            const isCurrent = state.currentConversation?.id === conversationId;
            return {
              conversationsMessages: {
                ...state.conversationsMessages,
                [conversationId]: updatedList,
              },
              messages: isCurrent ? updatedList : state.messages,
            };
          });
        },
        controller.signal
      );

      delete activeControllers[conversationId];

      set((state) => {
        const currentList = state.conversationsMessages[conversationId] || [];
        const updatedList = currentList.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                conversation_id: response.conversation_id,
                memories_used: response.memories_used || null,
                task_info: response.task_created
                  ? {
                      task_id: response.task_id || undefined,
                      title: 'Task Preflight',
                      status: 'pending',
                    }
                  : null,
              }
            : msg
        );
        const isCurrent = state.currentConversation?.id === conversationId;
        return {
          conversationsMessages: {
            ...state.conversationsMessages,
            [conversationId]: updatedList,
          },
          messages: isCurrent ? updatedList : state.messages,
          streamingConversations: {
            ...state.streamingConversations,
            [conversationId]: false,
          },
          isStreaming: isCurrent ? false : state.isStreaming,
        };
      });

      // Update conversation title if first message
      const totalMessages = get().conversationsMessages[conversationId] || [];
      if (totalMessages.length <= 2) {
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === conversationId
              ? { ...c, title: (content || 'Analysis').slice(0, 32) + (content.length > 32 ? '...' : '') }
              : c
          ),
        }));
      }
    } catch (err: any) {
      delete activeControllers[conversationId];
      if (err.name === 'AbortError' || controller.signal.aborted) {
        set((state) => {
          const isCurrent = state.currentConversation?.id === conversationId;
          return {
            streamingConversations: {
              ...state.streamingConversations,
              [conversationId]: false,
            },
            isStreaming: isCurrent ? false : state.isStreaming,
          };
        });
        return;
      }

      console.error('Chat error in conversation', conversationId, err);
      set((state) => {
        const currentList = state.conversationsMessages[conversationId] || [];
        const updatedList = currentList.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: msg.content
                  ? `${msg.content}\n\n*[Stream stopped or interrupted]*`
                  : err.response?.data?.detail || err.message || 'Stream connection interrupted.',
              }
            : msg
        );
        const isCurrent = state.currentConversation?.id === conversationId;
        return {
          conversationsMessages: {
            ...state.conversationsMessages,
            [conversationId]: updatedList,
          },
          messages: isCurrent ? updatedList : state.messages,
          streamingConversations: {
            ...state.streamingConversations,
            [conversationId]: false,
          },
          isStreaming: isCurrent ? false : state.isStreaming,
          error: err.message,
        };
      });
    }
  },
}));
