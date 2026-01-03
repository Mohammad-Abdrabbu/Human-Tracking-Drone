#!/usr/bin/env python3
"""
spawn_human_path_markers.py - Spawn visible markers along actor walking path in Gazebo.

Reads actor SDF file to extract trajectory waypoints and spawns cylinder/sphere markers
at each waypoint position so the human's path is visually apparent in Gazebo.

Usage:
    python3 spawn_human_path_markers.py [--world NAME] [--actor-sdf PATH] [--dry-run]
"""

import argparse
import subprocess
import sys
import os
import xml.etree.ElementTree as ET
from pathlib import Path


def get_default_actor_sdf() -> str:
    """Get the default actor SDF path (same as demo_committee.sh uses)."""
    sahtd_root = os.environ.get('SAHTD_ROOT', os.path.expanduser('~/sahtd'))
    default_path = os.path.join(
        sahtd_root, 
        'simulation/models/actor_walk_slow/model.sdf'
    )
    return default_path


def parse_waypoints_from_sdf(sdf_path: str) -> list:
    """
    Parse trajectory waypoints from actor SDF file.
    
    Args:
        sdf_path: Path to actor SDF file
        
    Returns:
        List of (x, y, z, time) tuples
    """
    tree = ET.parse(sdf_path)
    root = tree.getroot()
    
    # Find trajectory waypoints: sdf/actor/script/trajectory/waypoint
    waypoints = []
    
    for actor in root.findall('.//actor'):
        for script in actor.findall('.//script'):
            for trajectory in script.findall('.//trajectory'):
                for waypoint in trajectory.findall('.//waypoint'):
                    time_elem = waypoint.find('time')
                    pose_elem = waypoint.find('pose')
                    
                    if time_elem is not None and pose_elem is not None:
                        time = float(time_elem.text)
                        # Parse pose: "x y z roll pitch yaw"
                        pose_parts = pose_elem.text.strip().split()
                        if len(pose_parts) >= 3:
                            x, y, z = float(pose_parts[0]), float(pose_parts[1]), float(pose_parts[2])
                            waypoints.append((x, y, z, time))
    
    if not waypoints:
        raise ValueError(f"No waypoints found in {sdf_path}")
    
    return waypoints


def generate_pavement_sdf(name: str, x1: float, y1: float, x2: float, y2: float,
                          z: float = 0.01, width: float = 1.5, thickness: float = 0.02,
                          color_rgba: tuple = (0.6, 0.6, 0.6, 1.0)) -> str:
    """
    Generate SDF string for a pavement section between two waypoints.
    
    Args:
        name: Model name
        x1, y1: Start waypoint
        x2, y2: End waypoint
        z: Height above ground (very small for flat pavement)
        width: Pavement width in meters (default: 1.5m)
        thickness: Pavement thickness (default: 0.02m / 2cm)
        color_rgba: RGBA color tuple (gray pavement color)
    
    Returns:
        SDF XML string
    """
    import math
    
    # Calculate pavement center and orientation
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    cz = z  # Pavement stays flat on ground
    
    # Calculate length (distance between waypoints)
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx*dx + dy*dy)
    
    # Calculate yaw (rotation around z-axis for horizontal orientation)
    yaw = math.atan2(dy, dx)
    
    r, g, b, a = color_rgba
    
    sdf = f'''<?xml version="1.0"?>
<sdf version="1.9">
  <model name="{name}">
    <static>true</static>
    <pose>{cx} {cy} {cz} 0 0 {yaw}</pose>
    <link name="pavement_link">
      <visual name="pavement_visual">
        <geometry>
          <box>
            <size>{length} {width} {thickness}</size>
          </box>
        </geometry>
        <material>
          <ambient>{r} {g} {b} {a}</ambient>
          <diffuse>{r} {g} {b} {a}</diffuse>
          <specular>0.1 0.1 0.1 1</specular>
        </material>
      </visual>
    </link>
  </model>
</sdf>'''
    return sdf


def model_exists(world: str, model_name: str) -> bool:
    """Check if a model already exists in the Gazebo world."""
    try:
        result = subprocess.run(
            ['gz', 'model', '--list', '--world', world],
            capture_output=True, text=True, timeout=5
        )
        return model_name in result.stdout
    except Exception:
        return False


