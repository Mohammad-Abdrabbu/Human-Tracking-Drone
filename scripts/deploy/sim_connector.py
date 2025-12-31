#!/usr/bin/env python3
"""
SAHTD Simulation Connector
Reads local telemetry/events and POSTs to VPS backend over Tailscale.

Usage:
    python3 sim_connector.py --source-id serverA --vps-url https://sahtd.example.com

Environment variables:
    SAHTD_SOURCE_ID     - Source identifier (serverA/serverB)
    SAHTD_VPS_URL       - VPS backend URL
    SAHTD_INGEST_TOKEN  - Shared ingest token
    SAHTD_ROOT          - Path to sahtd repo root
"""
import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime, timezone


def iso_now():
    """Return ISO-8601 timestamp with Z suffix."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def tail_file(path: Path, callback, poll_interval=0.3):
    """Tail a file and call callback for each new line."""
    if not path.exists():
        return
    with open(path, "r") as f:
        f.seek(0, 2)  # End of file
        while True:
            line = f.readline()
            if line:
                callback(line.strip())
            else:
                time.sleep(poll_interval)
            if not path.exists():
                break


class Connector:
    def __init__(self, source_id: str, vps_url: str, ingest_token: str):
        self.source_id = source_id
        self.vps_url = vps_url.rstrip("/")
        self.headers = {"X-Ingest-Token": ingest_token, "Content-Type": "application/json"}
        self.sahtd_root = Path(os.getenv("SAHTD_ROOT", Path.home() / "sahtd"))
        self.telemetry_path = self.sahtd_root / "data" / "logs" / "telemetry.jsonl"
        self.events_path = self.sahtd_root / "data" / "logs" / "events.jsonl"
        self.running = True
    
    def send_heartbeat(self):
        """Send heartbeat to VPS."""
        try:
            r = requests.post(
                f"{self.vps_url}/ingest/heartbeat",
                json={"source_id": self.source_id, "ts": iso_now()},
                headers=self.headers,
                timeout=10,
            )
            print(f"[HEARTBEAT] {r.status_code}: {r.text[:100]}")
            return r.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"[HEARTBEAT] ERROR: {e}")
            return False
    
    def send_telemetry(self, line: str):
        """Send a telemetry line to VPS."""
        try:
            telemetry = json.loads(line)
            r = requests.post(
                f"{self.vps_url}/ingest/telemetry",
                json={"source_id": self.source_id, "telemetry": telemetry, "ts": iso_now()},
                headers=self.headers,
                timeout=5,
            )
            if r.status_code != 200:
                print(f"[TELEM] FAIL {r.status_code}: {r.text[:80]}")
        except json.JSONDecodeError:
            pass
        except requests.exceptions.RequestException as e:
            print(f"[TELEM] ERROR: {e}")
    
    def send_event(self, line: str):
        """Send an event line to VPS."""
        try:
            event = json.loads(line)
            r = requests.post(
                f"{self.vps_url}/ingest/events",
                json={
                    "source_id": self.source_id,
                    "event_type": event.get("type", "UNKNOWN"),
                    "data": event,
                    "ts": event.get("ts", iso_now()),
                },
                headers=self.headers,
                timeout=5,
            )
            if r.status_code != 200:
                print(f"[EVENT] FAIL {r.status_code}: {r.text[:80]}")
        except json.JSONDecodeError:
            pass
        except requests.exceptions.RequestException as e:
            print(f"[EVENT] ERROR: {e}")
    
    def run(self):
        """Main connector loop."""
        print(f"[CONNECTOR] source_id   = {self.source_id}")
        print(f"[CONNECTOR] vps_url     = {self.vps_url}")
        print(f"[CONNECTOR] sahtd_root  = {self.sahtd_root}")
        print(f"[CONNECTOR] telemetry   = {self.telemetry_path}")
        print(f"[CONNECTOR] events      = {self.events_path}")
        
        # Send initial heartbeat
        if not self.send_heartbeat():
            print("[CONNECTOR] WARNING: Initial heartbeat failed - check VPS URL and token")
        
        import threading
        
        # Tail telemetry in thread
        def tail_telemetry():
            while self.running:
                if self.telemetry_path.exists():
                    tail_file(self.telemetry_path, self.send_telemetry, poll_interval=0.5)
                time.sleep(2)
        
        # Tail events in thread
        def tail_events():
            while self.running:
                if self.events_path.exists():
                    tail_file(self.events_path, self.send_event, poll_interval=0.5)
                time.sleep(2)
        
        # Periodic heartbeat
        def heartbeat_loop():
            while self.running:
                time.sleep(30)
                self.send_heartbeat()
        
        t1 = threading.Thread(target=tail_telemetry, daemon=True, name="telemetry-tail")
        t2 = threading.Thread(target=tail_events, daemon=True, name="events-tail")
        t3 = threading.Thread(target=heartbeat_loop, daemon=True, name="heartbeat")
        
        t1.start()
        t2.start()
        t3.start()
        
        print("[CONNECTOR] Running... Press Ctrl+C to stop")
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[CONNECTOR] Stopping...")
            self.running = False


def main():
    parser = argparse.ArgumentParser(description="SAHTD Simulation Connector")
    parser.add_argument("--source-id", 
                        default=os.getenv("SAHTD_SOURCE_ID", "serverA"),
                        help="Source identifier (default: serverA)")
    parser.add_argument("--vps-url", 
                        default=os.getenv("SAHTD_VPS_URL", "https://sahtd.example.com"),
                        help="VPS backend URL")
    parser.add_argument("--ingest-token", 
                        default=os.getenv("SAHTD_INGEST_TOKEN", ""),
                        help="Ingest auth token")
    args = parser.parse_args()
    
    if not args.ingest_token:
        print("[WARN] No ingest token provided - requests may be rejected")
    
    connector = Connector(args.source_id, args.vps_url, args.ingest_token)
    connector.run()


if __name__ == "__main__":
    main()
