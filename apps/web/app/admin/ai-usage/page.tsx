'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchAdminAiUsage, type AdminAiUsage } from '@/lib/admin-api';
import { Skeleton } from '@/components/ui/skeleton';

export default function AdminAiUsagePage() {
  const [days, setDays] = useState(30);

  const { data, isLoading, error } = useQuery<AdminAiUsage>({
    queryKey: ['admin-ai-usage', days],
    queryFn: () => fetchAdminAiUsage(days),
    refetchInterval: 60_000,
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">AI Usage</h1>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
          <option value={365}>Last year</option>
        </select>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6 text-sm text-red-700 dark:text-red-300">
          Failed to load AI usage data.
        </div>
      )}

      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)
        ) : data ? (
          <>
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Total Cost</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">${data.total_cost_usd.toFixed(4)}</p>
            </div>
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Total Queries</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{data.total_queries.toLocaleString()}</p>
            </div>
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Cache Savings</p>
              <p className="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">${data.dedup_savings_usd.toFixed(4)}</p>
              <p className="text-xs text-gray-400 mt-1">from prompt cache dedup</p>
            </div>
          </>
        ) : null}
      </div>

      {/* By Feature */}
      <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">By Feature</h2>
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden mb-8">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-800">
              <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Feature</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Calls</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Tokens</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Cost</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Cache Hits</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-gray-100 dark:border-gray-800/50">
                  <td className="px-4 py-3"><Skeleton className="h-4 w-24" /></td>
                  <td className="px-4 py-3 text-right"><Skeleton className="h-4 w-8 ml-auto" /></td>
                  <td className="px-4 py-3 text-right"><Skeleton className="h-4 w-12 ml-auto" /></td>
                  <td className="px-4 py-3 text-right"><Skeleton className="h-4 w-12 ml-auto" /></td>
                  <td className="px-4 py-3 text-right"><Skeleton className="h-4 w-8 ml-auto" /></td>
                </tr>
              ))
            ) : data?.by_feature.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">No AI usage data yet</td>
              </tr>
            ) : (
              data?.by_feature.map((f) => (
                <tr key={f.feature} className="border-b border-gray-100 dark:border-gray-800/50">
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{f.feature}</td>
                  <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400">{f.calls}</td>
                  <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400">{f.total_tokens.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-white">${f.est_cost_usd.toFixed(4)}</td>
                  <td className="px-4 py-3 text-right text-green-600 dark:text-green-400">{f.dedup_hits}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* By Model */}
      <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">By Model</h2>
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-800">
              <th className="text-left px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Model</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Calls</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Tokens</th>
              <th className="text-right px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Cost</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <tr key={i} className="border-b border-gray-100 dark:border-gray-800/50">
                  <td className="px-4 py-3"><Skeleton className="h-4 w-32" /></td>
                  <td className="px-4 py-3 text-right"><Skeleton className="h-4 w-8 ml-auto" /></td>
                  <td className="px-4 py-3 text-right"><Skeleton className="h-4 w-12 ml-auto" /></td>
                  <td className="px-4 py-3 text-right"><Skeleton className="h-4 w-12 ml-auto" /></td>
                </tr>
              ))
            ) : data?.by_model.map((m) => (
              <tr key={m.model} className="border-b border-gray-100 dark:border-gray-800/50">
                <td className="px-4 py-3 font-medium text-gray-900 dark:text-white font-mono text-xs">{m.model}</td>
                <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400">{m.calls}</td>
                <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400">{m.total_tokens.toLocaleString()}</td>
                <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-white">${m.est_cost_usd.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
