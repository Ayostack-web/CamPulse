'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { authFetch } from '@/lib/auth-fetch';

export interface PointsInfo {
  total_points: number;
}

export interface PointsTransaction {
  id: string;
  amount: number;
  reason: string;
  description: string | null;
  created_at: string | null;
}

export interface LeaderboardEntry {
  user_id: string;
  full_name: string;
  avatar_url: string | null;
  value: number;
}

export interface BadgeInfo {
  id: string;
  code: string;
  name: string;
  description: string;
  icon: string;
  rarity: 'COMMON' | 'RARE' | 'EPIC' | 'LEGENDARY';
  earned_at: string | null;
}

export interface StreakAndPoints {
  current_streak: number;
  longest_streak: number;
  total_points: number;
  last_activity_at: string | null;
}

export interface RewardItem {
  code: string;
  name: string;
  description: string;
  category: string;
  points_cost: number;
  affordable: boolean;
}

export interface RewardsData {
  balance: number;
  items: RewardItem[];
}

export function useStreakAndPoints() {
  return useQuery({
    queryKey: ['gamification-streak-and-points'],
    queryFn: () => authFetch('/api/gamification/streak-and-points') as Promise<StreakAndPoints>,
    staleTime: 30_000,
  });
}

export function useCheckIn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      authFetch('/api/gamification/check-in', { method: 'POST' }) as Promise<{ streak: number; points_earned: number }>,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gamification-streak-and-points'] });
      qc.invalidateQueries({ queryKey: ['gamification-points'] });
      qc.invalidateQueries({ queryKey: ['gamification-leaderboard-streaks'] });
      qc.invalidateQueries({ queryKey: ['gamification-leaderboard-points'] });
    },
  });
}

export function useUserBadges() {
  return useQuery({
    queryKey: ['gamification-badges'],
    queryFn: () => authFetch('/api/gamification/badges') as Promise<BadgeInfo[]>,
    staleTime: 60_000,
  });
}

export function usePoints() {
  return useQuery({
    queryKey: ['gamification-points'],
    queryFn: () => authFetch('/api/gamification/points') as Promise<PointsInfo>,
  });
}

export function usePointsHistory() {
  return useQuery({
    queryKey: ['gamification-points-history'],
    queryFn: () => authFetch('/api/gamification/points/history') as Promise<PointsTransaction[]>,
  });
}

export function useStreakLeaderboard() {
  return useQuery({
    queryKey: ['gamification-leaderboard-streaks'],
    queryFn: () => authFetch('/api/gamification/leaderboard/streaks') as Promise<LeaderboardEntry[]>,
    staleTime: 60_000,
  });
}

export function usePointsLeaderboard() {
  return useQuery({
    queryKey: ['gamification-leaderboard-points'],
    queryFn: () => authFetch('/api/gamification/leaderboard/points') as Promise<LeaderboardEntry[]>,
    staleTime: 60_000,
  });
}

export function useRewards() {
  return useQuery({
    queryKey: ['gamification-rewards'],
    queryFn: () => authFetch('/api/gamification/rewards') as Promise<RewardsData>,
    staleTime: 30_000,
  });
}

export function useRedeemReward() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rewardCode: string) =>
      authFetch('/api/gamification/rewards/redeem', {
        method: 'POST',
        body: JSON.stringify({ reward_code: rewardCode }),
      }) as Promise<{ name: string; queries_granted: number; balance_after: number }>,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gamification-rewards'] });
      qc.invalidateQueries({ queryKey: ['gamification-streak-and-points'] });
      qc.invalidateQueries({ queryKey: ['gamification-points'] });
      qc.invalidateQueries({ queryKey: ['ai-tokens'] });
    },
  });
}
