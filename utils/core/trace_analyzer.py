import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

class TraceAnalyzer:
    """Core logic for extracting trace events from log files."""

    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
    
    @staticmethod
    def parse_line(line: str) -> Optional[Dict]:
        """
        Parse a log line formatted as:
        【YYYY-MM-DD HH:mm:ss,ms】[UUID]【Logger】Message
        """
        pattern = r"^【(.*?)】\[(.*?)\]【(.*?)】(.*)$"
        match = re.match(pattern, line)
        
        if match:
            timestamp_str = match.group(1)
            uuid = match.group(2)
            module = match.group(3)
            message = match.group(4).strip()
            
            try:
               timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
            except ValueError:
               try:
                   timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
               except:
                   timestamp = None

            return {
                "timestamp": timestamp,
                "timestamp_str": timestamp_str,
                "uuid": uuid,
                "module": module,
                "message": message,
                "raw": line.strip()
            }
        return None

    def analyze(self, trace_id: str) -> List[Dict]:
        """Extract events matching the trace_id."""
        events = []
        
        if not self.log_path.exists():
            return []
            
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if trace_id in line:
                        parsed = self.parse_line(line)
                        if parsed and parsed["uuid"] == trace_id:
                            events.append(parsed)
                        elif trace_id in line:
                             events.append({
                                 "timestamp": None,
                                 "timestamp_str": "---",
                                 "uuid": trace_id,
                                 "module": "UNKNOWN",
                                 "message": line.strip(),
                                 "raw": line.strip()
                             })
        except Exception:
            return []

        # Sort
        events.sort(key=lambda x: x["timestamp"] if x["timestamp"] else datetime.min)
        return events

    def generate_markdown(self, trace_id: str, events: List[Dict]) -> str:
        """Generate markdown report."""
        if not events:
            return f"# Trace Report: `{trace_id}`\n\nNo events found."
            
        lines = []
        lines.append(f"# Trace Report: `{trace_id}`\n")
        lines.append(f"- **Time**: {events[0]['timestamp_str']}")
        lines.append(f"- **Total Events**: {len(events)}")
        
        start_time = events[0]["timestamp"]
        if start_time and events[-1]["timestamp"]:
            duration = (events[-1]["timestamp"] - start_time).total_seconds() * 1000
            lines.append(f"- **Duration**: {duration:.2f} ms")
            
        lines.append("\n| Time | Delta (ms) | Module | Message |")
        lines.append("|---|---|---|---|")
        
        for event in events:
            delta = 0
            if event["timestamp"] and start_time:
                delta = (event["timestamp"] - start_time).total_seconds() * 1000
            
            msg = event['message'].replace('|', r'\|') # Escape pipes
            ts = event['timestamp_str'].split(' ')[1] if ' ' in event['timestamp_str'] else event['timestamp_str']
            lines.append(f"| {ts} | +{delta:.0f} | `{event['module']}` | {msg} |")
            
        return "\n".join(lines)
