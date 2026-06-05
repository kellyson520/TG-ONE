import sys
import json
import subprocess
import os

def run_coverage():
    """Run pytest with coverage and return json report"""
    # We target filters and repositories as core logic
    cmd = [
        sys.executable, "-m", "pytest", 
        "--cov=filters", 
        "--cov=repositories", 
        "--cov=services",
        "--cov-report=json:coverage.json", 
        "tests/unit/"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if not os.path.exists("coverage.json"):
        print("Error: coverage.json not generated")
        print(result.stdout)
        print(result.stderr)
        return None
    
    with open("coverage.json", "r") as f:
        return json.load(f)

def check_gate(data, threshold=80.0):
    """Check if coverage is above threshold"""
    total_percent = data["totals"]["percent_covered"]
    print(f"Total coverage: {total_percent:.2f}%")
    
    # Check specific modules
    modules_to_check = ["filters/", "repositories/", "services/"]
    violations = []
    
    for module in modules_to_check:
        # Sum up statements and missing for files in module
        m_statements = 0
        m_missing = 0
        
        for filepath, filedata in data["files"].items():
            if filepath.replace("\\", "/").startswith(module):
                m_statements += filedata["summary"]["num_statements"]
                m_missing += filedata["summary"]["missing_lines"]
        
        if m_statements > 0:
            m_percent = 100.0 * (m_statements - m_missing) / m_statements
            print(f"Module {module}: {m_percent:.2f}%")
            if m_percent < threshold:
                violations.append((module, m_percent))
    
    if violations:
        print("\n[GATE KEEPER] COVERAGE FAILED!")
        for module, percent in violations:
            print(f"  - {module} is at {percent:.2f}%, expected > {threshold}%")
        return False
    
    print("\n[GATE KEEPER] ALL GATES PASSED!")
    return True

if __name__ == "__main__":
    coverage_data = run_coverage()
    if not coverage_data:
        sys.exit(1)
    
    success = check_gate(coverage_data)
    if not success:
        sys.exit(1)
    sys.exit(0)
