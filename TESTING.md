# Testing Guide for DRF-API-Logger

This document provides comprehensive guidance on testing the DRF-API-Logger package, whether you're a user integrating it into your project or a developer contributing to the package.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Testing Your Integration](#testing-your-integration)
3. [Package Development Testing](#package-development-testing)
4. [Testing Different Configurations](#testing-different-configurations)
5. [Performance Testing](#performance-testing)
6. [CI/CD Integration](#cicd-integration)
7. [Troubleshooting](#troubleshooting)

## Quick Start

### For Users: Testing Your Integration

If you've added DRF-API-Logger to your Django project, here's how to verify it's working:

```python
# test_drf_logger_integration.py
import json
from django.test import TestCase, Client
from django.test.utils import override_settings
from drf_api_logger import API_LOGGER_SIGNAL

class TestDRFLoggerIntegration(TestCase):
    def setUp(self):
        self.client = Client()
        self.logged_data = []
        
        def capture_logs(**kwargs):
            self.logged_data.append(kwargs)
        
        self.log_capture = capture_logs

    @override_settings(DRF_API_LOGGER_SIGNAL=True)
    def test_api_logging_works(self):
        """Test that API calls are being logged"""
        API_LOGGER_SIGNAL.listen += self.log_capture
        
        try:
            # Make an API call to your endpoint
            response = self.client.get('/api/your-endpoint/')
            
            # Check that logging captured the request
            self.assertEqual(len(self.logged_data), 1)
            log_entry = self.logged_data[0]
            
            # Verify log data
            self.assertIn('api', log_entry)
            self.assertEqual(log_entry['method'], 'GET')
            self.assertEqual(log_entry['status_code'], response.status_code)
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.log_capture
```

### For Developers: Running Package Tests

```bash
# Clone and setup
git clone https://github.com/vishalanandl177/DRF-API-Logger.git
cd DRF-API-Logger
pip install -e .

# Install test dependencies
pip install django djangorestframework

# Run core tests (recommended first)
python test_runner_simple.py

# Run full test suite
python run_tests.py
```

## Testing Your Integration

### 1. Basic Functionality Test

Create a simple test to verify the logger is capturing your API calls:

```python
# tests/test_api_logging.py
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient
from drf_api_logger import API_LOGGER_SIGNAL

class APILoggingTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_logs = []
        
        def log_listener(**kwargs):
            self.api_logs.append(kwargs)
        
        self.listener = log_listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_DATABASE=False  # Use signals for testing
    )
    def test_get_request_logged(self):
        API_LOGGER_SIGNAL.listen += self.listener
        
        try:
            response = self.client.get('/api/users/')
            
            # Verify logging
            self.assertEqual(len(self.api_logs), 1)
            log = self.api_logs[0]
            
            self.assertEqual(log['method'], 'GET')
            self.assertIn('/api/users/', log['api'])
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_EXCLUDE_KEYS=['secret_key']
    )
    def test_sensitive_data_masking(self):
        API_LOGGER_SIGNAL.listen += self.listener
        
        try:
            data = {
                'username': 'testuser',
                'password': 'secret123',
                'secret_key': 'top-secret'
            }
            
            response = self.client.post('/api/login/', 
                                      data=data, 
                                      format='json')
            
            # Check sensitive data was masked
            log = self.api_logs[0]
            body = json.loads(log['body'])
            
            self.assertEqual(body['password'], '***FILTERED***')
            self.assertEqual(body['secret_key'], '***FILTERED***')
            self.assertEqual(body['username'], 'testuser')
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.listener
```

### 2. Database Logging Test

Test database logging functionality:

```python
@override_settings(
    DRF_API_LOGGER_DATABASE=True,
    DRF_API_LOGGER_SIGNAL=False
)
def test_database_logging(self):
    from drf_api_logger.models import APILogsModel
    
    # Clear existing logs
    APILogsModel.objects.all().delete()
    
    # Make API call
    response = self.client.post('/api/users/', {
        'name': 'Test User',
        'email': 'test@example.com'
    }, format='json')
    
    # Give time for background thread to process
    import time
    time.sleep(1)
    
    # Check database
    logs = APILogsModel.objects.filter(method='POST')
    self.assertGreater(logs.count(), 0)
    
    log = logs.first()
    self.assertIn('/api/users/', log.api)
    self.assertEqual(log.status_code, response.status_code)
```

### 3. Configuration Testing

Test different configurations:

```python
class ConfigurationTestCase(TestCase):
    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_METHODS=['POST', 'PUT']
    )
    def test_method_filtering(self):
        """Test that only specified methods are logged"""
        API_LOGGER_SIGNAL.listen += self.listener
        
        try:
            # GET should not be logged
            self.client.get('/api/users/')
            self.assertEqual(len(self.api_logs), 0)
            
            # POST should be logged
            self.client.post('/api/users/', {}, format='json')
            self.assertEqual(len(self.api_logs), 1)
            
        finally:
            API_LOGGER_SIGNAL.listen -= self.listener

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_STATUS_CODES=[200, 201]
    )
    def test_status_code_filtering(self):
        """Test filtering by status codes"""
        # Implementation depends on your API endpoints
        pass

    @override_settings(
        DRF_API_LOGGER_SIGNAL=True,
        DRF_API_LOGGER_SKIP_URL_NAME=['health-check']
    )
    def test_url_skipping(self):
        """Test skipping specific URLs"""
        # Test that health check endpoints are not logged
        pass
```

## Package Development Testing

### Running the Test Suite

The package includes a comprehensive test suite with 66+ tests:

```bash
# Install development dependencies
pip install -e .
pip install django djangorestframework

# Run all tests
python run_tests.py

# Run only core functionality tests
python test_runner_simple.py

# Run specific test modules
python -m django test tests.test_utils --settings=tests.test_settings
python -m django test tests.test_middleware --settings=tests.test_settings

# Run with coverage
pip install coverage
coverage run run_tests.py
coverage report
coverage html
```

### Test Categories

1. **Unit Tests** (`tests/test_*.py`)
   - `test_utils.py` - Utility function tests
   - `test_middleware.py` - Middleware functionality
   - `test_models.py` - Database models and admin
   - `test_signals.py` - Signal system and threading

2. **Integration Tests** (`tests/test_integration.py`)
   - End-to-end workflow testing
   - Middleware + signal integration
   - Complete API logging scenarios

### Adding New Tests

When contributing new features:

```python
# tests/test_new_feature.py
from django.test import TestCase
from django.test.utils import override_settings
from unittest.mock import Mock, patch

class TestNewFeature(TestCase):
    def test_new_functionality(self):
        """Test description"""
        # Setup
        # Execute
        # Assert
        pass

    @override_settings(SETTING_NAME=True)
    def test_with_setting_enabled(self):
        """Test with specific setting"""
        pass

    @patch('drf_api_logger.module.function')
    def test_with_mocked_dependency(self, mock_func):
        """Test with mocked external dependency"""
        pass
```

## Testing Different Configurations

### Configuration Test Matrix

Test your application with different DRF-API-Logger configurations:

```python
# conftest.py or test settings
LOGGER_TEST_CONFIGURATIONS = [
    {
        'DRF_API_LOGGER_DATABASE': True,
        'DRF_API_LOGGER_SIGNAL': False,
    },
    {
        'DRF_API_LOGGER_DATABASE': False,
        'DRF_API_LOGGER_SIGNAL': True,
    },
    {
        'DRF_API_LOGGER_DATABASE': True,
        'DRF_API_LOGGER_SIGNAL': True,
    },
    # Add more configurations as needed
]

# Use with parameterized tests
import pytest

@pytest.mark.parametrize("config", LOGGER_TEST_CONFIGURATIONS)
def test_with_different_configs(config):
    with override_settings(**config):
        # Your test logic here
        pass
```

### Environment-Specific Testing

```python
# Test production-like settings
PRODUCTION_TEST_SETTINGS = {
    'DEBUG': False,
    'DRF_API_LOGGER_DATABASE': True,
    'DRF_API_LOGGER_SIGNAL': False,
    'DRF_LOGGER_QUEUE_MAX_SIZE': 100,
    'DRF_LOGGER_INTERVAL': 5,
    'DRF_API_LOGGER_EXCLUDE_KEYS': [
        'password', 'token', 'access', 'refresh',
        'api_key', 'secret', 'private_key'
    ]
}

@override_settings(**PRODUCTION_TEST_SETTINGS)
class ProductionConfigTestCase(TestCase):
    def test_production_configuration(self):
        """Test with production-like settings"""
        pass
```

## Performance Testing

### Load Testing

```python
import time
import threading
from django.test import TestCase

class PerformanceTestCase(TestCase):
    @override_settings(DRF_API_LOGGER_SIGNAL=True)
    def test_logging_performance_impact(self):
        """Test performance impact of logging"""
        
        # Measure without logging
        start_time = time.time()
        for _ in range(100):
            self.client.get('/api/fast-endpoint/')
        without_logging = time.time() - start_time
        
        # Enable logging and measure
        API_LOGGER_SIGNAL.listen += lambda **kwargs: None
        
        start_time = time.time()
        for _ in range(100):
            self.client.get('/api/fast-endpoint/')
        with_logging = time.time() - start_time
        
        # Assert performance impact is minimal
        impact = (with_logging - without_logging) / without_logging
        self.assertLess(impact, 0.1)  # Less than 10% impact

    def test_concurrent_requests(self):
        """Test logging with concurrent requests"""
        def make_requests():
            for _ in range(10):
                self.client.get('/api/test-endpoint/')
        
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_requests)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        # Check logs were captured correctly
```

### Memory Usage Testing

```python
import psutil
import os

def test_memory_usage():
    """Test memory usage doesn't grow excessively"""
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Make many requests
    for _ in range(1000):
        client.get('/api/endpoint/')
    
    final_memory = process.memory_info().rss
    memory_growth = final_memory - initial_memory
    
    # Assert memory growth is reasonable (adjust threshold as needed)
    assert memory_growth < 50 * 1024 * 1024  # Less than 50MB growth
```

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, "3.10", "3.11"]
        django-version: [3.2, 4.0, 4.1, 4.2]

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install django==${{ matrix.django-version }}
        pip install djangorestframework
        pip install -e .
    
    - name: Run core tests
      run: python test_runner_simple.py
    
    - name: Run full test suite
      run: python run_tests.py
      continue-on-error: true  # Some integration tests may fail
    
    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
```

### Docker Testing

```dockerfile
# Dockerfile.test
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -e .
RUN pip install django djangorestframework coverage

# Run tests
CMD ["python", "run_tests.py"]
```

```bash
# Build and run tests in Docker
docker build -f Dockerfile.test -t drf-logger-tests .
docker run drf-logger-tests
```

### pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: run-tests
        name: Run DRF Logger Tests
        entry: python test_runner_simple.py
        language: system
        pass_filenames: false
        always_run: true
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Import Errors

```python
# Error: No module named 'drf_api_logger.models'
# Solution: Make sure DRF_API_LOGGER_DATABASE=True in settings

@override_settings(DRF_API_LOGGER_DATABASE=True)
def test_with_models(self):
    from drf_api_logger.models import APILogsModel
    # Your test code
```

#### 2. Threading Issues

```python
# Error: Background thread not processing
# Solution: Give time for processing or mock the thread

import time
from unittest.mock import patch

@patch('drf_api_logger.apps.LOGGER_THREAD')
def test_with_mocked_thread(self, mock_thread):
    mock_thread.put_log_data = Mock()
    # Your test code
    mock_thread.put_log_data.assert_called()
```

#### 3. Signal Not Firing

```python
# Error: Signal listener not called
# Solution: Ensure signal is enabled and properly registered

@override_settings(DRF_API_LOGGER_SIGNAL=True)
def test_signal_listener(self):
    received_data = []
    
    def listener(**kwargs):
        received_data.append(kwargs)
    
    API_LOGGER_SIGNAL.listen += listener
    
    try:
        # Your API call
        response = self.client.get('/api/test/')
        # Assertions
        self.assertEqual(len(received_data), 1)
    finally:
        API_LOGGER_SIGNAL.listen -= listener
```

#### 4. Database Connection Issues

```python
# Error: Database table doesn't exist
# Solution: Run migrations or use in-memory DB

# In test settings
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Or in test
@override_settings(DRF_API_LOGGER_DATABASE=True)
class DatabaseTestCase(TransactionTestCase):
    def setUp(self):
        from django.core.management import call_command
        call_command('migrate', verbosity=0, interactive=False)
```

### Debug Mode Testing

Enable verbose logging during tests:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('drf_api_logger')

@override_settings(
    DRF_API_LOGGER_SIGNAL=True,
    LOGGING={
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
            },
        },
        'loggers': {
            'drf_api_logger': {
                'handlers': ['console'],
                'level': 'DEBUG',
            },
        },
    }
)
def test_with_debug_logging(self):
    # Your test code with detailed logging
    pass
```

## Best Practices

1. **Isolate Tests**: Use `setUp()` and `tearDown()` to ensure test isolation
2. **Mock External Dependencies**: Use `@patch` for external services
3. **Test Edge Cases**: Test with empty data, large payloads, malformed requests
4. **Use Transactions**: Use `TransactionTestCase` for database tests
5. **Clean Up**: Always remove signal listeners in `finally` blocks
6. **Performance Aware**: Monitor test execution time and memory usage
7. **Document Test Requirements**: Clearly document what each test validates

This comprehensive testing guide should help you effectively test DRF-API-Logger in your projects and contribute to its development.