export const PROGRAM_TYPES = ['university', 'polytechnic', 'college_of_education'] as const;

export type ProgramType = (typeof PROGRAM_TYPES)[number];

const LEVEL_OPTIONS: Record<string, readonly string[]> = {
  university: ['100L', '200L', '300L', '400L', '500L', 'Spillover'],
  polytechnic: ['ND1', 'ND2', 'HND1', 'HND2'],
  college_of_education: ['NCE1', 'NCE2', 'NCE3'],
};

export const PROGRAM_TYPE_LABELS: Record<ProgramType, string> = {
  university: 'University',
  polytechnic: 'Polytechnic',
  college_of_education: 'College of Education',
};

export const PROGRAM_TYPE_ICONS: Record<ProgramType, string> = {
  university: '🎓',
  polytechnic: '🔧',
  college_of_education: '📚',
};

export const FACULTY_LABELS: Record<ProgramType, string> = {
  university: 'Faculty',
  polytechnic: 'School',
  college_of_education: 'Faculty',
};

export function levelOptionsFor(programType?: string | null): readonly string[] {
  return LEVEL_OPTIONS[programType ?? ''] ?? LEVEL_OPTIONS.university;
}

export function isLevelValidFor(programType: string | null | undefined, level: string): boolean {
  if (!level) return true;
  return levelOptionsFor(programType).includes(level);
}

export function labelForProgramType(programType?: string | null): string {
  return PROGRAM_TYPE_LABELS[programType as ProgramType] ?? 'Institution';
}

export function facultyLabelFor(programType?: string | null): string {
  return FACULTY_LABELS[programType as ProgramType] ?? 'Faculty';
}

export function iconForProgramType(programType?: string | null): string {
  return PROGRAM_TYPE_ICONS[programType as ProgramType] ?? '🏫';
}
