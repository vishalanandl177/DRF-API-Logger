import sys
from unittest import TestSuite

from boot_django import boot_django

# call the django setup routine
boot_django()

default_labels = ("drf_api_logger.tests",)


def get_suite(labels=default_labels):
    from django.test.runner import DiscoverRunner
    runner = DiscoverRunner(verbosity=1)
    failures = runner.run_tests(labels)
    if failures:
        sys.exit(failures)

    # in case this is called from setup tools, return a test suite
    return TestSuite()


if __name__ == "__main__":
    labels = default_labels
    if len(sys.argv[1:]) > 0:
        labels = sys.argv[1:]

    get_suite(labels)
