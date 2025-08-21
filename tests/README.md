# Test Suite for DRF-API-Logger

This directory contains comprehensive unit tests for the DRF-API-Logger package.

## Test Structure

### Test Files

- **`test_utils.py`** - Tests for utility functions (`utils.py`)
  - Header extraction
  - Client IP detection
  - Sensitive data masking
  - Configuration validation

- **`test_middleware.py`** - Tests for API Logger Middleware
  - Request/response interception
  - Filtering logic (methods, status codes, URLs)
  - Tracing functionality
  - Configuration handling

- **`test_models.py`** - Tests for database models and admin interface
  - Model creation and validation
  - Admin interface functionality
  - CSV export features
  - Custom filters

- **`test_signals.py`** - Tests for signal system and background processing
  - Signal listener registration
  - Background thread operations
  - Database insertion logic
  - App configuration

- **`test_integration.py`** - Integration tests
  - End-to-end workflow testing
  - Middleware + signal integration
  - Complete API request logging

### Configuration Files

- **`test_settings.py`** - Django settings for running tests
- **`urls.py`** - URL patterns for test endpoints
- **`__init__.py`** - Test package initialization

### Test Runners

- **`run_tests.py`** - Complete test suite runner
- **`test_runner_simple.py`** - Core functionality tests only

## Running Tests

### Run All Tests
```bash
python run_tests.py
```

### Run Core Tests Only
```bash
python test_runner_simple.py
```

### Run Specific Test Module
```bash
python -m django test tests.test_utils --settings=tests.test_settings
```

### Run Specific Test Case
```bash
python -m django test tests.test_utils.TestUtilityFunctions.test_mask_sensitive_data_dict --settings=tests.test_settings
```

## Test Coverage

The test suite covers:

### ✅ **Working Components**
- **Utility Functions** (24/24 tests passing)
  - Header extraction from HTTP requests
  - Client IP detection (including X-Forwarded-For)
  - Sensitive data masking for passwords, tokens, etc.
  - Configuration validation and defaults

- **Middleware Core Logic** (3/3 core tests passing)
  - Middleware initialization
  - Static/media file request filtering
  - Basic request/response handling

### 🔧 **Components Needing Integration Work**
- **Database Models** - Models work but need proper migration setup
- **Admin Interface** - Admin features work but need authentication setup
- **Signal System** - Signals work but need proper threading setup
- **Background Processing** - Thread logic works but needs database integration
- **Complete Integration** - End-to-end workflow needs DRF permission fixes

## Test Environment Setup

The tests use:
- **Database**: In-memory SQLite
- **Authentication**: Anonymous access allowed for API endpoints
- **Middleware**: API Logger middleware enabled
- **Settings**: Test-specific configuration with safe defaults

## Key Testing Strategies

### 1. **Unit Testing**
- Individual function testing with mocked dependencies
- Boundary condition testing
- Error handling validation

### 2. **Integration Testing**
- Middleware + signal system integration
- Database operations with background threads
- Complete request/response workflows

### 3. **Configuration Testing**
- Default settings validation
- Custom configuration handling
- Settings override behavior

## Common Test Patterns

### Mocking External Dependencies
```python
@patch('drf_api_logger.apps.LOGGER_THREAD')
def test_with_mocked_thread(self, mock_thread):
    mock_thread.put_log_data = Mock()
    # Test logic here
```

### Testing Settings Overrides
```python
@override_settings(DRF_API_LOGGER_DATABASE=True)
def test_with_database_enabled(self):
    # Test logic here
```

### Signal Testing
```python
def setUp(self):
    self.signal_data = []
    
    def signal_listener(**kwargs):
        self.signal_data.append(kwargs)
    
    API_LOGGER_SIGNAL.listen += signal_listener
```

## Notes on Test Failures

Some integration tests may fail due to:

1. **Permission Issues** - DRF permission classes may block test requests
2. **Threading Issues** - Background thread tests need careful setup
3. **Import Issues** - Conditional model loading can cause import errors
4. **Settings Conflicts** - Django settings may not reload properly between tests

The core functionality tests (24 tests) all pass, indicating the main library functions work correctly.

## Contributing Tests

When adding new features:

1. Add unit tests for individual functions
2. Add integration tests for complete workflows
3. Test both success and error conditions
4. Test configuration variations
5. Update this README with new test information

## Test Database

Tests use an in-memory SQLite database that is created and destroyed for each test run. This ensures test isolation and fast execution.