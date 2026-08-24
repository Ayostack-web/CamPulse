'use client';

import { useCallback, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { getSupabaseBrowserClient } from '@/lib/supabase-client';
import { openMaterialPdf, removeCachedPdf } from '@/lib/pdf-cache';
import { useAuth } from '@/context/auth-context';
import { UploadMaterialModal } from '@/components/dashboard/UploadMaterialModal';

interface PastQuestion {
  id: string;
  fileName: string;
  fileUrl: string;
  fileSize: number;
  examYear: number | null;
  semester: string | null;
  processingStatus: string;
  summary: string | null;
  uploadedAt: string;
  uploader_id: string;
  uploader_name: string | null;
  uploader_avatar: string | null;
  topic: {
    id: string;
    title: string;
    course: { id: string; code: string; title: string } | null;
  } | null;
}

interface PastQuestionPage {
  items: PastQuestion[];
  total: number;
}

const LIMIT = 20;

async function fetchPastQuestions(params: {
  page: number;
  searchCourse: string;
  searchYear: string;
  searchSemester: string;
}): Promise<PastQuestionPage> {
  const q = new URLSearchParams();
  q.set('page', params.page.toString());
  q.set('limit', LIMIT.toString());
  if (params.searchCourse) q.set('courseCode', params.searchCourse.toUpperCase());
  if (params.searchYear) q.set('year', params.searchYear);
  if (params.searchSemester) q.set('semester', params.searchSemester);

  const headers: Record<string, string> = {};
  const supabase = getSupabaseBrowserClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }

  const res = await fetch(`/api/materials/past-questions?${q.toString()}`, { headers });
  if (!res.ok) throw new Error('Failed to fetch past questions');
  return res.json();
}

