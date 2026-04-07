import { useEffect, useState } from 'react'
import { listFunctions, type FunctionSpec } from '../api'

const TYPE_COLORS: Record<string, string> = {
  query: 'bg-blue-600/20 text-blue-300 border-blue-600/40',
  mutation: 'bg-orange-600/20 text-orange-300 border-orange-600/40',
  action: 'bg-purple-600/20 text-purple-300 border-purple-600/40',
  httpAction: 'bg-green-600/20 text-green-300 border-green-600/40',
  unknown: 'bg-gray-600/20 text-gray-300 border-gray-600/40',
}

export default function FunctionsView() {
  const [functions, setFunctions] = useState<FunctionSpec[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')

  useEffect(() => {
    loadFunctions()
  }, [])

  async function loadFunctions() {
    setLoading(true)
    setError(null)
    try {
      const fns = await listFunctions()
      setFunctions(fns)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load functions')
    } finally {
      setLoading(false)
    }
  }

  const filtered = functions.filter((fn) => {
    const matchesText = fn.path.toLowerCase().includes(filter.toLowerCase())
    const matchesType = typeFilter === 'all' || fn.functionType === typeFilter
    return matchesText && matchesType
  })

  const types = ['all', ...new Set(functions.map((f) => f.functionType))]

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Functions</h2>
        <button onClick={loadFunctions} className="btn btn-secondary" disabled={loading}>
          {loading ? 'Loading...' : '↻ Refresh'}
        </button>
      </div>

      {error && (
        <div className="card p-4 mb-4 border-red-800 bg-red-900/20 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          placeholder="Filter functions..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="input flex-1"
        />
        <div className="flex gap-1">
          {types.map((type) => (
            <button
              key={type}
              onClick={() => setTypeFilter(type)}
              className={`px-2 py-1 rounded text-xs border transition-colors ${
                typeFilter === type
                  ? TYPE_COLORS[type] || TYPE_COLORS.unknown
                  : 'border-gray-700 text-gray-500 hover:text-gray-300'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* Function List */}
      <div className="card divide-y divide-gray-800">
        {filtered.map((fn) => (
          <div key={fn.path} className="px-4 py-3 hover:bg-gray-800/50 transition-colors">
            <div className="flex items-center gap-3">
              <span
                className={`px-2 py-0.5 rounded text-xs border font-medium ${
                  TYPE_COLORS[fn.functionType] || TYPE_COLORS.unknown
                }`}
              >
                {fn.functionType}
              </span>
              <span className="font-mono text-sm text-gray-200">{fn.path}</span>
              {fn.visibility && fn.visibility !== 'public' && (
                <span className="text-xs text-gray-500 ml-auto">
                  {fn.visibility}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {!loading && filtered.length === 0 && (
        <div className="card p-8 text-center text-gray-500">
          {functions.length === 0
            ? 'No functions found. Make sure the Convex backend has deployed functions.'
            : 'No functions match the current filter.'}
        </div>
      )}

      <p className="text-xs text-gray-600 mt-3">
        {filtered.length} of {functions.length} functions
      </p>
    </div>
  )
}
