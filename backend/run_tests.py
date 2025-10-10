#!/usr/bin/env python3
"""
Comprehensive test runner for the manuscript processor backend.

This script runs all test suites with proper configuration,
generates coverage reports, and provides detailed test results.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

def setup_test_environment():
    """Setup test environment variables and configuration."""
    test_env = {
        "TESTING": "true",
        "DATABASE_URL": "mongodb://localhost:27017",
        "DATABASE_NAME": "manuscript_processor_test",
        "JWT_SECRET_KEY": "test-secret-key-for-testing-only",
        "S3_BUCKET_NAME": "test-manuscript-bucket",
        "AWS_REGION": "us-east-1",
        "DEBUG": "true",
        "LOG_LEVEL": "INFO"
    }
    
    for key, value in test_env.items():
        os.environ[key] = value

def run_command(command, description=""):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(command)}")
    print()
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        print(f"\nExit code: {result.returncode}")
        
        return result.returncode == 0, result
    
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return False, None

def run_unit_tests():
    """Run unit tests."""
    command = [
        "python", "-m", "pytest",
        "tests/test_api_auth.py",
        "tests/test_api_manuscripts.py",
        "tests/test_scheduler_service.py",
        "-v",
        "--tb=short",
        "-m", "not integration and not s3",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov/unit",
        "--cov-report=xml:coverage-unit.xml"
    ]
    
    return run_command(command, "Running Unit Tests")

def run_integration_tests():
    """Run integration tests."""
    command = [
        "python", "-m", "pytest",
        "tests/test_database_integration.py",
        "-v",
        "--tb=short",
        "-m", "integration",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov/integration",
        "--cov-report=xml:coverage-integration.xml"
    ]
    
    return run_command(command, "Running Integration Tests")

def run_s3_tests():
    """Run S3 integration tests."""
    command = [
        "python", "-m", "pytest",
        "tests/test_s3_integration.py",
        "-v",
        "--tb=short",
        "-m", "s3",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov/s3",
        "--cov-report=xml:coverage-s3.xml"
    ]
    
    return run_command(command, "Running S3 Integration Tests")

def run_all_tests():
    """Run all tests with combined coverage."""
    command = [
        "python", "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov/all",
        "--cov-report=xml:coverage-all.xml",
        "--cov-fail-under=70"
    ]
    
    return run_command(command, "Running All Tests")

def run_specific_test_file(test_file):
    """Run a specific test file."""
    command = [
        "python", "-m", "pytest",
        f"tests/{test_file}",
        "-v",
        "--tb=long",
        "--cov=app",
        "--cov-report=term-missing"
    ]
    
    return run_command(command, f"Running Specific Test File: {test_file}")

def run_test_by_marker(marker):
    """Run tests by marker."""
    command = [
        "python", "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-m", marker,
        "--cov=app",
        "--cov-report=term-missing"
    ]
    
    return run_command(command, f"Running Tests with Marker: {marker}")

def check_test_dependencies():
    """Check if test dependencies are installed."""
    required_packages = [
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "pytest-mock",
        "httpx",
        "faker"
    ]
    
    print("🔍 Checking Test Dependencies")
    print("=" * 40)
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + " ".join(missing_packages))
        return False
    
    print("\n✅ All test dependencies are installed")
    return True

def generate_test_report(results):
    """Generate a comprehensive test report."""
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""
# Test Report - {report_time}

## Test Results Summary

"""
    
    total_tests = len(results)
    passed_tests = sum(1 for success, _ in results if success)
    failed_tests = total_tests - passed_tests
    
    report += f"- **Total Test Suites**: {total_tests}\n"
    report += f"- **Passed**: {passed_tests}\n"
    report += f"- **Failed**: {failed_tests}\n"
    report += f"- **Success Rate**: {(passed_tests/total_tests*100):.1f}%\n\n"
    
    report += "## Detailed Results\n\n"
    
    test_names = [
        "Unit Tests",
        "Integration Tests", 
        "S3 Integration Tests",
        "All Tests Combined"
    ]
    
    for i, (test_name, (success, result)) in enumerate(zip(test_names, results)):
        status = "✅ PASSED" if success else "❌ FAILED"
        report += f"### {test_name}\n"
        report += f"**Status**: {status}\n"
        
        if result:
            report += f"**Exit Code**: {result.returncode}\n"
            if result.stdout:
                lines = result.stdout.split('\n')
                # Extract key information
                for line in lines:
                    if "passed" in line and "failed" in line:
                        report += f"**Result**: {line.strip()}\n"
                        break
        
        report += "\n"
    
    report += "## Coverage Information\n\n"
    report += "Coverage reports are generated in the following locations:\n"
    report += "- HTML Reports: `htmlcov/` directory\n"
    report += "- XML Reports: `coverage-*.xml` files\n\n"
    
    report += "## Test Files\n\n"
    report += "The following test files were executed:\n"
    report += "- `test_api_auth.py` - Authentication API tests\n"
    report += "- `test_api_manuscripts.py` - Manuscript API tests\n"
    report += "- `test_database_integration.py` - Database integration tests\n"
    report += "- `test_s3_integration.py` - S3 service tests\n"
    report += "- `test_scheduler_service.py` - Scheduler monitoring tests\n\n"
    
    # Write report to file
    report_file = Path("test_report.md")
    report_file.write_text(report)
    
    print(f"\n📊 Test report generated: {report_file}")
    
    return report

