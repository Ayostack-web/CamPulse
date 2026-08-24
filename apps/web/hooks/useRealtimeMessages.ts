'use client';

import { useEffect } from 'react';
import { useQueryClient, type InfiniteData } from '@tanstack/react-query';
import { getRealtimeSocket, type RealtimeEvent } from '@/lib/realtime';
import type { Message } from '@/queries/use-collaboration';

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

export function useRealtimeMessages(conversationId: string | null, userId: string | undefined) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!conversationId || !userId) return;

    let cancelled = false;

    (async () => {
      const socket = await getRealtimeSocket();
      if (!socket || cancelled) return;

      const handleEvent = (event: RealtimeEvent) => {
        if (cancelled) return;
        if (event.roomType !== 'conversation' || event.roomKey !== conversationId) return;

        const payload = event.payload as Record<string, unknown> | undefined;

        if (event.kind === 'message' && payload?.fullMessage) {
          const msg = payload.fullMessage as Message;
          queryClient.setQueryData<InfiniteData<Message[]>>(
            ['messages', conversationId],
            (old) =>
              updateMessagesData(old, (msgs) =>
                msgs.some((m) => m.id === msg.id) ? msgs : [...msgs, msg]
              )
          );
          queryClient.invalidateQueries({ queryKey: ['conversations'] });
        }

        if (event.kind === 'edit' && payload?.fullMessage) {
          const msg = payload.fullMessage as Message;
          queryClient.setQueryData<InfiniteData<Message[]>>(
            ['messages', conversationId],
            (old) =>
              updateMessagesData(old, (msgs) => msgs.map((m) => (m.id === msg.id ? msg : m)))
          );
        }

        if (event.kind === 'delete' && payload?.messageId) {
          const messageId = payload.messageId as string;
          queryClient.setQueryData<InfiniteData<Message[]>>(
            ['messages', conversationId],
            (old) => updateMessagesData(old, (msgs) => msgs.filter((m) => m.id !== messageId))
          );
        }
      };

      socket.on('pulse:event', handleEvent);
    })();

    return () => {
      cancelled = true;
      getRealtimeSocket().then((socket) => {
        if (!socket) return;
        socket.off('pulse:event');
      });
    };
  }, [conversationId, userId, queryClient]);
}
