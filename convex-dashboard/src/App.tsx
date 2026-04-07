import { useState } from 'react'
import Sidebar from './components/Sidebar'
import TablesView from './components/TablesView'
import DocumentsView from './components/DocumentsView'
import FunctionsView from './components/FunctionsView'
import LogsView from './components/LogsView'
import RunnerView from './components/RunnerView'

export type View =
  | { type: 'tables' }
  | { type: 'documents'; table: string }
  | { type: 'functions' }
  | { type: 'logs' }
  | { type: 'runner' }

export default function App() {
  const [view, setView] = useState<View>({ type: 'tables' })

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar currentView={view} onNavigate={setView} />
      <main className="flex-1 overflow-auto p-6">
        {view.type === 'tables' && (
          <TablesView onSelectTable={(table) => setView({ type: 'documents', table })} />
        )}
        {view.type === 'documents' && (
          <DocumentsView
            tableName={view.table}
            onBack={() => setView({ type: 'tables' })}
          />
        )}
        {view.type === 'functions' && <FunctionsView />}
        {view.type === 'logs' && <LogsView />}
        {view.type === 'runner' && <RunnerView />}
      </main>
    </div>
  )
}
