'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useAuth } from '@/context/auth-context';
import {
  useMessages,
  useSendMessage,
  useEditMessage,
  useDeleteMessage,
  useMarkRead,
  useSendTyping,
  type Message,
} from '@/queries/use-collaboration';
import { useChatSocket } from '@/hooks/useChatSocket';
import { useRealtimeMessages } from '@/hooks/useRealtimeMessages';
import { Skeleton } from '@/components/ui/skeleton';

interface ConversationViewProps {
  conversationId: string;
  title: string;
  onBack: () => void;
  otherUser?: { id: string; fullName: string; avatarUrl: string | null };
}

function MessageBubble({
  message,
  isOwn,
  onEdit,
  onDelete,
}: {
  message: Message;
  isOwn: boolean;
  onEdit: (id: string, content: string) => void;
  onDelete: (id: string) => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);

  const isDeleted = !!message.deletedAt;

  if (isDeleted) {
    return (
      <div className={`flex ${isOwn ? 'justify-end' : 'justify-start'} opacity-50`}>
        <div className="max-w-[75%] rounded-2xl bg-gray-100 px-4 py-2 text-xs italic text-gray-500">
          [deleted]
        </div>
      </div>
    );
  }

  const handleSaveEdit = async () => {
    if (editContent.trim() && editContent !== message.content) {
      await onEdit(message.id, editContent.trim());
    }
    setIsEditing(false);
  };

  return (
    <div className={`group flex ${isOwn ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[75%] ${isOwn ? 'order-1' : 'order-1'}`}>
        {!isOwn && (
          <div className="mb-1 flex items-center gap-2 px-1">
            <Avatar className="h-5 w-5">
              <AvatarImage src={message.sender.avatarUrl ?? undefined} />
              <AvatarFallback className="bg-green-50 text-[10px] font-bold text-gray-900">
                {message.sender.fullName.charAt(0)}
              </AvatarFallback>
            </Avatar>
            <span className="text-[11px] font-semibold text-gray-700">{message.sender.fullName}</span>
          </div>
        )}
        <div
          className={`relative rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
            isOwn
              ? 'bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 text-white'
              : 'bg-gray-100 text-gray-900'
          }`}
        >
          {isEditing ? (
            <div className="flex flex-col gap-2">
              <input
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full rounded-lg border border-blue-200 bg-white px-3 py-1.5 text-sm text-gray-900 outline-none focus:ring-2 focus:ring-sky-400"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSaveEdit();
                  }
                  if (e.key === 'Escape') setIsEditing(false);
                }}
              />
              <div className="flex gap-2">
                <button
                  onClick={handleSaveEdit}
                  className="rounded-lg bg-blue-600 px-3 py-1 text-xs font-bold text-white hover:bg-blue-700 transition"
                >
                  Save
                </button>
                <button
                  onClick={() => setIsEditing(false)}
                  className="rounded-lg bg-gray-200 px-3 py-1 text-xs font-bold text-gray-700 hover:bg-gray-300 transition"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              <p className="whitespace-pre-wrap break-words">{message.content}</p>
              {message.editedAt && !isDeleted && (
                <span className={`text-[10px] ${isOwn ? 'text-white/70' : 'text-gray-500'} mt-0.5 block`}>
                  edited
                </span>
              )}
            </>
          )}
        </div>
        {isOwn && !isEditing && (
          <div className="mt-1 hidden gap-2 px-2 group-hover:flex">
            <button
              onClick={() => {
                setEditContent(message.content);
                setIsEditing(true);
              }}
              className="text-[10px] font-semibold text-gray-500 hover:text-blue-600 transition"
            >
              Edit
            </button>
            <button
              onClick={() => onDelete(message.id)}
              className="text-[10px] font-semibold text-gray-500 hover:text-red-600 transition"
            >
              Delete
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function ConversationView({ conversationId, title, onBack, otherUser }: ConversationViewProps) {
  const { user } = useAuth();
  const {
    data: messagesData,
    isLoading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useMessages(conversationId);
  const sendMessage = useSendMessage(user?.id);
  const editMessage = useEditMessage();
  const deleteMessage = useDeleteMessage();

  // Pages are chronological (oldest → newest); flatten for rendering.
  const messages: Message[] = useMemo(
    () => messagesData?.pages.flat() ?? [],
    [messagesData]
  );

  useRealtimeMessages(conversationId, user?.id);
  const markRead = useMarkRead();
  const sendTyping = useSendTyping();
  const { typingUsers, connected, otherOnline } = useChatSocket({
    conversationId,
    userId: user?.id ?? '',
    otherUserId: otherUser?.id,
    enabled: !!user,
  });

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isLoadingOlderRef = useRef(false);
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const lastMessageId = messages.length > 0 ? messages[messages.length - 1].id : null;

  // Auto-scroll only when the newest message changes — prepending older
  // history must not yank the viewport to the bottom.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastMessageId]);

  useEffect(() => {
    if (messages.length > 0 && user) {
      markRead.mutate({ conversationId, messageId: messages[messages.length - 1].id });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, lastMessageId]);

  // Upward infinite scroll: load one page of older history at a time and
  // compensate the scroll offset so the viewport stays anchored on the
  // messages the user is reading.
  const handleScroll = async () => {
    const container = scrollContainerRef.current;
    if (!container || !hasNextPage || isFetchingNextPage || isLoadingOlderRef.current) return;
    if (container.scrollTop > 120) return;

    isLoadingOlderRef.current = true;
    try {
      const previousHeight = container.scrollHeight;
      const previousTop = container.scrollTop;
      await fetchNextPage();
      requestAnimationFrame(() => {
        if (!scrollContainerRef.current) return;
        const delta = scrollContainerRef.current.scrollHeight - previousHeight;
        scrollContainerRef.current.scrollTop = previousTop + delta;
      });
    } finally {
      isLoadingOlderRef.current = false;
    }
  };

  const handleSend = async () => {
    if (!input.trim()) return;
    await sendMessage.mutateAsync({ conversationId, content: input.trim() });
    setInput('');
  };

  const handleEdit = async (messageId: string, content: string) => {
    await editMessage.mutateAsync({ messageId, content });
  };

  const handleDelete = async (messageId: string) => {
    if (!window.confirm('Are you sure you want to delete this message?')) return
    await deleteMessage.mutateAsync({ messageId });
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInput(e.target.value);

    sendTyping.mutate({ conversationId, isTyping: true });
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = setTimeout(() => {
      sendTyping.mutate({ conversationId, isTyping: false });
    }, 3000);
  };

  const otherTyping = typingUsers
    .filter((t) => t.userId !== user?.id)
    .map((t) => messages.find((m) => m.senderId === t.userId)?.sender.fullName ?? 'Someone')
    .filter((v, i, a) => a.indexOf(v) === i);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-blue-100 px-4 py-3">
        <button
          onClick={onBack}
          className="rounded-lg p-1.5 text-gray-600 hover:bg-blue-50 transition lg:hidden"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        {otherUser && (
          <Avatar className="h-9 w-9 shrink-0 shadow-sm ring-2 ring-blue-100">
            <AvatarImage src={otherUser.avatarUrl ?? undefined} />
            <AvatarFallback className="bg-green-50 text-sm font-bold text-gray-900">
              {otherUser.fullName.charAt(0)}
            </AvatarFallback>
          </Avatar>
        )}
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-bold text-gray-900">{title}</h3>
          {otherUser && (
            <div className="flex items-center gap-2">
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  otherOnline ? 'animate-pulse bg-emerald-500' : 'bg-gray-300'
                }`}
              />
              <span className="text-[10px] font-medium text-gray-500">
                {otherOnline ? 'Online' : 'Offline'}
              </span>
            </div>
          )}
          {!otherUser && connected && (
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
              <span className="text-[10px] font-medium text-gray-500">Connected</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto" ref={scrollContainerRef} onScroll={handleScroll}>
        <div className="mx-auto max-w-3xl px-4 py-4">
          {isFetchingNextPage && (
            <div className="flex justify-center py-2">
              <svg className="h-4 w-4 animate-spin text-gray-400" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            </div>
          )}
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full rounded-2xl" />
              ))}
            </div>
          ) : messages.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <div className="text-center">
                <span className="text-3xl">💬</span>
                <p className="mt-2 text-sm text-gray-600">No messages yet</p>
                <p className="text-xs text-gray-500">Send the first message!</p>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  isOwn={msg.senderId === user?.id}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}

          {otherTyping.length > 0 && (
            <div className="mt-3 text-xs italic text-gray-500 animate-pulse">
              {otherTyping.join(', ')} {otherTyping.length === 1 ? 'is' : 'are'} typing...
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="border-t border-blue-100 px-4 py-3">
        <div className="mx-auto max-w-3xl">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2"
          >
          <input
            value={input}
            onChange={handleInputChange}
            placeholder="Type a message..."
            className="flex-1 rounded-xl border border-blue-100 bg-blue-50/50 px-4 py-2.5 text-sm outline-none transition-all focus:border-blue-300 focus:bg-white focus:ring-2 focus:ring-blue-200"
            disabled={sendMessage.isPending}
          />
          <button
            type="submit"
            disabled={!input.trim() || sendMessage.isPending}
            className="rounded-xl bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 px-4 py-2.5 text-sm font-bold text-white shadow-md transition-all hover:shadow-lg disabled:opacity-40"
          >
            {sendMessage.isPending ? (
              <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            ) : (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            )}
          </button>
          </form>
        </div>
      </div>
    </div>
  );
}
