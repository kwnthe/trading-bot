async function readJsonSafe(res: Response): Promise<any> {
  const text = await res.text()
  if (!text) return {}
  try {
    const cleanedText = text.replace(/\bNaN\b/g, 'null').trim()
    return JSON.parse(cleanedText)
  } catch (error) {
    console.error('JSON parsing failed:', error)
    console.error('Response text:', text.substring(0, 200) + '...')
    // Try without cleaning as fallback
    try {
      return JSON.parse(text)
    } catch (secondError) {
      console.error('Second parsing attempt also failed:', secondError)
      return { raw: text }
    }
  }
}

export async function apiFetchJson(path: string, init?: RequestInit): Promise<any> {
  // Check if we're accessing via network IP and use direct FastAPI connection
  const isNetworkAccess = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1'
  const url = isNetworkAccess ? `http://127.0.0.1:8000${path}` : path
  
  const res = await fetch(url, {
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!res.ok) {
    const data = await readJsonSafe(res)
    throw new Error((data && data.error) ? String(data.error) : `HTTP ${res.status}`)
  }

  return await readJsonSafe(res)
}
