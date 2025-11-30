#!/usr/bin/env python3
"""
Analyze load test results and generate visualizations.

Usage:
    python scripts/analyze_results.py results/loadtest_20231201_120000
    python scripts/analyze_results.py results/loadtest_20231201_120000 --plot
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("⚠️  pandas not installed. Install with: pip install pandas")

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from datetime import datetime
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class ResultAnalyzer:
    """Analyze load test results."""
    
    def __init__(self, test_dir: Path):
        self.test_dir = test_dir
        self.monitor_file = test_dir / "system_monitor.csv"
        
        if not self.monitor_file.exists():
            print(f"❌ Monitor file not found: {self.monitor_file}")
            sys.exit(1)
    
    def load_data(self) -> pd.DataFrame:
        """Load monitoring data."""
        if not HAS_PANDAS:
            print("❌ pandas required for analysis")
            sys.exit(1)
        
        df = pd.read_csv(self.monitor_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    
    def print_summary(self, df: pd.DataFrame):
        """Print summary statistics."""
        print("\n" + "="*70)
        print("System Resource Summary")
        print("="*70 + "\n")
        
        metrics = {
            'CPU Usage (%)': 'cpu_percent',
            'RAM Usage (%)': 'mem_percent',
            'Process CPU (%)': 'process_cpu_percent',
            'Process RAM (MB)': 'process_mem_mb',
            'Disk Read (MB/s)': 'disk_read_mb_s',
            'Disk Write (MB/s)': 'disk_write_mb_s',
            'Network Recv (KB/s)': 'net_recv_kb_s',
            'Network Sent (KB/s)': 'net_sent_kb_s',
        }
        
        for label, col in metrics.items():
            if col in df.columns:
                values = df[col]
                print(f"{label:25} "
                      f"Min: {values.min():8.2f}  "
                      f"Avg: {values.mean():8.2f}  "
                      f"Max: {values.max():8.2f}  "
                      f"Std: {values.std():8.2f}")
        
        print("\n" + "="*70)
        
        # Find peak usage moments
        print("Peak Usage Moments:")
        print("="*70 + "\n")
        
        peak_cpu_idx = df['cpu_percent'].idxmax()
        peak_mem_idx = df['mem_percent'].idxmax()
        
        print(f"Peak CPU: {df.loc[peak_cpu_idx, 'cpu_percent']:.1f}% at {df.loc[peak_cpu_idx, 'timestamp']}")
        print(f"Peak RAM: {df.loc[peak_mem_idx, 'mem_percent']:.1f}% at {df.loc[peak_mem_idx, 'timestamp']}")
        print()
    
    def plot_results(self, df: pd.DataFrame):
        """Generate visualization plots."""
        if not HAS_MATPLOTLIB:
            print("⚠️  matplotlib not installed. Install with: pip install matplotlib")
            return
        
        print("📊 Generating plots...")
        
        fig, axes = plt.subplots(3, 2, figsize=(15, 12))
        fig.suptitle('BarQuina Load Test - System Resources', fontsize=16, fontweight='bold')
        
        # CPU Usage
        ax = axes[0, 0]
        ax.plot(df['timestamp'], df['cpu_percent'], 'b-', linewidth=1.5, label='Total CPU')
        ax.plot(df['timestamp'], df['process_cpu_percent'], 'r-', linewidth=1.5, label='BarQuina Process')
        ax.set_ylabel('CPU Usage (%)')
        ax.set_title('CPU Usage Over Time')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # Memory Usage
        ax = axes[0, 1]
        ax.plot(df['timestamp'], df['mem_percent'], 'g-', linewidth=1.5, label='Total RAM')
        ax.set_ylabel('Memory Usage (%)')
        ax.set_title('Memory Usage Over Time')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # Process Memory
        ax = axes[1, 0]
        ax.plot(df['timestamp'], df['process_mem_mb'], 'm-', linewidth=1.5)
        ax.set_ylabel('Memory (MB)')
        ax.set_title('BarQuina Process Memory')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # Disk I/O
        ax = axes[1, 1]
        ax.plot(df['timestamp'], df['disk_read_mb_s'], 'c-', linewidth=1.5, label='Read')
        ax.plot(df['timestamp'], df['disk_write_mb_s'], 'orange', linewidth=1.5, label='Write')
        ax.set_ylabel('Disk I/O (MB/s)')
        ax.set_title('Disk I/O Over Time')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # Network I/O
        ax = axes[2, 0]
        ax.plot(df['timestamp'], df['net_recv_kb_s'], 'b-', linewidth=1.5, label='Received')
        ax.plot(df['timestamp'], df['net_sent_kb_s'], 'r-', linewidth=1.5, label='Sent')
        ax.set_ylabel('Network I/O (KB/s)')
        ax.set_title('Network I/O Over Time')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # Resource Distribution
        ax = axes[2, 1]
        resources = ['CPU\n(%)', 'RAM\n(%)', 'Proc CPU\n(%)']
        values = [
            df['cpu_percent'].mean(),
            df['mem_percent'].mean(),
            df['process_cpu_percent'].mean()
        ]
        colors = ['blue', 'green', 'red']
        ax.bar(resources, values, color=colors, alpha=0.7)
        ax.set_ylabel('Average Usage (%)')
        ax.set_title('Average Resource Usage')
        ax.grid(True, alpha=0.3, axis='y')
        
        # Adjust layout
        plt.tight_layout()
        
        # Save plot
        plot_file = self.test_dir / "system_resources_plot.png"
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        print(f"✓ Plot saved: {plot_file}")
        
        # Show plot
        plt.show()
    
    def analyze(self, plot: bool = False):
        """Run complete analysis."""
        print(f"\n📊 Analyzing results from: {self.test_dir}\n")
        
        df = self.load_data()
        
        print(f"Samples collected: {len(df)}")
        print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        self.print_summary(df)
        
        if plot:
            self.plot_results(df)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze load test results",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        'test_dir',
        type=str,
        help='Path to test results directory'
    )
    parser.add_argument(
        '--plot',
        action='store_true',
        help='Generate visualization plots'
    )
    
    args = parser.parse_args()
    
    test_dir = Path(args.test_dir)
    
    if not test_dir.exists():
        print(f"❌ Directory not found: {test_dir}")
        sys.exit(1)
    
    analyzer = ResultAnalyzer(test_dir)
    analyzer.analyze(plot=args.plot)


if __name__ == "__main__":
    main()
