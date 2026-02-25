/**
 * WebSocket service for real-time live session updates.
 *
 * The server pushes three message types:
 *   - status_update  → full LiveStatusResponse (incl. stdout/stderr/params)
 *   - snapshot_update → full ResultJson snapshot
 *   - logs_update     → stdout + stderr only
 *   - connection_established / pong / error
 */

export interface StatusUpdateMessage {
  type: 'status_update'
  session_id: string
  timestamp: string
  status: Record<string, any>
}

export interface SnapshotUpdateMessage {
  type: 'snapshot_update'
  session_id: string
  timestamp: string
  snapshot: Record<string, any>
}

export interface LogsUpdateMessage {
  type: 'logs_update'
  session_id: string
  timestamp: string
  stdout: string
  stderr: string
}

export interface ConnectionMessage {
  type: 'connection_established'
  session_id: string
  timestamp: string
  message: string
}

export interface ErrorMessage {
  type: 'error'
  session_id: string
  timestamp: string
  message: string
}

export type WebSocketMessage =
  | StatusUpdateMessage
  | SnapshotUpdateMessage
  | LogsUpdateMessage
  | ConnectionMessage
  | ErrorMessage

// Also re-export legacy types for backward compat
export type ChartUpdateMessage = SnapshotUpdateMessage

function buildWsUrl(sessionId: string): string {
  const apiTarget = (import.meta.env.VITE_API_TARGET || '').trim()
  if (apiTarget) {
    // e.g. "http://192.168.2.22:8000" → "ws://192.168.2.22:8000"
    const wsBase = apiTarget.replace(/^http/, 'ws')
    return `${wsBase}/ws/live/${sessionId}/`
  }
  // Relative – derive from current page location
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}/ws/live/${sessionId}/`
}

export class LiveChartWebSocket {
  private ws: WebSocket | null = null
  private sessionId: string | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectDelay = 2000
  private pingIntervalId: ReturnType<typeof setInterval> | null = null
  private reconnectTimeoutId: ReturnType<typeof setTimeout> | null = null
  private messageHandlers: Map<string, (message: any) => void> = new Map()
  private connectionStatusHandlers: ((connected: boolean) => void)[] = []

  connect(sessionId: string): Promise<void> {
    return new Promise((resolve) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        if (this.sessionId === sessionId) {
          resolve()
          return
        }
        this.disconnect()
      }

      this.sessionId = sessionId
      const wsUrl = buildWsUrl(sessionId)

      try {
        this.ws = new WebSocket(wsUrl)

        const timeout = setTimeout(() => {
          this.updateConnectionStatus(false)
          resolve()
        }, 5000)

        this.ws.onopen = () => {
          clearTimeout(timeout)
          this.reconnectAttempts = 0
          this.updateConnectionStatus(true)
          this.startPing()
          resolve()
        }

        this.ws.onmessage = (event: MessageEvent) => {
          try {
            const message = JSON.parse(event.data)
            const handler = this.messageHandlers.get(message.type)
            if (handler) handler(message)
          } catch {
            // ignore parse errors
          }
        }

        this.ws.onclose = () => {
          this.stopPing()
          this.updateConnectionStatus(false)
          this.scheduleReconnect()
        }

        this.ws.onerror = () => {
          clearTimeout(timeout)
          this.updateConnectionStatus(false)
          resolve()
        }
      } catch {
        this.updateConnectionStatus(false)
        resolve()
      }
    })
  }

  disconnect() {
    this.stopPing()
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId)
      this.reconnectTimeoutId = null
    }
    if (this.ws) {
      this.ws.onopen = null
      this.ws.onmessage = null
      this.ws.onclose = null
      this.ws.onerror = null
      if (this.ws.readyState === WebSocket.OPEN) this.ws.close()
      this.ws = null
    }
    this.sessionId = null
    this.reconnectAttempts = 0
    this.updateConnectionStatus(false)
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  onMessage<T extends WebSocketMessage>(type: T['type'], handler: (message: T) => void) {
    this.messageHandlers.set(type, handler as (message: any) => void)
  }

  offMessage(type: string) {
    this.messageHandlers.delete(type)
  }

  onConnectionStatus(handler: (connected: boolean) => void) {
    this.connectionStatusHandlers.push(handler)
  }

  offConnectionStatus(handler: (connected: boolean) => void) {
    const idx = this.connectionStatusHandlers.indexOf(handler)
    if (idx > -1) this.connectionStatusHandlers.splice(idx, 1)
  }

  private startPing() {
    this.stopPing()
    this.pingIntervalId = setInterval(() => {
      if (this.isConnected()) {
        this.ws!.send(JSON.stringify({ type: 'ping' }))
      }
    }, 25000)
  }

  private stopPing() {
    if (this.pingIntervalId) {
      clearInterval(this.pingIntervalId)
      this.pingIntervalId = null
    }
  }

  private scheduleReconnect() {
    if (!this.sessionId) return
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return
    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.min(this.reconnectAttempts, 5)
    this.reconnectTimeoutId = setTimeout(() => {
      if (this.sessionId) this.connect(this.sessionId)
    }, delay)
  }

  private updateConnectionStatus(connected: boolean) {
    for (const handler of this.connectionStatusHandlers) {
      try { handler(connected) } catch { /* ignore */ }
    }
  }
}

// Singleton instance
export const liveChartWebSocket = new LiveChartWebSocket()
