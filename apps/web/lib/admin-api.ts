/**
 * Admin API helper — fetches from /api/v1/admin/* with auth.
 */

import { getSupabaseBrowserClient } from '@/lib/supabase-client';

async function adminFetch<T>(path: string): Promise<T> {
  const supabase = getSupabaseBrowserClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error('Not authenticated');

  const res = await fetch(`/api/v1${path}`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Admin API error ${res.status}`);
  }

  return res.json();
}

// ── Types ────────────────────────────────────────────────────────────

export interface AdminStats {
  total_users: number;
  users_today: number;
  users_this_week: number;
  active_subscriptions: number;
  revenue_ngn_today: number;
  revenue_ngn_week: number;
  revenue_ngn_month: number;
  ai_cost_usd_today: number;
  ai_cost_usd_week: number;
  ai_cost_usd_month: number;
  ai_queries_today: number;
  total_referrals: number;
}

export interface AdminUser {
  id: string;
  full_name: string;
  role: string;
  status: string;
  current_level: string | null;
  matric_number: string | null;
  created_at: string | null;
  last_active_at: string | null;
  subscription_plan: string | null;
  subscription_expires: string | null;
  ai_queries_today: number;
  contribution_score: number;
}

export interface AdminUsersResponse {
  users: AdminUser[];
  total: number;
  page: number;
  limit: number;
}

export interface RevenueByPlan {
  plan: string;
  count: number;
  revenue_ngn: number;
}

export interface AdminRevenue {
  total_revenue_ngn: number;
  by_plan: RevenueByPlan[];
  conversion_rate: number;
}

export interface AiUsageByFeature {
  feature: string;
  calls: number;
  total_tokens: number;
  est_cost_usd: number;
  dedup_hits: number;
}

export interface AiUsageByModel {
  model: string;
  calls: number;
  total_tokens: number;
  est_cost_usd: number;
}

export interface AdminAiUsage {
  total_cost_usd: number;
  total_queries: number;
  dedup_savings_usd: number;
  by_feature: AiUsageByFeature[];
  by_model: AiUsageByModel[];
}

// ── Fetchers ─────────────────────────────────────────────────────────

export const fetchAdminStats = () => adminFetch<AdminStats>('/admin/stats');
export const fetchAdminUsers = (page = 1, search = '', plan = '') =>
  adminFetch<AdminUsersResponse>(`/admin/users?page=${page}&limit=20&search=${encodeURIComponent(search)}&plan=${encodeURIComponent(plan)}`);
export const fetchAdminRevenue = () => adminFetch<AdminRevenue>('/admin/revenue');
export const fetchAdminAiUsage = (days = 30) =>
  adminFetch<AdminAiUsage>(`/admin/ai-usage?days=${days}`);
