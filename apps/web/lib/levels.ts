export const PROGRAM_TYPES = ['university', 'polytechnic', 'college_of_education'] as const;

export type ProgramType = (typeof PROGRAM_TYPES)[number];

const LEVEL_OPTIONS: Record<string, readonly string[]> = {
  university: ['100L', '200L', '300L', '400L', '500L', 'Spillover'],
  polytechnic: ['ND1', 'ND2', 'HND1', 'HND2'],
  college_of_education: ['NCE1', 'NCE2', 'NCE3'],
};

export function levelOptionsFor(programType?: string | null): readonly string[] {
  return LEVEL_OPTIONS[programType ?? ''] ?? LEVEL_OPTIONS.university;
}

export function isLevelValidFor(programType: string | null | undefined, level: string): boolean {
  if (!level) return true;
  return levelOptionsFor(programType).includes(level);
}
