/**
 * @jest-environment jsdom
 */

// Mock the chart library to avoid dependencies
jest.mock('lightweight-charts', () => ({
  createChart: jest.fn(),
  CandlestickSeries: {},
  BaselineSeries: {},
  LineSeries: {},
  CrosshairMode: {},
  createSeriesMarkers: jest.fn(),
  type: {},
  ISeriesMarkersPluginApi: {},
  SeriesMarker: {},
  IChartApi: {},
  ISeriesApi: {},
  Time: {},
}))

import { mergeOverlappingZones, type ChartSegment } from '../utils/chartSegments'

// Mock API data structure (similar to the real API response)
const mockApiData = {
  symbols: {
    SOLUSD: {
      chartOverlayData: {
        data: {
          SOLUSD: {
            "1770958800": { ema: 79.5061075, support: 76.82309, resistance: 82.08851 },
            "1770962400": { ema: 79.45810225609756, support: 76.82309, resistance: 82.08851 },
            "1770966000": { ema: 79.43029726799524, support: 76.82309, resistance: 82.08851 },
            "1771142400": { ema: 85.12345, support: 84.12345, resistance: 90.65711 },
            "1771146000": { ema: 85.23456, support: 84.23456, resistance: 90.65711 },
            "1771149600": { ema: 85.34567, support: 84.34567, resistance: 90.65711 },
            "1771153200": { ema: 85.45678, support: null, resistance: null }, // Break
            "1771156800": { ema: 85.56789, support: 85.12345, resistance: 86.26541 },
            "1771160400": { ema: 85.67890, support: 85.23456, resistance: 86.26541 },
            "1771164000": { ema: 85.78901, support: null, resistance: null }, // Break
            "1771167600": { ema: 85.89012, support: 84.60749, resistance: 86.11641 },
            "1771171200": { ema: 86.00123, support: 84.60749, resistance: 86.11641 },
            "1771174800": { ema: 86.11234, support: 84.60749, resistance: 86.11641 },
            "1771178400": { ema: 86.22345, support: 84.60749, resistance: 86.11641 },
            "1771182000": { ema: 86.33456, support: 84.60749, resistance: 86.11641 },
            "1771250400": { ema: 85.87259, support: 84.60749, resistance: 86.11641 },
            "1771254000": { ema: 85.73878, support: 84.60749, resistance: 86.11641 },
            "1771257600": { ema: 85.64979685879898, support: 84.60749, resistance: 86.11641 }, // Target
            "1771261200": { ema: 85.59090, support: 83.12959, resistance: 86.11641 },
            "1771264800": { ema: 85.53518, support: 83.12959, resistance: 86.11641 }
          }
        }
      }
    }
  }
}

