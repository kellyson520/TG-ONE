import os
import argparse
import sys
import json
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

# Import the new utility
from utils.core.trace_analyzer import TraceAnalyzer

LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE = Path(LOG_DIR) / "app.log"

def main():
    parser = argparse.ArgumentParser(description="Analyze logs for a specific Trace UUID.")
    parser.add_argument("uuid", help="The UUID/Trace ID to search for.")
    parser.add_argument("--file", default=str(LOG_FILE), help="Path to log file.")
    parser.add_argument("--format", choices=["text", "markdown", "json"], default="text", help="Output format.")
    
    args = parser.parse_args()
    
    target_uuid = args.uuid
    log_path = Path(args.file)
    
    analyzer = TraceAnalyzer(str(log_path))
    
    if not log_path.exists():
        print(f"Error: Log file not found at {log_path}")
        return

    print(f"Analyzing {log_path} for Trace ID: {target_uuid}...\n")
    
    events = analyzer.analyze(target_uuid)

    if not events:
        print("No events found for this UUID.")
        return

    start_time = events[0]["timestamp"]
    
    if args.format == "markdown":
        print(analyzer.generate_markdown(target_uuid, events))
            
    elif args.format == "json":
        def date_handler(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj
        print(json.dumps(events, default=date_handler, indent=2, ensure_ascii=False))
        
    else: # Text
        print(f"{'TIME':<24} {'DELTA':<8} {'MODULE':<20} {'MESSAGE'}")
        print("-" * 80)
        for event in events:
            delta_str = ""
            if event["timestamp"] and start_time:
                delta = (event["timestamp"] - start_time).total_seconds() * 1000
                delta_str = f"+{delta:.0f}ms"
            
            print(f"{event['timestamp_str']:<24} {delta_str:<8} {event['module']:<20} {event['message']}")

if __name__ == "__main__":
    main()
