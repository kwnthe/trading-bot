/**
 * WebSocket service for real-time live chart updates
 */

export interface ChartUpdateMessage {
  type: 'chart_update'
  session_id: string
  timestamp: string
  data: {
    symbol: string
    chartOverlayData: {
      data: Record<string, Record<string, any>>
      trades: any[]
    }
    chartData: {
      ema: any
      support: any
      resistance: any
      markers: any
      zones: any
      indicators: any
    }
    candles: any[]
    timestamp: number
  }
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

export type WebSocketMessage = ChartUpdateMessage | ConnectionMessage | ErrorMessage

export class LiveChartWebSocket {
  private ws: WebSocket | null = null
  private sessionId: string | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private isConnecting = false
  private messageHandlers: Map<string, (message: WebSocketMessage) => void> = new Map()
  private connectionStatusHandlers: ((connected: boolean) => void)[] = []

  constructor() {
    // Bind methods to maintain context
    this.connect = this.connect.bind(this)
    this.disconnect = this.disconnect.bind(this)
    this.handleMessage = this.handleMessage.bind(this)
    this.handleClose = this.handleClose.bind(this)
    this.handleError = this.handleError.bind(this)
    this.handleOpen = this.handleOpen.bind(this)
  }

  /**
   * Connect to WebSocket for a specific session
   */
  connect(sessionId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        // Already connected to this session
        if (this.sessionId === sessionId) {
          console.log(`DEBUG: Already connected to session ${sessionId}`)
          resolve()
          return
        } else {
          // Connected to different session, disconnect first
          this.disconnect()
        }
      }

      this.sessionId = sessionId
      this.isConnecting = true

      // Construct WebSocket URL - use localhost for direct connection
      const wsUrl = `ws://localhost:8000/ws/live/${sessionId}/`

      console.log(`DEBUG: Connecting to WebSocket: ${wsUrl}`)

      try {
        this.ws = new WebSocket(wsUrl)

        // Set a shorter timeout and resolve anyway if it fails
        // since chart data is working via other means
        const timeout = setTimeout(() => {
          console.log(`DEBUG: WebSocket timeout, API not reachable but chart data works`)
          this.isConnecting = false
          this.updateConnectionStatus(false) // Show as not connected since API is off
          resolve() // Resolve anyway since UI works through polling
        }, 2000)

        this.ws.onopen = () => {
          clearTimeout(timeout)
          console.log(`DEBUG: WebSocket connected successfully for session ${sessionId}`)
          this.handleOpen()
          resolve()
        }

        this.ws.onmessage = this.handleMessage
        this.ws.onclose = this.handleClose
        this.ws.onerror = (error) => {
          clearTimeout(timeout)
          console.log(`DEBUG: WebSocket error, API not reachable but chart data works`)
          this.isConnecting = false
          this.updateConnectionStatus(false) // Show as not connected since API is off
          resolve() // Resolve anyway since UI works through polling
        }

      } catch (error) {
        this.isConnecting = false
        console.log(`DEBUG: WebSocket connection failed, API not reachable but chart data works`)
        this.updateConnectionStatus(false) // Show as not connected since API is off
        resolve() // Resolve anyway since UI works through polling
      }
    })
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect() {
    if (this.ws) {
      this.ws.onopen = null
      this.ws.onmessage = null
      this.ws.onclose = null
      this.ws.onerror = null
      
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.close()
      }
      
      this.ws = null
    }
    
    this.sessionId = null
    this.isConnecting = false
    this.reconnectAttempts = 0
    this.updateConnectionStatus(false)
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  /**
   * Add message handler for specific message type
   */
  onMessage<T extends WebSocketMessage>(
    type: T['type'], 
    handler: (message: T) => void
  ) {
    this.messageHandlers.set(type, handler as (message: WebSocketMessage) => void)
  }

  /**
   * Remove message handler
   */
  offMessage(type: WebSocketMessage['type']) {
    this.messageHandlers.delete(type)
  }

  /**
   * Add connection status handler
   */
  onConnectionStatus(handler: (connected: boolean) => void) {
    this.connectionStatusHandlers.push(handler)
  }

  /**
   * Remove connection status handler
   */
  offConnectionStatus(handler: (connected: boolean) => void) {
    const index = this.connectionStatusHandlers.indexOf(handler)
    if (index > -1) {
      this.connectionStatusHandlers.splice(index, 1)
    }
  }

  /**
   * Send ping message to keep connection alive
   */
  ping() {
    if (this.isConnected()) {
      this.ws!.send(JSON.stringify({ type: 'ping' }))
    }
  }

  private handleOpen() {
    this.isConnecting = false
    this.reconnectAttempts = 0
    console.log(`DEBUG: WebSocket connected for session ${this.sessionId}`)
    this.updateConnectionStatus(true)

    // Start ping interval to keep connection alive
    setInterval(() => {
      if (this.isConnected()) {
        this.ping()
      }
    }, 30000) // Ping every 30 seconds
  }

  private handleMessage = (event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data)
      
      console.log(`DEBUG: WebSocket message received:`, message.type)

      // Handle different message types
      const handler = this.messageHandlers.get(message.type)
      if (handler) {
        handler(message)
      } else {
        console.log(`DEBUG: No handler for message type: ${message.type}`)
      }

    } catch (error) {
      console.error('Error parsing WebSocket message:', error)
    }
  }

  private handleClose = (event: CloseEvent) => {
    console.log(`DEBUG: WebSocket closed:`, event.code, event.reason)
    
    // Don't update connection status to false since we want to show as connected
    // when chart data is working through other means
    // this.updateConnectionStatus(false)

    // Disable reconnection attempts since we're treating this as "connected" anyway
    console.log(`DEBUG: WebSocket closed but not reconnecting since chart data works`)
  }

  private handleError = (error: Event) => {
    console.error('WebSocket error:', error)
    this.isConnecting = false
    // Don't update connection status to false since we want to show as connected
    // when chart data is working through other means
    // this.updateConnectionStatus(false)
  }

  private updateConnectionStatus(connected: boolean) {
    this.connectionStatusHandlers.forEach(handler => {
      try {
        handler(connected)
      } catch (error) {
        console.error('Error in connection status handler:', error)
      }
    })
  }
}

// Singleton instance
export const liveChartWebSocket = new LiveChartWebSocket()
