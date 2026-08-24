'use client';

import {
  useQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query';
import { authFetch } from '@/lib/auth-fetch';

export interface UserBrief {
  id: string;
  fullName: string;
  avatarUrl: string | null;
  departmentId: string | null;
}

export interface ConversationMember {
  role: 'OWNER' | 'ADMIN' | 'MEMBER';
  user: UserBrief;
}

export interface MessageReceipt {
  id: string;
  messageId: string;
  userId: string;
  readAt: string;
  user: UserBrief;
}

export interface Message {
  id: string;
  conversationId: string;
  senderId: string;
  content: string;
  metadata: Record<string, unknown> | null;
  editedAt: string | null;
  deletedAt: string | null;
  createdAt: string;
  updatedAt: string;
  sender: UserBrief;
  receipts: MessageReceipt[];
}

export interface ConversationListItem {
  id: string;
  type: 'DIRECT' | 'GROUP';
  title: string | null;
  createdAt: string;
  updatedAt: string;
  members: ConversationMember[];
  messages: { id: string; content: string; createdAt: string; sender: UserBrief }[];
  membership: {
    role: 'OWNER' | 'ADMIN' | 'MEMBER';
    lastReadAt: string | null;
    joinedAt: string;
    unreadCount: number;
  };
}

export interface UserSearchResult {
  id: string;
  fullName: string;
  avatarUrl: string | null;
  department: { code: string; name: string } | null;
  currentLevel: string | null;
  matricNumber: string | null;
}

export interface ConversationDetail {
  id: string;
  type: 'DIRECT' | 'GROUP';
  title: string | null;
  departmentId: string | null;
  topicId: string | null;
  createdById: string;
  createdAt: string;
  updatedAt: string;
  members: (ConversationMember & {
    id: string;
    conversationId: string;
    userId: string;
    lastReadAt: string | null;
    joinedAt: string;
  })[];
}

export interface UnreadSummary {
  totalUnreadMessages: number;
  unreadNotifications: number;
  conversations: { conversationId: string; unreadCount: number }[];
}

// ── Hooks ──────────────────────────────────────────────────────────

const MESSAGES_PAGE_SIZE = 50;

export function useConversations() {
  return useQuery({
    queryKey: ['conversations'],
    queryFn: () => authFetch('/api/collaboration/conversations') as Promise<ConversationListItem[]>,
    refetchInterval: 30_000,
  });
}

/**
 * Message history as cursor-paginated pages, each page chronological
 * (oldest → newest). Page 1 is the latest window; further pages are older
 * history fetched with the `before` cursor for upward infinite scroll.
 */
export function useMessages(conversationId: string | null) {
  return useInfiniteQuery({
    queryKey: ['messages', conversationId],
    enabled: !!conversationId,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const base = `/api/collaboration/conversations/${conversationId}/messages`;
      if (pageParam) {
        return await authFetch(
          `${base}?before=${encodeURIComponent(pageParam)}&limit=${MESSAGES_PAGE_SIZE}`
        ) as Promise<Message[]>;
      }
      const latest = await authFetch(`${base}?page=1&limit=${MESSAGES_PAGE_SIZE}`) as Message[];
      // API returns newest-first; normalize so pages concatenate chronologically.
      return [...latest].reverse();
    },
    getNextPageParam: (lastPage) => {
      if (lastPage.length < MESSAGES_PAGE_SIZE) return undefined;
      return lastPage[0]?.createdAt ?? undefined;
    },
  });
}

/** Apply a change to the flat message list while preserving page boundaries. */
function updateMessagesData(
  old: InfiniteData<Message[]> | undefined,
  updater: (msgs: Message[]) => Message[]
): InfiniteData<Message[]> | undefined {
  if (!old) return old;
  const all = updater(old.pages.flat());
  const pages: Message[][] = [];
  let offset = 0;
  for (const page of old.pages) {
    pages.push(all.slice(offset, offset + page.length));
    offset += page.length;
  }
  return { ...old, pages };
}