def spawn_model(world: str, sdf_string: str, model_name: str) -> bool:
    """
    Spawn a model in Gazebo using gz service.
    
    Args:
        world: Gazebo world name
        sdf_string: SDF XML string
        model_name: Name for the model
    
    Returns:
        True if successful
    """
    # Escape the SDF string for the request
    sdf_escaped = sdf_string.replace('"', '\\"').replace('\n', ' ')
    
    cmd = [
        'gz', 'service', '-s', f'/world/{world}/create',
        '--reqtype', 'gz.msgs.EntityFactory',
        '--reptype', 'gz.msgs.Boolean',
        '--timeout', '5000',
        '--req', f'sdf: "{sdf_escaped}", name: "{model_name}", allow_renaming: false'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception as e:
        print(f"  Error spawning {model_name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Spawn human path markers in Gazebo',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 spawn_human_path_markers.py --dry-run
  python3 spawn_human_path_markers.py --world default
  python3 spawn_human_path_markers.py --actor-sdf /path/to/custom_actor.sdf
  python3 spawn_human_path_markers.py --width 2.0  # Wider pavement
'''
    )
    
    parser.add_argument('--world', default='default',
                        help='Gazebo world name (default: default)')
    parser.add_argument('--actor-sdf', default=None,
                        help='Path to actor SDF file (default: auto-detect)')
    parser.add_argument('--width', type=float, default=1.5,
                        help='Pavement width in meters (default: 1.5)')
    parser.add_argument('--z-height', type=float, default=0.01,
                        help='Pavement height above ground (default: 0.01m)')
    parser.add_argument('--prefix', default='pavement',
                        help='Model name prefix (default: pavement)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print waypoints and planned pavement without spawning')
    
    args = parser.parse_args()
    
    # Get actor SDF path
    actor_sdf = args.actor_sdf or get_default_actor_sdf()
    
    if not os.path.exists(actor_sdf):
        print(f"Error: Actor SDF not found: {actor_sdf}")
        sys.exit(1)
    
    print(f"=== Human Path Pavement Spawner ===")
    print(f"  World:     {args.world}")
    print(f"  Actor SDF: {actor_sdf}")
    print(f"  Width:     {args.width}m")
    print(f"  Prefix:    {args.prefix}")
    print()
    
    # Parse waypoints
    try:
        waypoints = parse_waypoints_from_sdf(actor_sdf)
    except Exception as e:
        print(f"Error parsing SDF: {e}")
        sys.exit(1)
    
    print(f"Path waypoints ({len(waypoints)}):")
    for i, (x, y, z, t) in enumerate(waypoints):
        print(f"  W{i}: ({x:.2f}, {y:.2f}, {z:.2f}) @ t={t:.1f}s")
    print()
    
    if args.dry_run:
        print("Dry-run mode: No pavement will be spawned")
        print()
        print("Planned pavement sections:")
        for i in range(len(waypoints) - 1):
            x1, y1, _, _ = waypoints[i]
            x2, y2, _, _ = waypoints[i + 1]
            import math
            length = math.sqrt((x2-x1)**2 + (y2-y1)**2)
            name = f"{args.prefix}_segment{i}"
            print(f"  {name}: W{i} → W{i+1} (length: {length:.2f}m, width: {args.width}m)")
        
        sys.exit(0)
    
    # Spawn pavement sections
    print("Spawning pavement sections...")
    spawned = 0
    skipped = 0
    
    for i in range(len(waypoints) - 1):
        x1, y1, z1, _ = waypoints[i]
        x2, y2, z2, _ = waypoints[i + 1]
        name = f"{args.prefix}_segment{i}"
        
        # Check if already exists
        if model_exists(args.world, name):
            print(f"  {name}: Already exists, skipping")
            skipped += 1
            continue
        
        # Generate pavement SDF
        sdf = generate_pavement_sdf(
            name=name,
            x1=x1, y1=y1, x2=x2, y2=y2,
            z=args.z_height,
            width=args.width,
            thickness=0.02,
            color_rgba=(0.6, 0.6, 0.6, 1.0)  # Gray pavement
        )
        
        if spawn_model(args.world, sdf, name):
            print(f"  {name}: ✓ Spawned (W{i} → W{i+1})")
            spawned += 1
        else:
            print(f"  {name}: ✗ Failed to spawn")
    
    print()
    print(f"Summary: {spawned} spawned, {skipped} skipped")


if __name__ == '__main__':
    main()
