#!/bin/bash

# Script to run the trading bot twice with different RR values
# First run: RR = 2
# Second run: RR = 3

echo "=========================================="
echo "Running bot with RR = 2.0"
echo "=========================================="

source venv/bin/activate
rr=2 python main.py

echo ""
echo "=========================================="
echo "Running bot with RR = 3.0"
echo "=========================================="

rr=3 python main.py

echo ""
echo "=========================================="
echo "Comparison runs completed!"
echo "=========================================="

