'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchAdminRevenue, type AdminRevenue } from '@/lib/admin-api';
import { Skeleton } from '@/components/ui/skeleton';

const PLAN_NAMES: Record<string, string> = {
  night: 'Night Pass',
  weekly: 'Weekly Pass',
  semester: 'Semester Pass',
  session: 'Session VIP',
  topup: 'Top-Up',
  topup_mini: 'Mini Top-Up',
  micro: 'Micro',
};

export default function AdminRevenuePage() {
  const { data, isLoading, error } = useQuery<AdminRevenue>({
    queryKey: ['admin-revenue'],
    queryFn: fetchAdminRevenue,
    refetchInterval: 60_000,
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Revenue</h1>

      {error && (
        <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6 text-sm text-red-700 dark:text-red-300">
          Failed to load revenue data.
        </div>
      )}

      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
        {isLoading ? (
          <>
            <Skeleton className="h-28 rounded-xl" />
            <Skeleton className="h-28 rounded-xl" />
          </>
        ) : data ? (
          <>
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Total Revenue</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                ₦{data.total_revenue_ngn.toLocaleString()}
              </p>
            </div>
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Conversion Rate</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                {data.conversion_rate}%
              </p>
              <p className="text-xs text-gray-400 mt-1">paid users / total users</p>
            </div>
          </>
        ) : null}
      </div>

      {/* Breakdown by plan */}
      <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">Revenue by Plan</h2>
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-800">
              <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Plan</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Subscribers</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Revenue</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-gray-100 dark:border-gray-800/50">
                  <td className="px-4 py-3"><Skeleton className="h-4 w-28" /></td>
                  <td className="px-4 py-3 text-right"><Skeleton className="h-4 w-8 ml-auto" /></td>
                  <td className="px-4 py-3 text-right"><Skeleton className="h-4 w-16 ml-auto" /></td>
                </tr>
              ))
            ) : data?.by_plan.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-gray-400">No revenue data yet</td>
              </tr>
            ) : (
              data?.by_plan.map((p) => (
                <tr key={p.plan} className="border-b border-gray-100 dark:border-gray-800/50">
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                    {PLAN_NAMES[p.plan] || p.plan}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400">
                    {p.count}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-white">
                    ₦{p.revenue_ngn.toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