export function PastQuestionsView() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchCourse, setSearchCourse] = useState('');
  const [searchYear, setSearchYear] = useState('');
  const [searchSemester, setSearchSemester] = useState('');
  const [viewerUrl, setViewerUrl] = useState<string | null>(null);
  const [viewerTitle, setViewerTitle] = useState('');
  const [showUploadModal, setShowUploadModal] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ['past-questions', page, searchCourse, searchYear, searchSemester],
    queryFn: () => fetchPastQuestions({ page, searchCourse, searchYear, searchSemester }),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / LIMIT));

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      if (!window.confirm('Are you sure you want to delete this past question?')) return null;

      const supabase = getSupabaseBrowserClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error('No session');

      const res = await fetch(`/api/materials/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || 'Failed to delete material');
      }
      return id;
    },
    onSuccess: (id) => {
      if (id === null) return;
      queryClient.invalidateQueries({ queryKey: ['past-questions'] });
      queryClient.invalidateQueries({ queryKey: ['vault-materials'] });
      void removeCachedPdf(id).catch(() => {});
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Failed to delete material');
    },
  });

  const openFile = useCallback(async (id: string, title: string) => {
    try {
      const url = await openMaterialPdf(id);
      setViewerUrl(url);
      setViewerTitle(title);
    } catch { toast.error('Failed to open file'); }
  }, []);

  return (
    <section className="space-y-5 sm:space-y-8">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 p-[1px] shadow-sm">
            <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 font-bold text-[11px] uppercase tracking-wider text-gray-900">
              Exam prep
            </span>
          </div>
          <h2 className="text-[clamp(1.5rem,3vw,2.2rem)] leading-[1.2] tracking-[-0.03em] font-black bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 bg-clip-text text-transparent mb-3">
            Past Questions
          </h2>
          <p className="cp-body max-w-2xl sm:text-base">
            Browse past exam questions by course, year, and semester.
          </p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 px-4 py-2 text-sm font-bold text-white shadow-md hover:shadow-lg transition-all"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Upload Past Question
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Course code (e.g. CSC311)"
          value={searchCourse}
          onChange={(e) => { setSearchCourse(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm flex-1 min-w-[160px]"
        />
        <select
          value={searchYear}
          onChange={(e) => { setSearchYear(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="">All years</option>
          {Array.from({ length: 10 }, (_, i) => new Date().getFullYear() - i).map((year) => (
            <option key={year} value={year}>{year}</option>
          ))}
        </select>
        <select
          value={searchSemester}
          onChange={(e) => { setSearchSemester(e.target.value); setPage(1); }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="">All semesters</option>
          <option value="FIRST">First Semester</option>
          <option value="SECOND">Second Semester</option>
        </select>
      </div>

      {/* Content */}
      <div className="rounded-[1.75rem] border border-sky-100 bg-white p-5 shadow-sm">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-200 border-t-blue-600" />
          </div>
        ) : error ? (
          <div className="rounded-lg bg-red-50 p-4 text-sm text-red-800">
            {error instanceof Error ? error.message : 'Failed to load past questions'}
          </div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center">
            <span className="text-4xl">📝</span>
            <p className="mt-4 text-gray-600 font-semibold">No past questions found</p>
            <p className="text-sm text-gray-500 mt-1">Try adjusting your filters or upload one!</p>
          </div>
        ) : (
          <div className="grid gap-3">
            {items.map((item) => {
              const isDeleting = deleteMutation.isPending && deleteMutation.variables === item.id;
              return (
                <div
                  key={item.id}
                  className="flex flex-col gap-2 rounded-[1.25rem] border border-sky-100 bg-blue-50 p-4 transition-all hover:-translate-y-0.5 hover:border-sky-200 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="cp-card-title text-gray-900 truncate">{item.fileName}</p>
                      {item.examYear && (
                        <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-800">
                          {item.examYear}
                        </span>
                      )}
                      {item.semester && (
                        <span className="inline-flex items-center rounded-full bg-sky-100 px-2.5 py-0.5 text-xs font-semibold text-sky-800">
                          {item.semester === 'FIRST' ? '1st Sem' : '2nd Sem'}
                        </span>
                      )}
                    </div>
                    {item.topic?.course && (
                      <p className="text-xs text-gray-500 mt-1">
                        {item.topic.course.code} — {item.topic.course.title}
                      </p>
                    )}
                    {item.summary && (
                      <p className="text-xs text-gray-600 mt-1 line-clamp-2">{item.summary}</p>
                    )}
                    <p className="text-xs text-gray-400 mt-1">
                      {(item.fileSize / 1024 / 1024).toFixed(1)} MB • Uploaded by {item.uploader_name}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => openFile(item.id, item.fileName)}
                      className="inline-flex items-center gap-1 rounded-lg bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 px-4 py-2 text-xs font-bold text-white hover:shadow-md transition-shadow"
                    >
                      📖 View
                    </button>
                    {user?.id === item.uploader_id && (
                      <button
                        onClick={() => deleteMutation.mutate(item.id)}
                        disabled={isDeleting}
                        className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs font-bold text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
                      >
                        {isDeleting ? '...' : '🗑 Delete'}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-sm text-gray-600">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {viewerUrl && (
        <div className="fixed inset-0 z-[60] flex flex-col bg-black/90 backdrop-blur-sm">
          <div className="flex items-center justify-between gap-2 bg-black/80 px-3 py-2 sm:px-4 sm:py-3">
            <p className="min-w-0 truncate text-xs font-semibold text-white sm:text-sm">{viewerTitle}</p>
            <button
              onClick={() => { setViewerUrl(null); setViewerTitle(''); }}
              className="shrink-0 rounded-full bg-white/10 px-3 py-1 text-xs font-bold text-white hover:bg-white/20 transition-colors sm:px-4 sm:py-1.5 sm:text-sm"
            >
              Close
            </button>
          </div>
          <embed src={viewerUrl} type="application/pdf" className="flex-1 w-full" />
        </div>
      )}

      <UploadMaterialModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onSuccess={() => setShowUploadModal(false)}
        defaultIsPastQuestion
      />
    </section>
  );
}
