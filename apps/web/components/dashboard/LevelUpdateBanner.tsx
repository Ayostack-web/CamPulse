'use client';

import React, { useState, useCallback } from 'react';
import { getSupabaseBrowserClient } from '@/lib/supabase-client';
import { useAuth } from '@/context/auth-context';
import { useProgressiveGating, isInCurrentSession } from '@/context/progressive-gating-context';
import { levelOptionsFor } from '@/lib/levels';

export function LevelUpdateBanner() {
  const supabase = getSupabaseBrowserClient();
  const { user } = useAuth();
  const { openGraduationModal } = useProgressiveGating();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = useCallback(async (level: string) => {
    if (level === "I've Graduated! 🎓") {
      openGraduationModal();
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error('No active session');

      const res = await fetch(`/api/user/update-level`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ level }),
      });

      if (!res.ok) throw new Error('Failed to update level');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setIsLoading(false);
    }
  }, [supabase, openGraduationModal]);

  const hasCurrentSessionLevel = isInCurrentSession(user?.levelUpdatedAt);
  const levels = levelOptionsFor(user?.programType);
  if (!user || user.status !== 'STUDENT' || hasCurrentSessionLevel) return null;

  return (
    <div className="rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 via-white to-sky-50/50 p-5 shadow-sm animate-fade-in">
      <div className="flex items-start gap-3">
        <span className="text-2xl">🚀</span>
        <div className="min-w-0 flex-1">
          <h3 className="font-bold text-gray-900 text-base">
            Welcome to a New Session!
          </h3>
          <p className="text-sm text-gray-600 mt-0.5">
            What level are you rocking this year?
          </p>

          {error && (
            <div className="mt-3 rounded-xl bg-red-50 border border-red-200 p-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div className="flex flex-wrap gap-2 mt-4">
            {levels.map((lvl) => (
              <button
                key={lvl}
                onClick={() => handleSelect(lvl)}
                disabled={isLoading}
                className="rounded-full px-4 py-2 text-sm font-semibold transition-all border bg-white text-gray-700 border-gray-200 hover:border-blue-300 hover:bg-blue-50 disabled:opacity-50"
              >
                {lvl}
              </button>
            ))}
            <button
              onClick={() => handleSelect("I've Graduated! 🎓")}
              disabled={isLoading}
              className="rounded-full px-4 py-2 text-sm font-bold border border-[#e6d59b] bg-gradient-to-r from-[#fbf5dd] to-[#f6ecc8] text-[#8a6d1f] hover:from-[#f8efd0] hover:to-[#f3e5bd] hover:shadow-md shadow-amber-900/10 transition-all disabled:opacity-50"
            >
              I&apos;ve Graduated! 🎓
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
