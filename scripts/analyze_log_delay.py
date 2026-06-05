
import re
import sys

# Set stdout to utf-8
sys.stdout.reconfigure(encoding='utf-8')

LOG_FILE = r"e:\重构\TG ONE\telegram-forwarder-opt-20260208094719.log"

def parse_logs():
    print(f"Analyzing {LOG_FILE}...")
    
    events = []
    
    # Relaxed pattern: find date anywhere in line
    time_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})")
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            lines_read = 0
            for line in f:
                lines_read += 1
                match = time_pattern.search(line)
                if match:
                    timestamp_str = match.group(1)
                    
                    # Print first few lines to debug
                    if lines_read < 5:
                        print(f"DEBUG line {lines_read}: {line.strip()}")

                    # Check for 09:45
                    if "09:45" in timestamp_str:
                         print(f"MATCH 09:45: {line.strip()}")
                    
                    # Check for start of forwarding at 09:38
                    if "09:38" in timestamp_str:
                        if "NewMessage" in line or "Received" in line or "bootstrap" in line:
                             print(f"MATCH 09:38: {line.strip()}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    parse_logs()
