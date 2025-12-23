#!/usr/bin/env python3
"""
Script to run backtests with different RR (Risk/Reward) values and collect PnL results.
"""
import subprocess
import re
import sys
import os

# Determine the Python executable to use (prefer venv if available)
def get_python_executable():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(script_dir, 'venv', 'bin', 'python')
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable

def run_backtest(rr_value):
    """Run main.py with a specific RR value and extract PnL"""
    env = os.environ.copy()
    env['RR'] = str(rr_value)
    
    python_exe = get_python_executable()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    try:
        result = subprocess.run(
            [python_exe, 'main.py'],
            env=env,
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per run
        )
        
        output = result.stdout + result.stderr
        
        # Extract PnL values from output
        # Look for patterns like "Total PnL: 2108.69" and "PnL%: 2.11%"
        pnl_match = re.search(r'Total PnL:\s*([-\d.]+)', output)
        pnl_pct_match = re.search(r'PnL%:\s*([-\d.]+)%', output)
        
        # Debug: print last 500 chars if no match found
        if not pnl_match and len(output) > 0:
            # Check if there are any errors
            if 'Traceback' in output or 'Error' in output:
                return {
                    'rr': rr_value,
                    'pnl': None,
                    'pnl_pct': None,
                    'output': output[-500:],  # Last 500 chars for debugging
                    'success': False,
                    'error': 'Runtime error (check output)'
                }
        
        pnl = float(pnl_match.group(1)) if pnl_match else None
        pnl_pct = float(pnl_pct_match.group(1)) if pnl_pct_match else None
        
        return {
            'rr': rr_value,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'output': output,
            'success': pnl is not None
        }
    except subprocess.TimeoutExpired:
        return {
            'rr': rr_value,
            'pnl': None,
            'pnl_pct': None,
            'output': '',
            'success': False,
            'error': 'Timeout'
        }
    except Exception as e:
        return {
            'rr': rr_value,
            'pnl': None,
            'pnl_pct': None,
            'output': '',
            'success': False,
            'error': str(e)
        }

def main():
    # Test RR values from 1.0 to 3.0 with 0.1 increments
    rr_values = [round(1.0 + i * 0.1, 1) for i in range(21)]  # 1.0, 1.1, ..., 3.0
    
    print("=" * 80)
    print("Running backtests with different RR values...")
    print("=" * 80)
    print()
    
    results = []
    
    for rr in rr_values:
        print(f"Testing RR={rr}...", end=' ', flush=True)
        result = run_backtest(rr)
        results.append(result)
        
        if result['success']:
            print(f"✓ PnL: {result['pnl']:.2f} ({result['pnl_pct']:.2f}%)")
        else:
            error_msg = result.get('error', 'Failed to extract PnL')
            print(f"✗ {error_msg}")
    
    print()
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"{'RR':<8} {'PnL':<15} {'PnL %':<12} {'Status':<10}")
    print("-" * 80)
    
    for result in results:
        if result['success']:
            print(f"{result['rr']:<8.1f} {result['pnl']:<15.2f} {result['pnl_pct']:<12.2f} {'Success':<10}")
        else:
            error = result.get('error', 'Failed')
            print(f"{result['rr']:<8.1f} {'N/A':<15} {'N/A':<12} {error:<10}")
    
    print()
    print("=" * 80)
    print("BEST PERFORMING RR VALUES")
    print("=" * 80)
    
    # Sort by PnL (descending)
    successful_results = [r for r in results if r['success']]
    if successful_results:
        sorted_results = sorted(successful_results, key=lambda x: x['pnl'], reverse=True)
        print(f"{'Rank':<6} {'RR':<8} {'PnL':<15} {'PnL %':<12}")
        print("-" * 50)
        for i, result in enumerate(sorted_results[:10], 1):  # Top 10
            print(f"{i:<6} {result['rr']:<8.1f} {result['pnl']:<15.2f} {result['pnl_pct']:<12.2f}")
    else:
        print("No successful runs to display.")
    
    # Save detailed results to CSV
    csv_file = 'rr_pnl_results.csv'
    with open(csv_file, 'w') as f:
        f.write('RR,PnL,PnL_Percent,Status\n')
        for result in results:
            if result['success']:
                f.write(f"{result['rr']},{result['pnl']},{result['pnl_pct']},Success\n")
            else:
                error = result.get('error', 'Failed')
                f.write(f"{result['rr']},,{error}\n")
    
    print()
    print(f"Detailed results saved to: {csv_file}")

if __name__ == '__main__':
    main()

