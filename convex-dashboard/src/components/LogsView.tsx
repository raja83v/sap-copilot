import { useEffect, useRef, useState } from 'react'
import { subscribeLogs, type LogEntry } from '../api'

const LEVEL_COLORS: Record<string, string> = {
  INFO: 'text-blue-400',
  WARN: 'text-yellow-400',
  ERROR: 'text-red-400',
  DEBUG: 'text-gray-400',
}

export default function LogsView() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const unsub = subscribeLogs((newLogs) => {
      setLogs([...newLogs])
    })
    return unsub
  }, [])

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const filtered = filter
    ? logs.filter(
        (l) =>
          l.message.toLowerCase().includes(filter.toLowerCase()) ||
          l.functionPath?.toLowerCase().includes(filter.toLowerCase())
      )
    : logs

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Logs</h2>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded border-gray-600"
            />
            Auto-scroll
          </label>
          <button
            onClick={() => setLogs([])}
            className="btn btn-secondary text-xs"
          >
            Clear
          </button>
        </div>
      </div>

      <input
        type="text"
        placeholder="Filter logs..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="input mb-3"
      />

      <div
        ref={scrollRef}
        className="card flex-1 overflow-auto p-3 font-mono text-xs space-y-0.5"
      >
        {filtered.length === 0 ? (
          <div className="text-gray-600 text-center py-8">
            {logs.length === 0
              ? 'No logs yet. Logs will appear here when functions execute.'
              : 'No logs match the filter.'}
          </div>
        ) : (
          filtered.map((log, idx) => (
            <div key={idx} className="flex gap-2 py-0.5 hover:bg-gray-800/50 px-1 rounded">
              <span className="text-gray-600 flex-shrink-0">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span
                className={`flex-shrink-0 w-12 ${LEVEL_COLORS[log.level] || 'text-gray-400'}`}
              >
                {log.level}
              </span>
              {log.functionPath && (
                <span className="text-indigo-400 flex-shrink-0">
                  [{log.functionPath}]
                </span>
              )}
              <span className="text-gray-300 break-all">{log.message}</span>
            </div>
          ))
        )}
      </div>

      <p className="text-xs text-gray-600 mt-2">
        {filtered.length} log entries (polling every 2s)
      </p>
    </div>
  )
}