// Extract the segment creation logic for testing
const createSegmentsFromPoints = (points: { time: number; value: number | null }[]): ChartSegment[] => {
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

describe('Integration Tests - Chart Data Processing', () => {
  describe('Real API Data Processing', () => {
    it('should process resistance data correctly from mock API', () => {
      const symbolData = mockApiData.symbols.SOLUSD.chartOverlayData.data.SOLUSD
      
      // Convert to resistance points (including nulls)
      const resistancePoints = Object.entries(symbolData)
        .map(([timestamp, data]) => ({
          time: parseInt(timestamp),
          value: data.resistance !== undefined && data.resistance !== null ? Number(data.resistance) : null
        }))
        .filter(p => p.time && (p.value === null || Number.isFinite(p.value)))
        .sort((a, b) => a.time - b.time)
      
      // Create segments
      const segments = createSegmentsFromPoints(resistancePoints)
      
      // Should create multiple segments based on null breaks and price changes
      expect(segments.length).toBeGreaterThan(1)
      
      // Check that we have the expected resistance levels
      const resistanceValues = segments.map(s => s.value)
      expect(resistanceValues).toContain(82.08851)
      expect(resistanceValues).toContain(90.65711)
      expect(resistanceValues).toContain(86.26541)
      expect(resistanceValues).toContain(86.11641)
    })

    it('should process support data correctly from mock API', () => {
      const symbolData = mockApiData.symbols.SOLUSD.chartOverlayData.data.SOLUSD
      
      // Convert to support points (including nulls)
      const supportPoints = Object.entries(symbolData)
        .map(([timestamp, data]) => ({
          time: parseInt(timestamp),
          value: data.support !== undefined && data.support !== null ? Number(data.support) : null
        }))
        .filter(p => p.time && (p.value === null || Number.isFinite(p.value)))
        .sort((a, b) => a.time - b.time)
      
      // Create segments
      const segments = createSegmentsFromPoints(supportPoints)
      
      // Should create multiple segments based on null breaks and price changes
      expect(segments.length).toBeGreaterThan(1)
      
      // Check that we have the expected support levels
      const supportValues = segments.map(s => s.value)
      expect(supportValues).toContain(76.82309)
      expect(supportValues).toContain(84.12345)
      expect(supportValues).toContain(85.12345)
      expect(supportValues).toContain(84.60749)
      expect(supportValues).toContain(83.12959)
    })

    it('should correctly handle the target timestamp scenario', () => {
      const targetTimestamp = 1771257600
      const symbolData = mockApiData.symbols.SOLUSD.chartOverlayData.data.SOLUSD
      
      // Process resistance data
      const resistancePoints = Object.entries(symbolData)
        .map(([timestamp, data]) => ({
          time: parseInt(timestamp),
          value: data.resistance !== undefined && data.resistance !== null ? Number(data.resistance) : null
        }))
        .filter(p => p.time && (p.value === null || Number.isFinite(p.value)))
        .sort((a, b) => a.time - b.time)
      
      const resistanceSegments = createSegmentsFromPoints(resistancePoints)
      
      // Find segment containing target timestamp
      const targetSegment = resistanceSegments.find(seg => 
        seg.startTime <= targetTimestamp && seg.endTime >= targetTimestamp
      )
      
      expect(targetSegment).toBeDefined()
      expect(targetSegment!.value).toBe(86.11641)
      expect(targetSegment!.startTime).toBeLessThanOrEqual(targetTimestamp)
      expect(targetSegment!.endTime).toBeGreaterThanOrEqual(targetTimestamp)
      
      // Verify the segment spans the expected range
      expect(targetSegment!.startTime).toBe(1771167600)
      expect(targetSegment!.endTime).toBe(1771264800)
    })

    it('should handle null breaks correctly', () => {
      const symbolData = mockApiData.symbols.SOLUSD.chartOverlayData.data.SOLUSD
      
      // Find timestamps with null resistance
      const nullTimestamps = Object.entries(symbolData)
        .filter(([_, data]) => data.resistance === null)
        .map(([timestamp, _]) => parseInt(timestamp))
      
      expect(nullTimestamps).toContain(1771153200)
      expect(nullTimestamps).toContain(1771164000)
      
      // Process resistance data
      const resistancePoints = Object.entries(symbolData)
        .map(([timestamp, data]) => ({
          time: parseInt(timestamp),
          value: data.resistance !== undefined && data.resistance !== null ? Number(data.resistance) : null
        }))
        .filter(p => p.time && (p.value === null || Number.isFinite(p.value)))
        .sort((a, b) => a.time - b.time)
      
      const segments = createSegmentsFromPoints(resistancePoints)
      
      // Verify that segments are broken at null points
      // The segment before 1771153200 should end before or at that point
      const segmentBeforeNull1 = segments.find(seg => seg.endTime <= 1771153200)
      expect(segmentBeforeNull1).toBeDefined()
      expect(segmentBeforeNull1!.value).toBe(82.08851)
      
      // The segment after 1771153200 should start after that point
      const segmentAfterNull1 = segments.find(seg => seg.startTime > 1771153200)
      expect(segmentAfterNull1).toBeDefined()
      expect(segmentAfterNull1!.value).toBe(86.26541)
    })

    it('should merge overlapping zones correctly', () => {
      // Create test segments that should be merged
      const testSegments: ChartSegment[] = [
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 1500, endTime: 2500, value: 50 }, // Overlaps with first
        { startTime: 3000, endTime: 4000, value: 50 }, // Separate
        { startTime: 3500, endTime: 4500, value: 51 }, // Different price
        { startTime: 5000, endTime: 6000, value: 50 }  // Separate from first group
      ]
      
      const merged = mergeOverlappingZones(testSegments)
      
      // Should merge overlapping segments with same price
      expect(merged).toEqual([
        { startTime: 1000, endTime: 2500, value: 50 }, // First two merged
        { startTime: 3000, endTime: 4000, value: 50 }, // Separate
        { startTime: 5000, endTime: 6000, value: 50 },  // Separate
        { startTime: 3500, endTime: 4500, value: 51 }  // Different price, unchanged
      ])
    })

    it('should handle edge cases in real data', () => {
      const symbolData = mockApiData.symbols.SOLUSD.chartOverlayData.data.SOLUSD
      
      // Test with empty data
      const emptyResult = createSegmentsFromPoints([])
      expect(emptyResult).toEqual([])
      
      // Test with all null values
      const allNullPoints = Object.entries(symbolData)
        .map(([timestamp, _]) => ({ time: parseInt(timestamp), value: null }))
        .slice(0, 5)
      
      const allNullResult = createSegmentsFromPoints(allNullPoints)
      expect(allNullResult).toEqual([])
      
      // Test with single valid point
      const singlePoint = [{ time: 1000, value: 50 }]
      const singleResult = createSegmentsFromPoints(singlePoint)
      expect(singleResult).toEqual([
        { startTime: 1000, endTime: 1000, value: 50 }
      ])
    })
  })

  describe('Performance Tests', () => {
    it('should handle large datasets efficiently', () => {
      // Create a large dataset (1000 points)
      const largeDataset: { time: number; value: number | null }[] = []
      const startTime = 1600000000
      
      for (let i = 0; i < 1000; i++) {
        largeDataset.push({
          time: startTime + (i * 3600), // 1 hour intervals
          value: i % 100 === 0 ? null : 50 + (i % 10) // Some nulls, varying values
        })
      }
      
      const start = performance.now()
      const segments = createSegmentsFromPoints(largeDataset)
      const end = performance.now()
      
      // Should complete in reasonable time (< 100ms)
      expect(end - start).toBeLessThan(100)
      expect(segments.length).toBeGreaterThan(0)
    })
  })
})
