#!/usr/bin/env python3
"""
Institutional Options Test Runner

Executes the complete test suite and generates effectiveness evidence report.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --phase 1         # Run Phase 1 only
    python run_tests.py --evidence        # Generate evidence report
    python run_tests.py --baseline        # Document baseline capabilities
"""

import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def run_pytest(test_file=None, verbose=True):
    """Run pytest on specified file or all tests"""
    cmd = ["pytest"]

    if test_file:
        cmd.append(test_file)
    else:
        cmd.append(".")

    if verbose:
        cmd.extend(["-v", "-s"])

    cmd.append("--tb=short")  # Short traceback format

    print(f"{Colors.OKBLUE}Running: {' '.join(cmd)}{Colors.ENDC}\n")

    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def generate_baseline_report():
    """Generate baseline capabilities report"""
    print_header("BASELINE CAPABILITIES REPORT")

    print(f"{Colors.OKCYAN}Documenting current state before institutional upgrade...{Colors.ENDC}\n")

    # Run the effectiveness evidence test
    result = run_pytest("test_phase1_volatility_surface.py::TestEffectivenessEvidence", verbose=True)

    print_header("BASELINE REPORT COMPLETE")


def generate_evidence_report():
    """Generate comprehensive effectiveness evidence"""
    print_header("EFFECTIVENESS EVIDENCE REPORT")

    print(f"{Colors.OKCYAN}Generating evidence of institutional upgrade effectiveness...{Colors.ENDC}\n")

    evidence = {
        "report_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test_environment": {
            "python_version": sys.version.split()[0],
            "platform": sys.platform
        },
        "phase_status": {
            "phase_1_volatility_surface": "In Development",
            "phase_2_advanced_greeks": "Planned",
            "phase_3_portfolio_risk": "Planned",
            "phase_4_advanced_strategies": "Planned"
        }
    }

    print(f"{Colors.OKGREEN}Evidence Report Generated:{Colors.ENDC}")
    print(json.dumps(evidence, indent=2))

    # Save to file
    output_file = Path(__file__).parent / "evidence_report.json"
    with open(output_file, 'w') as f:
        json.dump(evidence, f, indent=2)

    print(f"\n{Colors.OKGREEN}Report saved to: {output_file}{Colors.ENDC}")


def run_phase_tests(phase_num):
    """Run tests for a specific phase"""
    phase_files = {
        1: "test_phase1_volatility_surface.py",
        2: "test_phase2_advanced_greeks.py",
        # Add more phases as they're created
    }

    if phase_num not in phase_files:
        print(f"{Colors.FAIL}Phase {phase_num} not found{Colors.ENDC}")
        return 1

    print_header(f"PHASE {phase_num} TESTS")
    return run_pytest(phase_files[phase_num])


def main():
    """Main test runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Institutional Options Test Runner")
    parser.add_argument("--phase", type=int, help="Run specific phase (1-4)")
    parser.add_argument("--evidence", action="store_true", help="Generate evidence report")
    parser.add_argument("--baseline", action="store_true", help="Generate baseline report")
    parser.add_argument("--all", action="store_true", help="Run all tests")

    args = parser.parse_args()

    if args.baseline:
        generate_baseline_report()
    elif args.evidence:
        generate_evidence_report()
    elif args.phase:
        return run_phase_tests(args.phase)
    elif args.all or len(sys.argv) == 1:
        print_header("INSTITUTIONAL OPTIONS TEST SUITE")
        print(f"{Colors.OKCYAN}Running complete test suite...{Colors.ENDC}\n")
        return run_pytest()
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
