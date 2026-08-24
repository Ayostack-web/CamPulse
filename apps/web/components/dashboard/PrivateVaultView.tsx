'use client';

import { useCallback, useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { getSupabaseBrowserClient } from '@/lib/supabase-client';
import { openMaterialPdf, removeCachedPdf } from '@/lib/pdf-cache';
import { useBackupEmailPrompt } from '@/hooks/useBackupEmailPrompt';
import { BackupEmailModal } from '@/components/auth/BackupEmailModal';
import { ProfileBackupBanner } from '@/components/profile/ProfileBackupBanner';
import { ChatPanel } from '@/components/chat/ChatPanel';

interface VaultMaterial {
  id: string;
  fileName: string;
  fileUrl: string;
  fileSize: number;
  processingStatus: string;
  uploadedAt: string;
  topic: { title: string } | null;
}

async function fetchVaultMaterials(): Promise<VaultMaterial[]> {
  const headers: Record<string, string> = {};
  const supabase = getSupabaseBrowserClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }

  const res = await fetch(`/api/materials/my-materials?limit=50`, { headers });
  if (!res.ok) throw new Error('Failed to fetch vault materials');
  const json = await res.json();
  return json.items ?? [];
}

export function PrivateVaultView() {
  const queryClient = useQueryClient();
  const [chatDocument, setChatDocument] = useState<{ id: string; title: string } | null>(null);
  const [viewerUrl, setViewerUrl] = useState<string | null>(null);
  const [viewerTitle, setViewerTitle] = useState('');
  const {
    showModal,
    checkAfterSave,
    closeModal,
    handleDismissed,
    handleSuccess,
  } = useBackupEmailPrompt();

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['vault-materials'],
    queryFn: fetchVaultMaterials,
  });

  useEffect(() => {
    checkAfterSave();
  }, [checkAfterSave]);

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      if (!window.confirm('Are you sure you want to delete this material?')) return null;

      const supabase = getSupabaseBrowserClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error('No session');

      const res = await fetch(`/api/materials/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (!res.ok) throw new Error('Failed to delete');
      return id;
    },
    onSuccess: (id) => {
      if (id === null) return;
      queryClient.invalidateQueries({ queryKey: ['vault-materials'] });
      queryClient.invalidateQueries({ queryKey: ['past-questions'] });
      void removeCachedPdf(id).catch(() => {});
    },
    onError: () => toast.error('Failed to delete material'),
  });

  const openFile = useCallback(async (id: string, title: string) => {
    try {
      const url = await openMaterialPdf(id);
      setViewerUrl(url);
      setViewerTitle(title);
    } catch { toast.error('Failed to open file'); }
  }, []);

  const totalSize = items.reduce((acc, i) => acc + (i.fileSize || 0), 0);
  const sizeMb = totalSize > 0 ? `${(totalSize / (1024 * 1024)).toFixed(1)} MB` : '0 MB';
  const stats = [
    { label: 'Saved PDFs', value: String(items.length) },
    { label: 'Space Used', value: sizeMb },
  ];

  return (
    <>
      <ProfileBackupBanner />
      <section className="space-y-5 rounded-[1.75rem] border border-sky-100 bg-blue-50 p-4 shadow-[0_16px_40px_rgba(59,130,246,0.08)] sm:space-y-8 sm:p-8">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 p-[1px] shadow-sm">
              <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 font-bold text-[11px] uppercase tracking-wider text-gray-900">
                Secure workspace
              </span>
            </div>
            <h2 className="text-[clamp(1.5rem,3vw,2.2rem)] leading-[1.2] tracking-[-0.03em] font-black bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 bg-clip-text text-transparent mb-3">
              Private Vault
            </h2>
            <p className="cp-body max-w-2xl sm:text-base">
              Your personal library for zero-interruption study sessions.
              Materials ready when campus network drops.
            </p>
          </div>

        </div>

        <div className="grid gap-3 sm:grid-cols-2 sm:gap-4">
          {stats.map((stat) => (
            <article
              key={stat.label}
              className="rounded-[1.5rem] border border-sky-100 bg-white p-4 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-md"
            >
              <p className="cp-label">{stat.label}</p>
              <p className="mt-3 text-3xl font-black tracking-tight text-gray-900">
                {isLoading ? '...' : stat.value}
              </p>
            </article>
          ))}
        </div>

        <div className="rounded-[1.75rem] border border-sky-100 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
            <h3 className="cp-card-title text-gray-900">Recent Vault Materials</h3>
          </div>

          <div className="mt-5 grid gap-3">
            {isLoading ? (
              <p className="text-sm text-slate-400">Loading...</p>
            ) : items.length === 0 ? (
              <p className="text-sm text-slate-400">No materials yet. Upload from the Past Questions tab.</p>
            ) : (
              items.map((item) => {
                const isDeleting = deleteMutation.isPending && deleteMutation.variables === item.id;
                return (
                  <div
                    key={item.id}
                    className="flex flex-col gap-2 rounded-[1.25rem] border border-sky-100 bg-blue-50 p-4 transition-all duration-300 hover:-translate-y-0.5 hover:border-sky-200 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <p className="cp-card-title text-gray-900">{item.fileName}</p>
                      <p className="text-xs text-slate-500">{item.topic?.title ?? ''}</p>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <button
                        onClick={() => openFile(item.id, item.fileName)}
                        className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-white px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-blue-700 hover:bg-blue-50 transition-colors"
                      >
                        View
                      </button>
                      <button
                        onClick={() => setChatDocument({ id: item.id, title: item.fileName })}
                        className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-white px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-blue-700 hover:bg-blue-50 transition-colors"
                      >
                        Chat
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(item.id)}
                        disabled={isDeleting}
                        className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-white px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
                      >
                        {isDeleting ? '...' : 'Delete'}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {chatDocument && (
            <ChatPanel
              documentId={chatDocument.id}
              documentTitle={chatDocument.title}
              onClose={() => setChatDocument(null)}
            />
          )}
        </div>

        {viewerUrl && (
          <div className="fixed inset-0 z-50 flex flex-col bg-black/90 backdrop-blur-sm">
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
      </section>

      <BackupEmailModal
        isOpen={showModal}
        onClose={closeModal}
        onDismiss={handleDismissed}
        onSuccess={handleSuccess}
      />
    </>
  );
}
