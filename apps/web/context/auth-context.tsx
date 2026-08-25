'use client';

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { getSupabaseBrowserClient } from '@/lib/supabase-client';
import { captureReferralCode, claimPendingReferral } from '@/lib/referral';

interface User {
  id: string;
  email: string;
  fullName: string;
  avatarUrl?: string;
  status?: 'STUDENT' | 'ALUMNI';
  entryYear?: number;
  matricNumber?: string;
  currentLevel?: string;
  levelUpdatedAt?: string;
  schoolEmail?: string;
  schoolEmailPromptDismissedAt?: string;
  graduatedAt?: string;
  collegeId?: string;
  collegeName?: string;
  programType?: string;
  departmentCode?: string;
  departmentName?: string;
}

interface AuthActionResult {
  success: boolean;
  message: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string, isSignUp?: boolean) => Promise<AuthActionResult>;
  signInWithGoogle: () => Promise<void>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  updateAvatar: (url: string) => void;
  showLoginModal: boolean;
  setShowLoginModal: (show: boolean) => void;
  promptLogin: (action: string) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const supabaseClient = getSupabaseBrowserClient();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const fetchProfile = useCallback(async (userId: string) => {
    try {
      const { data: { session } } = await supabaseClient.auth.getSession();
      if (!session) return;
      const res = await fetch('/api/user/profile', {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (!res.ok) return;
      const profile = await res.json();
      if (profile) {
        setUser((prev) =>
          prev && prev.id === userId
            ? {
                ...prev,
                avatarUrl: profile.avatar_url ?? prev.avatarUrl,
                status: profile.status,
                entryYear: profile.entry_year,
                matricNumber: profile.matric_number,
                currentLevel: profile.current_level,
                levelUpdatedAt: profile.level_updated_at,
                schoolEmail: profile.school_email,
                schoolEmailPromptDismissedAt: profile.school_email_prompt_dismissed_at,
                graduatedAt: profile.graduated_at,
                collegeId: profile.college_id,
                collegeName: profile.college_name,
                programType: profile.program_type,
                departmentCode: profile.department_code,
                departmentName: profile.department_name,
              }
            : prev
        );
      }
    } catch {
      // Profile fetch is non-critical
    }
  }, [supabaseClient.auth]);

  const buildBaseUser = useCallback((sessionUser: any): User => {
    return {
      id: sessionUser.id,
      email: sessionUser.email ?? '',
      fullName:
        sessionUser.user_metadata?.full_name ??
        sessionUser.user_metadata?.name ??
        sessionUser.email?.split('@')[0] ??
        'Student',
      avatarUrl: sessionUser.user_metadata?.avatar_url ?? sessionUser.user_metadata?.picture ?? undefined,
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const claimAttemptedRef = { current: false };

    captureReferralCode();

    const syncSession = async () => {
      const { data } = await supabaseClient.auth.getSession();
      const sessionUser = data.session?.user;

      if (!isMounted) {
        return;
      }

      if (sessionUser) {
        const baseUser = buildBaseUser(sessionUser);
        setUser(baseUser);
        fetchProfile(baseUser.id);
        if (!claimAttemptedRef.current) {
          claimAttemptedRef.current = true;
          const token = data.session?.access_token;
          if (token) {
            claimPendingReferral(token);
          }
        }
      } else {
        setUser(null);
      }

      setIsLoading(false);
    };

    syncSession();

    const { data: { subscription } } = supabaseClient.auth.onAuthStateChange((_event, currentSession) => {
      const sessionUser = currentSession?.user;

      if (!isMounted) {
        return;
      }

      if (sessionUser) {
        const baseUser = buildBaseUser(sessionUser);
        setUser(baseUser);
        fetchProfile(baseUser.id);
        if (!claimAttemptedRef.current) {
          claimAttemptedRef.current = true;
          const token = currentSession?.access_token;
          if (token) {
            claimPendingReferral(token);
          }
        }
      } else {
        setUser(null);
      }

      setIsLoading(false);
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, [supabaseClient, buildBaseUser, fetchProfile]);

  const login = useCallback(async (email: string, password: string, isSignUp = false): Promise<AuthActionResult> => {
    setIsLoading(true);
    try {
      if (isSignUp) {
        const { data, error } = await supabaseClient.auth.signUp({
          email,
          password,
          options: {
            data: {
              full_name: email.split('@')[0],
            },
          },
        });

        if (error) {
          throw error;
        }

        if (data.session?.user) {
          setUser({
            id: data.session.user.id,
            email: data.session.user.email ?? email,
            fullName:
              data.session.user.user_metadata?.full_name ??
              data.session.user.user_metadata?.name ??
              email.split('@')[0],
            avatarUrl: data.session.user.user_metadata?.avatar_url ?? data.session.user.user_metadata?.picture ?? undefined,
          });
          setShowLoginModal(false);
          return {
            success: true,
            message: 'Account created and signed in successfully.',
          };
        }

        return {
          success: true,
          message: 'Account created. Check your email to confirm your sign up.',
        };
      }

      const { data, error } = await supabaseClient.auth.signInWithPassword({
        email,
        password,
      });

      if (error) {
        throw error;
      }

      if (data.user) {
        setUser({
          id: data.user.id,
          email: data.user.email ?? email,
          fullName:
            data.user.user_metadata?.full_name ??
            data.user.user_metadata?.name ??
            email.split('@')[0],
          avatarUrl: data.user.user_metadata?.avatar_url ?? data.user.user_metadata?.picture ?? undefined,
        });
      }

      setShowLoginModal(false);
      return {
        success: true,
        message: 'Signed in successfully.',
      };
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [supabaseClient]);

  const logout = useCallback(async () => {
    await supabaseClient.auth.signOut();
    setUser(null);
  }, [supabaseClient]);

  const refreshProfile = useCallback(async () => {
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (session?.user) {
      await fetchProfile(session.user.id);
    }
  }, [supabaseClient, fetchProfile]);

  const updateAvatar = useCallback((url: string) => {
    setUser((prev) => prev ? { ...prev, avatarUrl: url } : prev);
  }, []);

  const signInWithGoogle = useCallback(async () => {
    const { error } = await supabaseClient.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    if (error) throw error;
  }, [supabaseClient]);

  const promptLogin = useCallback((action: string) => {
    setPendingAction(action);
    setShowLoginModal(true);
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    signInWithGoogle,
    logout,
    refreshProfile,
    updateAvatar,
    showLoginModal,
    setShowLoginModal,
    promptLogin,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