export function useUnreadSummary() {
  return useQuery({
    queryKey: ['unread-summary'],
    queryFn: () => authFetch('/api/collaboration/unread-summary') as Promise<UnreadSummary>,
    refetchInterval: 30_000,
  });
}

export function useSearchUsers(query: string) {
  return useQuery({
    queryKey: ['users', 'search', query],
    queryFn: () =>
      authFetch(`/api/collaboration/users/search?q=${encodeURIComponent(query)}`) as Promise<UserSearchResult[]>,
    enabled: query.trim().length >= 2,
    staleTime: 30_000,
  });
}

export function useClassmates() {
  return useQuery({
    queryKey: ['users', 'classmates'],
    queryFn: () =>
      authFetch('/api/collaboration/users/classmates') as Promise<UserSearchResult[]>,
    staleTime: 60_000,
  });
}

export function useCreateConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      type?: 'DIRECT' | 'GROUP';
      title?: string;
      memberIds?: string[];
    }) => authFetch('/api/collaboration/conversations', {
      method: 'POST',
      body: JSON.stringify(body),
    }) as Promise<ConversationDetail>,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['conversations'] });
    },
  });
}

export function useSendMessage(userId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      conversationId,
      content,
    }: {
      conversationId: string;
      content: string;
    }) =>
      authFetch(`/api/collaboration/conversations/${conversationId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content }),
      }) as Promise<Message>,
    onMutate: async ({ conversationId, content }) => {
      await qc.cancelQueries({ queryKey: ['messages', conversationId] });

      const previous = qc.getQueryData<InfiniteData<Message[]>>(['messages', conversationId]);

      const optimistic: Message = {
        id: `optimistic-${Date.now()}`,
        conversationId,
        senderId: userId ?? '',
        content,
        metadata: null,
        editedAt: null,
        deletedAt: null,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        sender: {
          id: userId ?? '',
          fullName: '',
          avatarUrl: null,
          departmentId: null,
        },
        receipts: [],
      };

      qc.setQueryData<InfiniteData<Message[]>>(['messages', conversationId], (old) =>
        updateMessagesData(old, (msgs) => [...msgs, optimistic])
      );

      return { previous };
    },
    onSuccess: (data) => {
      qc.setQueryData<InfiniteData<Message[]>>(['messages', data.conversationId], (old) =>
        updateMessagesData(old, (msgs) =>
          msgs.map((m) => (m.id.startsWith('optimistic-') ? data : m))
        )
      );
      qc.invalidateQueries({ queryKey: ['messages', data.conversationId] });
      qc.invalidateQueries({ queryKey: ['conversations'] });
    },
    onError: (_err, { conversationId }, context) => {
      if (context?.previous) {
        qc.setQueryData(['messages', conversationId], context.previous);
      }
    },
  });
}

export function useEditMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId, content }: { messageId: string; content: string }) =>
      authFetch(`/api/collaboration/messages/${messageId}`, {
        method: 'PATCH',
        body: JSON.stringify({ content }),
      }) as Promise<Message>,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['messages'] });
    },
  });
}

export function useDeleteMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId }: { messageId: string }) =>
      authFetch(`/api/collaboration/messages/${messageId}`, {
        method: 'DELETE',
      }) as Promise<Message>,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['messages'] });
    },
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      conversationId,
      messageId,
    }: {
      conversationId: string;
      messageId?: string;
    }) =>
      authFetch(`/api/collaboration/conversations/${conversationId}/read`, {
        method: 'POST',
        body: JSON.stringify({ messageId }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['conversations'] });
      qc.invalidateQueries({ queryKey: ['unread-summary'] });
    },
  });
}

export function useSendTyping() {
  return useMutation({
    mutationFn: ({
      conversationId,
      isTyping,
    }: {
      conversationId: string;
      isTyping: boolean;
    }) =>
      authFetch(`/api/collaboration/conversations/${conversationId}/typing`, {
        method: 'POST',
        body: JSON.stringify({ isTyping }),
      }),
  });
}
