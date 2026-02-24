/**
 * Base interface for all chart managers
 * All managers should implement this interface for consistent behavior
 */
export interface ChartManager {
  /**
   * Get the data keys this manager needs from symbolData
   * @returns Array of data keys required by this manager
   */
  getDataKeys(): string[]
  
  /**
   * Process data for the manager
   * @param data Raw data to process
   */
  processData(data: any): void
  
  /**
   * Render the manager's visual elements
   * @returns Rendering statistics
   */
  render(): {
    totalCount: number
    [key: string]: any
  }
  
  /**
   * Clear all rendered elements
   */
  clear(): void
  
  /**
   * Get the name/type of the manager
   */
  getName(): string
}
