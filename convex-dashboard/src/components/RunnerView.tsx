import { useState } from 'react'
import { runQuery, runMutation } from '../api'
import JsonViewer from './JsonViewer'

export default function RunnerView() {
  const [functionPath, setFunctionPath] = useState('')
  const [argsText, setArgsText] = useState('{}')
  const [mode, setMode] = useState<'query' | 'mutation'>('query')
  const [result, setResult] = useState<unknown>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<
    { path: string; mode: string; args: string; result: unknown; error?: string; ts: number }[]
  >([])

  async function execute() {
    if (!functionPath.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    let args: Record<string, unknown>
    try {
      args = JSON.parse(argsText)
    } catch {
      setError('Invalid JSON in arguments')
      setLoading(false)
      return
    }

    try {
      const res = mode === 'query' ? await runQuery(functionPath, args) : await runMutation(functionPath, args)
      setResult(res)
      setHistory((prev) => [
        { path: functionPath, mode, args: argsText, result: res, ts: Date.now() },
        ...prev.slice(0, 19),
      ])
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Execution failed'
      setError(msg)
      setHistory((prev) => [
        { path: functionPath, mode, args: argsText, result: null, error: msg, ts: Date.now() },
        ...prev.slice(0, 19),
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl">
      <h2 className="text-xl font-semibold mb-6">Function Runner</h2>

      <div className="card p-4 space-y-4">
        {/* Mode Toggle */}
        <div className="flex gap-2">
          <button
            onClick={() => setMode('query')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              mode === 'query'
                ? 'bg-blue-600/20 text-blue-300 border border-blue-600/40'
                : 'text-gray-400 border border-gray-700 hover:text-gray-200'
            }`}
          >
            Query
          </button>
          <button
            onClick={() => setMode('mutation')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              mode === 'mutation'
                ? 'bg-orange-600/20 text-orange-300 border border-orange-600/40'
                : 'text-gray-400 border border-gray-700 hover:text-gray-200'
            }`}
          >
            Mutation
          </button>
        </div>

        {/* Function Path */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Function Path</label>
          <input
            type="text"
            value={functionPath}
            onChange={(e) => setFunctionPath(e.target.value)}
            placeholder="e.g. messages:list or sessions:getAll"
            className="input w-full"
            onKeyDown={(e) => e.key === 'Enter' && execute()}
          />
        </div>

        {/* Arguments */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Arguments (JSON)</label>
          <textarea
            value={argsText}
            onChange={(e) => setArgsText(e.target.value)}
            placeholder="{}"
            rows={4}
            className="input w-full font-mono text-sm resize-y"
          />
        </div>

        {/* Execute Button */}
        <button
          onClick={execute}
          disabled={loading || !functionPath.trim()}
          className="btn btn-primary w-full"
        >
          {loading ? 'Executing...' : `Run ${mode}`}
        </button>
      </div>

      {/* Result */}
      {(result !== null || error) && (
        <div className="card p-4 mt-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Result</h3>
          {error ? (
            <div className="text-red-400 text-sm font-mono break-all">{error}</div>
          ) : (
            <div className="max-h-96 overflow-auto">
              <JsonViewer data={result} />
            </div>
          )}
        </div>
      )}

      {/* History */}
      {history.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-medium text-gray-400 mb-3">History</h3>
          <div className="space-y-2">
            {history.map((entry, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setFunctionPath(entry.path)
                  setArgsText(entry.args)
                  setMode(entry.mode as 'query' | 'mutation')
                }}
                className="card w-full text-left px-3 py-2 hover:border-indigo-600/40 transition-colors"
              >
                <div className="flex items-center gap-2 text-xs">
                  <span
                    className={`px-1.5 py-0.5 rounded border font-medium ${
                      entry.mode === 'query'
                        ? 'bg-blue-600/20 text-blue-300 border-blue-600/40'
                        : 'bg-orange-600/20 text-orange-300 border-orange-600/40'
                    }`}
                  >
                    {entry.mode}
                  </span>
                  <span className="font-mono text-gray-300">{entry.path}</span>
                  <span className="text-gray-600 ml-auto">
                    {new Date(entry.ts).toLocaleTimeString()}
                  </span>
                  {entry.error && <span className="text-red-400">✕</span>}
                  {!entry.error && <span className="text-green-400">✓</span>}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
