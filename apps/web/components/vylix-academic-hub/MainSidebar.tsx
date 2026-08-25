'use client';

import { useState, useMemo, useEffect, useCallback } from 'react'
import { getSupabaseBrowserClient } from '@/lib/supabase-client'
import { useStreakAndPoints } from '@/queries/use-gamification'
import { useAuth } from '@/context/auth-context'


interface Course {
  id: string
  code: string
  title: string
  level: number
  is_general: boolean
  past_question_count: number
  department_name: string | null
  department_code: string | null
  department_color: string | null
}

const DEPT_COLORS: Record<string, string> = {
  STA: '#3b82f6', PHY: '#f59e0b', CHM: '#10b981', MTH: '#2563eb',
  CSC: '#ef4444', ENG: '#f97316', ECO: '#06b6d4', BUS: '#3b82f6',
}

interface MainSidebarProps {
  selectedCourseId: string | null
  onSelectCourse: (id: string | null) => void
  variant?: 'desktop' | 'drawer'
}

export function MainSidebar({ selectedCourseId, onSelectCourse, variant = 'desktop' }: MainSidebarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [search, setSearch] = useState('')
  const [levelFilter, setLevelFilter] = useState<string | null>(null)
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const { isAuthenticated } = useAuth()
  const { data: stats } = useStreakAndPoints()

  const fetchCourses = useCallback(async () => {
    try {
      const supabase = getSupabaseBrowserClient()
      const { data: { session } } = await supabase.auth.getSession()
      const headers: Record<string, string> = {}
      if (session?.access_token) {
        headers['Authorization'] = `Bearer ${session.access_token}`
      }
      const res = await fetch(`/api/courses/my`, { headers })
      if (res.ok) {
        const data = await res.json()
        setCourses(data)
      }
    } catch {
      // Non-critical
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCourses()
  }, [fetchCourses])

  const departments = useMemo(() => {
    const grouped: Record<string, { name: string; code: string; color: string; courses: Course[] }> = {}
    for (const c of courses) {
      const key = c.department_name || 'General'
      if (!grouped[key]) {
        grouped[key] = {
          name: c.department_name || 'General',
          code: c.department_code || 'GEN',
          color: c.department_color || DEPT_COLORS[c.department_code || ''] || '#6b7280',
          courses: [],
        }
      }
      grouped[key].courses.push(c)
    }
    return Object.values(grouped)
  }, [courses])

  const filteredCourses = useMemo(() => {
    let filtered = courses
    if (search) {
      const q = search.toLowerCase()
      filtered = filtered.filter(c =>
        c.code.toLowerCase().includes(q) ||
        c.title.toLowerCase().includes(q) ||
        (c.department_name && c.department_name.toLowerCase().includes(q))
      )
    }
    if (levelFilter) {
      filtered = filtered.filter(c => c.level.toString() === levelFilter.replace('L', ''))
    }
    return filtered
  }, [courses, search, levelFilter])

  const levels = ['100L', '200L', '300L', '400L']

  return (
    <aside
      className={`${
        collapsed ? 'w-16' : 'w-[240px] xl:w-[280px]'
      } flex flex-col sidebar-premium transition-all duration-300 ease-in-out h-full overflow-hidden`}
    >
      {/* Sidebar header */}
      <div className="flex items-center justify-between px-3 py-3 divider-premium shrink-0">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-md bg-gradient-to-br from-blue-500/10 to-sky-500/10 flex items-center justify-center">
              <svg className="w-3 h-3 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <h2 className="text-[11px] font-bold uppercase tracking-wider text-gray-400">Courses</h2>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-lg hover:bg-gray-100/80 active:bg-gray-200/60 text-gray-400 hover:text-gray-600 transition-all shrink-0"
          aria-label={collapsed ? 'Expand' : 'Collapse'}
        >
          <svg className={`w-4 h-4 transition-transform duration-300 ${collapsed ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={collapsed ? 'M13 5l7 7-7 7M5 5l7 7-7 7' : 'M11 19l-7-7 7-7m8 14l-7-7 7-7'} />
          </svg>
        </button>
      </div>

      {/* Gamification widget - streak & points */}
      {isAuthenticated && !collapsed && stats && (stats.current_streak > 0 || stats.total_points > 0) && (
        <div className="px-3 pb-2 shrink-0">
          <div className="flex items-center gap-2 p-2 rounded-xl bg-gradient-to-r from-orange-50/80 to-amber-50/50 border border-orange-100/60">
            {stats.current_streak > 0 && (
              <div className="flex items-center gap-1">
                <span className="text-sm">🔥</span>
                <span className="text-[11px] font-bold text-orange-700">{stats.current_streak}</span>
              </div>
            )}
            {stats.current_streak > 0 && stats.total_points > 0 && (
              <span className="w-px h-3 bg-orange-200/60" />
            )}
            {stats.total_points > 0 && (
              <div className="flex items-center gap-1">
                <svg className="w-3.5 h-3.5 text-amber-500" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                </svg>
                <span className="text-[11px] font-bold text-amber-700">{stats.total_points.toLocaleString()}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Search & Filters */}
      {!collapsed && (
        <div className="px-3 pt-2.5 pb-2 space-y-2 shrink-0">
          <div className="relative group">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 group-focus-within:text-blue-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search courses..."
              className="w-full pl-9 pr-3 py-2 text-xs rounded-xl search-premium focus:outline-none"
            />
          </div>
          <div className="flex gap-1.5 overflow-x-auto pb-0.5 scrollbar-none">
            {levels.map((level) => (
              <button
                key={level}
                onClick={() => setLevelFilter(levelFilter === level ? null : level)}
                className={`shrink-0 text-[10px] px-2.5 py-1 rounded-lg border font-semibold transition-all duration-200 ${
                  levelFilter === level
                    ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white border-transparent shadow-sm shadow-blue-600/20'
                    : 'bg-gray-50/80 text-gray-500 border-gray-200/80 hover:border-blue-300 hover:bg-blue-50/50 hover:text-blue-600'
                }`}
              >
                {level}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Course list */}
      <nav className="flex-1 overflow-y-auto px-2 py-1.5 space-y-0.5 premium-stagger">
        {/* All Courses button */}
        <button
          onClick={() => { onSelectCourse(null); setSearch(''); setLevelFilter(null) }}
          className={`nav-item-premium w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-xl text-xs font-medium transition-all duration-200 ${
            selectedCourseId === null && !search && !levelFilter
              ? 'is-selected bg-blue-50/80 text-blue-700'
              : 'text-gray-600 hover:bg-gray-50/80 hover:text-gray-900'
          }`}
        >
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-600 to-sky-500 flex items-center justify-center text-white text-[10px] font-bold shrink-0 shadow-sm shadow-blue-600/20">
            A
          </div>
          {!collapsed && (
            <>
              <span className="truncate font-semibold">All Courses</span>
              {selectedCourseId === null && !search && !levelFilter && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
              )}
            </>
          )}
        </button>

        {loading ? (
          !collapsed && (
            <div className="flex items-center justify-center py-8">
              <div className="flex items-center gap-2 text-gray-400">
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span className="text-[11px] font-medium">Loading courses...</span>
              </div>
            </div>
          )
        ) : (
          <>
            {/* Department groups */}
            {!collapsed && !search && !levelFilter && departments.map((dept) => (
              <div key={dept.code} className="mt-3">
                <div className="flex items-center gap-2 px-3 py-1.5">
                  <div className="w-2 h-2 rounded-full shrink-0 ring-2 ring-offset-1" style={{ backgroundColor: dept.color, boxShadow: `0 0 6px ${dept.color}40` }} />
                  <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 truncate">{dept.name}</span>
                  <span className="text-[10px] text-gray-300 font-medium ml-auto bg-gray-100/80 px-1.5 py-0.5 rounded-md">{dept.courses.length}</span>
                </div>
                {dept.courses.map((course, i) => (
                  <button
                    key={course.id}
                    onClick={() => onSelectCourse(course.id)}
                    className={`nav-item-premium w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-xs font-medium transition-all duration-200 ${
                      selectedCourseId === course.id
                        ? 'is-selected bg-blue-50/80 text-blue-700'
                        : 'text-gray-600 hover:bg-gray-50/80 hover:text-gray-900'
                    }`}
                    style={{ animationDelay: `${i * 30}ms` }}
                  >
                    <div
                      className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-[9px] font-bold shrink-0 shadow-sm"
                      style={{ backgroundColor: dept.color, boxShadow: `0 2px 6px ${dept.color}30` }}
                    >
                      {course.code.slice(0, 2)}
                    </div>
                    <div className="flex-1 text-left min-w-0">
                      <div className="truncate font-semibold text-[11px]">{course.code}</div>
                      <div className="truncate text-[10px] text-gray-400 leading-tight">{course.title} · {course.level}L</div>
                    </div>
                  </button>
                ))}
              </div>
            ))}

            {/* Filtered results */}
            {!collapsed && (search || levelFilter) && filteredCourses.map((course) => (
              <button
                key={course.id}
                onClick={() => onSelectCourse(course.id)}
                className={`nav-item-premium w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-xs font-medium transition-all duration-200 ${
                  selectedCourseId === course.id
                    ? 'is-selected bg-blue-50/80 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-50/80 hover:text-gray-900'
                }`}
              >
                <div className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-[9px] font-bold shrink-0 shadow-sm" style={{ backgroundColor: course.department_color || DEPT_COLORS[course.department_code || ''] || '#6b7280', boxShadow: `0 2px 6px ${course.department_color || '#6b7280'}30` }}>
                  {course.code.slice(0, 2)}
                </div>
                <div className="flex-1 text-left min-w-0">
                  <div className="truncate font-semibold text-[11px]">{course.code}</div>
                  <div className="truncate text-[10px] text-gray-400">{course.title} · {course.level}L · {course.department_name || 'General'}</div>
                </div>
              </button>
            ))}

            {/* Empty search state */}
            {!collapsed && (search || levelFilter) && filteredCourses.length === 0 && (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <div className="w-10 h-10 rounded-2xl bg-gray-100 flex items-center justify-center mb-2">
                  <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <p className="text-[11px] text-gray-400 font-medium">No courses found</p>
                <p className="text-[10px] text-gray-300">Try a different search</p>
              </div>
            )}

            {/* Empty state */}
            {!collapsed && !search && !levelFilter && courses.length === 0 && (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <div className="w-10 h-10 rounded-2xl bg-gray-100 flex items-center justify-center mb-2">
                  <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <p className="text-[11px] text-gray-400 font-medium">No courses yet</p>
                <p className="text-[10px] text-gray-300">Set your department in profile to see courses</p>
              </div>
            )}
          </>
        )}
      </nav>

      {/* Footer */}
      <div className="px-2 py-2 divider-premium shrink-0">
        <button
          onClick={() => onSelectCourse(null)}
          className="group w-full flex items-center gap-2 px-2.5 py-2 rounded-xl text-xs font-medium text-gray-500 hover:bg-gray-50/80 hover:text-gray-700 transition-all"
        >
          <div className="w-7 h-7 rounded-lg bg-gray-100/80 flex items-center justify-center group-hover:bg-gray-200/60 transition-colors shrink-0">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          {!collapsed && <span>Clear Selection</span>}
        </button>
      </div>
    </aside>
  )
}
