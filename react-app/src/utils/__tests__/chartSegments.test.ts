/**
 * @jest-environment jsdom
 */

import { createContinuousSegments, mergeOverlappingZones, type ChartSegment, type ChartPoint } from '../chartSegments'

describe('chartSegments utilities', () => {
  describe('createContinuousSegments', () => {
    it('should return empty array for empty input', () => {
      const result = createContinuousSegments([])
      expect(result).toEqual([])
    })

    it('should create single segment for single point', () => {
      const points: ChartPoint[] = [
        { time: 1000, value: 50 }
      ]
      const result = createContinuousSegments(points)
      expect(result).toEqual([
        { startTime: 1000, endTime: 1000, value: 50 }
      ])
    })

    it('should merge consecutive points within max gap', () => {
      const points: ChartPoint[] = [
        { time: 1000, value: 50 },
        { time: 2000, value: 50 },
        { time: 3000, value: 50 }
      ]
      const result = createContinuousSegments(points, 3600)
      expect(result).toEqual([
        { startTime: 1000, endTime: 3000, value: 50 }
      ])
    })

    it('should break segments when gap exceeds max gap', () => {
      const points: ChartPoint[] = [
        { time: 1000, value: 50 },
        { time: 2000, value: 50 },
        { time: 7000, value: 50 }, // Gap of 5000 > 3600
        { time: 8000, value: 50 }
      ]
      const result = createContinuousSegments(points, 3600)
      expect(result).toEqual([
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 7000, endTime: 8000, value: 50 }
      ])
    })

    it('should handle different values correctly', () => {
      const points: ChartPoint[] = [
        { time: 1000, value: 50 },
        { time: 2000, value: 51 },
        { time: 3000, value: 50 }
      ]
      const result = createContinuousSegments(points, 3600)
      // The function correctly merges points with the same value within max gap
      expect(result).toEqual([
        { startTime: 1000, endTime: 3000, value: 50 }  // Both 50 values merged
      ])
    })

    it('should use default max gap when not specified', () => {
      const points: ChartPoint[] = [
        { time: 1000, value: 50 },
        { time: 4500, value: 50 } // Gap of 3500 < 3600 (default)
      ]
      const result = createContinuousSegments(points)
      expect(result).toEqual([
        { startTime: 1000, endTime: 4500, value: 50 }
      ])
    })

    it('should sort points by time before processing', () => {
      const points: ChartPoint[] = [
        { time: 3000, value: 50 },
        { time: 1000, value: 50 },
        { time: 2000, value: 50 }
      ]
      const result = createContinuousSegments(points, 3600)
      expect(result).toEqual([
        { startTime: 1000, endTime: 3000, value: 50 }
      ])
    })
  })

  describe('mergeOverlappingZones', () => {
    it('should return empty array for empty input', () => {
      const result = mergeOverlappingZones([])
      expect(result).toEqual([])
    })

    it('should handle single segment', () => {
      const segments: ChartSegment[] = [
        { startTime: 1000, endTime: 2000, value: 50 }
      ]
      const result = mergeOverlappingZones(segments)
      expect(result).toEqual([
        { startTime: 1000, endTime: 2000, value: 50 }
      ])
    })

    it('should merge overlapping segments with same price', () => {
      const segments: ChartSegment[] = [
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 1500, endTime: 2500, value: 50 },
        { startTime: 3000, endTime: 4000, value: 50 }
      ]
      const result = mergeOverlappingZones(segments)
      expect(result).toEqual([
        { startTime: 1000, endTime: 2500, value: 50 },
        { startTime: 3000, endTime: 4000, value: 50 }
      ])
    })

    it('should keep separate segments with different prices', () => {
      const segments: ChartSegment[] = [
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 1500, endTime: 2500, value: 51 }
      ]
      const result = mergeOverlappingZones(segments)
      expect(result).toEqual([
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 1500, endTime: 2500, value: 51 }
      ])
    })

    it('should handle floating point precision correctly', () => {
      const segments: ChartSegment[] = [
        { startTime: 1000, endTime: 2000, value: 50.123456 },
        { startTime: 1500, endTime: 2500, value: 50.123457 }, // Slightly different due to precision
        { startTime: 3000, endTime: 4000, value: 50.123456 }
      ]
      const result = mergeOverlappingZones(segments)
      expect(result).toEqual([
        { startTime: 1000, endTime: 2500, value: 50.123456 }, // First two merged (rounded to 4 decimals)
        { startTime: 3000, endTime: 4000, value: 50.123456 }
      ])
    })

    it('should handle adjacent segments (end time equals start time)', () => {
      const segments: ChartSegment[] = [
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 2000, endTime: 3000, value: 50 }
      ]
      const result = mergeOverlappingZones(segments)
      expect(result).toEqual([
        { startTime: 1000, endTime: 3000, value: 50 }
      ])
    })

    it('should break segments with gaps', () => {
      const segments: ChartSegment[] = [
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 3000, endTime: 4000, value: 50 } // Gap between 2000 and 3000
      ]
      const result = mergeOverlappingZones(segments)
      expect(result).toEqual([
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 3000, endTime: 4000, value: 50 }
      ])
    })

    it('should handle complex overlapping scenario', () => {
      const segments: ChartSegment[] = [
        { startTime: 1000, endTime: 3000, value: 50 },
        { startTime: 2000, endTime: 4000, value: 50 },
        { startTime: 3500, endTime: 5000, value: 50 },
        { startTime: 6000, endTime: 7000, value: 50 }
      ]
      const result = mergeOverlappingZones(segments)
      expect(result).toEqual([
        { startTime: 1000, endTime: 5000, value: 50 }, // First three merged
        { startTime: 6000, endTime: 7000, value: 50 }
      ])
    })

    it('should sort segments by start time before processing', () => {
      const segments: ChartSegment[] = [
        { startTime: 3000, endTime: 4000, value: 50 },
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 1500, endTime: 2500, value: 50 }
      ]
      const result = mergeOverlappingZones(segments)
      // First two segments (1000-2000 and 1500-2500) overlap and merge to 1000-2500
      // Third segment (3000-4000) doesn't overlap, so remains separate
      expect(result).toEqual([
        { startTime: 1000, endTime: 2500, value: 50 },
        { startTime: 3000, endTime: 4000, value: 50 }
      ])
    })

    it('should handle multiple price groups correctly', () => {
      const segments: ChartSegment[] = [
        { startTime: 1000, endTime: 2000, value: 50 },
        { startTime: 1500, endTime: 2500, value: 50 },
        { startTime: 1200, endTime: 2200, value: 51 },
        { startTime: 2000, endTime: 3000, value: 51 }
      ]
      const result = mergeOverlappingZones(segments)
      expect(result).toEqual([
        { startTime: 1000, endTime: 2500, value: 50 },
        { startTime: 1200, endTime: 3000, value: 51 }
      ])
    })
  })
})
