'use client';

import React, { createContext, useCallback, useContext, useState } from 'react';

export function getCurrentAcademicSession(): number {
  const now = new Date();
  return now.getMonth() >= 8 ? now.getFullYear() : now.getFullYear() - 1;
}

export function isInCurrentSession(date: Date | string | undefined | null): boolean {
  if (!date) return false;
  const d = new Date(date);
  const session = getCurrentAcademicSession();
  const year = d.getFullYear();
  const month = d.getMonth();
  const itemSession = month >= 8 ? year : year - 1;
  return itemSession === session;
}

interface ProgressiveGatingContextType {
  showGraduationModal: boolean;
  openGraduationModal: () => void;
  closeGraduationModal: () => void;
}

const ProgressiveGatingContext = createContext<ProgressiveGatingContextType | undefined>(undefined);

export function ProgressiveGatingProvider({ children }: { children: React.ReactNode }) {
  const [showGraduationModal, setShowGraduationModal] = useState(false);
  const openGraduationModal = useCallback(() => setShowGraduationModal(true), []);
  const closeGraduationModal = useCallback(() => setShowGraduationModal(false), []);

  const value: ProgressiveGatingContextType = {
    showGraduationModal,
    openGraduationModal,
    closeGraduationModal,
  };

  return (
    <ProgressiveGatingContext.Provider value={value}>
      {children}
    </ProgressiveGatingContext.Provider>
  );
}

export function useProgressiveGating() {
  const context = useContext(ProgressiveGatingContext);
  if (context === undefined) {
    throw new Error('useProgressiveGating must be used within ProgressiveGatingProvider');
  }
  return context;
}
