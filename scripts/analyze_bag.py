#!/usr/bin/env python3
"""
Step 0: Stand-off Geometry Calibration Analysis

Analyzes multiple W1 bags to find realistic values for:
- stand_off_px: the bbox height we can realistically achieve at comfortable distance
- max_close_px: the bbox height marking "too close" zone

Filters for "good near" situations:
- state == LOCKED
- h_f between 150 and 260 px (not too far, not completely on top)
- Optionally vx < 0.4 (not chasing hard)
"""

import sqlite3
import re
import os
import glob
from rclpy.serialization import deserialize_message
from std_msgs.msg import String
import statistics

def analyze_bag_for_calibration(bag_name, bag_dir='~/gp2/bags/follow'):
    """Analyze a single bag and return h_f samples in 'good near' situations."""
    
    bag_path = os.path.expanduser(f'{bag_dir}/{bag_name}')
    db_files = glob.glob(os.path.join(bag_path, '*.db3'))
    
    if not db_files:
        print(f"  WARNING: No .db3 file found in {bag_path}")
        return None
    
    db_file = db_files[0]
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Get HUD topic ID
    cursor.execute('SELECT id FROM topics WHERE name = "/gp2/follow/hud"')
    result = cursor.fetchone()
    if not result:
        print(f"  WARNING: /gp2/follow/hud topic not found in {bag_name}")
        conn.close()
        return None
    
    hud_id = result[0]
    cursor.execute(f'SELECT timestamp, data FROM messages WHERE topic_id = {hud_id} ORDER BY timestamp')
    rows = cursor.fetchall()
    
    # Extract data
    all_hf = []
    good_near_hf = []
    
    for ts, data in rows:
        msg = deserialize_message(data, String)
        text = msg.data
        
        # Parse state
        state = text.split()[0]
        
        # Parse h_f
        hf_m = re.search(r'h_f=(\d+\.?\d*)px', text)
        if not hf_m:
            continue
        h_f = float(hf_m.group(1))
        
        # Parse vx
        vx_m = re.search(r'vx=([+-]?\d+\.?\d*)m/s', text)
        vx = float(vx_m.group(1)) if vx_m else 0
        
        # All h_f > 0
        if h_f > 0:
            all_hf.append(h_f)
        
        # "Good near" filter:
        # - LOCKED state
        # - h_f between 150 and 260 (not too far, not on top of target)
        # - vx < 0.5 (not chasing at full speed)
        if state == 'LOCKED' and 150 <= h_f <= 260 and vx < 0.5:
            good_near_hf.append(h_f)
    
    conn.close()
    
    return {
        'bag': bag_name,
        'total_samples': len(rows),
        'all_hf': all_hf,
        'good_near_hf': good_near_hf
    }


def compute_stats(values, label=""):
    """Compute statistics for a list of values."""
    if not values:
        return None
    
    values_sorted = sorted(values)
    n = len(values)
    
    return {
        'count': n,
        'min': min(values),
        'max': max(values),
        'mean': statistics.mean(values),
        'median': statistics.median(values),
        'p25': values_sorted[int(n * 0.25)],
        'p75': values_sorted[int(n * 0.75)],
        'stdev': statistics.stdev(values) if n > 1 else 0
    }


def print_histogram(values, label, bins=[(0,100),(100,130),(130,160),(160,180),(180,200),(200,220),(220,250),(250,280),(280,320),(320,400)]):
    """Print a histogram of values."""
    if not values:
        print(f"  No data for {label}")
        return
    
    print(f"\n  {label} Histogram (n={len(values)}):")
    for lo, hi in bins:
        count = sum(1 for v in values if lo <= v < hi)
        pct = 100 * count / len(values) if values else 0
        bar = '#' * int(pct / 2)
        print(f"    [{lo:3d}-{hi:3d}): {count:4d} ({pct:5.1f}%) {bar}")


