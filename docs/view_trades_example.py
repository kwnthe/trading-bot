"""
Example script showing how to view stored trades from BreakRetestStrategy

After running a backtest, you can access trades in several ways:
"""

# Example 1: After backtesting, access trades directly
# In your main.py or after cerebro.run():
# 
# strat = cerebro.strats[0][0][0]  # Get the strategy instance
# 
# # Method 1: Print all trades in a nice table format
# strat.print_trades()  # Shows only completed trades
# strat.print_trades(include_pending=True)  # Shows all trades including pending
# 
# # Method 2: Get trades as Python lists/dicts
# all_trades = strat.get_all_trades()  # All trades
# completed_trades = strat.get_completed_trades()  # Only completed
# pending_trades = strat.get_pending_trades()  # Only pending
# running_trades = strat.get_running_trades()  # Only running
# 
# # Method 3: Access directly via dictionary
# trades_dict = strat.trades  # Dictionary: trade_id -> trade_record
# 
# # Method 4: Access completed_trades list (from BaseStrategy)
# completed_list = strat.completed_trades  # List of completed trades
# 
# # Method 5: Export to CSV
# csv_file = strat.export_trades_to_csv()  # Exports to CSV file
# 
# # Example: Access individual trade fields
# for trade_id, trade in strat.trades.items():
#     print(f"Trade ID: {trade_id}")
#     print(f"  Symbol: {trade.get('symbol')}")
#     print(f"  Side: {trade.get('order_side')}")
#     print(f"  Entry Price: {trade.get('entry_price')}")
#     print(f"  Entry Executed Price: {trade.get('entry_executed_price')}")
#     print(f"  Exit Price: {trade.get('exit_price', 'N/A')}")
#     print(f"  PnL: {trade.get('pnl', 'N/A')}")
#     print(f"  Close Reason: {trade.get('close_reason', 'N/A')}")
#     print(f"  Placed: {trade.get('placed_datetime')}")
#     print(f"  Opened: {trade.get('open_datetime')}")
#     print(f"  Closed: {trade.get('close_datetime')}")
#     print(f"  TP: {trade.get('tp')}")
#     print(f"  SL: {trade.get('sl')}")
#     print()

if __name__ == "__main__":
    print("This is an example file showing how to view trades.")
    print("See the comments above for usage examples.")
    print("\nTo use in your code:")
    print("1. After running cerebro.run(), get the strategy: strat = cerebro.strats[0][0][0]")
    print("2. Call strat.print_trades() to see all trades in a table")
    print("3. Or access strat.trades dictionary directly")
    print("4. Or call strat.export_trades_to_csv() to export to CSV")

