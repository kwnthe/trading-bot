import {
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts'
import { toTime } from './timeSeries'
import { mergeOverlappingZones, type ChartSegment } from './chartSegments'
import { type ChartManager } from './ChartManager'

export interface ResistanceSupportPoint {
  time: number
  value: number | null
}

export interface ProcessedChartData {
  resistanceSegments: ChartSegment[]
  supportSegments: ChartSegment[]
  resistancePoints: ResistanceSupportPoint[]
  supportPoints: ResistanceSupportPoint[]
}

export interface ChartZoneManagerConfig {
  debugMode?: boolean
  targetTimestamp?: number
  onDebugInfo?: (info: {
    resistancePoint: ResistanceSupportPoint | null
    supportPoint: ResistanceSupportPoint | null
    resistanceSegment: ChartSegment | null
    supportSegment: ChartSegment | null
  }) => void
}

/**
 * Process raw chart data into segments and points
 * @param symbolData Raw symbol data from API
 * @returns Processed chart data with segments and points
 */
export function processChartData(symbolData: Record<string, any>): ProcessedChartData {
  // Convert to resistance points (including nulls)
  const resistancePoints: ResistanceSupportPoint[] = Object.entries(symbolData)
    .map(([timestamp, data]: [string, any]) => ({
      time: parseInt(timestamp),
      value: data.resistance !== undefined && data.resistance !== null ? Number(data.resistance) : null
    }))
    .filter(p => p.time && (p.value === null || Number.isFinite(p.value)))
  
  // Convert to support points (including nulls)
  const supportPoints: ResistanceSupportPoint[] = Object.entries(symbolData)
    .map(([timestamp, data]: [string, any]) => ({
      time: parseInt(timestamp),
      value: data.support !== undefined && data.support !== null ? Number(data.support) : null
    }))
    .filter(p => p.time && (p.value === null || Number.isFinite(p.value)))
  
  // Sort by time to ensure chronological processing
  resistancePoints.sort((a, b) => a.time - b.time)
  supportPoints.sort((a, b) => a.time - b.time)
  
  // Create segments that respect null breaks
  const resistanceSegments = createSegmentsFromPoints(resistancePoints)
  const supportSegments = createSegmentsFromPoints(supportPoints)
  
  return {
    resistanceSegments,
    supportSegments,
    resistancePoints,
    supportPoints
  }
}

/**
 * Create segments from points respecting null breaks and same-price continuity
 * @param points Array of points with timestamps and values
 * @returns Array of chart segments
 */
export function createSegmentsFromPoints(points: ResistanceSupportPoint[]): ChartSegment[] {
  const segments: ChartSegment[] = []
  let currentSegment: ChartSegment | null = null
  
  for (const point of points) {
    if (point.value === null) {
      // Null value breaks the line - end current segment if exists
      if (currentSegment) {
        segments.push(currentSegment)
        currentSegment = null
      }
    } else {
      // Valid resistance/support value
      if (currentSegment === null) {
        // Start new segment
        currentSegment = {
          startTime: point.time,
          endTime: point.time,
          value: point.value
        }
      } else if (currentSegment.value === point.value) {
        // Same price - extend the segment
        currentSegment.endTime = point.time
      } else {
        // Different price - end current segment and start new one
        segments.push(currentSegment)
        currentSegment = {
          startTime: point.time,
          endTime: point.time,
          value: point.value
        }
      }
    }
  }
  
  // Don't forget the last segment
  if (currentSegment) {
    segments.push(currentSegment)
  }
  
  return segments
}

/**
 * Find a segment containing a specific timestamp
 * @param segments Array of segments to search
 * @param timestamp Target timestamp
 * @returns Segment containing the timestamp or null
 */
export function findSegmentByTimestamp(segments: ChartSegment[], timestamp: number): ChartSegment | null {
  return segments.find(seg => seg.startTime <= timestamp && seg.endTime >= timestamp) || null
}

/**
 * Get debug information for a specific timestamp
 * @param processedData Processed chart data
 * @param timestamp Target timestamp
 * @returns Debug information
 */
export function getDebugInfo(processedData: ProcessedChartData, timestamp: number): {
  resistancePoint: ResistanceSupportPoint | null
  supportPoint: ResistanceSupportPoint | null
  resistanceSegment: ChartSegment | null
  supportSegment: ChartSegment | null
} {
  const resistancePoint = processedData.resistancePoints.find(p => p.time === timestamp) || null
  const supportPoint = processedData.supportPoints.find(p => p.time === timestamp) || null
  const resistanceSegment = findSegmentByTimestamp(processedData.resistanceSegments, timestamp)
  const supportSegment = findSegmentByTimestamp(processedData.supportSegments, timestamp)
  
  return {
    resistancePoint,
    supportPoint,
    resistanceSegment,
    supportSegment
  }
}

export interface ZoneRenderStats {
  resistanceCount: number
  supportCount: number
  totalCount: number
  skippedCount?: number
}

/**
 * ChartZoneManager - Responsible for managing resistance/support zones
 * Handles data processing, segment creation, and rendering in both debug and production modes
 */
export class ChartZoneManager implements ChartManager {
  private chart: IChartApi
  private zoneSeriesRef: React.MutableRefObject<ISeriesApi<'Line'>[]>
  private config: ChartZoneManagerConfig
  private processedData: ProcessedChartData | null = null

  constructor(
    chart: IChartApi,
    zoneSeriesRef: React.MutableRefObject<ISeriesApi<'Line'>[]>,
    config: ChartZoneManagerConfig = {}
  ) {
    this.chart = chart
    this.zoneSeriesRef = zoneSeriesRef
    this.config = {
      debugMode: false,
      ...config
    }
  }

  /**
   * Get the data keys this manager needs from symbolData
   * @returns Array of data keys required by this manager
   */
  public getDataKeys(): string[] {
    return ['resistance', 'support']
  }

  /**
   * Process raw chart data into segments and points
   * @param symbolData Raw symbol data from API
   */
  public processData(symbolData: Record<string, any>): void {
    this.processedData = processChartData(symbolData)
    
    // Debug mode: Log target timestamp information
    if (this.config.debugMode && this.config.targetTimestamp) {
      const debugInfo = getDebugInfo(this.processedData, this.config.targetTimestamp)
      if (this.config.onDebugInfo) {
        this.config.onDebugInfo(debugInfo)
      }
      
      if (debugInfo.resistancePoint) {
        console.log(`🎯 DEBUG: Found target timestamp ${this.config.targetTimestamp} with resistance: ${debugInfo.resistancePoint.value}`)
      }
    }
  }

  /**
   * Render zones based on current mode (debug or production)
   * @returns Zone rendering statistics
   */
  public render(): ZoneRenderStats {
    if (!this.processedData) {
      throw new Error('No data processed. Call processData() first.')
    }

    if (this.config.debugMode) {
      return this.renderDebugVisualization()
    } else {
      return this.renderAggregatedZones()
    }
  }

  /**
   * Clear all rendered zones
   */
  public clear(): void {
    this.zoneSeriesRef.current.forEach(series => {
      try {
        this.chart.removeSeries(series)
      } catch (error) {
        console.warn('Failed to remove zone series:', error)
      }
    })
    this.zoneSeriesRef.current = []
  }

  /**
   * Get the name/type of the manager
   * @returns Manager name
   */
  public getName(): string {
    return 'ChartZoneManager'
  }

  /**
   * Get processed data for external access
   * @returns Processed chart data or null if not processed
   */
  public getProcessedData(): ProcessedChartData | null {
    return this.processedData
  }

  /**
   * Get debug information for a specific timestamp
   * @param timestamp Target timestamp
   * @returns Debug information
   */
  public getDebugInfo(timestamp: number): {
    resistancePoint: ResistanceSupportPoint | null
    supportPoint: ResistanceSupportPoint | null
    resistanceSegment: ChartSegment | null
    supportSegment: ChartSegment | null
  } {
    if (!this.processedData) {
      throw new Error('No data processed. Call processData() first.')
    }
    return getDebugInfo(this.processedData, timestamp)
  }

  /**
   * Clear all rendered zones
   */
  public clearZones(): void {
    this.zoneSeriesRef.current.forEach(series => {
      try {
        this.chart.removeSeries(series)
      } catch (error) {
        console.warn('Failed to remove zone series:', error)
      }
    })
    this.zoneSeriesRef.current = []
  }

  /**
   * Toggle debug mode
   * @param enabled Whether debug mode should be enabled
   */
  public setDebugMode(enabled: boolean): void {
    this.config.debugMode = enabled
  }

  /**
   * Check if debug mode is enabled
   * @returns True if debug mode is enabled
   */
  public isDebugMode(): boolean {
    return this.config.debugMode || false
  }

  /**
   * Render individual resistance/support points as circles (debug mode)
   * @private
   */
  private renderDebugVisualization(): ZoneRenderStats {
    if (!this.processedData) {
      throw new Error('No data processed. Call processData() first.')
    }

    console.log('🐛 DEBUG: Showing individual resistance/support points as circles')
    
    const resistanceCount = this.renderDebugPoints(
      this.processedData.resistancePoints, 
      'rgba(239, 83, 80, 0.8)', 
      'resistance'
    )
    
    const supportCount = this.renderDebugPoints(
      this.processedData.supportPoints, 
      'rgba(33, 150, 243, 0.8)', 
      'support'
    )
    
    const totalCount = resistanceCount + supportCount
    
    console.log(`🐛 DEBUG: Rendered ${resistanceCount} resistance points and ${supportCount} support points as circles`)
    
    return { resistanceCount, supportCount, totalCount }
  }

  /**
   * Render aggregated resistance/support zones (production mode)
   * @private
   */
  private renderAggregatedZones(): ZoneRenderStats {
    if (!this.processedData) {
      throw new Error('No data processed. Call processData() first.')
    }

    let zonesRendered = 0
    let zonesSkipped = 0
    
    // Merge overlapping zones to prevent rendering conflicts
    const mergedResistanceSegments = mergeOverlappingZones(this.processedData.resistanceSegments)
    const mergedSupportSegments = mergeOverlappingZones(this.processedData.supportSegments)
    
    // Sort resistance segments by value to ensure consistent rendering order
    // Lower values (closer to current price) should be rendered last to appear on top
    mergedResistanceSegments.sort((a, b) => Number(b.value) - Number(a.value))
    
    // Render resistance zones
    zonesRendered += this.renderZoneSegments(mergedResistanceSegments, 'rgba(239, 83, 80, 0.95)')
    
    // Render support zones
    zonesRendered += this.renderZoneSegments(mergedSupportSegments, 'rgba(33, 150, 243, 0.95)')
    
    return { 
      resistanceCount: mergedResistanceSegments.length, 
      supportCount: mergedSupportSegments.length, 
      totalCount: zonesRendered, 
      skippedCount: zonesSkipped 
    }
  }

  /**
   * Render zone segments with given color
   * @param segments Array of segments to render
   * @param color Color for the zones
   * @private
   */
  private renderZoneSegments(segments: ChartSegment[], color: string): number {
    let zonesRendered = 0
    
    for (const seg of segments) {
      const val = Number(seg.value)
      const s = toTime(seg.startTime)
      const e = toTime(seg.endTime)
      
      if (s && e && Number.isFinite(val) && s !== e) {
        const zone = this.chart.addSeries(LineSeries, { 
          color, 
          lineWidth: 3, 
          priceLineVisible: false, 
          lastValueVisible: false 
        })
        const zoneData = [{ time: s as Time, value: val }, { time: e as Time, value: val }]
        
        zone.setData(zoneData)
        this.zoneSeriesRef.current.push(zone)
        zonesRendered++
      }
    }
    
    return zonesRendered
  }

  /**
   * Render individual points as circles
   * @param points Array of points to render
   * @param color Color for the points
   * @param label Label for logging
   * @private
   */
  private renderDebugPoints(points: ResistanceSupportPoint[], color: string, label: string): number {
    let pointsRendered = 0
    
    points.forEach(point => {
      if (point.value !== null) {
        const time = toTime(point.time)
        if (time && Number.isFinite(point.value)) {
          const zone = this.chart.addSeries(LineSeries, { 
            color, 
            lineWidth: 2, 
            lineVisible: false, // Hide the line
            pointMarkersVisible: true, // Show points as circles
            pointMarkersRadius: 4,
            priceLineVisible: false, 
            lastValueVisible: false 
          })
          const zoneData = [{ time: time as Time, value: Number(point.value) }]
          
          zone.setData(zoneData)
          this.zoneSeriesRef.current.push(zone)
          pointsRendered++
          
          // Log the specific point we're rendering
          if (this.config.targetTimestamp && point.time === this.config.targetTimestamp) {
            console.log(`🎯 DEBUG: Rendering target timestamp ${point.time} -> ${label}: ${point.value}`)
          }
        }
      }
    })
    
    return pointsRendered
  }
}
