'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useAuth } from '@/context/auth-context';
import { getSupabaseBrowserClient } from '@/lib/supabase-client';
import { fetchApi, parseApiError } from '@/lib/api-request';
import { useStreakAndPoints, useUserBadges } from '@/queries/use-gamification';
import { useTheme } from '@/providers/theme-provider';
import { InviteModal } from '@/components/vylix-academic-hub/InviteModal';
import { fetchReferralCode } from '@/lib/referral';
import { levelOptionsFor, isLevelValidFor, labelForProgramType, facultyLabelFor, iconForProgramType, PROGRAM_TYPES } from '@/lib/levels';
import type { ProgramType } from '@/lib/levels';

interface University {
  id: string;
  code: string;
  name: string;
  program_type?: string;
}

interface College {
  id: string;
  code: string;
  name: string;
  durationYears: number;
}

interface Department {
  id: string;
  code: string;
  name: string;
}

export interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const RARITY_COLORS: Record<string, string> = {
  COMMON: 'bg-gray-100 border-gray-200 text-gray-600',
  RARE: 'bg-blue-50 border-blue-200 text-blue-600',
  EPIC: 'bg-sky-50 border-sky-200 text-sky-600',
  LEGENDARY: 'bg-amber-50 border-amber-200 text-amber-600',
};