def main():
    print("=" * 70)
    print("STEP 0: STAND-OFF GEOMETRY CALIBRATION")
    print("=" * 70)
    
    # List of bags to analyze
    bags = [
        'B_follow_W1_20251208_235407',           # baseline
        'B_follow_W1_tuned_20251209_001653',     # tuned
        'B_follow_W1_tuned_20251209_001839',     # tuned 2
        'B_follow_W1_vel_est_20251209_004929',   # velocity estimation
        'B_follow_W1_prox_brake_20251209_010951',# prox brake first
        'B_follow_W1_prox_brake_20251209_011814',# prox brake second
        'B_follow_W1_prox_fix_20251209_012108',  # prox fix
        'B_follow_W1_progressive_20251209_125802', # progressive 1
        'B_follow_W1_progressive_20251209_130003', # progressive 2
    ]
    
    # Check which bags exist
    bag_dir = os.path.expanduser('~/gp2/bags/follow')
    existing_bags = []
    for bag in bags:
        if os.path.isdir(os.path.join(bag_dir, bag)):
            existing_bags.append(bag)
        else:
            print(f"  Note: {bag} not found, skipping")
    
    print(f"\nAnalyzing {len(existing_bags)} bags...")
    
    # Analyze each bag
    results = []
    all_good_near = []
    all_hf_combined = []
    
    for bag in existing_bags:
        print(f"\n--- {bag} ---")
        result = analyze_bag_for_calibration(bag)
        if result:
            results.append(result)
            
            stats = compute_stats(result['good_near_hf'], "good_near")
            if stats:
                print(f"  Total HUD samples: {result['total_samples']}")
                print(f"  Good-near samples: {stats['count']} ({100*stats['count']/result['total_samples']:.1f}%)")
                print(f"    min={stats['min']:.1f}, max={stats['max']:.1f}")
                print(f"    mean={stats['mean']:.1f}, median={stats['median']:.1f}")
                print(f"    p25={stats['p25']:.1f}, p75={stats['p75']:.1f}")
                
                all_good_near.extend(result['good_near_hf'])
                all_hf_combined.extend(result['all_hf'])
            else:
                print(f"  No good-near samples found")
    
    # Combined analysis
    print("\n" + "=" * 70)
    print("COMBINED ANALYSIS (ALL BAGS)")
    print("=" * 70)
    
    print_histogram(all_good_near, "Good-Near h_f Distribution")
    
    stats = compute_stats(all_good_near, "good_near_combined")
    if stats:
        print(f"\n  Combined Good-Near Statistics (n={stats['count']}):")
        print(f"    min:    {stats['min']:.1f} px")
        print(f"    max:    {stats['max']:.1f} px")
        print(f"    mean:   {stats['mean']:.1f} px")
        print(f"    median: {stats['median']:.1f} px")
        print(f"    P25:    {stats['p25']:.1f} px")
        print(f"    P75:    {stats['p75']:.1f} px")
        print(f"    stdev:  {stats['stdev']:.1f} px")
    
    # All h_f histogram for context
    print_histogram(all_hf_combined, "All h_f Distribution (context)")
    
    # Recommendation
    print("\n" + "=" * 70)
    print("RECOMMENDED CALIBRATION VALUES")
    print("=" * 70)
    
    if stats:
        # Use median of good-near as stand_off_px
        recommended_stand_off = round(stats['median'])
        # Use P75 + margin as max_close_px
        recommended_max_close = round(stats['p75'] + 80)
        
        print(f"""
  Based on analysis of {len(results)} bags with {stats['count']} "good-near" samples:
  
  CURRENT VALUES:
    stand_off_px: 300.0  (often unachievable)
    max_close_px: 420.0
    
  RECOMMENDED VALUES:
    stand_off_px: {recommended_stand_off:.1f}  (median of good-near h_f)
    max_close_px: {recommended_max_close:.1f}  (P75 + 80px margin)
    
  REASONING:
    - Good-near h_f median = {stats['median']:.1f} px
    - Good-near h_f P75 = {stats['p75']:.1f} px
    - Setting stand_off to median ensures it's achievable
    - max_close at P75+80 gives a comfortable "too close" buffer
""")
    else:
        print("  ERROR: No good-near samples to base recommendation on!")


if __name__ == '__main__':
    main()
