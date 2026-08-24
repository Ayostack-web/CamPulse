'use client';

import { useState, useRef, useEffect, useCallback } from 'react'
import { offlineStore } from '@/lib/offline-store'
import { useAuth } from '@/context/auth-context'
import { PaywallModal } from '@/components/profile/PaywallModal'
import { authFetchRaw } from '@/lib/auth-fetch'

import type { DocumentInfo } from '../ThreePanelLayout'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

interface AIProfessorTabProps {
  selectedDoc: DocumentInfo | null
  isReadOnly?: boolean
}

export function AIProfessorTab({ selectedDoc, isReadOnly = false }: AIProfessorTabProps) {
  const { promptLogin } = useAuth()
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hello! I'm your AI Professor. Select a document from the library or ask me anything about your course.",
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [showLimitModal, setShowLimitModal] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const prevDocRef = useRef<DocumentInfo | null>(selectedDoc)
  const mountedRef = useRef(false)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true
      return
    }

    const prev = prevDocRef.current
    prevDocRef.current = selectedDoc

    if (!selectedDoc) {
      if (prev) {
        setMessages((msgs) => [
          ...msgs,
          {
            id: `ctx-cleared-${Date.now()}`,
            role: 'assistant',
            content: `Document context cleared. Feel free to ask me anything about your courses, or open a new document.`,
          },
        ])
      }
      return
    }

    const announcement: Message = prev
      ? {
          id: `ctx-switch-${Date.now()}`,
          role: 'assistant',
          content: `I see you've opened "${selectedDoc.name}" from ${selectedDoc.courseCode}. I've switched context to this document. What would you like to know?`,
        }
      : {
          id: `ctx-first-${Date.now()}`,
          role: 'assistant',
          content: `I can see "${selectedDoc.name}" from ${selectedDoc.courseCode}. Want me to summarize it or create practice questions?`,
        }

    setMessages((msgs) => [...msgs, announcement])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDoc?.id])

  const callAI = useCallback(async (userMessage: string) => {
    setIsLoading(true)

    const history = messages
      .filter((m) => m.id !== 'welcome')
      .map((m) => ({ role: m.role, content: m.content }))
    history.push({ role: 'user', content: userMessage })

    try {
      if (selectedDoc) {
        const res = await authFetchRaw(`/api/documents/chat`, {
          method: 'POST',
          body: JSON.stringify({
            document_id: selectedDoc.id,
            query: userMessage,
          }),
        })

        if (res.ok) {
          const data = await res.json()

          await offlineStore.saveChatMessage(selectedDoc.courseId, {
            role: 'user',
            content: userMessage,
            documentId: selectedDoc.id,
          })
          await offlineStore.saveChatMessage(selectedDoc.courseId, {
            role: 'assistant',
            content: data.answer,
            documentId: selectedDoc.id,
          })

          return data.answer
        }

        if (res.status === 429) {
          const err = await res.json().catch(() => ({}))
          if (err.detail === 'DAILY_LIMIT_REACHED') {
            if (res.headers.get('X-Quota-Scope') === 'paid-pool') {
              return 'Your pass has run out. Grab an AI Top-Up from your profile to keep going — no need to wait for midnight.'
            }
            setShowLimitModal(true)
            return 'You\'ve reached your daily AI query limit. Upgrade to premium for more.'
          }
          return err.detail || 'You\'re sending messages too quickly. Please wait a moment before trying again.'
        }
      }

      const res = await authFetchRaw(`/api/documents/general-chat`, {
        method: 'POST',
        body: JSON.stringify({ messages: history }),
      })

      if (res.status === 429) {
        const err = await res.json().catch(() => ({}))
        if (err.detail === 'DAILY_LIMIT_REACHED') {
          if (res.headers.get('X-Quota-Scope') === 'paid-pool') {
            return 'Your pass has run out. Grab an AI Top-Up from your profile to keep going — no need to wait for midnight.'
          }
          setShowLimitModal(true)
          return 'You\'ve reached your daily AI query limit. Upgrade to premium for more.'
        }
        return err.detail || 'You\'re sending messages too quickly. Please wait a moment before trying again.'
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        return err.detail || err.error || 'Something went wrong. Please try again.'
      }

      const data = await res.json()
      return data.content
    } catch (error) {
      console.error('[AIProfessor] Request failed:', error)
      const cached = selectedDoc
        ? await offlineStore.getChatHistory(selectedDoc.courseId)
        : []
      if (cached.length > 0) {
        return "I couldn't reach the server, but here are your cached messages. I'll respond properly when you're back online."
      }
      return 'Network error. Check your connection and try again.'
    } finally {
      setIsLoading(false)
    }
  }, [messages, selectedDoc])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return
    const userMsg = input.trim()
    setInput('')
    const userMessage: Message = { id: crypto.randomUUID(), role: 'user', content: userMsg }
    setMessages((prev) => [...prev, userMessage])
    const response = await callAI(userMsg)
    if (response) {
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: response }])
    }
  }

  const handleQuickAction = async (action: string) => {
    if (isLoading) return
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', content: action }])
    const response = await callAI(action)
    if (response) {
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: response }])
    }
  }

  return (
    <>
    <div className="flex flex-col h-full bg-white">
      <div className="p-3 border-b border-gray-100 tool-header-bg">
        <h3 className="text-sm font-semibold text-gray-900 tracking-tight">AI Professor</h3>
        <p className="text-xs text-gray-400">
          {selectedDoc ? `Reading: ${selectedDoc.name}` : 'No document selected'}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {selectedDoc && (
          <div className="flex gap-2 mb-3">
            <button
              onClick={() => isReadOnly ? promptLogin('use AI tutor') : handleQuickAction('Summarize this document')}
              disabled={isLoading}
              className="flex-1 text-xs py-2.5 px-3 min-h-[44px] rounded-lg bg-gradient-to-r from-blue-50 to-blue-100/80 text-blue-700 font-medium hover:from-blue-100 hover:to-blue-200/80 transition-all duration-200 disabled:opacity-50 border border-blue-200/50 shadow-sm"
            >
              Summarize
            </button>
            <button
              onClick={() => isReadOnly ? promptLogin('use AI tutor') : handleQuickAction('Create 3 practice questions from this material')}
              disabled={isLoading}
              className="flex-1 text-xs py-2.5 px-3 min-h-[44px] rounded-lg bg-gradient-to-r from-emerald-50 to-emerald-100/80 text-emerald-700 font-medium hover:from-emerald-100 hover:to-emerald-200/80 transition-all duration-200 disabled:opacity-50 border border-emerald-200/50 shadow-sm"
            >
              Practice Questions
            </button>
          </div>
        )}

        {!selectedDoc && (
          <div className="flex gap-2 mb-3">
            <button
              onClick={() => isReadOnly ? promptLogin('use AI tutor') : handleQuickAction('Explain the concept of probability distributions')}
              disabled={isLoading}
              className="flex-1 text-xs py-2.5 px-3 min-h-[44px] rounded-lg bg-gradient-to-r from-blue-50 to-blue-100/80 text-blue-700 font-medium hover:from-blue-100 hover:to-blue-200/80 transition-all duration-200 disabled:opacity-50 border border-blue-200/50 shadow-sm"
            >
              Explain a concept
            </button>
            <button
              onClick={() => isReadOnly ? promptLogin('use AI tutor') : handleQuickAction('Help me prepare for my exam')}
              disabled={isLoading}
              className="flex-1 text-xs py-2.5 px-3 min-h-[44px] rounded-lg bg-gradient-to-r from-emerald-50 to-emerald-100/80 text-emerald-700 font-medium hover:from-emerald-100 hover:to-emerald-200/80 transition-all duration-200 disabled:opacity-50 border border-emerald-200/50 shadow-sm"
            >
              Exam Prep Tips
            </button>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                msg.role === 'user'
                  ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-br-md shadow-md'
                  : 'bg-gray-100 text-gray-800 rounded-bl-md border border-gray-200/50'
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start animate-fade-in">
            <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="p-3 border-t border-gray-100 bg-white">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !isReadOnly && handleSend()}
            placeholder={isReadOnly ? 'Sign in to chat with AI...' : (selectedDoc ? 'Ask about this document...' : 'Ask anything about your course...')}
            className="flex-1 min-h-[44px] text-sm rounded-xl border-gray-200 bg-gray-50 focus:bg-white focus:border-blue-300 focus:ring-1 focus:ring-blue-300 px-4 py-3 transition-all"
            disabled={isLoading || isReadOnly}
            maxLength={2000}
          />
          <button
            onClick={() => isReadOnly ? promptLogin('use AI tutor') : handleSend()}
            disabled={!input.trim() || isLoading || isReadOnly}
            className="p-3 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 text-white hover:from-blue-600 hover:to-sky-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg"
            aria-label="Send message"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>

      <PaywallModal isOpen={showLimitModal} onClose={() => setShowLimitModal(false)} />
    </>
  )
}
