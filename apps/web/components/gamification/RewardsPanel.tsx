'use client';

import { useRedeemReward, useRewards } from '@/queries/use-gamification';

export function RewardsPanel() {
  const { data, isLoading } = useRewards();
  const redeem = useRedeemReward();

  if (isLoading || !data) return null;

  return (
    <div className="rounded-2xl border border-amber-100 bg-white p-4 shadow-sm sm:col-span-2 lg:col-span-4">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600">Rewards store</p>
          <h3 className="text-sm font-bold text-gray-900">Spend your points</h3>
        </div>
        <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-bold text-amber-700">
          {data.balance.toLocaleString()} pts
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {data.items.map((item) => (
          <div key={item.code} className="rounded-xl border border-gray-100 bg-gray-50/70 p-3">
            <div className="flex items-start justify-between gap-2">
              <p className="text-xs font-bold text-gray-900">{item.name}</p>
              <span className="shrink-0 text-[10px] font-bold text-amber-700">{item.points_cost.toLocaleString()} pts</span>
            </div>
            <p className="mt-1 text-[11px] leading-snug text-gray-500">{item.description}</p>
            <button
              type="button"
              onClick={() => redeem.mutate(item.code)}
              disabled={!item.affordable || redeem.isPending}
              className="mt-3 w-full rounded-lg bg-amber-500 px-3 py-2 text-[11px] font-bold text-white transition hover:bg-amber-600 disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-400"
            >
              {redeem.isPending ? 'Redeeming...' : item.affordable ? 'Redeem' : 'Not enough points'}
            </button>
          </div>
        ))}
      </div>
      {redeem.isSuccess && <p className="mt-3 text-xs font-medium text-emerald-600">{redeem.data.name} activated successfully.</p>}
      {redeem.isError && <p className="mt-3 text-xs font-medium text-red-600">Could not redeem that reward. Please try again.</p>}
    </div>
  );
}