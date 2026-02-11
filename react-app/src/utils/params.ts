export function normalizeFormValueByName(_name: string, raw: any): any {
  // Keep it simple: server-side (Django) validates and casts.
  // We only need to format datetime-local values as-is.
  return raw
}
