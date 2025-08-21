# Developer Testing Guide

This guide is specifically for developers contributing to the DRF-API-Logger package. It covers advanced testing scenarios, debugging techniques, and development workflows.

## Development Environment Setup

### Local Development

```bash
# Clone the repository
git clone https://github.com/vishalanandl177/DRF-API-Logger.git
cd DRF-API-Logger

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt
```

### Docker Development Environment

```bash
# Build development container
docker build -f Dockerfile.dev -t drf-logger-dev .

# Run with volume mounting for live development
docker run -it --rm \
  -v $(pwd):/app \
  -p 8000:8000 \
  drf-logger-dev bash

# Inside container
python test_runner_simple.py
python run_tests.py
```

## Test Architecture Overview

### Test Structure

```
tests/
├── __init__.py              # Test package
├── test_settings.py         # Django test configuration
├── urls.py                  # Test URL patterns
├── test_utils.py            # Utility function tests (24 tests)
├── test_middleware.py       # Middleware tests (18 tests) 
├── test_models.py           # Model and admin tests (12 tests)
├── test_signals.py          # Signal system tests (14 tests)
├── test_integration.py      # Integration tests (varies)
└── README.md               # Test documentation
```

### Test Categories

1. **Unit Tests**: Test individual functions in isolation
2. **Integration Tests**: Test component interactions
3. **System Tests**: Test complete workflows
4. **Performance Tests**: Test performance characteristics

## Running Tests

### Quick Test Commands

```bash
# Core functionality only (fastest, most reliable)
python test_runner_simple.py

# Full test suite
python run_tests.py

# Specific test module
python -m django test tests.test_utils --settings=tests.test_settings

# Single test case
python -m django test tests.test_utils.TestUtilityFunctions.test_mask_sensitive_data_dict --settings=tests.test_settings

# Verbose output
python -m django test tests.test_utils --settings=tests.test_settings -v 2

# Stop on first failure
python -m django test tests.test_utils --settings=tests.test_settings --failfast
```

### Test Coverage Analysis

```bash
# Install coverage
pip install coverage

# Run tests with coverage
coverage run --source='drf_api_logger' run_tests.py

# Generate coverage report
coverage report

# Generate HTML coverage report
coverage html
open htmlcov/index.html

# Coverage for specific module
coverage run --source='drf_api_logger.utils' -m django test tests.test_utils --settings=tests.test_settings
```

## Advanced Testing Techniques

### Testing Conditional Imports

DRF-API-Logger uses conditional imports based on settings:

```python
# Test when models are not loaded
@override_settings(DRF_API_LOGGER_DATABASE=False)
def test_without_models(self):
    """Test behavior when database logging is disabled"""
    from drf_api_logger.utils import database_log_enabled
    self.assertFalse(database_log_enabled())
    
    # Models should not be available
    with self.assertRaises(ImportError):
        from drf_api_logger.models import APILogsModel

# Test when models are loaded
@override_settings(DRF_API_LOGGER_DATABASE=True)
def test_with_models(self):
    """Test behavior when database logging is enabled"""
    from drf_api_logger.utils import database_log_enabled
    self.assertTrue(database_log_enabled())
    
    # Models should be available
    from drf_api_logger.models import APILogsModel
    self.assertIsNotNone(APILogsModel)
```

### Testing Background Threads