export function ProfileModal({ isOpen, onClose }: ProfileModalProps) {
  const { user, refreshProfile, logout, updateAvatar } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const supabase = getSupabaseBrowserClient();
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const { data: stats } = useStreakAndPoints();
  const { data: badges } = useUserBadges();

  const [isEditing, setIsEditing] = useState(false);
  const [universities, setUniversities] = useState<University[]>([]);
  const [colleges, setColleges] = useState<College[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [selectedProgramType, setSelectedProgramType] = useState('');
  const [selectedUniId, setSelectedUniId] = useState('');
  const [selectedCollegeId, setSelectedCollegeId] = useState('');
  const [selectedDeptId, setSelectedDeptId] = useState('');
  const [currentLevel, setCurrentLevel] = useState('');
  const [fullName, setFullName] = useState('');
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [showInvite, setShowInvite] = useState(false);
  const [referralCode, setReferralCode] = useState('');
  const [referralEarned, setReferralEarned] = useState(0);

  const levelOptions = levelOptionsFor(selectedProgramType);

  const fetchUniversities = useCallback(async (programType?: string) => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const url = programType
        ? `/api/colleges?program_type=${encodeURIComponent(programType)}`
        : '/api/colleges';
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) setUniversities(await res.json());
    } catch { toast.error('Failed to load institutions'); }
  }, [supabase]);

  const fetchColleges = useCallback(async (universityId: string) => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const res = await fetch(`/api/colleges/${universityId}/colleges`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) setColleges(await res.json());
    } catch { toast.error('Failed to load colleges'); }
  }, [supabase]);

  const fetchDepartments = useCallback(async (collegeId: string) => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const res = await fetch(`/api/colleges/colleges/${collegeId}/departments`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) setDepartments(await res.json());
    } catch { toast.error('Failed to load departments'); }
  }, [supabase]);

  useEffect(() => {
    if (!isOpen || !selectedProgramType) {
      setUniversities([]);
      setSelectedUniId('');
      setColleges([]);
      setSelectedCollegeId('');
      setDepartments([]);
      setSelectedDeptId('');
      return;
    }
    fetchUniversities(selectedProgramType);
  }, [isOpen, selectedProgramType, fetchUniversities]);

  useEffect(() => {
    if (!selectedUniId) {
      setColleges([]);
      setSelectedCollegeId('');
      setDepartments([]);
      setSelectedDeptId('');
      return;
    }
    fetchColleges(selectedUniId);
  }, [selectedUniId, fetchColleges]);

  useEffect(() => {
    if (!selectedCollegeId) {
      setDepartments([]);
      setSelectedDeptId('');
      return;
    }
    fetchDepartments(selectedCollegeId);
  }, [selectedCollegeId, fetchDepartments]);

  useEffect(() => {
    if (!isOpen || universities.length === 0 || !user?.collegeId) return;
    const matched = universities.find((u) => u.id === user.collegeId);
    if (matched && matched.id !== selectedUniId) {
      setSelectedUniId(matched.id);
    }
  }, [isOpen, universities, user?.collegeId, selectedUniId]);

  useEffect(() => {
    if (!isOpen || !user?.programType) return;
    if (!selectedProgramType) {
      setSelectedProgramType(user.programType);
    }
  }, [isOpen, user?.programType, selectedProgramType]);

  useEffect(() => {
    if (!isOpen) return;
    (async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;
        const info = await fetchReferralCode(session.access_token);
        if (info) {
          setReferralCode(info.code);
          setReferralEarned(info.total_earned);
        }
      } catch {
        setReferralCode('');
      }
    })();
  }, [isOpen, supabase]);

  const enterEditMode = async () => {
    setFullName(user?.fullName || '');
    setCurrentLevel(user?.currentLevel || '');
    setSelectedProgramType(user?.programType || '');
    setSelectedUniId('');
    setSelectedCollegeId('');
    setSelectedDeptId('');
    setError('');
    setIsEditing(true);
  };

  const handleAvatarUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      setError('Accepted formats: JPEG, PNG, GIF, WebP');
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError('File too large. Maximum size is 5MB');
      return;
    }

    setUploading(true);
    setError('');

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error('No session');

      const formData = new FormData();
      formData.append('file', file);

      const res = await fetchApi('/api/user/avatar', {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: formData,
        direct: true,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(parseApiError(err, `Failed to upload avatar (HTTP ${res.status})`));
      }

      const json = await res.json();
      updateAvatar(json.avatar_url ?? json.avatarUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload avatar');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, [supabase, updateAvatar]);

  const cancelEdit = () => {
    setIsEditing(false);
    setError('');
    setSelectedProgramType('');
    setSelectedUniId('');
    setSelectedCollegeId('');
    setSelectedDeptId('');
    setCurrentLevel('');
  };

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError('');

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error('No session');

      const body: Record<string, unknown> = {};
      if (fullName.trim()) body.full_name = fullName.trim();
      if (currentLevel) body.current_level = currentLevel;
      if (selectedUniId) body.college_id = selectedUniId;
      if (selectedDeptId) body.department_id = selectedDeptId;

      const res = await fetch('/api/user/profile', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || 'Failed to save profile');
      }

      await refreshProfile();
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setSaving(false);
    }
  }, [supabase, fullName, currentLevel, selectedUniId, selectedDeptId, refreshProfile]);

  if (!isOpen) return null;

  if (!user) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
        <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl border border-blue-100 p-8 text-center">
          <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto" />
          <p className="mt-4 text-sm text-gray-500">Loading profile...</p>
        </div>
      </div>
    );
  }

  const initials = user.fullName?.charAt(0) ?? 'CS';
  const points = stats?.total_points ?? 0;
  const streak = stats?.current_streak ?? 0;
  const level = points >= 1000 ? 'Platinum' : points >= 500 ? 'Gold' : points >= 200 ? 'Silver' : 'Bronze';
  const levelColor = points >= 1000 ? 'from-sky-500 to-sky-600' : points >= 500 ? 'from-yellow-500 to-amber-500' : points >= 200 ? 'from-gray-400 to-gray-500' : 'from-orange-400 to-orange-500';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl border border-blue-100 overflow-hidden animate-fade-in max-h-[90vh] flex flex-col">
        {/* Header with gradient */}
        <div className="bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 p-6 text-center shrink-0">
          <div className="flex justify-center mb-3">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="relative group"
              title="Change photo"
            >
              <Avatar className="h-20 w-20 ring-4 ring-white/60 shadow-lg">
                <AvatarImage src={user.avatarUrl ?? undefined} alt={user.fullName} />
                <AvatarFallback className="bg-white text-2xl font-black text-gray-900">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/0 group-hover:bg-black/40 transition-colors">
                {uploading ? (
                  <svg className="animate-spin h-6 w-6 text-white" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <svg className="h-6 w-6 text-white opacity-0 group-hover:opacity-100 transition-opacity" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                )}
              </div>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/jpg,image/png,image/gif,image/webp"
              className="hidden"
              onChange={handleAvatarUpload}
            />
          </div>
          <h2 className="text-xl font-bold text-white">{user.fullName}</h2>
          <p className="text-sm text-white/80 mt-1">{user.email}</p>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {error && (
            <div className="rounded-xl bg-red-50 border border-red-200 p-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Gamification Stats */}
          {!isEditing && (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-xl bg-gradient-to-br from-orange-50 to-amber-50/80 border border-orange-200/60 p-3 text-center">
                  <span className="text-lg">
                    {streak >= 7 ? '🔥' : streak >= 3 ? '⚡' : streak > 0 ? '✨' : '📅'}
                  </span>
                  <p className="text-lg font-black text-gray-900 mt-1">{streak}</p>
                  <p className="text-[9px] font-bold uppercase tracking-wider text-orange-600">Day Streak</p>
                </div>
                <div className="rounded-xl bg-gradient-to-br from-emerald-50 to-teal-50/80 border border-emerald-200/60 p-3 text-center">
                  <span className="text-lg">💰</span>
                  <p className="text-lg font-black text-gray-900 mt-1">{points.toLocaleString()}</p>
                  <p className="text-[9px] font-bold uppercase tracking-wider text-emerald-600">Points</p>
                </div>
                <div className="rounded-xl bg-gradient-to-br from-emerald-50 to-emerald-50/80 border border-emerald-200/60 p-3 text-center">
                  <span className="text-lg">🏅</span>
                  <p className="text-lg font-black text-gray-900 mt-1">{badges?.length ?? 0}</p>
                  <p className="text-[9px] font-bold uppercase tracking-wider text-emerald-600">Badges</p>
                </div>
              </div>

              {points > 0 && (
                <div className="flex items-center justify-center">
                  <span className={`inline-flex items-center rounded-full bg-gradient-to-r ${levelColor} p-[1px] shadow-sm`}>
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-[10px] font-bold text-gray-900">
                      <span className={`w-1.5 h-1.5 rounded-full bg-gradient-to-r ${levelColor}`} />
                      {level} Tier
                    </span>
                  </span>
                </div>
              )}

              {/* Badges showcase */}
              {badges && badges.length > 0 && (
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">Earned Badges</p>
                  <div className="flex flex-wrap gap-2">
                    {badges.slice(0, 8).map((badge) => (
                      <div
                        key={badge.id}
                        className={`relative group w-12 h-12 rounded-xl border flex flex-col items-center justify-center cursor-default transition-all hover:scale-110 ${
                          RARITY_COLORS[badge.rarity] || RARITY_COLORS.COMMON
                        }`}
                        title={`${badge.name}: ${badge.description}`}
                      >
                        <span className="text-lg">{badge.icon}</span>
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10 w-40 rounded-xl border border-gray-200 bg-white p-2.5 shadow-lg">
                          <p className="text-[10px] font-bold text-gray-900">{badge.name}</p>
                          <p className="text-[9px] text-gray-500 mt-0.5">{badge.description}</p>
                        </div>
                      </div>
                    ))}
                    {badges.length > 8 && (
                      <div className="w-12 h-12 rounded-xl bg-gray-50 border border-gray-200 flex items-center justify-center">
                        <span className="text-[10px] font-bold text-gray-500">+{badges.length - 8}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Profile Info */}
          {isEditing ? (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Your full name"
                  className="block w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-2">Institution Type</label>
                <div className="grid grid-cols-3 gap-2">
                  {PROGRAM_TYPES.map((type) => {
                    const isSelected = selectedProgramType === type;
                    return (
                      <button
                        key={type}
                        type="button"
                        onClick={() => {
                          if (type !== selectedProgramType) {
                            setSelectedProgramType(type);
                            setSelectedUniId('');
                            setSelectedCollegeId('');
                            setSelectedDeptId('');
                            setCurrentLevel('');
                          }
                        }}
                        className={`flex flex-col items-center gap-1 rounded-xl border-2 p-3 text-center transition-all ${
                          isSelected
                            ? 'border-blue-500 bg-blue-50 shadow-sm'
                            : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/50'
                        }`}
                      >
                        <span className="text-2xl">{iconForProgramType(type)}</span>
                        <span className={`text-xs font-bold ${isSelected ? 'text-blue-700' : 'text-gray-700'}`}>
                          {labelForProgramType(type)}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {selectedProgramType && (
                <>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">
                      {labelForProgramType(selectedProgramType)}
                    </label>
                    <select
                      value={selectedUniId}
                      onChange={(e) => {
                        const nextUniId = e.target.value;
                        setSelectedUniId(nextUniId);
                        setSelectedCollegeId('');
                        setSelectedDeptId('');
                        const nextType = universities.find((u) => u.id === nextUniId)?.program_type;
                        if (!isLevelValidFor(nextType, currentLevel)) setCurrentLevel('');
                      }}
                      className="block w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    >
                      <option value="">{universities.length === 0 ? 'No institutions loaded' : `Select ${labelForProgramType(selectedProgramType)}`}</option>
                      {universities.map((u) => (
                        <option key={u.id} value={u.id}>{u.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">
                      {facultyLabelFor(selectedProgramType)}
                    </label>
                    <select
                      value={selectedCollegeId}
                      onChange={(e) => {
                        setSelectedCollegeId(e.target.value);
                        setSelectedDeptId('');
                      }}
                      disabled={!selectedUniId}
                      className="block w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200 disabled:opacity-50"
                    >
                      <option value="">{colleges.length === 0 ? `No ${facultyLabelFor(selectedProgramType).toLowerCase()}s loaded` : `Select ${facultyLabelFor(selectedProgramType)}`}</option>
                      {colleges.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">Department</label>
                    <select
                      value={selectedDeptId}
                      onChange={(e) => setSelectedDeptId(e.target.value)}
                      disabled={!selectedCollegeId}
                      className="block w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200 disabled:opacity-50"
                    >
                      <option value="">{departments.length === 0 ? 'No departments loaded' : 'Select Department'}</option>
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">Level</label>
                    <select
                      value={currentLevel}
                      onChange={(e) => setCurrentLevel(e.target.value)}
                      className="block w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    >
                      <option value="">Select Level</option>
                      {levelOptions.map((lvl) => (
                        <option key={lvl} value={lvl}>{lvl}</option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  onClick={cancelEdit}
                  disabled={saving}
                  className="flex-1 rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving || !selectedProgramType}
                  className="flex-1 rounded-xl bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 px-4 py-2.5 text-sm font-bold text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
                >
                  {saving ? (
                    <svg className="animate-spin h-5 w-5 mx-auto" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : 'Save'}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-xl bg-blue-50 border border-blue-100 p-3">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-blue-600">Status</p>
                  <p className="mt-1 font-semibold text-gray-900 text-sm">{user.status === 'ALUMNI' ? '🎓 Alumni' : '🎒 Student'}</p>
                </div>
                {user.currentLevel && (
                  <div className="rounded-xl bg-blue-50 border border-blue-100 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-blue-600">Level</p>
                    <p className="mt-1 font-semibold text-gray-900 text-sm">{user.currentLevel}</p>
                  </div>
                )}
                {user.matricNumber && (
                  <div className="rounded-xl bg-blue-50 border border-blue-100 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-blue-600">Matric No</p>
                    <p className="mt-1 font-semibold text-gray-900 text-sm">{user.matricNumber}</p>
                  </div>
                )}
                {user.entryYear && (
                  <div className="rounded-xl bg-blue-50 border border-blue-100 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-blue-600">Started</p>
                    <p className="mt-1 font-semibold text-gray-900 text-sm">{user.entryYear}</p>
                  </div>
                )}
                {user.collegeName && (
                  <div className="rounded-xl bg-blue-50 border border-blue-100 p-3 col-span-2">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-blue-600">{labelForProgramType(user?.programType)}</p>
                    <p className="mt-1 font-semibold text-gray-900 text-sm">{user.collegeName}</p>
                  </div>
                )}
                {user.departmentName && (
                  <div className="rounded-xl bg-blue-50 border border-blue-100 p-3 col-span-2">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-blue-600">Department</p>
                    <p className="mt-1 font-semibold text-gray-900 text-sm">{user.departmentName}</p>
                  </div>
                )}
              </div>

              <div className="flex gap-3 pt-1">
                <button
                  onClick={enterEditMode}
                  className="flex-1 rounded-xl border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm font-bold text-blue-700 hover:bg-blue-100 transition-colors"
                >
                  Edit Profile
                </button>
                <button
                  onClick={async () => {
                    await logout();
                    onClose();
                  }}
                  className="rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-700 hover:bg-red-100 transition-colors"
                >
                  Sign Out
                </button>
              </div>

              <div className="divider" />

              {/* Refer & Earn */}
              <div className="rounded-2xl bg-gradient-to-br from-emerald-50 via-teal-50 to-cyan-50 border border-emerald-200/70 p-4">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 text-white shadow-sm">
                    <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  </span>
                  <div className="flex-1">
                    <p className="text-sm font-bold text-gray-900">Refer & Earn</p>
                    <p className="text-[11px] text-gray-600">Invite a friend, you both get <span className="font-bold text-emerald-700">100 points</span>.</p>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <div className="min-w-0 flex-1 rounded-xl border border-dashed border-emerald-300 bg-white/70 px-3 py-2 text-center">
                    <span className="text-sm font-black tracking-[0.2em] text-emerald-700">{referralCode || '---'}</span>
                  </div>
                  <button
                    onClick={() => setShowInvite(true)}
                    className="shrink-0 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-4 py-2 text-sm font-bold text-white hover:shadow-md hover:scale-[1.01] active:scale-[0.99] transition-all"
                  >
                    Invite Friends
                  </button>
                </div>
                {referralEarned > 0 && (
                  <p className="mt-2 text-[11px] font-semibold text-emerald-700">
                    You&apos;ve earned {referralEarned.toLocaleString()} points from referrals 🎉
                  </p>
                )}
              </div>

              <div className="divider" />

              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">Appearance</p>
                <button
                  onClick={toggleTheme}
                  className="w-full flex items-center justify-between rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 transition-colors hover:bg-gray-100"
                >
                  <span className="flex items-center gap-2.5">
                    {theme === 'dark' ? (
                      <svg className="w-5 h-5 text-sky-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2m0 14v2m9-9h-2M5 12H3m15.36 6.36l-1.42-1.42M7.06 7.06L5.64 5.64m13.72 0l-1.42 1.42M7.06 16.94l-1.42 1.42M12 8a4 4 0 100 8 4 4 0 000-8z" />
                      </svg>
                    )}
                    <span className="text-sm font-semibold text-gray-900">{theme === 'dark' ? 'Dark Mode' : 'Light Mode'}</span>
                  </span>
                  <span
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      theme === 'dark' ? 'bg-gradient-to-r from-blue-600 to-sky-500' : 'bg-gray-300'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                        theme === 'dark' ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </span>
                </button>
              </div>

              <div className="divider" />

              {/* Quick Links */}
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">Quick Links</p>
                <div className="space-y-1.5">
                  <Link
                    href="/pricing"
                    className="flex items-center gap-2.5 rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-100 transition-colors"
                  >
                    <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Pricing & Plans
                  </Link>
                  <Link
                    href="/terms"
                    className="flex items-center gap-2.5 rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-100 transition-colors"
                  >
                    <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Terms of Service
                  </Link>
                  <Link
                    href="/privacy"
                    className="flex items-center gap-2.5 rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-100 transition-colors"
                  >
                    <svg className="w-4 h-4 text-purple-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                    Privacy Policy
                  </Link>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Close button */}
        <div className="p-4 pt-0 shrink-0">
          <button
            onClick={onClose}
            className="w-full rounded-xl bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 px-4 py-2.5 text-sm font-bold text-white hover:opacity-90 transition-opacity"
          >
            Close
          </button>
        </div>
      </div>

      <InviteModal isOpen={showInvite} onClose={() => setShowInvite(false)} />
    </div>
  );
}
