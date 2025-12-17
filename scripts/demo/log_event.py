#!/usr/bin/env python3
"""
log_event.py - Helper script for logging events from shell scripts.

Usage:
    python3 log_event.py EVENT_NAME '{"key": "value"}'
    python3 log_event.py ACTOR_SPAWNED '{"actor": "human_target", "world": "default"}'
    python3 log_event.py DEMO_RESET '{}'

Events are appended to ~/sahtd/data/logs/events.jsonl in the same format
as the ROS event_logger_node.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_timestamp() -> str:
    """Get ISO 8601 timestamp with milliseconds."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def log_event(event_name: str, source: str, data: dict, log_path: Path):
    """Append event to JSONL log file."""
    event = {
        'ts': get_timestamp(),
        'event': event_name,
        'source': source,
        'data': data
    }

    # Ensure directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Append to file
    with open(log_path, 'a') as f:
        line = json.dumps(event, separators=(',', ':'))
        f.write(line + '\n')

    # Print for terminal visibility
    data_str = ' '.join(f'{k}={v}' for k, v in data.items() if v)
    print(f"EVENT: {event['ts']} {event_name} [{source}] {data_str}", flush=True)

    return event


def main():
    if len(sys.argv) < 2:
        print("Usage: log_event.py EVENT_NAME [JSON_DATA] [--source SOURCE]", file=sys.stderr)
        print("  EVENT_NAME: Event type (e.g., ACTOR_SPAWNED, DEMO_RESET)", file=sys.stderr)
        print("  JSON_DATA:  Optional JSON object with event data (default: {})", file=sys.stderr)
        print("  --source:   Event source identifier (default: demo_script)", file=sys.stderr)
        sys.exit(1)

    event_name = sys.argv[1]
    
    # Parse optional JSON data
    data = {}
    source = 'demo_script'
    
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--source' and i + 1 < len(sys.argv):
            source = sys.argv[i + 1]
            i += 2
        elif arg.startswith('{'):
            try:
                data = json.loads(arg)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON: {e}", file=sys.stderr)
                sys.exit(1)
            i += 1
        else:
            i += 1

    # Compute log path using SAHTD_ROOT or fallback
    sahtd_root = os.environ.get('SAHTD_ROOT')
    if not sahtd_root:
        # Auto-detect by walking up from this script
        current = Path(__file__).resolve().parent
        for _ in range(10):
            if (current / '.git').is_dir() or ((current / 'ros2').is_dir() and (current / 'web').is_dir()):
                sahtd_root = str(current)
                break
            parent = current.parent
            if parent == current:
                break
            current = parent
        if not sahtd_root:
            sahtd_root = os.path.expanduser('~/sahtd')
    
    log_path = Path(sahtd_root) / 'data' / 'logs' / 'events.jsonl'

    try:
        log_event(event_name, source, data, log_path)
    except Exception as e:
        print(f"Error logging event: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
