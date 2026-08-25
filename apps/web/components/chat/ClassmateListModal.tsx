'use client';

import { useCallback, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useAuth } from '@/context/auth-context';
import { getSupabaseBrowserClient } from '@/lib/supabase-client';
import { useClassmates, useCreateConversation, type ConversationDetail } from '@/queries/use-collaboration';
import { levelOptionsFor, isLevelValidFor } from '@/lib/levels';

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

interface ClassmateListModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (conv: ConversationDetail) => void;
}

export function ClassmateListModal({ isOpen, onClose, onCreated }: ClassmateListModalProps) {
  const { user, refreshProfile } = useAuth();
  const qc = useQueryClient();
  const { data: classmates, isLoading } = useClassmates();
  const createConversation = useCreateConversation();

  const [universities, setUniversities] = useState<University[]>([]);
  const [colleges, setColleges] = useState<College[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [selectedUniId, setSelectedUniId] = useState('');
  const [selectedCollegeId, setSelectedCollegeId] = useState('');
  const [selectedDeptId, setSelectedDeptId] = useState('');
  const [currentLevel, setCurrentLevel] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedProgramType = universities.find((u) => u.id === selectedUniId)?.program_type;
  const levelOptions = levelOptionsFor(selectedProgramType);

  const needsProfile = !user?.collegeId || !user?.departmentCode;

  const fetchUniversities = useCallback(async () => {
    try {
      const res = await fetch('/api/colleges');
      if (res.ok) setUniversities(await res.json());
    } catch { /* ignore */ }
  }, []);

  const fetchColleges = useCallback(async (universityId: string) => {
    try {
      const res = await fetch(`/api/colleges/${universityId}/colleges`);
      if (res.ok) setColleges(await res.json());
    } catch { /* ignore */ }
  }, []);

  const fetchDepartments = useCallback(async (collegeId: string) => {
    try {
      const res = await fetch(`/api/colleges/colleges/${collegeId}/departments`);
      if (res.ok) setDepartments(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    if (needsProfile) {
      fetchUniversities();
      setSelectedUniId('');
      setSelectedCollegeId('');
      setSelectedDeptId('');
      setCurrentLevel('');
      setError(null);
    }
  }, [isOpen, needsProfile, fetchUniversities]);

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

  const handleSave = useCallback(async () => {
    if (!selectedUniId) { setError('Select your university'); return; }
    if (!selectedCollegeId) { setError('Select your college'); return; }
    if (!selectedDeptId) { setError('Select your department'); return; }

    setSaving(true);
    setError(null);

    try {
      const supabase = getSupabaseBrowserClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error('No active session');

      const body: Record<string, unknown> = {
        college_id: selectedUniId,
        department_id: selectedDeptId,
      };
      if (currentLevel) body.current_level = currentLevel;

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
        throw new Error(err.message || 'Failed to save');
      }

      await refreshProfile();
      qc.invalidateQueries({ queryKey: ['users', 'classmates'] });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setSaving(false);
    }
  }, [selectedUniId, selectedCollegeId, selectedDeptId, currentLevel, refreshProfile, qc]);

  const handleStartChat = async (classmate: { id: string; fullName: string }) => {
    try {
      const conv = await createConversation.mutateAsync({
        type: 'DIRECT',
        memberIds: [classmate.id],
      });
      onCreated(conv);
      onClose();
    } catch {
      // handled by mutation
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl border border-blue-100 flex flex-col max-h-[80vh]">
        <div className="border-b border-blue-100 bg-gradient-to-r from-blue-50 to-sky-50/35 px-6 py-4 shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-black text-gray-900">Classmates</h2>
              <p className="text-sm text-gray-600 mt-1">
                {user?.departmentName ?? 'Your department'} &middot; {user?.currentLevel ?? ''}
              </p>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-gray-500 hover:bg-blue-50 transition"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {needsProfile ? (
            <div className="space-y-4 py-4">
              <div className="text-center">
                <span className="text-3xl mb-2 block">🎓</span>
                <p className="text-sm font-semibold text-gray-700">Set up your academic profile</p>
                <p className="text-xs text-gray-500 mt-1">Select your university and department to find coursemates.</p>
              </div>

              {error && (
                <div className="rounded-xl bg-red-50 border border-red-200 p-3">
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">
                  {selectedProgramType === 'polytechnic' ? 'Polytechnic' : selectedProgramType === 'college_of_education' ? 'College of Education' : 'University'}
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
                  <option value="">{universities.length === 0 ? 'No universities loaded' : 'Select your university'}</option>
                  {universities.map((u) => (
                    <option key={u.id} value={u.id}>{u.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">College / Faculty</label>
                <select
                  value={selectedCollegeId}
                  onChange={(e) => { setSelectedCollegeId(e.target.value); setSelectedDeptId(''); }}
                  disabled={!selectedUniId}
                  className="block w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200 disabled:opacity-50"
                >
                  <option value="">{colleges.length === 0 ? 'No colleges loaded' : 'Select your college'}</option>
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
                  <option value="">{departments.length === 0 ? 'No departments loaded' : 'Select your department'}</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1">
                  Current Level <span className="text-gray-400 font-normal normal-case">(optional)</span>
                </label>
                <select
                  value={currentLevel}
                  onChange={(e) => setCurrentLevel(e.target.value)}
                  className="block w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200"
                >
                  <option value="">Select your level</option>
                  {levelOptions.map((lvl) => (
                    <option key={lvl} value={lvl}>{lvl}</option>
                  ))}
                </select>
              </div>

              <button
                onClick={handleSave}
                disabled={saving || !selectedUniId || !selectedDeptId}
                className="w-full rounded-xl bg-gradient-to-r from-blue-600 via-sky-600 to-cyan-400 px-4 py-2.5 text-sm font-bold text-white shadow-md transition-all hover:shadow-lg disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Continue'}
              </button>
            </div>
          ) : isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex items-center gap-3 animate-pulse">
                  <div className="h-10 w-10 rounded-full bg-slate-200" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-4 w-32 rounded bg-slate-200" />
                    <div className="h-3 w-20 rounded bg-slate-100" />
                  </div>
                </div>
              ))}
            </div>
          ) : !classmates || classmates.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <span className="text-3xl mb-3">👥</span>
              <p className="text-sm font-semibold text-gray-700">No classmates found</p>
              <p className="text-xs text-gray-500 mt-1">
                Make sure your department and level are set in your profile
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              {classmates.map((cm) => (
                <button
                  key={cm.id}
                  onClick={() => handleStartChat(cm)}
                  disabled={createConversation.isPending}
                  className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-blue-50 transition disabled:opacity-50"
                >
                  <Avatar className="h-10 w-10 shrink-0 shadow-sm ring-2 ring-blue-100">
                    <AvatarImage src={cm.avatarUrl ?? undefined} />
                    <AvatarFallback className="bg-green-50 font-bold text-gray-900 text-sm">
                      {cm.fullName.charAt(0)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-gray-900 truncate">{cm.fullName}</p>
                    <p className="text-xs text-gray-500">
                      {cm.department?.code ?? ''}{cm.matricNumber ? ` · ${cm.matricNumber}` : ''}
                    </p>
                  </div>
                  <svg className="h-4 w-4 shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h8m-4-4l4 4-4 4" />
                  </svg>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