```python
import time
import threading
from unittest.mock import patch, Mock

class ThreadingTestCase(TestCase):
    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_background_thread_lifecycle(self, mock_model):
        """Test complete thread lifecycle"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        # Setup mocks
        mock_manager = Mock()
        mock_model.objects = mock_manager
        mock_manager.using.return_value.bulk_create.return_value = None
        
        # Create thread
        thread = InsertLogIntoDatabase()
        self.assertFalse(thread._stop_event.is_set())
        
        # Test queue operations
        log_data = {
            'api': '/test/',
            'method': 'GET',
            'status_code': 200,
            'headers': '{}',
            'body': '',
            'response': '{}',
            'client_ip_address': '127.0.0.1',
            'execution_time': 0.1,
            'added_on': timezone.now()
        }
        
        # Add data to queue
        thread.put_log_data(log_data)
        self.assertEqual(thread._queue.qsize(), 1)
        
        # Test bulk insertion
        thread._start_bulk_insertion()
        self.assertEqual(thread._queue.qsize(), 0)
        
        # Verify database call
        mock_manager.using.return_value.bulk_create.assert_called_once()

    @patch('drf_api_logger.insert_log_into_database.signal.signal')
    def test_signal_handlers(self, mock_signal):
        """Test signal handler registration"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        import signal
        
        thread = InsertLogIntoDatabase()
        
        # Verify signal handlers were registered
        expected_calls = [
            ((signal.SIGINT, thread._clean_exit),),
            ((signal.SIGTERM, thread._clean_exit),)
        ]
        
        for expected_call in expected_calls:
            self.assertIn(expected_call, mock_signal.call_args_list)
```

### Testing Signal System

```python
class SignalSystemTestCase(TestCase):
    def setUp(self):
        """Setup signal testing environment"""
        # Clear existing listeners
        API_LOGGER_SIGNAL.listen = EventTypes()
        self.signal_data = []
        self.error_count = 0
        
    def test_signal_error_isolation(self):
        """Test that errors in one listener don't affect others"""
        def working_listener(**kwargs):
            self.signal_data.append(kwargs)
        
        def failing_listener(**kwargs):
            self.error_count += 1
            raise Exception("Test error")
        
        def another_working_listener(**kwargs):
            self.signal_data.append({'secondary': True, **kwargs})
        
        # Register listeners
        API_LOGGER_SIGNAL.listen += working_listener
        API_LOGGER_SIGNAL.listen += failing_listener
        API_LOGGER_SIGNAL.listen += another_working_listener
        
        # Trigger signal
        test_data = {'test': 'data'}
        API_LOGGER_SIGNAL.listen(test_data)
        
        # Verify error isolation
        self.assertEqual(self.error_count, 1)
        self.assertEqual(len(self.signal_data), 2)  # Two working listeners
        
    def test_listener_cleanup(self):
        """Test proper listener cleanup"""
        def temp_listener(**kwargs):
            pass
        
        # Add listener
        API_LOGGER_SIGNAL.listen += temp_listener
        self.assertEqual(len(API_LOGGER_SIGNAL.listen._listeners), 1)
        
        # Remove listener
        API_LOGGER_SIGNAL.listen -= temp_listener
        self.assertEqual(len(API_LOGGER_SIGNAL.listen._listeners), 0)
```

### Testing App Configuration

```python
class AppConfigTestCase(TestCase):
    @patch('os.environ.get')
    @patch('drf_api_logger.apps.database_log_enabled')
    @patch('threading.enumerate')
    @patch('drf_api_logger.apps.InsertLogIntoDatabase')
    def test_app_ready_conditions(self, mock_thread_class, mock_enumerate, 
                                  mock_db_enabled, mock_environ):
        """Test all app.ready() conditions"""
        from drf_api_logger.apps import LoggerConfig
        
        # Test Case 1: RUN_MAIN=true, DB enabled, no existing thread
        mock_environ.return_value = 'true'
        mock_db_enabled.return_value = True
        mock_enumerate.return_value = []
        
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread
        
        config = LoggerConfig('test', Mock())
        config.ready()
        
        mock_thread_class.assert_called_once()
        mock_thread.start.assert_called_once()
        
        # Reset mocks
        mock_thread_class.reset_mock()
        mock_thread.reset_mock()
        
        # Test Case 2: RUN_MAIN=false, should not start thread
        mock_environ.return_value = 'false'
        config.ready()
        
        mock_thread_class.assert_not_called()
        
        # Test Case 3: Thread already exists
        mock_environ.return_value = 'true'
        existing_thread = Mock()
        existing_thread.name = 'insert_log_into_database'
        mock_enumerate.return_value = [existing_thread]
        
        config.ready()
        
        mock_thread_class.assert_not_called()  # Should not create new thread
```

## Debugging Failed Tests

### Common Test Failures

