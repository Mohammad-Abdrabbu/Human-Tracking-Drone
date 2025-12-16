#!/usr/bin/env python3
"""
auto_select_target.py - Simple auto-select using the same mechanism as follow_node

Waits for seen_ids from follow_node, picks first ID, and publishes selection.
Much simpler than a full ROS node - just a one-shot command.

Usage:
  python3 auto_select_target.py [--timeout 15]
"""
import argparse
import subprocess
import time
import sys


def get_seen_ids(timeout=1.0):
    """Get current seen IDs from follow_node."""
    try:
        result = subprocess.run(
            ['ros2', 'topic', 'echo', '/sahtd/follow/seen_ids', '--once'],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        # Parse output like: data: 'ids=1,3,5'
        for line in result.stdout.split('\n'):
            if "data:" in line and "ids=" in line:
                # Extract the ids part
                start = line.find("ids=") + 4
                # Find end (could be quote or end of line)
                ids_str = line[start:].strip().strip("'\"")
                if ids_str:
                    return [int(x.strip()) for x in ids_str.split(',') if x.strip()]
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        print(f"Error getting seen_ids: {e}")
    
    return []


def publish_selection(target_id):
    """Publish target selection."""
    try:
        subprocess.run(
            ['ros2', 'topic', 'pub', '/perception/target_select', 
             'std_msgs/msg/Int32', f'{{data: {target_id}}}', '--once'],
            capture_output=True,
            timeout=5
        )
        return True
    except Exception as e:
        print(f"Error publishing selection: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Auto-select first visible target')
    parser.add_argument('--timeout', type=float, default=15.0,
                        help='Timeout in seconds (default: 15)')
    parser.add_argument('--policy', choices=['first', 'best'], default='first',
                        help='Selection policy (default: first)')
    args = parser.parse_args()
    
    print(f"Auto-selecting target (timeout: {args.timeout}s)...")
    
    start = time.time()
    while time.time() - start < args.timeout:
        ids = get_seen_ids(timeout=2.0)
        
        if ids:
            # Pick first ID (simplest, most reliable)
            target_id = ids[0]
            
            if publish_selection(target_id):
                print(f"✓ Selected target id={target_id}")
                return 0
            else:
                print(f"✗ Failed to publish selection")
                return 1
        
        time.sleep(0.5)
    
    print(f"✗ Timeout: No targets found after {args.timeout}s")
    return 1


if __name__ == '__main__':
    sys.exit(main())
