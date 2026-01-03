#!/usr/bin/env python3
"""
spawn_actors.py - Spawn actors for Fit Expo demo.
"""
import sys
import os
import subprocess
import argparse

def spawn_model(world, sdf_path, name, x, y, z):
    if not os.path.exists(sdf_path):
        print(f"Error: SDF not found: {sdf_path}")
        return False
        
    req_str = f'sdf_filename: "{sdf_path}", name: "{name}", allow_renaming: true, pose: {{position: {{x: {x}, y: {y}, z: {z}}}}}'
    
    try:
        subprocess.run(['gz', 'service', '-s', f'/world/{world}/create',
                       '--reqtype', 'gz.msgs.EntityFactory',
                       '--reptype', 'gz.msgs.Boolean',
                       '--timeout', '5000',
                       '--req', req_str], check=True, capture_output=True)
        print(f"  {name} spawned")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Failed to spawn {name}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--world', default='default')
    parser.add_argument('--spawn_walker', action='store_true', help='Spawn the walking actor')
    parser.add_argument('--extras', type=int, default=0, help='Number of standing humans')
    args = parser.parse_args()
    
    sahtd_root = os.environ.get('SAHTD_ROOT', os.path.expanduser('~/sahtd'))
    
    # Spawn Walker
    if args.spawn_walker:
        walker_sdf = os.path.join(sahtd_root, 'simulation/models/actor_expo_walker/model.sdf')
        spawn_model(args.world, walker_sdf, 'expo_walker', 2.0, 3.0, 1.0)
    
    # Spawn Extras (Standing at booths)
    if args.extras > 0:
        standing_sdf = os.path.join(sahtd_root, 'simulation/models/Casual female/model.sdf')
        
        booth_positions = [
            (2.0, -2.0), # Booth 1
            (8.0, 5.0),  # Booth 2
            (15.0, 0.0), # Booth 3
            (10.0, -5.0) # Booth 4
        ]
        
        for i in range(min(args.extras, len(booth_positions))):
            x, y = booth_positions[i]
            spawn_model(args.world, standing_sdf, f'expo_stand_{i+1}', x, y, 0.0)

if __name__ == '__main__':
    main()
