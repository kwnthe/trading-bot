/**
 * Chart segment utilities for converting points to continuous segments
 */

export interface ChartPoint {
  time: number
  value: number
}

export interface ChartSegment {
  startTime: number
  endTime: number
  value: number
}

/**
 * Convert discrete points to continuous segments by merging consecutive points at the same price level
 * @param points Array of chart points with time and value
 * @param maxGapSeconds Maximum time gap between points to consider them continuous (default: 3600 for H1 data)
 * @returns Array of continuous segments
 */
export function createContinuousSegments(points: ChartPoint[], maxGapSeconds: number = 3600): ChartSegment[] {
  if (points.length === 0) return []
  
  // Sort points by time
  points.sort((a, b) => a.time - b.time)
  
  const segments: ChartSegment[] = []
  let currentSegment: ChartSegment = {
    startTime: points[0].time,
    endTime: points[0].time,
    value: points[0].value
  }
  
  for (let i = 1; i < points.length; i++) {
    const nextPoint = points[i]
    const timeGap = nextPoint.time - currentSegment.endTime
    
    // If the gap is small (within reasonable timeframe), extend the segment
    if (timeGap <= maxGapSeconds) {
      currentSegment.endTime = nextPoint.time
    } else {
      // Gap is too large, start a new segment
      segments.push(currentSegment)
      currentSegment = {
        startTime: nextPoint.time,
        endTime: nextPoint.time,
        value: nextPoint.value
      }
    }
  }
  
  segments.push(currentSegment)
  return segments
}

/**
 * Merge overlapping segments at the same price level to prevent rendering conflicts
 * @param segments Array of chart segments
 * @returns Array of merged segments
 */
export function mergeOverlappingZones(segments: ChartSegment[]): ChartSegment[] {
  const priceGroups = new Map<number, ChartSegment[]>()
  
  // Group segments by price value
  segments.forEach(seg => {
    const price = Number(seg.value)
    if (!priceGroups.has(price)) {
      priceGroups.set(price, [])
    }
    priceGroups.get(price)!.push(seg)
  })
  
  const mergedSegments: ChartSegment[] = []
  
  // Merge overlapping segments within each price group
  for (const [, group] of priceGroups.entries()) {
    if (group.length === 0) continue
    
    // Sort by start time
    group.sort((a, b) => a.startTime - b.startTime)
    
    let current: ChartSegment = {
      startTime: group[0].startTime,
      endTime: group[0].endTime,
      value: group[0].value
    }
    
    for (let i = 1; i < group.length; i++) {
      const next = group[i]
      
      // Check if segments overlap or are adjacent
      if (next.startTime <= current.endTime) {
        // Merge them - extend the end time if needed
        current = {
          startTime: current.startTime,
          endTime: Math.max(current.endTime, next.endTime),
          value: current.value
        }
      } else {
        // No overlap, push current and start new one
        mergedSegments.push(current)
        current = {
          startTime: next.startTime,
          endTime: next.endTime,
          value: next.value
        }
      }
    }
    
    // Push the last merged segment
    mergedSegments.push(current)
  }
  
  return mergedSegments
}
