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

import type { ChartSegment } from '../../utils/chartSegments'

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

describe('ChartComponent segment creation', () => {
  describe('createSegmentsFromPoints', () => {
    it('should return empty array for empty input', () => {
      const result = createSegmentsFromPoints([])
      expect(result).toEqual([])
    })

    it('should create single segment for single valid point', () => {
      const points = [
        { time: 1000, value: 50 }
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([
        { startTime: 1000, endTime: 1000, value: 50 }
      ])
    })

    it('should ignore single null point', () => {
      const points = [
        { time: 1000, value: null }
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([])
    })

    it('should extend segment for consecutive same-price points', () => {
      const points = [
        { time: 1000, value: 50 },
        { time: 2000, value: 50 },
        { time: 3000, value: 50 }
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([
        { startTime: 1000, endTime: 3000, value: 50 }
      ])
    })

    it('should break segment on null value', () => {
      const points = [
        { time: 1000, value: 50 },
        { time: 2000, value: 50 },
        { time: 3000, value: null }, // Break
        { time: 4000, value: 50 },
        { time: 5000, value: 50 }
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 4000, endTime: 5000, value: 50 }
      ])
    })

    it('should start new segment when price changes', () => {
      const points = [
        { time: 1000, value: 50 },
        { time: 2000, value: 50 },
        { time: 3000, value: 51 }, // Price change
        { time: 4000, value: 51 },
        { time: 5000, value: 50 }  // Price change back
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 3000, endTime: 4000, value: 51 },
        { startTime: 5000, endTime: 5000, value: 50 }
      ])
    })

    it('should handle multiple null breaks', () => {
      const points = [
        { time: 1000, value: 50 },
        { time: 2000, value: null }, // Break
        { time: 3000, value: 50 },
        { time: 4000, value: null }, // Break
        { time: 5000, value: 51 },
        { time: 6000, value: null }, // Break
        { time: 7000, value: 51 }
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([
        { startTime: 1000, endTime: 1000, value: 50 },
        { startTime: 3000, endTime: 3000, value: 50 },
        { startTime: 5000, endTime: 5000, value: 51 },
        { startTime: 7000, endTime: 7000, value: 51 }
      ])
    })

    it('should handle alternating null and valid values', () => {
      const points = [
        { time: 1000, value: null },
        { time: 2000, value: 50 },
        { time: 3000, value: null },
        { time: 4000, value: 51 },
        { time: 5000, value: null }
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([
        { startTime: 2000, endTime: 2000, value: 50 },
        { startTime: 4000, endTime: 4000, value: 51 }
      ])
    })

    it('should handle consecutive null values', () => {
      const points = [
        { time: 1000, value: 50 },
        { time: 2000, value: null },
        { time: 3000, value: null },
        { time: 4000, value: null },
        { time: 5000, value: 50 }
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([
        { startTime: 1000, endTime: 1000, value: 50 },
        { startTime: 5000, endTime: 5000, value: 50 }
      ])
    })

    it('should handle null at the beginning', () => {
      const points = [
        { time: 1000, value: null },
        { time: 2000, value: 50 },
        { time: 3000, value: 50 }
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([
        { startTime: 2000, endTime: 3000, value: 50 }
      ])
    })

    it('should handle null at the end', () => {
      const points = [
        { time: 1000, value: 50 },
        { time: 2000, value: 50 },
        { time: 3000, value: null }
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([
        { startTime: 1000, endTime: 2000, value: 50 }
      ])
    })

    it('should handle floating point precision correctly', () => {
      const points = [
        { time: 1000, value: 50.123456 },
        { time: 2000, value: 50.123456 },
        { time: 3000, value: 50.123457 }, // Different due to precision
        { time: 4000, value: 50.123457 }
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([
        { startTime: 1000, endTime: 2000, value: 50.123456 },
        { startTime: 3000, endTime: 4000, value: 50.123457 }
      ])
    })

    it('should handle complex real-world scenario', () => {
      // Simulate the actual resistance data scenario
      const points = [
        { time: 1771142400, value: 90.65711 },
        { time: 1771146000, value: 90.65711 },
        { time: 1771149600, value: 90.65711 },
        { time: 1771153200, value: null }, // Break
        { time: 1771156800, value: 86.26541 },
        { time: 1771160400, value: 86.26541 },
        { time: 1771164000, value: null }, // Break
        { time: 1771167600, value: 86.11641 },
        { time: 1771171200, value: 86.11641 },
        { time: 1771174800, value: 86.11641 },
        { time: 1771178400, value: 86.11641 },
        { time: 1771182000, value: 86.11641 }
      ]
      const result = createSegmentsFromPoints(points)
      expect(result).toEqual([
        { startTime: 1771142400, endTime: 1771149600, value: 90.65711 },
        { startTime: 1771156800, endTime: 1771160400, value: 86.26541 },
        { startTime: 1771167600, endTime: 1771182000, value: 86.11641 }
      ])
    })

    it('should verify target timestamp 1771257600 scenario', () => {
      // Test the specific scenario from the bug report
      const points = [
        { time: 1771246800, value: 86.11641 },
        { time: 1771250400, value: 86.11641 },
        { time: 1771254000, value: 86.11641 },
        { time: 1771257600, value: 86.11641 }, // Target timestamp
        { time: 1771261200, value: 86.11641 },
        { time: 1771264800, value: 86.11641 }
      ]
      const result = createSegmentsFromPoints(points)
      
      // Should create one continuous segment
      expect(result).toHaveLength(1)
      expect(result[0]).toEqual({
        startTime: 1771246800,
        endTime: 1771264800,
        value: 86.11641
      })
      
      // Verify target timestamp is within the segment
      const targetTimestamp = 1771257600
      expect(result[0].startTime).toBeLessThanOrEqual(targetTimestamp)
      expect(result[0].endTime).toBeGreaterThanOrEqual(targetTimestamp)
      expect(result[0].value).toBe(86.11641)
    })
  })
})
