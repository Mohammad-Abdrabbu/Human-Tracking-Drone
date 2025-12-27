#!/usr/bin/env python3
"""
perf_report_phaseA3.py - Phase A3 Performance Report Generator

Parses log files from a perf_phaseA3 run and generates a Markdown report.

Usage:
    python3 scripts/debug/perf_report_phaseA3.py --run-dir ~/sahtd/data/perf/phaseA3_*/

Output:
    Creates REPORT.md in the run directory.
"""

import argparse
import re
import os
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import statistics


def parse_meta(run_dir: Path) -> Dict[str, str]:
    """Parse meta.yaml for run metadata."""
    meta = {}
    meta_file = run_dir / "meta.yaml"
    if meta_file.exists():
        with open(meta_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip()
    return meta


def parse_hz_log(log_path: Path) -> Optional[Dict[str, float]]:
    """
    Parse ros2 topic hz output.
    
    Example format:
        average rate: 29.981
            min: 0.028s max: 0.040s std dev: 0.00285s window: 30
    """
    if not log_path.exists() or log_path.stat().st_size == 0:
        return None
    
    with open(log_path) as f:
        content = f.read()
    
    # Find all rate measurements and take the last one (most stable)
    rate_matches = re.findall(r"average rate:\s*([\d.]+)", content)
    minmax_matches = re.findall(r"min:\s*([\d.]+)s\s*max:\s*([\d.]+)s\s*std dev:\s*([\d.]+)s", content)
    
    if not rate_matches:
        return None
    
    result = {"avg": float(rate_matches[-1])}
    
    if minmax_matches:
        last_match = minmax_matches[-1]
        # Convert min/max from seconds to rate-equivalent (1/interval)
        result["min_interval"] = float(last_match[0])
        result["max_interval"] = float(last_match[1])
        result["std_dev"] = float(last_match[2])
    
    return result


def parse_bw_log(log_path: Path) -> Optional[Dict[str, str]]:
    """
    Parse ros2 topic bw output.
    
    Example format:
        Subscribed to [/camera/image_raw]
        1.23 MB/s from 30 messages
            Message size mean: 0.041 MB min: 0.041 MB max: 0.041 MB
    """
    if not log_path.exists() or log_path.stat().st_size == 0:
        return None
    
    with open(log_path) as f:
        content = f.read()
    
    # Extract bandwidth (MB/s)
    bw_matches = re.findall(r"([\d.]+)\s*MB/s\s*from\s*(\d+)\s*messages", content)
    size_matches = re.findall(r"Message size mean:\s*([\d.]+)\s*MB", content)
    
    if not bw_matches:
        return None
    
    result = {
        "bandwidth_mb_s": bw_matches[-1][0],
        "msg_count": bw_matches[-1][1],
    }
    
    if size_matches:
        result["msg_size_mb"] = size_matches[-1]
    
    return result


def parse_gpu_csv(log_path: Path) -> Optional[Dict[str, Dict[str, float]]]:
    """
    Parse nvidia-smi CSV output.
    
    Expected columns:
        timestamp, utilization.gpu [%], utilization.memory [%], 
        memory.used [MiB], memory.total [MiB], power.draw [W], temperature.gpu
    """
    if not log_path.exists() or log_path.stat().st_size < 100:
        return None
    
    gpu_utils = []
    mem_utils = []
    mem_used = []
    power = []
    temps = []
    
    try:
        with open(log_path) as f:
            # Try to detect if it's actually a CSV
            first_line = f.readline()
            if "nvidia-smi not found" in first_line:
                return None
            f.seek(0)
            
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return None
            
            for row in reader:
                if len(row) < 7:
                    continue
                try:
                    # Extract numeric values, handling units like "10 %" or "1234 MiB"
                    gpu_util = float(re.sub(r"[^\d.]", "", row[1]) or 0)
                    mem_util = float(re.sub(r"[^\d.]", "", row[2]) or 0)
                    mem_u = float(re.sub(r"[^\d.]", "", row[3]) or 0)
                    pwr = float(re.sub(r"[^\d.]", "", row[5]) or 0)
                    temp = float(re.sub(r"[^\d.]", "", row[6]) or 0)
                    
                    gpu_utils.append(gpu_util)
                    mem_utils.append(mem_util)
                    mem_used.append(mem_u)
                    power.append(pwr)
                    temps.append(temp)
                except (ValueError, IndexError):
                    continue
    except Exception:
        return None
    
    if not gpu_utils:
        return None
    
    return {
        "gpu_util": {"avg": statistics.mean(gpu_utils), "max": max(gpu_utils)},
        "mem_util": {"avg": statistics.mean(mem_utils), "max": max(mem_utils)},
        "mem_used_mib": {"avg": statistics.mean(mem_used), "max": max(mem_used)},
        "power_w": {"avg": statistics.mean(power), "max": max(power)},
        "temp_c": {"avg": statistics.mean(temps), "max": max(temps)},
    }


def parse_cpu_log(log_path: Path) -> Optional[Dict[str, Dict[str, float]]]:
    """
    Parse top -b output for CPU and load averages.
    
    Looks for:
        %Cpu(s):  5.2 us, ...
        load average: 1.23, 0.98, 0.87
        
    Also identifies hot processes (gz, python, px4).
    """
    if not log_path.exists() or log_path.stat().st_size == 0:
        return None
    
    with open(log_path) as f:
        content = f.read()
    
    # Extract CPU usage percentages
    cpu_matches = re.findall(r"%Cpu\(s\):\s*([\d.]+)\s*us", content)
    
    # Extract load averages
    load_matches = re.findall(r"load average:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)", content)
    
    # Find hot processes
    process_cpu = {}
    for line in content.split("\n"):
        # Match process lines with CPU %
        # Format: PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
        match = re.match(r"\s*\d+\s+\w+\s+\d+\s+\d+\s+[\d.]+\w?\s+[\d.]+\w?\s+[\d.]+\w?\s+\w\s+([\d.]+)\s+[\d.]+\s+[\d:.]+\s+(\S+)", line)
        if match:
            cpu_pct = float(match.group(1))
            cmd = match.group(2)
            # Track key processes
            for key in ["gz", "python", "px4", "ruby"]:
                if key in cmd.lower():
                    if key not in process_cpu:
                        process_cpu[key] = []
                    process_cpu[key].append(cpu_pct)
    
    if not cpu_matches and not load_matches:
        return None
    
    result = {}
    
    if cpu_matches:
        cpu_values = [float(x) for x in cpu_matches]
        result["cpu_user"] = {"avg": statistics.mean(cpu_values), "max": max(cpu_values)}
    
    if load_matches:
        load_1m = [float(x[0]) for x in load_matches]
        result["load_1m"] = {"avg": statistics.mean(load_1m), "max": max(load_1m)}
    
    # Hot process summary
    hot_procs = {}
    for name, values in process_cpu.items():
        if values:
            hot_procs[name] = {"avg": statistics.mean(values), "max": max(values)}
    if hot_procs:
        result["hot_processes"] = hot_procs
    
    return result


def parse_latency_age_csv(log_path: Path) -> Optional[Dict]:
    """
    Parse latency_age.csv for per-topic age and inter-arrival analysis.
    
    New format has columns: wall_ts, topic, stamp_s, age_sim_ms, dt_ms, count
    """
    if not log_path.exists() or log_path.stat().st_size < 100:
        return None
    
    # Per-topic data
    data = {
        'camera': {'age': [], 'dt': [], 'timestamps': []},
        'detections': {'age': [], 'dt': [], 'timestamps': []},
        'tracks': {'age': [], 'dt': [], 'timestamps': []},
    }
    
    stall_windows = []  # (wall_ts, topic, age_ms, dt_ms)
    
    try:
        with open(log_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    topic = row.get('topic', '')
                    if topic not in data:
                        continue
                    
                    wall_ts = row.get('wall_ts', '')
                    age_ms = float(row.get('age_sim_ms', 0))
                    dt_ms = float(row.get('dt_ms', 0))
                    
                    data[topic]['age'].append(age_ms)
                    data[topic]['dt'].append(dt_ms)
                    data[topic]['timestamps'].append(wall_ts)
                    
                    # Detect stalls (age > 150ms OR dt > 150ms)
                    if age_ms > 150 or dt_ms > 150:
                        stall_windows.append((wall_ts, topic, age_ms, dt_ms))
                        
                except (ValueError, KeyError):
                    continue
    except Exception:
        return None
    
    if not data['camera']['age']:
        return None
    
    def percentiles(vals: List[float]) -> Dict[str, float]:
        if not vals:
            return {"p50": 0, "p95": 0, "p99": 0, "max": 0}
        s = sorted(vals)
        n = len(s)
        return {
            "p50": s[int(n * 0.50)],
            "p95": s[int(n * 0.95)] if n >= 20 else s[-1],
            "p99": s[int(n * 0.99)] if n >= 100 else s[-1],
            "max": s[-1]
        }
    
    result = {}
    for topic in data:
        if data[topic]['age']:
            result[f'{topic}_age'] = percentiles(data[topic]['age'])
            result[f'{topic}_dt'] = percentiles(data[topic]['dt'])
            result[f'{topic}_count'] = len(data[topic]['age'])
    
    # Sort stall windows by severity (max of age, dt)
    stall_windows.sort(key=lambda x: max(x[2], x[3]), reverse=True)
    result['stall_windows'] = stall_windows[:10]  # Top 10
    result['total_stalls'] = len(stall_windows)
    
    return result


def parse_latency_summary(log_path: Path) -> Optional[Dict]:
    """Parse latency_probe_summary.txt for lineage mismatch stats."""
    if not log_path.exists():
        return None
    
    result = {}
    try:
        with open(log_path) as f:
            content = f.read()
            # Extract key stats
            for line in content.split('\n'):
                if 'Max camera age' in line:
                    match = re.search(r'([\d.]+)\s*ms', line)
                    if match:
                        result['max_cam_age_ms'] = float(match.group(1))
                if 'mismatch' in line.lower():
                    match = re.search(r'(\d+)\s*mismatch.*?([\d.]+)%', line)
                    if match:
                        if 'Detections' in line:
                            result['det_mismatch_pct'] = float(match.group(2))
                        elif 'Tracks' in line:
                            result['trk_mismatch_pct'] = float(match.group(2))
    except Exception:
        return None
    
    return result if result else None


def generate_latency_interpretation(latency_data: Dict) -> List[str]:
    """Generate spike attribution heuristics based on latency data."""
    lines = []
    
    if not latency_data:
        return lines
    
    cam_age = latency_data.get("camera_age", {})
    cam_dt = latency_data.get("camera_dt", {})
    det_age = latency_data.get("detections_age", {})
    det_dt = latency_data.get("detections_dt", {})
    
    # Attribution heuristic based on where spikes appear
    cam_age_spike = cam_age.get("p95", 0) > 100
    cam_dt_spike = cam_dt.get("p95", 0) > 100
    det_age_spike = det_age.get("p95", 0) > 100
    det_dt_spike = det_dt.get("p95", 0) > 100
    
    if cam_age_spike or cam_dt_spike:
        lines.append("- **Upstream stall detected**: Camera messages arriving late or with gaps.")
        lines.append("  → Cause: ros_gz_image bridge, Gazebo camera sensor, or CPU starvation.")
    
    if det_age_spike and not cam_age_spike:
        lines.append("- **YOLO processing bottleneck**: Detections age exceeds camera age.")
        lines.append("  → Cause: YOLO inference time, queue buildup, or GPU memory pressure.")
    
    if det_dt_spike and not cam_dt_spike:
        lines.append("- **Detection rate drop**: Detections inter-arrival exceeds camera inter-arrival.")
        lines.append("  → Cause: YOLO node blocking or dropping frames.")
    
    total_stalls = latency_data.get('total_stalls', 0)
    if total_stalls > 0:
        lines.append(f"- **Total stall events**: {total_stalls} (age > 150ms or dt > 150ms)")
    
    if not lines:
        lines.append("- Pipeline latency is within normal bounds (p95 < 100ms).")
    
    return lines


def generate_interpretation(hz_data: Dict, gpu_data: Optional[Dict], cpu_data: Optional[Dict]) -> str:
    """Generate interpretation text based on collected data."""
    lines = []
    
    # Check topic intervals
    max_intervals = []
    for topic, data in hz_data.items():
        if data and "max_interval" in data:
            max_intervals.append((topic, data["max_interval"]))
    
    if max_intervals:
        worst = max(max_intervals, key=lambda x: x[1])
        if worst[1] > 0.3:
            lines.append(f"**Stall detected**: Max interval of {worst[1]:.3f}s on `{worst[0]}` suggests pipeline stalls remain.")
            lines.append("If running in headless mode, the stall is likely NOT from Gazebo GUI rendering.")
            lines.append("Consider investigating: YOLO inference time, GPU memory pressure, or CPU contention.")
        elif worst[1] > 0.1:
            lines.append(f"**Moderate latency**: Max interval of {worst[1]:.3f}s on `{worst[0]}`.")
            lines.append("Pipeline is reasonably healthy but occasional delays occur.")
        else:
            lines.append("**Good performance**: All topics have consistent timing (max interval < 100ms).")
    
    # GPU analysis
    if gpu_data:
        gpu_util = gpu_data.get("gpu_util", {})
        if gpu_util.get("max", 0) > 90:
            lines.append(f"**GPU saturated**: Peak GPU utilization {gpu_util['max']:.1f}% suggests GPU is a bottleneck.")
        elif gpu_util.get("avg", 0) < 30:
            lines.append(f"**GPU underutilized**: Avg GPU utilization only {gpu_util['avg']:.1f}%. Consider increasing batch size or resolution.")
    
    # CPU analysis
    if cpu_data and "hot_processes" in cpu_data:
        hot = cpu_data["hot_processes"]
        for proc, stats in hot.items():
            if stats.get("max", 0) > 80:
                lines.append(f"**CPU hot process**: `{proc}` peaked at {stats['max']:.1f}% CPU.")
    
    return "\n".join(lines) if lines else "No significant performance issues detected in collected data."


def generate_report(run_dir: Path) -> str:
    """Generate Markdown report from run directory logs."""
    meta = parse_meta(run_dir)
    
    # Parse all logs
    hz_topics = {
        "/camera/image_raw": parse_hz_log(run_dir / "hz_camera.log"),
        "/perception/detections": parse_hz_log(run_dir / "hz_detections.log"),
        "/perception/tracks": parse_hz_log(run_dir / "hz_tracks.log"),
        "/sahtd/follow/cmd_body": parse_hz_log(run_dir / "hz_cmd_body.log"),
    }
    
    bw_data = parse_bw_log(run_dir / "bw_camera.log")
    gpu_data = parse_gpu_csv(run_dir / "gpu.csv")
    cpu_data = parse_cpu_log(run_dir / "cpu.log")
    
    # Build report
    lines = []
    lines.append("# SAHTD Phase A3 Performance Report\n")
    
    # Metadata
    lines.append("## Run Metadata\n")
    lines.append(f"- **Timestamp**: {meta.get('timestamp', 'N/A')}")
    lines.append(f"- **Host**: {meta.get('host', 'N/A')}")
    lines.append(f"- **Git**: {meta.get('git_branch', 'N/A')} @ {meta.get('git_commit', 'N/A')}")
    lines.append(f"- **Mode**: Headless Gazebo")
    lines.append(f"- **Hz Duration**: {meta.get('hz_duration', '30')}s per topic")
    lines.append("")
    
    # Topic Hz Summary
    lines.append("## Topic Rate Summary (Hz)\n")
    lines.append("| Topic | Avg Rate | Min Interval | Max Interval | Std Dev |")
    lines.append("|-------|----------|--------------|--------------|---------|")
    for topic, data in hz_topics.items():
        if data:
            avg = f"{data['avg']:.2f}"
            min_int = f"{data.get('min_interval', 'N/A'):.4f}s" if 'min_interval' in data else "N/A"
            max_int = f"{data.get('max_interval', 'N/A'):.4f}s" if 'max_interval' in data else "N/A"
            std = f"{data.get('std_dev', 'N/A'):.5f}s" if 'std_dev' in data else "N/A"
        else:
            avg = min_int = max_int = std = "N/A"
        lines.append(f"| `{topic}` | {avg} | {min_int} | {max_int} | {std} |")
    lines.append("")
    
    # Camera Bandwidth
    lines.append("## Camera Bandwidth\n")
    if bw_data:
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Avg Bandwidth | {bw_data.get('bandwidth_mb_s', 'N/A')} MB/s |")
        lines.append(f"| Msg Count | {bw_data.get('msg_count', 'N/A')} |")
        if 'msg_size_mb' in bw_data:
            lines.append(f"| Avg Msg Size | {bw_data['msg_size_mb']} MB |")
    else:
        lines.append("*No bandwidth data collected.*")
    lines.append("")
    
    # GPU Summary
    lines.append("## GPU Summary\n")
    if gpu_data:
        lines.append("| Metric | Avg | Max |")
        lines.append("|--------|-----|-----|")
        lines.append(f"| Utilization % | {gpu_data['gpu_util']['avg']:.1f} | {gpu_data['gpu_util']['max']:.1f} |")
        lines.append(f"| Memory Used (MiB) | {gpu_data['mem_used_mib']['avg']:.0f} | {gpu_data['mem_used_mib']['max']:.0f} |")
        lines.append(f"| Power (W) | {gpu_data['power_w']['avg']:.1f} | {gpu_data['power_w']['max']:.1f} |")
        lines.append(f"| Temperature (°C) | {gpu_data['temp_c']['avg']:.1f} | {gpu_data['temp_c']['max']:.1f} |")
    else:
        lines.append("*No GPU data collected (nvidia-smi not available or no NVIDIA GPU).*")
    lines.append("")
    
    # CPU Summary
    lines.append("## CPU/Load Summary\n")
    if cpu_data:
        lines.append("| Metric | Avg | Max |")
        lines.append("|--------|-----|-----|")
        if "cpu_user" in cpu_data:
            lines.append(f"| CPU User % | {cpu_data['cpu_user']['avg']:.1f} | {cpu_data['cpu_user']['max']:.1f} |")
        if "load_1m" in cpu_data:
            lines.append(f"| Load Avg (1m) | {cpu_data['load_1m']['avg']:.2f} | {cpu_data['load_1m']['max']:.2f} |")
        
        if "hot_processes" in cpu_data:
            lines.append("")
            lines.append("### Hot Processes\n")
            lines.append("| Process | Avg CPU % | Max CPU % |")
            lines.append("|---------|-----------|-----------|")
            for proc, stats in cpu_data["hot_processes"].items():
                lines.append(f"| {proc} | {stats['avg']:.1f} | {stats['max']:.1f} |")
    else:
        lines.append("*No CPU data collected.*")
    lines.append("")
    
    # Pipeline Latency Breakdown (using new latency_age.csv format)
    latency_data = parse_latency_age_csv(run_dir / "latency_age.csv")
    latency_summary = parse_latency_summary(run_dir / "latency_probe_summary.txt")
    
    lines.append("## Pipeline Latency Breakdown\n")
    if latency_data:
        total_count = latency_data.get('camera_count', 0)
        lines.append(f"*Based on {total_count} camera messages*\n")
        
        # Per-topic age and inter-arrival table
        lines.append("### Message Age (sim time) - ms\n")
        lines.append("| Topic | p50 | p95 | p99 | max |")
        lines.append("|-------|-----|-----|-----|-----|")
        
        for topic in ['camera', 'detections', 'tracks']:
            d = latency_data.get(f'{topic}_age', {})
            if d.get("max", 0) > 0:
                lines.append(f"| {topic} | {d.get('p50', 0):.0f} | {d.get('p95', 0):.0f} | {d.get('p99', 0):.0f} | {d.get('max', 0):.0f} |")
        lines.append("")
        
        lines.append("### Inter-Arrival Time (dt) - ms\n")
        lines.append("| Topic | p50 | p95 | p99 | max |")
        lines.append("|-------|-----|-----|-----|-----|")
        
        for topic in ['camera', 'detections', 'tracks']:
            d = latency_data.get(f'{topic}_dt', {})
            if d.get("max", 0) > 0:
                lines.append(f"| {topic} | {d.get('p50', 0):.0f} | {d.get('p95', 0):.0f} | {d.get('p99', 0):.0f} | {d.get('max', 0):.0f} |")
        lines.append("")
        
        # Stall windows
        stalls = latency_data.get("stall_windows", [])
        if stalls:
            lines.append(f"### Stall Events ({latency_data.get('total_stalls', 0)} total, top 5 shown)\n")
            lines.append("| Time | Topic | Age (ms) | dt (ms) |")
            lines.append("|------|-------|----------|---------|")
            for ts, topic, age_ms, dt_ms in stalls[:5]:
                lines.append(f"| {ts} | {topic} | {age_ms:.0f} | {dt_ms:.0f} |")
            lines.append("")
        
        # Spike attribution
        lines.append("### Spike Attribution\n")
        interpretation_lines = generate_latency_interpretation(latency_data)
        for line in interpretation_lines:
            lines.append(line)
        lines.append("")
        
        # Lineage check
        if latency_summary:
            lines.append("### Stamp Lineage Check\n")
            if 'det_mismatch_pct' in latency_summary:
                lines.append(f"- Detection stamp mismatch: {latency_summary['det_mismatch_pct']:.1f}%")
            if 'trk_mismatch_pct' in latency_summary:
                lines.append(f"- Track stamp mismatch: {latency_summary['trk_mismatch_pct']:.1f}%")
            lines.append("")
        
        # Interpretation guide
        lines.append("> **How to interpret**: ")
        lines.append("> - **age_sim_ms**: How old the message is when received (ROS sim time). High = processing delay.")
        lines.append("> - **dt_ms**: Time between messages (wall clock). High = frame drops or scheduling gaps.")
        lines.append("> - Camera stalls with normal detections = upstream (bridge/Gazebo).")
        lines.append("> - Detection stalls with normal camera = YOLO bottleneck.")
    else:
        lines.append("*No latency data collected. Run with latency probe enabled.*")
    lines.append("")
    
    # Interpretation
    lines.append("## Interpretation\n")
    lines.append(generate_interpretation(hz_topics, gpu_data, cpu_data))
    lines.append("")
    
    # Footer
    lines.append("---")
    lines.append(f"*Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate performance report from Phase A3 perf run logs"
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        required=True,
        help="Path to the perf run directory (e.g., ~/sahtd/data/perf/phaseA3_*/)"
    )
    args = parser.parse_args()
    
    run_dir = Path(args.run_dir).expanduser().resolve()
    
    if not run_dir.exists():
        print(f"Error: Run directory not found: {run_dir}")
        return 1
    
    print(f"Parsing logs from: {run_dir}")
    
    report = generate_report(run_dir)
    
    report_path = run_dir / "REPORT.md"
    with open(report_path, "w") as f:
        f.write(report)
    
    print(f"Report generated: {report_path}")
    return 0


if __name__ == "__main__":
    exit(main())
