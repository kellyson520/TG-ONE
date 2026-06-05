
import re
import sys
from collections import defaultdict

# Set stdout to utf-8
sys.stdout.reconfigure(encoding='utf-8')

LOG_FILE = r"e:\重构\TG ONE\telegram-forwarder-opt-20260208094719.log"

def analyze_density():
    print(f"Analyzing log density for {LOG_FILE}...")
    
    # regex for timestamp
    time_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2})")
    
    minute_counts = defaultdict(int)
    first_lines = {}
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                match = time_pattern.match(line.strip()) # Handle leading BOM/garbage by using search or strip?
                # Actually earlier regex worked with match on line, but let's be safe.
                # The log lines start with date.
                
                if match:
                    minute_str = match.group(1)
                    minute_counts[minute_str] += 1
                    if minute_str not in first_lines:
                        first_lines[minute_str] = line.strip()
                else:
                    # Try searching inside line if prefix is garbage
                    match_search = re.search(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2})", line)
                    if match_search:
                         minute_str = match_search.group(1)
                         minute_counts[minute_str] += 1
                         if minute_str not in first_lines:
                            first_lines[minute_str] = line.strip()

    except Exception as e:
        print(f"Error: {e}")
        return

    # Print results sorted by time
    sorted_minutes = sorted(minute_counts.keys())
    print("\nLog Activity per Minute:")
    for minute in sorted_minutes:
        print(f"{minute}: {minute_counts[minute]} lines")
        print(f"  First log: {first_lines[minute][:100]}...") # Truncate for display

if __name__ == "__main__":
    analyze_density()
