'use client';

import { createStore, del, get, keys, set } from 'idb-keyval';

import { getSupabaseBrowserClient } from '@/lib/supabase-client';

/**
 * Offline-first PDF byte cache.
 *
 * Materials are served as short-lived Supabase signed URLs that change on every
 * mint, so HTTP/service-worker caching of URLs is useless. Instead we persist
 * the actual PDF bytes in IndexedDB keyed by stable material id, and hand the
 * UI a blob:// URL. Once a document has been opened (or explicitly saved for
 * offline), it renders instantly and works with zero connectivity.
 */

const blobStore = createStore('vylix-pdf-cache', 'blobs');
const INDEX_KEY = 'index';
const MAX_TOTAL_BYTES = 250 * 1024 * 1024;

type PdfCacheIndex = Record<string, { size: number; savedAt: number }>;

let indexMemo: PdfCacheIndex | null = null;
const urlMemo = new Map<string, string>();
const inflight = new Map<string, Promise<string>>();

async function readIndex(): Promise<PdfCacheIndex> {
  if (indexMemo) return indexMemo;
  indexMemo = (await get<PdfCacheIndex>(INDEX_KEY, blobStore)) ?? {};
  return indexMemo;
}

async function writeIndex(index: PdfCacheIndex): Promise<void> {
  indexMemo = index;
  await set(INDEX_KEY, index, blobStore);
}

async function evictOldest(preserveIds: string[]): Promise<void> {
  const index = await readIndex();
  const preserve = new Set(preserveIds);
  let total = Object.values(index).reduce((acc, entry) => acc + entry.size, 0);
  if (total <= MAX_TOTAL_BYTES) return;

  const oldestFirst = Object.entries(index)
    .filter(([id]) => !preserve.has(id))
    .sort((a, b) => a[1].savedAt - b[1].savedAt);

  for (const [id, meta] of oldestFirst) {
    if (total <= MAX_TOTAL_BYTES) break;
    await del(`blob:${id}`, blobStore);
    delete index[id];
    total -= meta.size;
    const url = urlMemo.get(id);
    if (url) {
      URL.revokeObjectURL(url);
      urlMemo.delete(id);
    }
  }
  await writeIndex(index);
}

async function cachePdfBlob(materialId: string, blob: Blob): Promise<void> {
  await set(`blob:${materialId}`, blob, blobStore);
  const index = await readIndex();
  index[materialId] = { size: blob.size, savedAt: Date.now() };
  await writeIndex(index);
  await evictOldest([materialId]);
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  try {
    const supabase = getSupabaseBrowserClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      return { Authorization: `Bearer ${session.access_token}` };
    }
  } catch (error) {
    console.warn('[pdf-cache] Failed to resolve session:', error);
  }
  return {};
}

async function fetchPdfBlob(materialId: string): Promise<Blob> {
  const res = await fetch(`/api/materials/${materialId}/file`, {
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to get file');
  const { download_url: downloadUrl } = await res.json();
  if (!downloadUrl) throw new Error('No download URL returned');

  const fileRes = await fetch(downloadUrl);
  if (!fileRes.ok) throw new Error('Failed to download file');
  return fileRes.blob();
}

/** Resolve a playable object URL for a material, downloading and caching on first view. */
export async function openMaterialPdf(materialId: string): Promise<string> {
  const memoized = urlMemo.get(materialId);
  if (memoized) return memoized;

  const pending = inflight.get(materialId);
  if (pending) return pending;

  const promise = (async () => {
    const cached = await getCachedPdfBlob(materialId);
    if (cached) {
      const url = URL.createObjectURL(cached);
      urlMemo.set(materialId, url);
      return url;
    }

    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      throw new Error('You are offline and this document is not saved for offline reading');
    }

    const blob = await fetchPdfBlob(materialId);
    try {
      await cachePdfBlob(materialId, blob);
    } catch (error) {
      console.warn('[pdf-cache] Could not persist blob:', error);
    }
    const url = URL.createObjectURL(blob);
    urlMemo.set(materialId, url);
    return url;
  })();

  inflight.set(materialId, promise);
  try {
    return await promise;
  } finally {
    inflight.delete(materialId);
  }
}

/**
 * Explicitly download and persist a material's PDF bytes (Save for offline).
 * Pass `directUrl` for static assets such as the bundled seed PDFs.
 */
export async function cacheMaterialPdf(
  materialId: string,
  opts: { directUrl?: string } = {},
): Promise<void> {
  const index = await readIndex();
  if (index[materialId]) return;

  let blob: Blob;
  if (opts.directUrl) {
    const res = await fetch(opts.directUrl);
    if (!res.ok) throw new Error('Failed to download file');
    blob = await res.blob();
  } else {
    blob = await fetchPdfBlob(materialId);
  }
  await cachePdfBlob(materialId, blob);
}

export async function getCachedPdfBlob(materialId: string): Promise<Blob | null> {
  return (await get<Blob>(`blob:${materialId}`, blobStore)) ?? null;
}

export async function isPdfCached(materialId: string): Promise<boolean> {
  const index = await readIndex();
  return Boolean(index[materialId]);
}

export async function removeCachedPdf(materialId: string): Promise<void> {
  await del(`blob:${materialId}`, blobStore);
  const index = await readIndex();
  delete index[materialId];
  await writeIndex(index);
  const url = urlMemo.get(materialId);
  if (url) {
    URL.revokeObjectURL(url);
    urlMemo.delete(materialId);
  }
}

export async function clearPdfCache(): Promise<void> {
  const allKeys = await keys(blobStore);
  await Promise.all(allKeys.map((key) => del(key, blobStore)));
  indexMemo = {};
  await writeIndex(indexMemo);
  for (const [id, url] of urlMemo) {
    URL.revokeObjectURL(url);
    urlMemo.delete(id);
  }
}
