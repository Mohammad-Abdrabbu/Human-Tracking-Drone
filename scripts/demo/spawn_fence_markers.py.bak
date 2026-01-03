#!/usr/bin/env python3
"""
spawn_fence_markers.py - Spawn visible markers at geo-fence polygon vertices in Gazebo.

Reads the same fence YAML used by geo_guard_node and spawns cylinder markers
at each vertex position so the fence is visually apparent in Gazebo.

Usage:
    python3 spawn_fence_markers.py [--world NAME] [--fence-yaml PATH] [--dry-run]
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

import yaml


def get_default_fence_yaml() -> str:
    """Get the default fence YAML path (same as geo_guard_node uses)."""
    # Try SAHTD_ROOT first
    sahtd_root = os.environ.get('SAHTD_ROOT', os.path.expanduser('~/sahtd'))
    
    # Default path used by demo_follow.launch.py
    default_path = os.path.join(
        sahtd_root, 
        'ros2/src/sahtd_launch/config/geo_guard.yaml'
    )
    return default_path


def parse_vertices_from_yaml(yaml_path: str, node_name: str = 'geo_guard_node') -> list:
    """
    Parse polygon vertices from fence YAML file.
    
    Args:
        yaml_path: Path to fence YAML file
        node_name: YAML node name containing ros__parameters.vertices
        
    Returns:
        List of (x, y) tuples
    """
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Navigate: node_name -> ros__parameters -> vertices
    if node_name not in data:
        raise ValueError(f"Node '{node_name}' not found in {yaml_path}")
    
    params = data[node_name].get('ros__parameters', {})
    vertices_flat = params.get('vertices', [])
    
    if len(vertices_flat) < 6:  # Need at least 3 vertices (6 values)
        raise ValueError(f"Invalid vertices array (need >= 6 values): {vertices_flat}")
    
    # Parse flat array into (x, y) pairs
    vertices = list(zip(vertices_flat[0::2], vertices_flat[1::2]))
    return vertices


def generate_cylinder_sdf(name: str, x: float, y: float, z: float,
                          radius: float, height: float, 
                          color_rgba: tuple = (1.0, 0.2, 0.2, 1.0)) -> str:
    """
    Generate SDF string for a cylinder marker model.
    
    Args:
        name: Model name
        x, y, z: Position in world frame
        radius: Cylinder radius (meters)
        height: Cylinder height (meters)
        color_rgba: RGBA color tuple (0-1 range)
    
    Returns:
        SDF XML string
    """
    r, g, b, a = color_rgba
    
    sdf = f'''<?xml version="1.0"?>
<sdf version="1.9">
  <model name="{name}">
    <static>true</static>
    <pose>{x} {y} {z} 0 0 0</pose>
    <link name="marker_link">
      <visual name="marker_visual">
        <geometry>
          <cylinder>
            <radius>{radius}</radius>
            <length>{height}</length>
          </cylinder>
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


def generate_edge_sdf(name: str, x1: float, y1: float, x2: float, y2: float,
                      z: float, thickness: float = 0.03,
                      color_rgba: tuple = (1.0, 0.5, 0.0, 0.8)) -> str:
    """
    Generate SDF string for an edge (thin box) between two vertices.
    
    Args:
        name: Model name
        x1, y1: Start vertex
        x2, y2: End vertex
        z: Height above ground
        thickness: Edge line thickness
        color_rgba: RGBA color tuple
    
    Returns:
        SDF XML string
    """
    import math
    
    # Calculate edge center and orientation
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    length = math.hypot(x2 - x1, y2 - y1)
    yaw = math.atan2(y2 - y1, x2 - x1)
    
    r, g, b, a = color_rgba
    
    sdf = f'''<?xml version="1.0"?>
<sdf version="1.9">
  <model name="{name}">
    <static>true</static>
    <pose>{cx} {cy} {z} 0 0 {yaw}</pose>
    <link name="edge_link">
      <visual name="edge_visual">
        <geometry>
          <box>
            <size>{length} {thickness} {thickness}</size>
          </box>
        </geometry>
        <material>
          <ambient>{r} {g} {b} {a}</ambient>
          <diffuse>{r} {g} {b} {a}</diffuse>
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
        description='Spawn geo-fence markers in Gazebo',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 spawn_fence_markers.py --dry-run
  python3 spawn_fence_markers.py --world default
  python3 spawn_fence_markers.py --fence-yaml /path/to/custom.yaml
'''
    )
    
    parser.add_argument('--world', default='default',
                        help='Gazebo world name (default: default)')
    parser.add_argument('--fence-yaml', default=None,
                        help='Path to fence YAML (default: auto-detect)')
    parser.add_argument('--polygon', default='geo_guard_node',
                        help='YAML node name for vertices (default: geo_guard_node)')
    parser.add_argument('--z', type=float, default=0.05,
                        help='Marker height above ground (default: 0.05)')
    parser.add_argument('--radius', type=float, default=0.12,
                        help='Cylinder radius in meters (default: 0.12)')
    parser.add_argument('--height', type=float, default=0.20,
                        help='Cylinder height in meters (default: 0.20)')
    parser.add_argument('--prefix', default='fence_marker',
                        help='Model name prefix (default: fence_marker)')
    parser.add_argument('--edges', choices=['on', 'off'], default='off',
                        help='Draw edges between vertices (default: off)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print vertices and planned markers without spawning')
    
    args = parser.parse_args()
    
    # Get fence YAML path
    fence_yaml = args.fence_yaml or get_default_fence_yaml()
    
    if not os.path.exists(fence_yaml):
        print(f"Error: Fence YAML not found: {fence_yaml}")
        sys.exit(1)
    
    print(f"=== Geo-Fence Marker Spawner ===")
    print(f"  World:      {args.world}")
    print(f"  Fence YAML: {fence_yaml}")
    print(f"  Polygon:    {args.polygon}")
    print(f"  Prefix:     {args.prefix}")
    print()
    
    # Parse vertices
    try:
        vertices = parse_vertices_from_yaml(fence_yaml, args.polygon)
    except Exception as e:
        print(f"Error parsing YAML: {e}")
        sys.exit(1)
    
    print(f"Polygon vertices ({len(vertices)}):")
    for i, (x, y) in enumerate(vertices):
        print(f"  V{i}: ({x:.2f}, {y:.2f})")
    print()
    
    if args.dry_run:
        print("Dry-run mode: No markers will be spawned")
        print()
        print("Planned markers:")
        for i, (x, y) in enumerate(vertices):
            name = f"{args.prefix}_v{i}"
            print(f"  {name} at ({x:.2f}, {y:.2f}, {args.z:.2f})")
        
        if args.edges == 'on':
            print()
            print("Planned edges:")
            for i in range(len(vertices)):
                j = (i + 1) % len(vertices)
                name = f"{args.prefix}_e{i}"
                print(f"  {name}: V{i} → V{j}")
        
        sys.exit(0)
    
    # Spawn vertex markers
    print("Spawning vertex markers...")
    spawned = 0
    skipped = 0
    
    for i, (x, y) in enumerate(vertices):
        name = f"{args.prefix}_v{i}"
        
        # Check if already exists
        if model_exists(args.world, name):
            print(f"  {name}: Already exists, skipping")
            skipped += 1
            continue
        
        # Generate SDF
        sdf = generate_cylinder_sdf(
            name=name,
            x=x, y=y, z=args.z + args.height/2,  # Adjust z to center cylinder
            radius=args.radius,
            height=args.height,
            color_rgba=(1.0, 0.2, 0.2, 1.0)  # Bright red
        )
        
        if spawn_model(args.world, sdf, name):
            print(f"  {name}: ✓ Spawned at ({x:.2f}, {y:.2f})")
            spawned += 1
        else:
            print(f"  {name}: ✗ Failed to spawn")
    
    # Spawn edges if requested
    if args.edges == 'on':
        print()
        print("Spawning edge markers...")
        for i in range(len(vertices)):
            j = (i + 1) % len(vertices)
            x1, y1 = vertices[i]
            x2, y2 = vertices[j]
            name = f"{args.prefix}_e{i}"
            
            if model_exists(args.world, name):
                print(f"  {name}: Already exists, skipping")
                skipped += 1
                continue
            
            sdf = generate_edge_sdf(
                name=name,
                x1=x1, y1=y1, x2=x2, y2=y2,
                z=args.z,
                thickness=0.03,
                color_rgba=(1.0, 0.5, 0.0, 0.8)  # Orange
            )
            
            if spawn_model(args.world, sdf, name):
                print(f"  {name}: ✓ Spawned (V{i} → V{j})")
                spawned += 1
            else:
                print(f"  {name}: ✗ Failed to spawn")
    
    print()
    print(f"Summary: {spawned} spawned, {skipped} skipped")


if __name__ == '__main__':
    main()
