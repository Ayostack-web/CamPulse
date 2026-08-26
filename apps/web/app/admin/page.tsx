'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchAdminStats, type AdminStats } from '@/lib/admin-api';
import { Skeleton } from '@/components/ui/skeleton';

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

function StatSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
      <Skeleton className="h-3 w-24 mb-2" />
      <Skeleton className="h-8 w-16" />
    </div>
  );
}

export default function AdminDashboardPage() {
  const { data, isLoading, error } = useQuery<AdminStats>({
    queryKey: ['admin-stats'],
    queryFn: fetchAdminStats,
    refetchInterval: 30_000,
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Dashboard</h1>

      {error && (
        <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6 text-sm text-red-700 dark:text-red-300">
          Failed to load stats. Are you an admin?
        </div>
      )}

      {/* Users */}
      <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">Users</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <StatSkeleton key={i} />)
        ) : data ? (
          <>
            <StatCard label="Total Users" value={data.total_users.toLocaleString()} />
            <StatCard label="Today" value={data.users_today} sub="new signups" />
            <StatCard label="This Week" value={data.users_this_week} />
            <StatCard label="Active Subscriptions" value={data.active_subscriptions} />
          </>
        ) : null}
      </div>

      {/* Revenue */}
      <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">Revenue</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => <StatSkeleton key={i} />)
        ) : data ? (
          <>
            <StatCard label="Today" value={`₦${data.revenue_ngn_today.toLocaleString()}`} />
            <StatCard label="This Week" value={`₦${data.revenue_ngn_week.toLocaleString()}`} />
            <StatCard label="This Month" value={`₦${data.revenue_ngn_month.toLocaleString()}`} />
          </>
        ) : null}
      </div>

      {/* AI */}
      <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">AI Usage</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <StatSkeleton key={i} />)
        ) : data ? (
          <>
            <StatCard label="Cost Today" value={`$${data.ai_cost_usd_today.toFixed(4)}`} />
            <StatCard label="Cost This Week" value={`$${data.ai_cost_usd_week.toFixed(4)}`} />
            <StatCard label="Cost This Month" value={`$${data.ai_cost_usd_month.toFixed(4)}`} />
            <StatCard label="Queries Today" value={data.ai_queries_today} />
          </>
        ) : null}
      </div>

      {/* Referrals */}
      <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">Growth</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {isLoading ? (
          <StatSkeleton />
        ) : data ? (
          <StatCard label="Total Referrals" value={data.total_referrals} />
        ) : null}
      </div>
    </div>
  );
}
