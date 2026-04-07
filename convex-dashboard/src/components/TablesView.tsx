import { useEffect, useState } from 'react'
import { listTables, getDocumentCount, type TableInfo } from '../api'

interface TablesViewProps {
  onSelectTable: (table: string) => void
}

export default function TablesView({ onSelectTable }: TablesViewProps) {
  const [tables, setTables] = useState<(TableInfo & { count?: number })[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadTables()
  }, [])

  async function loadTables() {
    setLoading(true)
    setError(null)
    try {
      const tableList = await listTables()
      setTables(tableList)

      // Load counts in parallel
      const withCounts = await Promise.all(
        tableList.map(async (t) => {
          try {
            const count = await getDocumentCount(t.name)
            return { ...t, count }
          } catch {
            return { ...t, count: undefined }
          }
        })
      )
      setTables(withCounts)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tables')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Tables</h2>
        <button onClick={loadTables} className="btn btn-secondary" disabled={loading}>
          {loading ? 'Loading...' : '↻ Refresh'}
        </button>
      </div>

      {error && (
        <div className="card p-4 mb-4 border-red-800 bg-red-900/20 text-red-300 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {tables.map((table) => (
          <button
            key={table.name}
            onClick={() => onSelectTable(table.name)}
            className="card p-4 text-left hover:border-indigo-600 transition-colors group"
          >
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-gray-200 group-hover:text-indigo-300">
                {table.name}
              </h3>
              <span className="text-xs text-gray-500">→</span>
            </div>
            <p className="text-sm text-gray-500 mt-1">
              {table.count !== undefined ? (
                <span className="text-indigo-400 font-mono">{table.count}</span>
              ) : (
                <span className="text-gray-600">—</span>
              )}{' '}
              documents
            </p>
          </button>
        ))}
      </div>

      {!loading && tables.length === 0 && !error && (
        <div className="card p-8 text-center text-gray-500">
          No tables found. Make sure the Convex backend is running.
        </div>
      )}
    </div>
  )
}