#### 1. Import Errors
```python
# Error: ImportError: No module named 'drf_api_logger.models'
# Debug approach:
def debug_import_issue(self):
    from drf_api_logger.utils import database_log_enabled
    print(f"Database logging enabled: {database_log_enabled()}")
    
    try:
        from drf_api_logger.models import APILogsModel
        print("Models imported successfully")
    except ImportError as e:
        print(f"Import failed: {e}")
        print("Make sure DRF_API_LOGGER_DATABASE=True in settings")
```

#### 2. Threading Issues
```python
# Debug thread state
def debug_thread_issue(self):
    from drf_api_logger.apps import LOGGER_THREAD
    print(f"Logger thread: {LOGGER_THREAD}")
    
    if LOGGER_THREAD:
        print(f"Thread alive: {LOGGER_THREAD.is_alive()}")
        print(f"Thread name: {LOGGER_THREAD.name}")
        print(f"Queue size: {LOGGER_THREAD._queue.qsize()}")
```

#### 3. Signal Issues
```python
# Debug signal registration
def debug_signal_issue(self):
    print(f"Signal listeners: {len(API_LOGGER_SIGNAL.listen._listeners)}")
    for i, listener in enumerate(API_LOGGER_SIGNAL.listen._listeners):
        print(f"Listener {i}: {listener}")
```

### Test Debugging Utilities

```python
# Add to test_utils.py or create debug_utils.py
import logging
import traceback
from django.conf import settings

class TestDebugger:
    @staticmethod
    def print_settings():
        """Print relevant DRF Logger settings"""
        setting_names = [
            'DRF_API_LOGGER_DATABASE',
            'DRF_API_LOGGER_SIGNAL', 
            'DRF_LOGGER_QUEUE_MAX_SIZE',
            'DRF_LOGGER_INTERVAL',
            'DRF_API_LOGGER_EXCLUDE_KEYS'
        ]
        
        for setting in setting_names:
            value = getattr(settings, setting, 'NOT SET')
            print(f"{setting}: {value}")
    
    @staticmethod
    def print_thread_state():
        """Print current thread state"""
        import threading
        from drf_api_logger.apps import LOGGER_THREAD
        
        print(f"Active threads: {threading.active_count()}")
        print(f"Logger thread: {LOGGER_THREAD}")
        
        if LOGGER_THREAD:
            print(f"  - Alive: {LOGGER_THREAD.is_alive()}")
            print(f"  - Daemon: {LOGGER_THREAD.daemon}")
            print(f"  - Queue size: {LOGGER_THREAD._queue.qsize()}")
    
    @staticmethod
    def enable_debug_logging():
        """Enable verbose logging for debugging"""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Enable DRF Logger specific logging
        logger = logging.getLogger('drf_api_logger')
        logger.setLevel(logging.DEBUG)

# Usage in tests
class MyTestCase(TestCase):
    def setUp(self):
        TestDebugger.enable_debug_logging()
        TestDebugger.print_settings()
    
    def test_with_debug_info(self):
        TestDebugger.print_thread_state()
        # Your test code
```

## Performance Testing

### Load Testing Framework

```python
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
from django.test import TestCase

class PerformanceTestCase(TestCase):
    def performance_test(self, test_func, iterations=100, 
                        max_time=1.0, max_memory_mb=50):
        """Generic performance test framework"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        times = []
        
        for _ in range(iterations):
            start_time = time.time()
            test_func()
            end_time = time.time()
            times.append(end_time - start_time)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_used = final_memory - initial_memory
        
        # Performance assertions
        avg_time = statistics.mean(times)
        max_single_time = max(times)
        
        self.assertLess(avg_time, max_time / iterations, 
                       f"Average time {avg_time:.4f}s exceeds limit")
        self.assertLess(memory_used, max_memory_mb,
                       f"Memory usage {memory_used:.1f}MB exceeds limit")
        
        return {
            'avg_time': avg_time,
            'max_time': max_single_time,
            'total_time': sum(times),
            'memory_used_mb': memory_used
        }

    @override_settings(DRF_API_LOGGER_SIGNAL=True)
    def test_signal_performance(self):
        """Test signal system performance"""
        def single_signal_call():
            API_LOGGER_SIGNAL.listen({
                'api': '/test/',
                'method': 'GET',
                'status_code': 200,
                'execution_time': 0.1
            })
        
        results = self.performance_test(single_signal_call, iterations=1000)
        print(f"Signal performance: {results}")

    @override_settings(DRF_API_LOGGER_DATABASE=True)
    def test_queue_performance(self):
        """Test background queue performance"""
        def single_queue_operation():
            from drf_api_logger.apps import LOGGER_THREAD
            if LOGGER_THREAD:
                LOGGER_THREAD.put_log_data({
                    'api': '/test/',
                    'method': 'GET',
                    'status_code': 200,
                    'headers': '{}',
                    'body': '',
                    'response': '{}',
                    'client_ip_address': '127.0.0.1',
                    'execution_time': 0.1,
                    'added_on': timezone.now()
                })
        
        results = self.performance_test(single_queue_operation, iterations=1000)
        print(f"Queue performance: {results}")
```

