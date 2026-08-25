'use client';

import { useState } from 'react'
import { MainSidebar } from './MainSidebar'
import { MainContentPanel } from './MainContentPanel'
import { InteractiveSidebar } from './InteractiveSidebar'
import { ReadOnlyBanner } from '@/components/auth/ReadOnlyMode'
import { ProfileModal } from '@/components/auth/ProfileModal'
import { CollaborationView } from '@/components/chat/CollaborationView'
import { PastQuestionsView } from '@/components/dashboard/PastQuestionsView'
import { VylixDashboard } from '@/components/dashboard/VylixDashboard'
import { useAuth } from '@/context/auth-context'

export interface DocumentInfo {
  id: string
  name: string
  courseId: string
  courseCode: string
}

type MobileView = 'home' | 'courses' | 'content' | 'chat' | 'tools' | 'pastquestions'

export function ThreePanelLayout() {
  const { user, isAuthenticated, promptLogin } = useAuth()
  const [mobileView, setMobileView] = useState<MobileView>('home')
  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(null)
  const [selectedDoc, setSelectedDoc] = useState<DocumentInfo | null>(null)
  const [showMobileSidebar, setShowMobileSidebar] = useState(false)
  const [showTools, setShowTools] = useState(false)
  const [showProfile, setShowProfile] = useState(false)

  const isHome = mobileView === 'home'
  const activeView = mobileView === 'chat' ? 'chat' : mobileView === 'pastquestions' ? 'pastquestions' : 'courses'

  const initials = (user?.fullName || 'U').split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)

  return (
    <div className="flex h-dvh w-full overflow-hidden premium-bg">
      {/* Mobile premium header - hidden on home view (VylixDashboard has its own) */}
      {!isHome && (
      <header className={`fixed left-0 right-0 z-30 header-premium pt-[env(safe-area-inset-top)] md:hidden ${!isAuthenticated ? 'top-[72px]' : 'top-0'}`}>
        <div className="flex items-center justify-between px-3 py-2">
          <div className="flex items-center gap-2.5 min-w-0">
            {selectedCourseId && activeView === 'courses' ? (
              <button
                onClick={() => { setSelectedCourseId(null); setSelectedDoc(null) }}
                className="p-2 rounded-xl hover:bg-gray-100/80 active:bg-gray-200/60 shrink-0 transition-colors"
                aria-label="Back to all courses"
              >
                <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
            ) : (
              <button
                onClick={() => { setShowMobileSidebar(!showMobileSidebar); setMobileView('courses') }}
                className="p-2 rounded-xl hover:bg-gray-100/80 active:bg-gray-200/60 shrink-0 transition-colors"
                aria-label="Toggle course list"
              >
                <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            )}
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-600 to-sky-500 flex items-center justify-center shadow-md shadow-blue-600/20">
                <span className="text-white text-[11px] font-black">V</span>
              </div>
              <span className="text-sm font-bold tracking-tight">
                <span className="text-gradient">Vylix Academic Hub</span>
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {!isAuthenticated && (
              <button
                onClick={() => promptLogin('unlock all features')}
                className="inline-flex items-center gap-1 text-[10px] font-bold px-2.5 py-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-sky-500 text-white shadow-sm shadow-blue-600/20 active:scale-95 transition-all"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                </svg>
                Sign In
              </button>
            )}
            {isAuthenticated && (
              <button
                onClick={() => setShowProfile(true)}
                className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-600 to-sky-500 flex items-center justify-center text-white text-[11px] font-bold shadow-md shadow-blue-600/20 active:scale-95 transition-all"
              >
                {user?.avatarUrl ? (
                  <img src={user.avatarUrl} alt="" className="w-8 h-8 rounded-full object-cover" />
                ) : initials}
              </button>
            )}
          </div>
        </div>
      </header>
      )}

      {/* Read-only banner for unauthenticated users - desktop (hidden on home view) */}
      {!isAuthenticated && !isHome && (
        <div className="hidden md:block fixed top-0 left-[240px] xl:left-[280px] right-0 z-40">
          <div className="px-4 pt-3 pb-1">
            <ReadOnlyBanner action="upload, chat with AI, and save documents offline" />
          </div>
        </div>
      )}

      {/* Read-only banner for unauthenticated users - mobile (hidden on home view) */}
      {!isAuthenticated && !isHome && (
        <div className="md:hidden fixed top-0 left-0 right-0 z-40">
          <div className="px-3 pt-2 pb-1">
            <ReadOnlyBanner action="upload, chat with AI, and save documents offline" />
          </div>
        </div>
      )}

      {/* Mobile course drawer */}
      {showMobileSidebar && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/30 backdrop-blur-sm transition-opacity"
            onClick={() => setShowMobileSidebar(false)}
          />
          <div className="absolute left-0 top-0 bottom-0 w-[85vw] max-w-sm sidebar-premium shadow-2xl drawer-enter flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 pt-[max(0.75rem,env(safe-area-inset-top))] divider-premium">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-sky-500 flex items-center justify-center shadow-md shadow-blue-600/20">
                  <span className="text-white text-xs font-black">V</span>
                </div>
                <span className="text-sm font-bold text-gray-900">Courses</span>
              </div>
              <button
                onClick={() => setShowMobileSidebar(false)}
                className="p-2 rounded-xl hover:bg-gray-100/80 active:bg-gray-200/60 text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Close drawer"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <MainSidebar variant="drawer" selectedCourseId={selectedCourseId} onSelectCourse={(id) => { setSelectedCourseId(id); setShowMobileSidebar(false); setMobileView('content') }} />
            </div>
          </div>
        </div>
      )}

      {/* Desktop sidebar - hidden on home view */}
      {!isHome && (
      <div className="hidden md:flex shrink-0 panel-glow-right flex-col">
        {/* Top bar with user identity and nav */}
        <div className="flex items-center justify-between px-3 py-2.5 divider-premium shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-600 to-sky-500 flex items-center justify-center shadow-md shadow-blue-600/20">
              <span className="text-white text-[11px] font-black">V</span>
            </div>
            <span className="text-xs font-bold tracking-tight text-gray-700">Vylix</span>
          </div>
          {isAuthenticated && (
            <button
              onClick={() => setShowProfile(true)}
              className="flex items-center gap-2 px-2 py-1.5 rounded-xl hover:bg-gray-100/80 active:bg-gray-200/60 transition-colors group"
            >
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-600 to-sky-500 flex items-center justify-center text-white text-[10px] font-bold shadow-sm shadow-blue-600/20 overflow-hidden">
                {user?.avatarUrl ? (
                  <img src={user.avatarUrl} alt="" className="w-7 h-7 rounded-full object-cover" />
                ) : initials}
              </div>
              <span className="text-[11px] font-semibold text-gray-600 group-hover:text-gray-900 transition-colors truncate max-w-[100px]">
                {user?.fullName?.split(' ')[0] || 'Profile'}
              </span>
            </button>
          )}
        </div>

        {/* View switcher */}
        <div className="px-3 pb-2 flex gap-1 shrink-0">
          <button
            onClick={() => setMobileView('home')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-[11px] font-semibold transition-all duration-200 ${
              isHome
                ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white shadow-sm shadow-blue-600/20'
                : 'text-gray-500 hover:bg-gray-100/80 hover:text-gray-700'
            }`}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            Home
          </button>
          <button
            onClick={() => setMobileView('content')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-[11px] font-semibold transition-all duration-200 ${
              activeView === 'courses'
                ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white shadow-sm shadow-blue-600/20'
                : 'text-gray-500 hover:bg-gray-100/80 hover:text-gray-700'
            }`}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            Courses
          </button>
          <button
            onClick={() => { if (!isAuthenticated) { promptLogin('chat with classmates'); return } setMobileView('chat') }}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-[11px] font-semibold transition-all duration-200 ${
              activeView === 'chat'
                ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white shadow-sm shadow-blue-600/20'
                : 'text-gray-500 hover:bg-gray-100/80 hover:text-gray-700'
            }`}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            Chat
          </button>
          <button
            onClick={() => setMobileView('pastquestions')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-[11px] font-semibold transition-all duration-200 ${
              activeView === 'pastquestions'
                ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white shadow-sm shadow-blue-600/20'
                : 'text-gray-500 hover:bg-gray-100/80 hover:text-gray-700'
            }`}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
            Past Qs
          </button>
        </div>

        {/* Sidebar content */}
        {activeView === 'courses' && (
          <MainSidebar selectedCourseId={selectedCourseId} onSelectCourse={setSelectedCourseId} />
        )}
      </div>
      )}

      {/* Main content */}
      <div className={`flex-1 flex flex-col min-w-0 pb-[max(4rem,env(safe-area-inset-bottom)+3.5rem)] md:pb-0 ${isHome ? '' : !isAuthenticated ? 'pt-[max(8rem,env(safe-area-inset-top)+7.5rem)] md:pt-0 md:mt-[68px]' : 'pt-[max(3.25rem,env(safe-area-inset-top)+2.5rem)] md:pt-0'}`}>
        {isHome ? (
          <div className="flex-1 overflow-y-auto">
            <VylixDashboard />
          </div>
        ) : activeView === 'chat' ? (
          <div className="flex-1 overflow-hidden">
            <CollaborationView />
          </div>
        ) : activeView === 'pastquestions' ? (
          <div className="flex-1 overflow-y-auto p-3 sm:p-6">
            <PastQuestionsView />
          </div>
        ) : (
          <MainContentPanel
            selectedCourseId={selectedCourseId}
            selectedDoc={selectedDoc}
            onSelectDoc={setSelectedDoc}
            isReadOnly={!isAuthenticated}
          />
        )}
      </div>

      {/* Interactive sidebar - hidden on home view */}
      {!isHome && (
        <InteractiveSidebar selectedDoc={selectedDoc} isOpen={showTools} onOpenChange={(open) => { setShowTools(open); if (!open && mobileView === 'tools') setMobileView('content') }} isReadOnly={!isAuthenticated} />
      )}

      {/* Profile Modal */}
      <ProfileModal isOpen={showProfile} onClose={() => setShowProfile(false)} />

      {/* Mobile Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 z-30 bottom-nav pb-[env(safe-area-inset-bottom)] md:hidden safe-bottom">
        <div className="flex items-center justify-around px-2 py-1.5">
          <button
            onClick={() => { setShowTools(false); setMobileView('home') }}
            className={`bottom-nav-item flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl relative ${mobileView === 'home' ? 'is-active' : 'text-gray-400'}`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            <span className="text-[10px] font-semibold">Home</span>
            <div className="bottom-nav-dot" />
          </button>

          <button
            onClick={() => { setShowMobileSidebar(true); setMobileView('courses') }}
            className={`bottom-nav-item flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl relative ${mobileView === 'courses' ? 'is-active' : 'text-gray-400'}`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <span className="text-[10px] font-semibold">Courses</span>
            <div className="bottom-nav-dot" />
          </button>

          <button
            onClick={() => setMobileView('content')}
            className={`bottom-nav-item flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl relative ${mobileView === 'content' ? 'is-active' : 'text-gray-400'}`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-[10px] font-semibold">Docs</span>
            <div className="bottom-nav-dot" />
          </button>

          <button
            onClick={() => { if (!isAuthenticated) { promptLogin('chat with classmates'); return } setMobileView('chat'); setShowTools(false) }}
            className={`bottom-nav-item flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl relative ${mobileView === 'chat' ? 'is-active' : 'text-gray-400'}`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <span className="text-[10px] font-semibold">Chat</span>
            <div className="bottom-nav-dot" />
          </button>

          <button
            onClick={() => { setMobileView('tools'); setShowTools(true) }}
            className={`bottom-nav-item flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl relative ${mobileView === 'tools' ? 'is-active' : 'text-gray-400'}`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <span className="text-[10px] font-semibold">AI Tools</span>
            <div className="bottom-nav-dot" />
          </button>

          <button
            onClick={() => { setShowTools(false); setMobileView('pastquestions') }}
            className={`bottom-nav-item flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl relative ${mobileView === 'pastquestions' ? 'is-active' : 'text-gray-400'}`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
            <span className="text-[10px] font-semibold">Past Qs</span>
            <div className="bottom-nav-dot" />
          </button>
        </div>
      </nav>
    </div>
  )
}
