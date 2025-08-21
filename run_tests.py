#!/usr/bin/env python
"""
Test runner for DRF-API-Logger
"""
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner


def run_tests():
    """Run the test suite"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.test_settings')
    
    # Configure Django
    django.setup()
    
    # Get test runner
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, keepdb=False)
    
    # Discover and run tests
    failures = test_runner.run_tests(['tests'])
    
    if failures:
        print(f"\n❌ {failures} test(s) failed!")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == '__main__':
    run_tests()