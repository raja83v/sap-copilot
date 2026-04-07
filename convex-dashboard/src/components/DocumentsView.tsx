import { useEffect, useState } from 'react'
import { queryTable } from '../api'
import JsonViewer from './JsonViewer'

interface DocumentsViewProps {
  tableName: string
  onBack: () => void
}

export default function DocumentsView({ tableName, onBack }: DocumentsViewProps) {
  const [documents, setDocuments] = useState<Record<string, unknown>[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedDoc, setSelectedDoc] = useState<Record<string, unknown> | null>(null)
  const [cursor, setCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)

  useEffect(() => {
    loadDocuments()
  }, [tableName])

  async function loadDocuments(nextCursor: string | null = null) {
    setLoading(true)
    setError(null)
    try {
      const result = await queryTable(tableName, nextCursor)
      if (nextCursor) {
        setDocuments((prev) => [...prev, ...result.documents])
      } else {
        setDocuments(result.documents)
      }
      setCursor(result.cursor)
      setHasMore(result.hasMore)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex gap-4 h-full">
      {/* Document List */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 mb-4">
          <button onClick={onBack} className="btn btn-secondary text-xs">
            ← Back
          </button>
          <h2 className="text-xl font-semibold">
            {tableName}
            <span className="text-sm text-gray-500 ml-2 font-normal">
              ({documents.length} loaded)
            </span>
          </h2>
          <button
            onClick={() => loadDocuments()}
            className="btn btn-secondary text-xs ml-auto"
            disabled={loading}
          >
            ↻ Refresh
          </button>
        </div>

        {error && (
          <div className="card p-4 mb-4 border-red-800 bg-red-900/20 text-red-300 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-1">
          {documents.map((doc, idx) => {
            const id = (doc._id as string) || `doc-${idx}`
            const isSelected = selectedDoc === doc
            return (
              <button
                key={id}
                onClick={() => setSelectedDoc(doc)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm font-mono transition-colors ${
                  isSelected
                    ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-600/40'
                    : 'hover:bg-gray-800 text-gray-400 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-600">{idx + 1}.</span>
                  <span className="truncate">
                    {id}
                  </span>
                  {doc._creationTime && (
                    <span className="text-xs text-gray-600 ml-auto flex-shrink-0">
                      {new Date(doc._creationTime as number).toLocaleString()}
                    </span>
                  )}
                </div>
              </button>
            )
          })}
        </div>

        {hasMore && (
          <button
            onClick={() => loadDocuments(cursor)}
            className="btn btn-secondary mt-4 w-full"
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Load More'}
          </button>
        )}

        {!loading && documents.length === 0 && !error && (
          <div className="card p-8 text-center text-gray-500">
            No documents in this table.
          </div>
        )}
      </div>

      {/* Document Detail */}
      {selectedDoc && (
        <div className="w-[480px] flex-shrink-0">
          <div className="card p-4 sticky top-0">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-300">Document Detail</h3>
              <button
                onClick={() => setSelectedDoc(null)}
                className="text-gray-500 hover:text-gray-300 text-xs"
              >
                ✕ Close
              </button>
            </div>
            <JsonViewer data={selectedDoc} />
          </div>
        </div>
      )}
    </div>
  )
}
