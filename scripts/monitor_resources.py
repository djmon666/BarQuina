#!/usr/bin/env python3
"""
System resource monitoring script for load testing.

Monitors CPU, RAM, disk I/O, and network while load tests run.
Results are saved to a CSV file for analysis.

Usage:
    python scripts/monitor_resources.py --duration 300 --output results/monitor.csv
    
    Or start it before running locust:
    python scripts/monitor_resources.py --output results/monitor.csv &
    MONITOR_PID=$!
    locust -f tests/locustfile.py --host=http://localhost:5000 --headless -u 50 -r 5 -t 300s
    kill $MONITOR_PID
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil
except ImportError:
    print("Error: psutil is not installed. Install with: pip install psutil")
    sys.exit(1)


class SystemMonitor:
    """Monitor system resources over time."""
    
    def __init__(self, interval: float = 1.0, output_file: str | None = None):
        """
        Initialize the monitor.
        
        Args:
            interval: Seconds between samples
            output_file: Path to output CSV file
        """
        self.interval = interval
        self.output_file = output_file
        self.process = psutil.Process()
        self.samples = []
        
        # Initial values for delta calculations
        self.last_net = psutil.net_io_counters()
        self.last_disk = psutil.disk_io_counters()
        self.last_time = time.time()
    
    def get_sample(self) -> dict:
        """Collect a single sample of system metrics."""
        current_time = time.time()
        time_delta = current_time - self.last_time
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        # Memory metrics
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Disk I/O metrics
        disk = psutil.disk_io_counters()
        disk_read_rate = (disk.read_bytes - self.last_disk.read_bytes) / time_delta if time_delta > 0 else 0
        disk_write_rate = (disk.write_bytes - self.last_disk.write_bytes) / time_delta if time_delta > 0 else 0
        self.last_disk = disk
        
        # Network I/O metrics
        net = psutil.net_io_counters()
        net_sent_rate = (net.bytes_sent - self.last_net.bytes_sent) / time_delta if time_delta > 0 else 0
        net_recv_rate = (net.bytes_recv - self.last_net.bytes_recv) / time_delta if time_delta > 0 else 0
        self.last_net = net
        
        # Process-specific metrics (for the Python app)
        process_cpu = self.process.cpu_percent()
        process_mem = self.process.memory_info()
        
        self.last_time = current_time
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": cpu_percent,
            "cpu_count": cpu_count,
            "cpu_freq_current": cpu_freq.current if cpu_freq else 0,
            "mem_total_gb": mem.total / (1024**3),
            "mem_used_gb": mem.used / (1024**3),
            "mem_percent": mem.percent,
            "mem_available_gb": mem.available / (1024**3),
            "swap_percent": swap.percent,
            "disk_read_mb_s": disk_read_rate / (1024**2),
            "disk_write_mb_s": disk_write_rate / (1024**2),
            "net_sent_kb_s": net_sent_rate / 1024,
            "net_recv_kb_s": net_recv_rate / 1024,
            "process_cpu_percent": process_cpu,
            "process_mem_mb": process_mem.rss / (1024**2),
            "process_mem_vms_mb": process_mem.vms / (1024**2),
        }
    
    def monitor(self, duration: float | None = None):
        """
        Run monitoring loop.
        
        Args:
            duration: Duration in seconds (None = infinite)
        """
        start_time = time.time()
        
        print("🔍 System Monitoring Started")
        print("="*60)
        print(f"Interval: {self.interval}s")
        print(f"Output: {self.output_file or 'stdout only'}")
        print(f"Duration: {duration}s" if duration else "Duration: infinite (Ctrl+C to stop)")
        print("="*60)
        print()
        
        # Print header
        print(f"{'Time':<12} {'CPU%':<8} {'RAM%':<8} {'RAM(GB)':<10} {'Disk R':<10} {'Disk W':<10} {'Net ↓':<10} {'Net ↑':<10}")
        print("-"*90)
        
        try:
            while True:
                sample = self.get_sample()
                self.samples.append(sample)
                
                # Print to console
                print(
                    f"{datetime.now().strftime('%H:%M:%S'):<12} "
                    f"{sample['cpu_percent']:>6.1f}% "
                    f"{sample['mem_percent']:>6.1f}% "
                    f"{sample['mem_used_gb']:>8.2f} "
                    f"{sample['disk_read_mb_s']:>8.1f}MB/s "
                    f"{sample['disk_write_mb_s']:>7.1f}MB/s "
                    f"{sample['net_recv_kb_s']:>8.1f}KB/s "
                    f"{sample['net_sent_kb_s']:>7.1f}KB/s"
                )
                
                # Check duration
                if duration and (time.time() - start_time) >= duration:
                    break
                
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Monitoring stopped by user")
        
        self.save_results()
        self.print_summary()
    
    def save_results(self):
        """Save collected samples to CSV file."""
        if not self.output_file or not self.samples:
            return
        
        # Create directory if needed
        output_path = Path(self.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write CSV
        with open(self.output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.samples[0].keys())
            writer.writeheader()
            writer.writerows(self.samples)
        
        print(f"\n💾 Results saved to: {self.output_file}")
    
    def print_summary(self):
        """Print summary statistics."""
        if not self.samples:
            return
        
        print("\n" + "="*60)
        print("📊 Summary Statistics")
        print("="*60)
        
        cpu_values = [s['cpu_percent'] for s in self.samples]
        mem_values = [s['mem_percent'] for s in self.samples]
        proc_cpu_values = [s['process_cpu_percent'] for s in self.samples]
        proc_mem_values = [s['process_mem_mb'] for s in self.samples]
        
        print(f"Samples collected: {len(self.samples)}")
        print(f"Duration: {self.samples[-1]['timestamp']} - {self.samples[0]['timestamp']}")
        print()
        print("System CPU:")
        print(f"  Average: {sum(cpu_values)/len(cpu_values):.1f}%")
        print(f"  Min: {min(cpu_values):.1f}%")
        print(f"  Max: {max(cpu_values):.1f}%")
        print()
        print("System RAM:")
        print(f"  Average: {sum(mem_values)/len(mem_values):.1f}%")
        print(f"  Min: {min(mem_values):.1f}%")
        print(f"  Max: {max(mem_values):.1f}%")
        print()
        print("Process CPU (BarQuina):")
        print(f"  Average: {sum(proc_cpu_values)/len(proc_cpu_values):.1f}%")
        print(f"  Min: {min(proc_cpu_values):.1f}%")
        print(f"  Max: {max(proc_cpu_values):.1f}%")
        print()
        print("Process RAM (BarQuina):")
        print(f"  Average: {sum(proc_mem_values)/len(proc_mem_values):.1f} MB")
        print(f"  Min: {min(proc_mem_values):.1f} MB")
        print(f"  Max: {max(proc_mem_values):.1f} MB")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Monitor system resources during load testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor for 5 minutes
  python scripts/monitor_resources.py --duration 300 --output results/monitor.csv
  
  # Monitor indefinitely (Ctrl+C to stop)
  python scripts/monitor_resources.py --output results/monitor.csv
  
  # Quick monitoring with 0.5s intervals
  python scripts/monitor_resources.py --interval 0.5 --duration 60
        """
    )
    
    parser.add_argument(
        '--duration',
        type=float,
        help='Monitoring duration in seconds (default: infinite)'
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=1.0,
        help='Sampling interval in seconds (default: 1.0)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output CSV file path (default: no file output)'
    )
    
    args = parser.parse_args()
    
    monitor = SystemMonitor(interval=args.interval, output_file=args.output)
    monitor.monitor(duration=args.duration)


if __name__ == "__main__":
    main()
