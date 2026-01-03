#!/usr/bin/env python3
"""
spawn_markers.py - Spawn visible markers for Fit Expo fence.
"""

import argparse
import subprocess
import sys
import os
import yaml

def get_default_fence_yaml() -> str:
    """Get the fit expo fence YAML path."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, 'geo_guard_fitexpo.yaml')

def parse_vertices_from_yaml(yaml_path: str, node_name: str = 'geo_guard_node') -> list:
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    
    if node_name not in data:
        raise ValueError(f"Node '{node_name}' not found in {yaml_path}")
    
    params = data[node_name].get('ros__parameters', {})
    vertices_flat = params.get('vertices', [])
    
    if len(vertices_flat) < 6:
        raise ValueError(f"Invalid vertices array: {vertices_flat}")
    
    return list(zip(vertices_flat[0::2], vertices_flat[1::2]))

def generate_cylinder_sdf(name: str, x: float, y: float, z: float,
                          radius: float, height: float, 
                          color_rgba: tuple) -> str:
    r, g, b, a = color_rgba
    return f'''<?xml version="1.0"?>
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

def model_exists(world: str, model_name: str) -> bool:
    try:
        result = subprocess.run(
            ['gz', 'model', '--list', '--world', world],
            capture_output=True, text=True, timeout=5
        )
        return model_name in result.stdout
    except Exception:
        return False

def spawn_model(world: str, sdf_string: str, model_name: str) -> bool:
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
        print(f"Error spawning {model_name}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Spawn Fit Expo fence markers')
    parser.add_argument('--world', default='default')
    args = parser.parse_args()
    
    fence_yaml = get_default_fence_yaml()
    if not os.path.exists(fence_yaml):
        print(f"Error: YAML not found: {fence_yaml}")
        sys.exit(1)
        
    try:
        vertices = parse_vertices_from_yaml(fence_yaml)
    except Exception as e:
        print(f"Error parsing YAML: {e}")
        sys.exit(1)
        
    print(f"Spawning {len(vertices)} markers for Fit Expo...")
    
    for i, (x, y) in enumerate(vertices):
        name = f"expo_marker_v{i}"
        if model_exists(args.world, name):
            continue
            
        # Green/Teal scheme for expo
        sdf = generate_cylinder_sdf(
            name=name,
            x=x, y=y, z=0.15,
            radius=0.15, height=0.30,
            color_rgba=(0.0, 0.8, 0.6, 0.9) # Teal
        )
        spawn_model(args.world, sdf, name)
        
    print("Done.")

if __name__ == '__main__':
    main()
