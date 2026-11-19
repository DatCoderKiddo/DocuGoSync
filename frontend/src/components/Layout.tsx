import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  GitBranch,
  AlertTriangle,
  Settings,
  Zap,
  BookOpen,
  Radio,
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/repositories', label: 'Repositories', icon: GitBranch },
  { to: '/drift', label: 'Drift Issues', icon: AlertTriangle },
  { to: '/analyze', label: 'Analyze', icon: Zap },
  { to: '/auto-tracking', label: 'Auto Tracking', icon: Radio },
  { to: '/docs', label: 'Documentation', icon: BookOpen },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()

  return (
    <div className="min-h-screen flex bg-surface">
      {/* Sidebar */}
      <nav className="w-64 flex-shrink-0 bg-surface-elevated border-r border-surface-border flex flex-col">
        {/* Logo */}
        <div className="px-6 py-5 border-b border-surface-border">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
              <span className="text-white font-bold text-sm">D</span>
            </div>
            <div>
              <div className="text-white font-semibold text-sm">DocuGoSync</div>
              <div className="text-gray-500 text-xs">Documentation Sync</div>
            </div>
          </div>
        </div>

        {/* Nav items */}
        <div className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => {
            const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
            return (
              <Link
                key={to}
                to={to}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  active
                    ? 'bg-accent/10 text-accent-light border border-accent/20'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-surface-card',
                )}
              >
                <Icon size={16} />
                {label}
              </Link>
            )
          })}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-border">
          <div className="text-xs text-gray-600">v0.1.0 · Phase 1 MVP</div>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  )
}