def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run manuscript processor backend tests")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "s3", "all", "file", "marker"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--file",
        help="Specific test file to run (when type=file)"
    )
    parser.add_argument(
        "--marker",
        help="Test marker to run (when type=marker)"
    )
    parser.add_argument(
        "--no-deps-check",
        action="store_true",
        help="Skip dependency check"
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip generating test report"
    )
    
    args = parser.parse_args()
    
    print("🚀 Manuscript Processor Backend Test Runner")
    print("=" * 60)
    
    # Setup test environment
    setup_test_environment()
    print("✅ Test environment configured")
    
    # Check dependencies
    if not args.no_deps_check:
        if not check_test_dependencies():
            sys.exit(1)
    
    # Change to backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    print(f"📁 Working directory: {backend_dir}")
    
    # Run tests based on type
    results = []
    
    if args.type == "unit":
        success, result = run_unit_tests()
        results.append((success, result))
    
    elif args.type == "integration":
        success, result = run_integration_tests()
        results.append((success, result))
    
    elif args.type == "s3":
        success, result = run_s3_tests()
        results.append((success, result))
    
    elif args.type == "file":
        if not args.file:
            print("❌ --file argument required when type=file")
            sys.exit(1)
        success, result = run_specific_test_file(args.file)
        results.append((success, result))
    
    elif args.type == "marker":
        if not args.marker:
            print("❌ --marker argument required when type=marker")
            sys.exit(1)
        success, result = run_test_by_marker(args.marker)
        results.append((success, result))
    
    elif args.type == "all":
        # Run all test suites
        unit_success, unit_result = run_unit_tests()
        results.append((unit_success, unit_result))
        
        integration_success, integration_result = run_integration_tests()
        results.append((integration_success, integration_result))
        
        s3_success, s3_result = run_s3_tests()
        results.append((s3_success, s3_result))
        
        # Run combined test for overall coverage
        all_success, all_result = run_all_tests()
        results.append((all_success, all_result))
    
    # Generate report
    if not args.no_report and results:
        generate_test_report(results)
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST EXECUTION SUMMARY")
    print("=" * 60)
    
    total_success = all(success for success, _ in results)
    
    if total_success:
        print("🎉 All tests completed successfully!")
        exit_code = 0
    else:
        print("❌ Some tests failed. Check the output above for details.")
        exit_code = 1
    
    print(f"\nTotal test suites run: {len(results)}")
    print(f"Successful: {sum(1 for success, _ in results if success)}")
    print(f"Failed: {sum(1 for success, _ in results if not success)}")
    
    if Path("htmlcov").exists():
        print(f"\n📊 Coverage reports available in: htmlcov/")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
