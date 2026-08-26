'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchAdminUsers, type AdminUsersResponse } from '@/lib/admin-api';
import { Skeleton } from '@/components/ui/skeleton';

const PLAN_BADGES: Record<string, string> = {
  night: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
  weekly: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  semester: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  session: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  topup: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  topup_mini: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  micro: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300',
};

export default function AdminUsersPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [planFilter, setPlanFilter] = useState('');

  const { data, isLoading, error } = useQuery<AdminUsersResponse>({
    queryKey: ['admin-users', page, search, planFilter],
    queryFn: () => fetchAdminUsers(page, search, planFilter),
  });

  const handleSearch = () => {
    setPage(1);
    setSearch(searchInput);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Users</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="flex gap-2">
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search name or matric..."
            className="px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 w-64"
          />
          <button
            onClick={handleSearch}
            className="px-3 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Search
          </button>
        </div>
        <select
          value={planFilter}
          onChange={(e) => { setPlanFilter(e.target.value); setPage(1); }}
          className="px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">All Plans</option>
          <option value="night">Night</option>
          <option value="weekly">Weekly</option>
          <option value="semester">Semester</option>
          <option value="session">Session</option>
          <option value="topup">Top-Up</option>
          <option value="topup_mini">Mini Top-Up</option>
          <option value="micro">Micro</option>
        </select>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6 text-sm text-red-700 dark:text-red-300">
          Failed to load users.
        </div>
      )}

      {/* Table */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-800">
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">User</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Level</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Plan</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">AI Today</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Joined</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Role</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i} className="border-b border-gray-100 dark:border-gray-800/50">
                    <td className="px-4 py-3"><Skeleton className="h-4 w-32" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-12" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-5 w-16 rounded-full" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-8" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-12" /></td>
                  </tr>
                ))
              ) : data?.users.map((u) => (
                <tr key={u.id} className="border-b border-gray-100 dark:border-gray-800/50 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                  <td className="px-4 py-3">
                    <div>
                      <p className="font-medium text-gray-900 dark:text-white">{u.full_name}</p>
                      {u.matric_number && (
                        <p className="text-xs text-gray-400">{u.matric_number}</p>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{u.current_level || '—'}</td>
                  <td className="px-4 py-3">
                    {u.subscription_plan ? (
                      <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${PLAN_BADGES[u.subscription_plan] || 'bg-gray-100 text-gray-800'}`}>
                        {u.subscription_plan}
                      </span>
                    ) : (
                      <span className="text-gray-400 text-xs">free</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{u.ai_queries_today}</td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {u.role === 'admin' ? (
                      <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300">
                        admin
                      </span>
                    ) : (
                      <span className="text-gray-400 text-xs">student</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {data && data.total > data.limit && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">
            Showing {(page - 1) * data.limit + 1}–{Math.min(page * data.limit, data.total)} of {data.total}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * data.limit >= data.total}
              className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
