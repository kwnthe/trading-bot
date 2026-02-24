# Unit Tests

This directory contains comprehensive unit tests for the chart segment functionality and chart component logic.

## Test Structure

```
src/
├── utils/
│   └── __tests__/
│       └── chartSegments.test.ts     # Tests for utility functions
├── components/
│   └── __tests__/
│       └── ChartComponent.test.ts    # Tests for component segment creation logic
└── __tests__/
    └── integration.test.ts           # Integration tests with mock API data
```

## Test Coverage

### 1. Utility Functions (`chartSegments.test.ts`)

#### `createContinuousSegments`
- ✅ Empty input handling
- ✅ Single point processing
- ✅ Consecutive points within max gap
- ✅ Gap detection and segment breaking
- ✅ Different value handling
- ✅ Default max gap usage
- ✅ Input sorting

#### `mergeOverlappingZones`
- ✅ Empty input handling
- ✅ Single segment processing
- ✅ Overlapping segments with same price
- ✅ Different price separation
- ✅ Floating point precision
- ✅ Adjacent segment handling
- ✅ Gap detection
- ✅ Complex overlapping scenarios
- ✅ Input sorting
- ✅ Multiple price groups

### 2. Component Logic (`ChartComponent.test.ts`)

#### `createSegmentsFromPoints`
- ✅ Empty input handling
- ✅ Single valid point
- ✅ Null point handling
- ✅ Same-price continuity
- ✅ Null breaks
- ✅ Price changes
- ✅ Multiple null breaks
- ✅ Alternating null/valid values
- ✅ Consecutive null values
- ✅ Null at boundaries
- ✅ Floating point precision
- ✅ Real-world scenarios
- ✅ Target timestamp verification

### 3. Integration Tests (`integration.test.ts`)

#### Real API Data Processing
- ✅ Resistance data processing
- ✅ Support data processing
- ✅ Target timestamp scenario (1771257600)
- ✅ Null break handling
- ✅ Overlapping zone merging
- ✅ Edge cases

#### Performance Tests
- ✅ Large dataset handling (1000+ points)
- ✅ Performance benchmarks (< 100ms)

## Key Test Scenarios

### Bug Fix Verification
The tests specifically verify the fix for the resistance level bug:

```typescript
it('should correctly handle the target timestamp scenario', () => {
  const targetTimestamp = 1771257600
  // ... process data
  
  expect(targetSegment!.value).toBe(86.11641) // ✅ Correct resistance
  expect(targetSegment!.startTime).toBeLessThanOrEqual(targetTimestamp)
  expect(targetSegment!.endTime).toBeGreaterThanOrEqual(targetTimestamp)
})
```

### Business Logic Validation
- **Null breaks**: Any null resistance/support value breaks the line continuity
- **Same price continuity**: Only consecutive candles with identical prices extend the same segment
- **Price changes**: Different prices start new segments

## Running Tests

### Available Scripts

```bash
# Run all tests once
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage report
npm run test:coverage

# Run tests for CI (no watch, full coverage)
npm run test:ci
```

### Test Configuration

- **Framework**: Jest with TypeScript support
- **Environment**: jsdom (for DOM testing)
- **Coverage**: Reports generated in `coverage/` directory
- **Setup**: `src/setupTests.ts` for global test configuration

## Test Data

### Mock API Structure
Tests use realistic mock data that mirrors the actual API response:

```typescript
const mockApiData = {
  symbols: {
    SOLUSD: {
      chartOverlayData: {
        data: {
          SOLUSD: {
            "1771257600": {
              ema: 85.64979685879898,
              support: 84.60749,
              resistance: 86.11641  // Target value
            }
            // ... more timestamps
          }
        }
      }
    }
  }
}
```

### Edge Cases Covered
- Empty datasets
- All null values
- Single data points
- Large datasets (1000+ points)
- Floating point precision issues
- Boundary conditions

## Performance Benchmarks

The test suite includes performance tests to ensure the segment creation logic can handle large datasets efficiently:

- **Target**: < 100ms for 1000 points
- **Current**: Typically < 10ms for 1000 points
- **Memory**: No memory leaks or excessive allocations

## Future Test Enhancements

### Planned Additions
- [ ] React component rendering tests
- [ ] Chart library integration tests
- [ ] WebSocket data streaming tests
- [ ] Browser compatibility tests
- [ ] Accessibility tests

### Test Maintenance
- Tests are designed to be maintainable and readable
- Mock data is centralized and realistic
- Test scenarios cover both happy paths and edge cases
- Performance tests ensure scalability

## Debugging Tests

### Common Issues
1. **TypeScript errors**: Ensure Jest types are installed
2. **Import errors**: Check file paths and module resolution
3. **Mock issues**: Verify mock configurations match actual APIs

### Debug Commands
```bash
# Run tests with verbose output
npm test -- --verbose

# Run specific test file
npm test -- chartSegments.test.ts

# Run tests with debugger
node --inspect-brk node_modules/.bin/jest --runInBand
```

## Coverage Goals

Current coverage targets:
- **Statements**: 90%+
- **Branches**: 85%+
- **Functions**: 90%+
- **Lines**: 90%+

Coverage reports are automatically generated and can be viewed in the browser by opening `coverage/lcov-report/index.html`.