### Concurrency Testing

```python
class ConcurrencyTestCase(TestCase):
    def test_concurrent_signal_calls(self):
        """Test signal system under concurrent load"""
        import threading
        from concurrent.futures import ThreadPoolExecutor
        
        received_signals = []
        lock = threading.Lock()
        
        def signal_listener(**kwargs):
            with lock:
                received_signals.append(kwargs)
        
        API_LOGGER_SIGNAL.listen += signal_listener
        
        def make_signal_call(i):
            API_LOGGER_SIGNAL.listen({
                'id': i,
                'api': f'/test/{i}/',
                'method': 'GET',
                'status_code': 200
            })
        
        try:
            # Run 100 concurrent signal calls
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_signal_call, i) 
                          for i in range(100)]
                
                # Wait for all to complete
                for future in futures:
                    future.result(timeout=5)
            
            # Verify all signals were received
            self.assertEqual(len(received_signals), 100)
            
            # Verify no data corruption
            received_ids = {signal['id'] for signal in received_signals}
            expected_ids = set(range(100))
            self.assertEqual(received_ids, expected_ids)
            
        finally:
            API_LOGGER_SIGNAL.listen -= signal_listener
```

## Continuous Integration Setup

### GitHub Actions Workflow

```yaml
# .github/workflows/comprehensive-test.yml
name: Comprehensive Testing

on: 
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.8", "3.9", "3.10", "3.11", "3.12"]
        django-version: ["3.2", "4.0", "4.1", "4.2", "5.0"]
        drf-version: ["3.12", "3.13", "3.14"]
        exclude:
          # Django 5.0+ requires Python 3.10+
          - django-version: "5.0"
            python-version: "3.8"
          - django-version: "5.0" 
            python-version: "3.9"

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Cache pip packages
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
        restore-keys: |
          ${{ runner.os }}-pip-

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install Django==${{ matrix.django-version }}
        pip install djangorestframework==${{ matrix.drf-version }}
        pip install coverage pytest pytest-django
        pip install -e .

    - name: Run core tests
      run: |
        python test_runner_simple.py

    - name: Run full test suite with coverage
      run: |
        coverage run --source='drf_api_logger' run_tests.py
        coverage xml

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella

  quality:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"
    
    - name: Install quality tools
      run: |
        pip install flake8 black isort mypy
        pip install -e .
    
    - name: Run linting
      run: |
        flake8 drf_api_logger tests
        black --check drf_api_logger tests
        isort --check-only drf_api_logger tests
        mypy drf_api_logger

  performance:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"
    
    - name: Install dependencies
      run: |
        pip install Django djangorestframework psutil
        pip install -e .
    
    - name: Run performance tests
      run: |
        python -m pytest tests/test_performance.py -v
```

### Pre-commit Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: local
    hooks:
      - id: core-tests
        name: Run core tests
        entry: python test_runner_simple.py
        language: system
        pass_filenames: false
        always_run: true
```

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "1", "content": "Create testing documentation for package users", "status": "completed"}, {"id": "2", "content": "Create developer testing guide", "status": "completed"}, {"id": "3", "content": "Create CI/CD testing examples", "status": "in_progress"}]