import { useState } from 'react'

interface JsonViewerProps {
  data: unknown
  depth?: number
}

export default function JsonViewer({ data, depth = 0 }: JsonViewerProps) {
  if (data === null) return <span className="text-orange-400">null</span>
  if (data === undefined) return <span className="text-gray-500">undefined</span>
  if (typeof data === 'boolean')
    return <span className="text-yellow-400">{data ? 'true' : 'false'}</span>
  if (typeof data === 'number')
    return <span className="text-blue-400">{data}</span>
  if (typeof data === 'string') {
    // Check if it looks like a timestamp
    if (/^\d{13}$/.test(data) || (typeof data === 'string' && data.length > 50)) {
      return (
        <span className="text-green-400 break-all" title={data}>
          "{data.length > 100 ? data.slice(0, 100) + '…' : data}"
        </span>
      )
    }
    return <span className="text-green-400">"{data}"</span>
  }

  if (Array.isArray(data)) {
    return <CollapsibleArray data={data} depth={depth} />
  }

  if (typeof data === 'object') {
    return <CollapsibleObject data={data as Record<string, unknown>} depth={depth} />
  }

  return <span className="text-gray-400">{String(data)}</span>
}

function CollapsibleObject({
  data,
  depth,
}: {
  data: Record<string, unknown>
  depth: number
}) {
  const [collapsed, setCollapsed] = useState(depth > 2)
  const entries = Object.entries(data)

  if (entries.length === 0) return <span className="text-gray-500">{'{}'}</span>

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="text-gray-500 hover:text-gray-300"
      >
        {'{'} {entries.length} keys {'}'}
      </button>
    )
  }

  return (
    <div className="pl-4 border-l border-gray-800">
      <button
        onClick={() => setCollapsed(true)}
        className="text-gray-600 hover:text-gray-400 text-xs"
      >
        ▼
      </button>
      {entries.map(([key, value]) => (
        <div key={key} className="flex gap-1 py-0.5">
          <span className="text-purple-400 flex-shrink-0">"{key}"</span>
          <span className="text-gray-600">:</span>
          <div className="min-w-0">
            <JsonViewer data={value} depth={depth + 1} />
          </div>
        </div>
      ))}
    </div>
  )
}

function CollapsibleArray({
  data,
  depth,
}: {
  data: unknown[]
  depth: number
}) {
  const [collapsed, setCollapsed] = useState(depth > 2)

  if (data.length === 0) return <span className="text-gray-500">[]</span>

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="text-gray-500 hover:text-gray-300"
      >
        [{data.length} items]
      </button>
    )
  }

  return (
    <div className="pl-4 border-l border-gray-800">
      <button
        onClick={() => setCollapsed(true)}
        className="text-gray-600 hover:text-gray-400 text-xs"
      >
        ▼
      </button>
      {data.map((item, idx) => (
        <div key={idx} className="flex gap-1 py-0.5">
          <span className="text-gray-600 flex-shrink-0 text-xs">{idx}:</span>
          <div className="min-w-0">
            <JsonViewer data={item} depth={depth + 1} />
          </div>
        </div>
      ))}
    </div>
  )
}
