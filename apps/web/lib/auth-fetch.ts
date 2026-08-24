'use client';

import { getSupabaseBrowserClient } from '@/lib/supabase-client';
import { fetchApi } from '@/lib/api-request';

export async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = getSupabaseBrowserClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error('Not authenticated');
  return { Authorization: `Bearer ${session.access_token}` };
}

/**
 * Like authFetch but resolves to the raw Response so callers can inspect
 * status codes (e.g. 429 DAILY_LIMIT_REACHED → upgrade modal).
 */
export async function authFetchRaw(path: string, options?: RequestInit): Promise<Response> {
  const authHeaders = await getAuthHeaders();
  return fetchApi(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...options?.headers,
    },
  });
}

export async function authFetch(path: string, options?: RequestInit): Promise<unknown> {
  const supabase = getSupabaseBrowserClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error('Not authenticated');

  const res = await fetchApi(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${session.access_token}`,
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      const parsed = JSON.parse(body);
      if (typeof parsed.detail === 'string') detail = parsed.detail;
      else if (typeof parsed.message === 'string') detail = parsed.message;
      else if (typeof parsed.error === 'string') detail = parsed.error;
    } catch {
      // Body was not JSON — use it as-is.
    }
    throw new Error(detail || `Request failed: ${res.status}`);
  }

  return res.json();
}
