async function readJsonSafe(res: Response): Promise<any> {
  const text = await res.text()
  if (!text) return {}
  try {
    return JSON.parse(text)
  } catch {
    return { raw: text }
  }
}

export async function apiFetchJson(path: string, init?: RequestInit): Promise<any> {
  const res = await fetch(path, {
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
