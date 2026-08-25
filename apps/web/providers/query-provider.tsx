'use client';

import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { queryClient } from '@/lib/query-client';
import { indexedDBPersister } from '@/lib/indexeddb-persister';
import { AuthProvider } from '@/context/auth-context';
import { ProgressiveGatingProvider, useProgressiveGating } from '@/context/progressive-gating-context';
import { DriveProvider } from '@/context/drive-context';
import { LoginModal } from '@/components/auth/LoginModal';
import { GraduationCelebrationModal } from '@/components/auth/GraduationCelebrationModal';
import { InstallPrompt } from '@/components/pwa/InstallPrompt';
import { PointsRefreshListener } from '@/components/gamification/PointsRefreshListener';

function ProgressiveGatingModals() {
  const { showGraduationModal, closeGraduationModal } = useProgressiveGating();

  return (
    <GraduationCelebrationModal
      isOpen={showGraduationModal}
      onClose={closeGraduationModal}
    />
  );
}

export function QueryProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <AuthProvider>
      <PersistQueryClientProvider client={queryClient} persistOptions={{ persister: indexedDBPersister }}>
        <ProgressiveGatingProvider>
          <DriveProvider>
            {children}
            <LoginModal />
            <ProgressiveGatingModals />
            <InstallPrompt />
            <PointsRefreshListener />
          </DriveProvider>
        </ProgressiveGatingProvider>
      </PersistQueryClientProvider>
    </AuthProvider>
  );
}
