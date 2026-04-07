import type { View } from '../App'

interface SidebarProps {
  currentView: View
  onNavigate: (view: View) => void
}

const navItems: { label: string; icon: string; view: View }[] = [
  { label: 'Tables', icon: '📊', view: { type: 'tables' } },
  { label: 'Functions', icon: '⚡', view: { type: 'functions' } },
  { label: 'Logs', icon: '📋', view: { type: 'logs' } },
  { label: 'Runner', icon: '▶️', view: { type: 'runner' } },
]

export default function Sidebar({ currentView, onNavigate }: SidebarProps) {
  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <h1 className="text-lg font-bold text-indigo-400 flex items-center gap-2">
          ⚡ Convex Dashboard
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          carnitas · localhost:3210
        </p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-1">
        {navItems.map((item) => {
          const isActive = currentView.type === item.view.type
          return (
            <button
              key={item.label}
              onClick={() => onNavigate(item.view)}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
                isActive
                  ? 'bg-indigo-600/20 text-indigo-300 font-medium'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
              }`}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-800">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Connected
        </div>
      </div>
    </aside>
  )
}
