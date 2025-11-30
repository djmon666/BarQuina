#!/usr/bin/env python3
"""
Integrated load testing script for BarQuina.

This script:
1. Starts system resource monitoring
2. Runs Locust load tests
3. Collects and analyzes results
4. Generates a comprehensive report

Usage:
    python scripts/run_load_test.py --users 50 --duration 300
    python scripts/run_load_test.py --users 100 --duration 600 --spawn-rate 10
    python scripts/run_load_test.py --quick  # Quick test with 10 users for 60s
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


class LoadTestRunner:
    """Orchestrate load testing with monitoring."""
    
    def __init__(
        self,
        host: str,
        users: int,
        spawn_rate: int,
        duration: int,
        output_dir: str = "results"
    ):
        self.host = host
        self.users = users
        self.spawn_rate = spawn_rate
        self.duration = duration
        self.output_dir = Path(output_dir)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create output directory
        self.test_dir = self.output_dir / f"loadtest_{self.timestamp}"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        self.monitor_process = None
        self.locust_process = None
    
    def start_monitoring(self):
        """Start system resource monitoring."""
        monitor_output = self.test_dir / "system_monitor.csv"
        
        print("🔍 Starting system monitoring...")
        
        cmd = [
            sys.executable,
            "scripts/monitor_resources.py",
            "--interval", "1.0",
            "--duration", str(self.duration + 10),  # Extra time for cleanup
            "--output", str(monitor_output)
        ]
        
        self.monitor_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        time.sleep(2)  # Wait for monitor to start
        print(f"✓ Monitoring started (PID: {self.monitor_process.pid})")
        print(f"  Output: {monitor_output}\n")
    
    def run_locust(self):
        """Run Locust load test."""
        locust_output = self.test_dir / "locust_stats.json"
        locust_html = self.test_dir / "locust_report.html"
        
        print("🚀 Starting Locust load test...")
        print(f"  Host: {self.host}")
        print(f"  Users: {self.users}")
        print(f"  Spawn rate: {self.spawn_rate} users/sec")
        print(f"  Duration: {self.duration}s\n")
        
        cmd = [
            "locust",
            "-f", "tests/locustfile.py",
            "--host", self.host,
            "--headless",
            "-u", str(self.users),
            "-r", str(self.spawn_rate),
            "-t", f"{self.duration}s",
            "--json",
            "--html", str(locust_html)
        ]
        
        # Run Locust and capture output
        try:
            result = subprocess.run(
                cmd,
                check=False,  # Don't raise on non-zero exit
                capture_output=True,
                text=True,
                timeout=self.duration + 120  # Extra margin for startup/cleanup
            )
            
            # Save output
            with open(self.test_dir / "locust_output.txt", "w") as f:
                f.write(result.stdout)
                f.write("\n\n=== STDERR ===\n\n")
                f.write(result.stderr)
            
            # Check if test completed (exit code 0 or 1 are both OK - 1 just means some failures)
            if result.returncode in (0, 1):
                print("✓ Locust test completed")
                if result.returncode == 1:
                    print("  ⚠️  Some requests failed (see report for details)")
                print(f"  HTML report: {locust_html}\n")
            else:
                print(f"❌ Locust test failed with exit code {result.returncode}")
                print(f"Output: {result.stdout[-500:]}")  # Last 500 chars
                print(f"Error: {result.stderr[-500:]}")
                return False
            
        except subprocess.TimeoutExpired:
            print("⚠️  Locust test timed out")
            return False
        
        return True
    
    def stop_monitoring(self):
        """Stop system monitoring."""
        if self.monitor_process:
            print("🛑 Stopping monitoring...")
            self.monitor_process.send_signal(signal.SIGINT)
            self.monitor_process.wait(timeout=10)
            print("✓ Monitoring stopped\n")
    
    def generate_report(self):
        """Generate comprehensive test report."""
        report_file = self.test_dir / "test_report.txt"
        
        print("📊 Generating test report...")
        
        with open(report_file, "w") as f:
            f.write("="*70 + "\n")
            f.write("BarQuina Load Test Report\n")
            f.write("="*70 + "\n\n")
            
            f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Test ID: {self.timestamp}\n\n")
            
            f.write("Test Configuration:\n")
            f.write(f"  Host: {self.host}\n")
            f.write(f"  Users: {self.users}\n")
            f.write(f"  Spawn Rate: {self.spawn_rate} users/sec\n")
            f.write(f"  Duration: {self.duration}s\n\n")
            
            f.write("="*70 + "\n")
            f.write("Output Files:\n")
            f.write("="*70 + "\n")
            
            for file in sorted(self.test_dir.iterdir()):
                if file.is_file():
                    size_kb = file.stat().st_size / 1024
                    f.write(f"  {file.name:<30} {size_kb:>10.1f} KB\n")
            
            f.write("\n" + "="*70 + "\n")
            f.write("Quick Access Commands:\n")
            f.write("="*70 + "\n")
            f.write(f"# View HTML report\n")
            f.write(f"xdg-open {self.test_dir / 'locust_report.html'}\n\n")
            f.write(f"# Analyze system metrics\n")
            f.write(f"python -c \"import pandas as pd; df = pd.read_csv('{self.test_dir / 'system_monitor.csv'}'); print(df.describe())\"\n\n")
        
        print(f"✓ Report generated: {report_file}\n")
        
        # Print summary to console
        print("="*70)
        print("Test Complete!")
        print("="*70)
        print(f"Results directory: {self.test_dir}")
        print("\nKey files:")
        print(f"  📄 Test report:    {report_file.name}")
        print(f"  📊 HTML report:    locust_report.html")
        print(f"  💻 System metrics: system_monitor.csv")
        print("="*70)
    
    def run(self):
        """Execute the complete test."""
        print("\n" + "="*70)
        print("BarQuina Load Test Suite")
        print("="*70 + "\n")
        
        try:
            # Step 1: Start monitoring
            self.start_monitoring()
            
            # Step 2: Run load test
            success = self.run_locust()
            
            # Step 3: Stop monitoring
            time.sleep(2)  # Brief wait for final metrics
            self.stop_monitoring()
            
            # Step 4: Generate report
            if success:
                self.generate_report()
                return 0
            else:
                print("❌ Test failed")
                return 1
                
        except KeyboardInterrupt:
            print("\n⚠️  Test interrupted by user")
            self.stop_monitoring()
            return 1
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.stop_monitoring()
            return 1


def main():
    parser = argparse.ArgumentParser(
        description="Run integrated load tests on BarQuina",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard test: 50 users for 5 minutes
  python scripts/run_load_test.py --users 50 --duration 300
  
  # Heavy test: 100 users for 10 minutes
  python scripts/run_load_test.py --users 100 --duration 600 --spawn-rate 10
  
  # Quick smoke test
  python scripts/run_load_test.py --quick
  
  # Test remote server
  python scripts/run_load_test.py --host http://codebany.ddns.net:5000 --users 50
        """
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default='http://localhost:5000',
        help='Target host URL (default: http://localhost:5000)'
    )
    parser.add_argument(
        '--users',
        type=int,
        default=50,
        help='Number of concurrent users (default: 50)'
    )
    parser.add_argument(
        '--spawn-rate',
        type=int,
        default=5,
        help='Users to spawn per second (default: 5)'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=300,
        help='Test duration in seconds (default: 300)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='results',
        help='Output directory for results (default: results/)'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick test: 10 users for 60 seconds'
    )
    
    args = parser.parse_args()
    
    # Quick test override
    if args.quick:
        args.users = 10
        args.spawn_rate = 2
        args.duration = 60
        print("⚡ Quick test mode enabled\n")
    
    runner = LoadTestRunner(
        host=args.host,
        users=args.users,
        spawn_rate=args.spawn_rate,
        duration=args.duration,
        output_dir=args.output_dir
    )
    
    sys.exit(runner.run())


if __name__ == "__main__":
    main()
