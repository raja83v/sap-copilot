const BACKEND_URL = 'http://127.0.0.1:3210'
const ADMIN_KEY =
  '0135d8598650f8f5cb0f30c34ec2e2bb62793bc28717c8eb6fb577996d50be5f4281b59181095065c5d0f86a2c31ddbe9b597ec62b47ded69782cd'

async function post(path: string, body: Record<string, unknown> = {}) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ adminKey: ADMIN_KEY, ...body }),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json()
}

async function postWithAuth(path: string, body: Record<string, unknown> = {}) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Convex ${ADMIN_KEY}`,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json()
}

// ─── Table Operations ───────────────────────────────────────────────

export interface TableInfo {
  name: string
  count?: number
}

export async function listTables(): Promise<TableInfo[]> {
  try {
    // Try the admin API shape_table_summary endpoint
    const data = await post('/api/list_tables')
    if (Array.isArray(data)) {
      return data.map((t: string | { name: string }) =>
        typeof t === 'string' ? { name: t } : t
      )
    }
    if (data?.tables) {
      return data.tables.map((t: string | { name: string }) =>
        typeof t === 'string' ? { name: t } : t
      )
    }
    return []
  } catch {
    // Fallback: query each known table
    const knownTables = ['systems', 'sessions', 'messages', 'workflows', 'llmConfig']
    return knownTables.map((name) => ({ name }))
  }
}

export async function queryTable(
  tableName: string,
  cursor: string | null = null,
  limit: number = 50
): Promise<{ documents: Record<string, unknown>[]; cursor: string | null; hasMore: boolean }> {
  try {
    // Use the query endpoint to run a table scan
    const result = await post('/api/query', {
      path: `${tableName}:list`,
      args: {},
      format: 'json',
    })
    
    const docs = Array.isArray(result?.value) ? result.value : 
                 Array.isArray(result) ? result : []
    
    // Client-side pagination
    const startIdx = cursor ? parseInt(cursor, 10) : 0
    const page = docs.slice(startIdx, startIdx + limit)
    const nextIdx = startIdx + limit
    const hasMore = nextIdx < docs.length
    
    return {
      documents: page,
      cursor: hasMore ? String(nextIdx) : null,
      hasMore,
    }
  } catch {
    // Fallback: try direct table query via different endpoint patterns
    try {
      const result = await postWithAuth('/api/query', {
        path: `${tableName}:list`,
        args: {},
        format: 'json',
      })
      const docs = Array.isArray(result?.value) ? result.value :
                   Array.isArray(result) ? result : []
      return { documents: docs, cursor: null, hasMore: false }
    } catch {
      return { documents: [], cursor: null, hasMore: false }
    }
  }
}

export async function getDocumentCount(tableName: string): Promise<number> {
  try {
    const result = await queryTable(tableName, null, 10000)
    return result.documents.length
  } catch {
    return 0
  }
}

// ─── Function Operations ────────────────────────────────────────────

export interface FunctionSpec {
  path: string
  functionType: string
  visibility?: string
  args?: string
  returns?: string
}

export async function listFunctions(): Promise<FunctionSpec[]> {
  try {
    const data = await post('/api/function_spec')
    if (data?.modules) {
      const fns: FunctionSpec[] = []
      for (const mod of data.modules) {
        if (mod.functions) {
          for (const fn of mod.functions) {
            fns.push({
              path: `${mod.path}:${fn.name}`,
              functionType: fn.functionType || fn.udfType || 'unknown',
              visibility: fn.visibility?.kind || fn.visibility || 'public',
              args: fn.args ? JSON.stringify(fn.args) : undefined,
              returns: fn.returns ? JSON.stringify(fn.returns) : undefined,
            })
          }
        }
      }
      return fns
    }
    return []
  } catch {
    return []
  }
}

// ─── Run Query/Mutation ─────────────────────────────────────────────

export async function runQuery(
  path: string,
  args: Record<string, unknown> = {}
): Promise<unknown> {
  const result = await post('/api/query', { path, args, format: 'json' })
  return result?.value !== undefined ? result.value : result
}

export async function runMutation(
  path: string,
  args: Record<string, unknown> = {}
): Promise<unknown> {
  const result = await post('/api/mutation', { path, args, format: 'json' })
  return result?.value !== undefined ? result.value : result
}

// ─── Deployment Config ──────────────────────────────────────────────

export async function getDeploymentConfig(): Promise<Record<string, unknown>> {
  try {
    return await post('/api/get_config')
  } catch {
    return {}
  }
}

// ─── Logs (polling-based) ───────────────────────────────────────────

export interface LogEntry {
  timestamp: number
  level: string
  message: string
  functionPath?: string
}

let logListeners: ((logs: LogEntry[]) => void)[] = []
let logBuffer: LogEntry[] = []
let logPolling = false

export function subscribeLogs(listener: (logs: LogEntry[]) => void) {
  logListeners.push(listener)
  listener(logBuffer)
  
  if (!logPolling) {
    logPolling = true
    pollLogs()
  }
  
  return () => {
    logListeners = logListeners.filter((l) => l !== listener)
    if (logListeners.length === 0) {
      logPolling = false
    }
  }
}

async function pollLogs() {
  while (logPolling) {
    try {
      const res = await fetch(`${BACKEND_URL}/api/logs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ adminKey: ADMIN_KEY }),
      })
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data)) {
          const newLogs = data.map((entry: Record<string, unknown>) => ({
            timestamp: (entry.timestamp as number) || Date.now(),
            level: (entry.level as string) || 'INFO',
            message: (entry.message as string) || JSON.stringify(entry),
            functionPath: entry.functionPath as string | undefined,
          }))
          logBuffer = [...logBuffer, ...newLogs].slice(-500)
          logListeners.forEach((l) => l(logBuffer))
        }
      }
    } catch {
      // Logs endpoint may not be available
    }
    await new Promise((r) => setTimeout(r, 2000))
  }
}
