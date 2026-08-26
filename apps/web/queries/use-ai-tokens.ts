'use client';

import { useQuery } from '@tanstack/react-query';
import { getSupabaseBrowserClient } from '@/lib/supabase-client';

export interface AiTokensData {
  used: number;
  limit: number;
  remaining: number;
  is_premium: boolean;
  plan: string;
  plan_name: string;
  quota_remaining: number;
  storage_total_bytes: number;
  storage_used_bytes: number;
  storage_remaining_bytes: number;
  expires_at: string | null;
  has_paid_pass: boolean;
  daily_query_cap: number | null;
  daily_queries_used: number | null;
}

export function useAiTokens() {
  const supabase = getSupabaseBrowserClient();

  return useQuery({
    queryKey: ['ai-tokens'],
    queryFn: async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error('Not authenticated');

      const res = await fetch('/api/user/ai-tokens', {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      if (!res.ok) throw new Error('Failed to fetch AI tokens');

      return res.json() as Promise<AiTokensData>;
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export interface Plan {
  key: string;
  name: string;
  price_ngn: number;
  price_kobo: number;
  duration_days: number | null;
  query_quota: number | null;
  storage_mb: number;
  tagline: string;
  featured: boolean;
  paid: boolean;
}

export function usePlans() {
  return useQuery({
    queryKey: ['plans'],
    queryFn: async () => {
      const res = await fetch('/api/plans');
      if (!res.ok) throw new Error('Failed to fetch plans');
      const data = (await res.json()) as { plans: Plan[] };
      return data.plans;
    },
    staleTime: Infinity,
  });
}
