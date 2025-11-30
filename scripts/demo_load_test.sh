#!/bin/bash
#
# Demo script for BarQuina load testing
# 
# This script demonstrates how to:
# 1. Start the Flask server in test mode
# 2. Run a quick load test
# 3. Analyze the results
#

set -e  # Exit on error

echo "=================================="
echo "BarQuina Load Test Demo"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if server is running
if ! curl -s http://localhost:5000 > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Server not running on localhost:5000${NC}"
    echo -e "${YELLOW}Please start the server first:${NC}"
    echo ""
    echo "  export LOGIN_DISABLED=True"
    echo "  python barquina.py"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Server is running${NC}"
echo ""

# Run quick load test
echo "=================================="
echo "Running Quick Load Test"
echo "=================================="
echo "Configuration:"
echo "  - Users: 10"
echo "  - Duration: 30 seconds"
echo "  - Spawn rate: 2 users/sec"
echo ""

read -p "Press Enter to start the test (Ctrl+C to cancel)..."
echo ""

python scripts/run_load_test.py --users 10 --spawn-rate 2 --duration 30

# Find the latest results directory
LATEST_RESULT=$(ls -td results/loadtest_* 2>/dev/null | head -1)

if [ -z "$LATEST_RESULT" ]; then
    echo -e "${RED}❌ No results found${NC}"
    exit 1
fi

echo ""
echo "=================================="
echo "Analyzing Results"
echo "=================================="
echo ""

python scripts/analyze_results.py "$LATEST_RESULT"

echo ""
echo "=================================="
echo "Test Complete!"
echo "=================================="
echo ""
echo "Results saved to: $LATEST_RESULT"
echo ""
echo "To view the HTML report:"
echo "  xdg-open $LATEST_RESULT/locust_report.html"
echo ""
echo "To generate plots:"
echo "  python scripts/analyze_results.py $LATEST_RESULT --plot"
echo ""
