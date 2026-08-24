'use client';

import { useCallback, useRef, useState } from 'react';
import { authFetchRaw } from '@/lib/auth-fetch';


interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatPanelProps {
  documentId: string;
  documentTitle: string;
  onClose: () => void;
}

export function ChatPanel({ documentId, documentTitle, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: `Ask me anything about "${documentTitle}" — I'll search the document for answers.` },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [followUps, setFollowUps] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;

    const userMessage: Message = { role: 'user', content: text.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const res = await authFetchRaw(`/api/documents/chat`, {
        method: 'POST',
        body: JSON.stringify({ document_id: documentId, query: text.trim() }),
      });

      if (!res.ok) throw new Error('Chat request failed');

      const data = await res.json();
      const assistantMessage: Message = { role: 'assistant', content: data.answer };
      setMessages((prev) => [...prev, assistantMessage]);
      setFollowUps(data.follow_up_questions ?? []);
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Sorry, I couldn\'t process that request. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  }, [documentId, loading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40">
      <div className="flex flex-col w-full max-w-lg h-[80vh] sm:h-[70vh] bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 text-white">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-lg">💬</span>
            <div className="min-w-0">
              <p className="font-bold text-sm truncate">{documentTitle}</p>
              <p className="text-xs opacity-80">Chat with document</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-white/20 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-md'
                    : 'bg-gray-100 text-gray-800 rounded-bl-md'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm text-gray-500">
                <span className="inline-flex gap-1">
                  <span className="animate-bounce">.</span>
                  <span className="animate-bounce delay-100">.</span>
                  <span className="animate-bounce delay-200">.</span>
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Follow-ups */}
        {followUps.length > 0 && !loading && (
          <div className="px-4 pb-2 flex flex-wrap gap-1.5">
            {followUps.map((q, i) => (
              <button
                key={i}
                onClick={() => sendMessage(q)}
                className="text-xs bg-blue-50 text-blue-700 rounded-full px-3 py-1.5 border border-blue-200 hover:bg-blue-100 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <form onSubmit={handleSubmit} className="border-t border-gray-200 p-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about this document..."
              disabled={loading}
              className="flex-1 rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="rounded-xl bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 px-4 py-2.5 text-white font-semibold text-sm hover:shadow-md disabled:opacity-50 transition-all"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
