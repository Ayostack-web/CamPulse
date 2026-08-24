'use client';

import { useState, useCallback, useEffect } from 'react'
import { getSupabaseBrowserClient } from '@/lib/supabase-client'
import { offlineStore } from '@/lib/offline-store'
import { cacheMaterialPdf, openMaterialPdf, removeCachedPdf } from '@/lib/pdf-cache'
import { fetchApi, parseApiError } from '@/lib/api-request'
import { getAuthHeaders } from '@/lib/auth-fetch'

import type { DocumentInfo } from './ThreePanelLayout'
import { PdfViewerInline } from './PdfViewerInline'
import { DriveSyncBanner } from './DriveSyncBanner'
import { DriveFilePickerModal } from './DriveFilePickerModal'
import { InviteModal } from './InviteModal'
import { useDrive } from '@/context/drive-context'
import { useAuth } from '@/context/auth-context'

interface Course {
  id: string
  code: string
  title: string
  level: number
}

interface Material {
  id: string
  file_name: string
  file_url: string
  file_size: number
  topic_id: string
  uploader_id: string
  uploader_name: string | null
  uploader_avatar: string | null
  processing_status: string
  is_shared: boolean
  is_seed: boolean
  uploaded_at: string | null
  last_opened_at?: string | null
}

interface MainContentPanelProps {
  selectedCourseId: string | null
  selectedDoc: DocumentInfo | null
  onSelectDoc: (doc: DocumentInfo | null) => void
  isReadOnly?: boolean
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const SEED_MATERIALS: Material[] = [
  { id: 'seed-1', file_name: 'Calculus Study Guide.pdf', file_url: '/seed/calculus-study-guide.pdf', file_size: 11817, topic_id: '', uploader_id: '', uploader_name: 'Vylix Team', uploader_avatar: null, processing_status: 'COMPLETED', is_shared: true, is_seed: true, uploaded_at: null },
  { id: 'seed-2', file_name: 'Physics Formula Sheet.pdf', file_url: '/seed/physics-formula-sheet.pdf', file_size: 8486, topic_id: '', uploader_id: '', uploader_name: 'Vylix Team', uploader_avatar: null, processing_status: 'COMPLETED', is_shared: true, is_seed: true, uploaded_at: null },
  { id: 'seed-3', file_name: 'Introduction to Programming.pdf', file_url: '/seed/introduction-to-programming.pdf', file_size: 11788, topic_id: '', uploader_id: '', uploader_name: 'Vylix Team', uploader_avatar: null, processing_status: 'COMPLETED', is_shared: true, is_seed: true, uploaded_at: null },
  { id: 'seed-4', file_name: 'Organic Chemistry Notes.pdf', file_url: '/seed/organic-chemistry-notes.pdf', file_size: 9036, topic_id: '', uploader_id: '', uploader_name: 'Vylix Team', uploader_avatar: null, processing_status: 'COMPLETED', is_shared: true, is_seed: true, uploaded_at: null },
  { id: 'seed-5', file_name: 'Linear Algebra Basics.pdf', file_url: '/seed/linear-algebra-basics.pdf', file_size: 12884, topic_id: '', uploader_id: '', uploader_name: 'Vylix Team', uploader_avatar: null, processing_status: 'COMPLETED', is_shared: true, is_seed: true, uploaded_at: null },
]

const openedThisSession = new Set<string>()

function trackMaterialOpen(materialId: string): void {
  if (openedThisSession.has(materialId)) return
  openedThisSession.add(materialId)
  getAuthHeaders()
    .then((headers) => fetchApi(`/api/materials/${materialId}/open`, { method: 'POST', headers }))
    .catch(() => {})
}

export function MainContentPanel({ selectedCourseId, selectedDoc, onSelectDoc, isReadOnly = false }: MainContentPanelProps) {
  const { connectDrive, driveConnected, driveError, clearError } = useDrive()
  const { promptLogin } = useAuth()
  const [documents, setDocuments] = useState<Material[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [viewerUrl, setViewerUrl] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [offlineStatus] = useState<'online' | 'offline'>(
    typeof navigator !== 'undefined' && navigator.onLine ? 'online' : 'offline'
  )
  const [userId, setUserId] = useState<string | null>(null)
  const [showDrivePicker, setShowDrivePicker] = useState(false)
  const [showInvite, setShowInvite] = useState(false)

  const course = courses.find((c) => c.id === selectedCourseId) || null

  const fetchMaterials = useCallback(async () => {
    try {
      setLoading(true)
      const supabase = getSupabaseBrowserClient()
      const { data: { session } } = await supabase.auth.getSession()

      if (!session?.access_token) {
        setDocuments(SEED_MATERIALS)
        return
      }

      const url = selectedCourseId
        ? `/api/materials/course/${selectedCourseId}`
        : `/api/materials/recent`
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setDocuments(data)
      } else {
        setDocuments(SEED_MATERIALS)
      }
    } catch (error) {
      console.error('[MainContentPanel] Failed to load materials:', error)
      setDocuments(SEED_MATERIALS)
    } finally {
      setLoading(false)
    }
  }, [selectedCourseId])

  const fetchCourses = useCallback(async () => {
    try {
      const supabase = getSupabaseBrowserClient()
      const { data: { session } } = await supabase.auth.getSession()
      if (!session?.access_token) return
      const res = await fetch(`/api/courses/my`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setCourses(data)
      }
    } catch (error) {
      console.error('[MainContentPanel] Failed to load courses:', error)
    }
  }, [])

  useEffect(() => {
    fetchCourses()
  }, [fetchCourses])

  useEffect(() => {
    fetchMaterials()
  }, [fetchMaterials])

  useEffect(() => {
    const getUid = async () => {
      const supabase = getSupabaseBrowserClient()
      const { data: { session } } = await supabase.auth.getSession()
      if (session?.user?.id) setUserId(session.user.id)
    }
    getUid()
  }, [])

  const handleToggleShare = useCallback(async (doc: Material) => {
    try {
      const supabase = getSupabaseBrowserClient()
      const { data: { session } } = await supabase.auth.getSession()
      if (!session?.access_token) return
      const res = await fetch(`/api/materials/${doc.id}/share`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ is_shared: !doc.is_shared }),
      })
      if (res.ok) {
        setDocuments((prev) => prev.map((d) => d.id === doc.id ? { ...d, is_shared: !d.is_shared } : d))
      }
    } catch (error) {
      console.error('[MainContentPanel] Failed to toggle share:', error)
    }
  }, [])

  const handleSelectDoc = useCallback((doc: Material) => {
    onSelectDoc({
      id: doc.id,
      name: doc.file_name,
      courseId: selectedCourseId || '',
      courseCode: course?.code || '',
    })
  }, [onSelectDoc, selectedCourseId, course])

  const handleSaveOffline = useCallback(async () => {
    if (!selectedDoc) return
    setSaving(true)
    try {
      await offlineStore.cacheDocument(selectedDoc.id, { name: selectedDoc.name, courseId: selectedDoc.courseId, courseCode: selectedDoc.courseCode, savedAt: Date.now() })
      try {
        const doc = documents.find((d) => d.id === selectedDoc.id)
        const directUrl = doc?.is_seed || selectedDoc.id.startsWith('seed-') ? doc?.file_url : undefined
        await cacheMaterialPdf(selectedDoc.id, { directUrl })
      } catch (error) {
        console.error('[MainContentPanel] Failed to cache PDF bytes:', error)
        setActionError('Saved details, but the file could not be downloaded for offline reading.')
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (error) {
      console.error('[MainContentPanel] Failed to save offline:', error)
    }
    setSaving(false)
  }, [selectedDoc, documents])

  const handleViewPdf = useCallback(async (materialId: string) => {
    if (materialId.startsWith('seed-')) {
      const seed = documents.find((d) => d.id === materialId)
      if (seed) setViewerUrl(seed.file_url)
      return
    }
    try {
      const url = await openMaterialPdf(materialId)
      setViewerUrl(url)
      trackMaterialOpen(materialId)
    } catch (error) {
      console.error('[MainContentPanel] Failed to load PDF:', error)
      setActionError('Failed to load PDF. Check your connection or save it for offline first.')
    }
  }, [documents])

  const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setActionError(null)
    try {
      const supabase = getSupabaseBrowserClient()
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setActionError('Sign in to upload documents.')
        return
      }

      const formData = new FormData()
      formData.append('file', file)
      formData.append('title', file.name)
      formData.append('course_code', course?.code || '')

      const res = await fetchApi('/api/materials/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: formData,
        direct: true,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        setActionError(parseApiError(err, `Upload failed. Please try again. (HTTP ${res.status})`))
        return
      }
      await fetchMaterials()
    } catch (error) {
      console.error('[MainContentPanel] Upload failed:', error)
      setActionError(error instanceof Error ? error.message : 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }, [fetchMaterials, course])

  const handleDeleteDoc = useCallback(async (doc: Material) => {
    if (!window.confirm(`Are you sure you want to delete "${doc.file_name}"?`)) return
    setActionError(null)
    try {
      const supabase = getSupabaseBrowserClient()
      const { data: { session } } = await supabase.auth.getSession()
      if (!session?.access_token) {
        setActionError('Sign in to delete documents.')
        return
      }
      const res = await fetch(`/api/materials/${doc.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${session.access_token}` },
      })
      if (!res.ok) {
        const err = await res.json().catch(() => null)
        const detail = err?.detail
        setActionError(typeof detail === 'string' ? detail : 'Failed to delete document.')
        return
      }
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id))
      void removeCachedPdf(doc.id).catch(() => {})
    } catch (error) {
      console.error('[MainContentPanel] Failed to delete document:', error)
      setActionError('Failed to delete document.')
    }
  }, [])

  return (
    <main className="flex-1 flex flex-col min-w-0 h-full">
      {/* Premium header */}
      <header className="header-premium flex items-center justify-between gap-2 px-3 sm:px-5 py-2.5 sm:py-3 shrink-0">
        <div className="min-w-0 flex-1 flex items-center gap-2">
          {selectedDoc && (
            <button
              onClick={() => onSelectDoc(null)}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors shrink-0"
              aria-label="Back to documents"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          )}
          <h1 className="text-xs sm:text-base font-bold text-gray-900 truncate tracking-tight">
            {selectedDoc ? selectedDoc.name : (course ? `${course.code} — ${course.title}` : 'All Documents')}
          </h1>
          <div className="flex items-center gap-2 text-[10px] sm:text-xs text-gray-400 mt-0.5">
            <span className="font-medium truncate">{selectedDoc ? course?.code : `${documents.length} documents`}</span>
            <span className="w-1 h-1 rounded-full bg-gray-300 shrink-0" />
            <span className={`inline-flex items-center gap-1.5 px-1.5 sm:px-2 py-0.5 rounded-full text-[9px] sm:text-[10px] font-semibold shrink-0 ${
              offlineStatus === 'online'
                ? 'bg-emerald-50 text-emerald-600 ring-1 ring-emerald-200/60'
                : 'bg-amber-50 text-amber-600 ring-1 ring-amber-200/60'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full status-dot ${offlineStatus === 'online' ? 'bg-emerald-500' : 'bg-amber-500'}`} style={{ background: offlineStatus === 'online' ? '#10b981' : '#f59e0b' }} />
              {offlineStatus}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          {selectedDoc && (
            <button
              onClick={() => isReadOnly ? promptLogin('save documents offline') : handleSaveOffline()}
              disabled={saving || saved}
              className={`hidden sm:inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded-xl border font-semibold transition-all duration-200 ${
                isReadOnly
                  ? 'bg-gray-50/60 border-gray-200/60 text-gray-400 cursor-not-allowed hover:bg-amber-50/60 hover:border-amber-200/60 hover:text-amber-600'
                  : 'bg-gray-50/80 border-gray-200/80 text-gray-700 hover:bg-white hover:border-gray-300 hover:shadow-sm disabled:opacity-50'
              }`}
            >
              {isReadOnly ? (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                  Save Offline
                </>
              ) : saved ? (
                <>
                  <svg className="w-3.5 h-3.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                  Saved
                </>
              ) : saving ? (
                <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                  </svg>
                  Save Offline
                </>
              )}
            </button>
          )}
          <label className={`inline-flex items-center gap-1.5 text-[11px] sm:text-xs px-2.5 sm:px-3 py-2 rounded-xl border font-semibold transition-all duration-200 ${
            isReadOnly
              ? 'bg-gray-50/60 border-gray-200/60 text-gray-400 cursor-not-allowed hover:bg-amber-50/60 hover:border-amber-200/60 hover:text-amber-600'
              : 'bg-gray-50/80 border-gray-200/80 text-gray-700 hover:bg-white hover:border-gray-300 hover:shadow-sm cursor-pointer'
          } ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
            {isReadOnly ? (
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            ) : uploading ? (
              <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
            )}
            <span className="hidden xs:inline">{uploading ? 'Uploading...' : 'Upload'}</span>
            <span className="xs:hidden">{uploading ? '...' : '+'}</span>
            <input type="file" accept=".pdf" className="hidden" onChange={handleUpload} />
          </label>
          <button
            onClick={() => {
              if (isReadOnly) {
                promptLogin('connect Google Drive')
              } else if (driveConnected) {
                setShowDrivePicker(true)
              } else {
                connectDrive()
              }
            }}
            className={`inline-flex items-center gap-1.5 text-[11px] sm:text-xs px-2 sm:px-3 py-2 rounded-xl font-semibold min-h-[36px] sm:min-h-[38px] transition-all duration-200 ${
              isReadOnly
                ? 'bg-gray-50/60 border border-gray-200/60 text-gray-400 cursor-not-allowed hover:bg-amber-50/60 hover:border-amber-200/60 hover:text-amber-600'
                : driveConnected
                  ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200/60 hover:bg-emerald-100 btn-glow hover:shadow-lg'
                  : 'bg-gradient-to-r from-blue-600 to-sky-500 text-white hover:shadow-lg btn-glow'
            }`}
          >
            {isReadOnly ? (
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            ) : driveConnected ? (
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M7.71 3.5L1.15 15l3.43 6h13.72l3.42-6L15.29 3.5H7.71zm4.58 2.28l4.14 7.22H4.71l4.14-7.22h3.44z" opacity="0.9" />
              </svg>
            )}
            <span className="hidden sm:inline">{driveConnected ? 'Import from Drive' : 'Google Drive'}</span>
            <span className="sm:hidden">{driveConnected ? '↓' : 'Drive'}</span>
          </button>
          <button
            onClick={() => {
              if (isReadOnly) {
                promptLogin('invite friends')
              } else {
                setShowInvite(true)
              }
            }}
            className="inline-flex items-center gap-1.5 text-[11px] sm:text-xs px-2 sm:px-3 py-2 rounded-xl font-semibold min-h-[36px] sm:min-h-[38px] transition-all duration-200 bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:shadow-lg hover:scale-[1.01] active:scale-[0.99] btn-glow"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            <span className="hidden sm:inline">Invite</span>
            <span className="sm:hidden">Invite</span>
          </button>
        </div>
      </header>

      {/* Drive connection error */}
      {driveError && (
        <div className="mx-3 sm:mx-5 mt-2 flex items-center gap-2 px-3 py-2 rounded-xl bg-red-50 border border-red-200/60 text-xs text-red-700 font-medium">
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <span className="flex-1">{driveError}</span>
          <button onClick={clearError} className="text-red-400 hover:text-red-600 transition-colors">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Upload/delete error */}
      {actionError && (
        <div className="mx-3 sm:mx-5 mt-2 flex items-center gap-2 px-3 py-2 rounded-xl bg-red-50 border border-red-200/60 text-xs text-red-700 font-medium">
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <span className="flex-1">{actionError}</span>
          <button onClick={() => setActionError(null)} className="text-red-400 hover:text-red-600 transition-colors">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-5">
        {viewerUrl ? (
          <PdfViewerInline fileUrl={viewerUrl} onClose={() => { setViewerUrl(null) }} />
        ) : selectedDoc ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4 premium-fade-in">
            <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-blue-50 to-sky-50 flex items-center justify-center mb-4 ring-1 ring-blue-100/50">
              <svg className="w-10 h-10 text-blue-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-sm font-bold text-gray-700 mb-1">Ready to read</h3>
            <p className="text-xs text-gray-400 max-w-xs">Click <strong className="text-blue-500">View</strong> on a document to start reading, or chat with AI about it.</p>
          </div>
        ) : (
          <div>
            {/* Drive sync banner for new users */}
            {!selectedCourseId && <DriveSyncBanner />}

            {/* Section header */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base sm:text-lg font-bold text-gray-900 tracking-tight">
                  {course ? `${course.code} Materials` : 'Recent Documents'}
                </h2>
                <p className="text-xs text-gray-400 mt-0.5 font-medium">
                  {course ? course.title : 'Materials shared by students in your department'}
                </p>
              </div>
            </div>

            {/* Document grid */}
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <div className="flex items-center gap-3 text-gray-400">
                  <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <span className="text-sm font-medium">Loading documents...</span>
                </div>
              </div>
            ) : documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 sm:py-20 text-center px-4 premium-fade-in">
                <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-blue-50 to-sky-50 flex items-center justify-center mb-5 ring-1 ring-blue-100/50">
                  <svg className="w-10 h-10 text-blue-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                </div>
                <h3 className="text-base font-bold text-gray-800 mb-1.5">                  No materials in this course yet</h3>
                <p className="text-sm text-gray-400 max-w-sm mb-6 leading-relaxed">
                  {driveConnected
                    ? 'No materials imported yet. Import from Google Drive or upload PDFs to get started — they\'ll be shared with your classmates automatically.'
                    : 'Connect your Google Drive to import your course materials, or upload PDFs directly. Everything you import is shared with students in your department.'}
                </p>
                <div className="flex flex-col sm:flex-row items-center gap-3">
                  {driveConnected ? (
                    <button
                      onClick={() => setShowDrivePicker(true)}
                      className="inline-flex items-center gap-2 text-sm px-5 py-2.5 rounded-xl font-bold transition-all duration-200 bg-gradient-to-r from-blue-600 to-sky-500 text-white btn-glow hover:shadow-lg hover:shadow-blue-600/25 hover:scale-[1.02] active:scale-[0.98]"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M7.71 3.5L1.15 15l3.43 6h13.72l3.42-6L15.29 3.5H7.71zm4.58 2.28l4.14 7.22H4.71l4.14-7.22h3.44z" opacity="0.9" />
                      </svg>
                      Import from Drive
                    </button>
                  ) : (
                    <button
                      onClick={() => isReadOnly ? promptLogin('connect Google Drive') : connectDrive()}
                      className={`inline-flex items-center gap-2 text-sm px-5 py-2.5 rounded-xl font-bold transition-all duration-200 ${
                        isReadOnly
                          ? 'bg-gray-100 text-gray-400 cursor-not-allowed hover:bg-amber-50 hover:text-amber-600 hover:shadow-sm'
                          : 'bg-gradient-to-r from-blue-600 to-sky-500 text-white btn-glow hover:shadow-lg hover:shadow-blue-600/25 hover:scale-[1.02] active:scale-[0.98]'
                      }`}
                    >
                      {isReadOnly ? (
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                      ) : (
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M7.71 3.5L1.15 15l3.43 6h13.72l3.42-6L15.29 3.5H7.71zm4.58 2.28l4.14 7.22H4.71l4.14-7.22h3.44z" opacity="0.9" />
                        </svg>
                      )}
                      {isReadOnly ? 'Sign in to Connect Drive' : 'Connect Google Drive'}
                    </button>
                  )}
                  <label className={`inline-flex items-center gap-2 text-sm px-5 py-2.5 rounded-xl font-bold transition-all duration-200 ${
                    isReadOnly
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed hover:bg-amber-50 hover:text-amber-600 hover:shadow-sm'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 hover:shadow-sm cursor-pointer'
                  }`}>
                    {isReadOnly ? (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                      </svg>
                    )}
                    {isReadOnly ? 'Sign in to Upload' : 'Upload PDF'}
                    {!isReadOnly && <input type="file" accept=".pdf" className="hidden" onChange={handleUpload} />}
                  </label>
                </div>
              </div>
            ) : (
              <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 premium-stagger">
                {documents.map((doc) => (
                  <div key={doc.id} className="doc-card group">
                    <div className="p-3.5 sm:p-4">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-12 rounded-xl bg-gradient-to-br from-red-400 to-orange-400 flex items-center justify-center text-white text-[10px] font-bold shrink-0 shadow-sm shadow-red-400/20 group-hover:shadow-md group-hover:shadow-red-400/30 transition-shadow duration-300">
                          PDF
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-xs sm:text-sm font-semibold text-gray-900 truncate group-hover:text-blue-700 transition-colors">{doc.file_name}</h3>
                          <div className="flex items-center gap-1.5 text-[10px] sm:text-xs text-gray-400 mt-1">
                            <span className="font-medium">{formatFileSize(doc.file_size)}</span>
                            <span className="w-0.5 h-0.5 rounded-full bg-gray-300" />
                            <span>{formatDate(doc.uploaded_at)}</span>
                            {doc.is_seed && (
                              <>
                                <span className="w-0.5 h-0.5 rounded-full bg-gray-300" />
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-semibold bg-blue-50 text-blue-600">
                                  Demo
                                </span>
                              </>
                            )}
                            {doc.uploader_name && (
                              <>
                                <span className="w-0.5 h-0.5 rounded-full bg-gray-300" />
                                <span className="flex items-center gap-1 text-gray-500">
                                  {doc.uploader_avatar ? (
                                    <img src={doc.uploader_avatar} alt="" className="w-3.5 h-3.5 rounded-full object-cover" />
                                  ) : (
                                    <span className="w-3.5 h-3.5 rounded-full bg-gradient-to-br from-blue-500 to-sky-500 flex items-center justify-center text-white text-[8px] font-bold">
                                      {doc.uploader_name.charAt(0).toUpperCase()}
                                    </span>
                                  )}
                                  {doc.uploader_name.split(' ')[0]}
                                </span>
                              </>
                            )}
                            {doc.uploader_id === userId && (
                              <button
                                onClick={(e) => { e.stopPropagation(); handleToggleShare(doc) }}
                                className={`ml-auto inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium transition-all ${
                                  doc.is_shared
                                    ? 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'
                                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                                }`}
                                title={doc.is_shared ? 'Shared with classmates — click to make private' : 'Private — click to share with classmates'}
                              >
                                {doc.is_shared ? (
                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                                  </svg>
                                ) : (
                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                                  </svg>
                                )}
                                {doc.is_shared ? 'Shared' : 'Private'}
                              </button>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Action buttons */}
                      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100/80">
                        <button
                          onClick={() => { handleSelectDoc(doc); handleViewPdf(doc.id) }}
                          className="flex-1 flex items-center justify-center gap-1.5 text-[10px] sm:text-xs font-semibold text-blue-600 hover:text-white px-3 py-2 rounded-lg hover:bg-blue-500 transition-all duration-200"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                          View
                        </button>
                        <button
                          onClick={() => handleSelectDoc(doc)}
                          className="flex-1 flex items-center justify-center gap-1.5 text-[10px] sm:text-xs font-semibold text-emerald-600 hover:text-white px-3 py-2 rounded-lg hover:bg-emerald-500 transition-all duration-200"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                          </svg>
                          Chat
                        </button>
                        {doc.uploader_id === userId && (
                          <button
                            onClick={() => handleDeleteDoc(doc)}
                            className="flex-1 flex items-center justify-center gap-1.5 text-[10px] sm:text-xs font-semibold text-red-500 hover:text-white px-3 py-2 rounded-lg hover:bg-red-500 transition-all duration-200"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            Delete
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {/* Upload placeholder card */}
                <label className={`doc-card group border-dashed !border-gray-200 hover:!border-blue-300 ${isReadOnly ? 'pointer-events-none' : 'cursor-pointer'}`}>
                  <div className="p-3.5 sm:p-4 flex flex-col items-center justify-center min-h-[140px]">
                    <div className={`w-10 h-10 rounded-2xl flex items-center justify-center mb-2 transition-colors duration-200 ${isReadOnly ? 'bg-amber-50' : 'bg-gray-50 group-hover:bg-blue-50'}`}>
                      {isReadOnly ? (
                        <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5 text-gray-300 group-hover:text-sky-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                        </svg>
                      )}
                    </div>
                    <p className={`text-[11px] font-semibold transition-colors ${isReadOnly ? 'text-amber-400' : 'text-gray-400 group-hover:text-blue-500'}`}>
                      {isReadOnly ? 'Sign in to Upload' : 'Upload PDF'}
                    </p>
                    {!isReadOnly && <input type="file" accept=".pdf" className="hidden" onChange={handleUpload} />}
                  </div>
                </label>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Drive File Picker Modal */}
      <DriveFilePickerModal
        isOpen={showDrivePicker}
        onClose={() => setShowDrivePicker(false)}
        onSuccess={() => {
          setShowDrivePicker(false)
          fetchMaterials()
        }}
      />

      {/* Invite Friends Modal */}
      <InviteModal
        isOpen={showInvite}
        onClose={() => setShowInvite(false)}
      />
    </main>
  )
}
