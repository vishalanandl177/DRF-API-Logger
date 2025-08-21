"""
Test cases for utility functions
"""
from django.test import TestCase, RequestFactory
from django.test.utils import override_settings
from unittest.mock import Mock, patch

from drf_api_logger.utils import (
    get_headers,
    get_client_ip,
    is_api_logger_enabled,
    database_log_enabled,
    mask_sensitive_data,
    SENSITIVE_KEYS
)


class TestUtilityFunctions(TestCase):
    """Test cases for utility functions"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()

    def test_get_headers_from_request(self):
        """Test extracting headers from request"""
        request = self.factory.get(
            '/api/test/',
            HTTP_AUTHORIZATION='Bearer token123',
            HTTP_CONTENT_TYPE='application/json',
            HTTP_X_CUSTOM_HEADER='custom_value'
        )
        
        headers = get_headers(request)
        
        self.assertIn('AUTHORIZATION', headers)
        self.assertEqual(headers['AUTHORIZATION'], 'Bearer token123')
        self.assertIn('CONTENT_TYPE', headers)
        self.assertEqual(headers['CONTENT_TYPE'], 'application/json')
        self.assertIn('X_CUSTOM_HEADER', headers)
        self.assertEqual(headers['X_CUSTOM_HEADER'], 'custom_value')

    def test_get_headers_empty_request(self):
        """Test get_headers with request without headers"""
        request = self.factory.get('/api/test/')
        headers = get_headers(request)
        
        # Should return dict even if no HTTP_ headers
        self.assertIsInstance(headers, dict)

    def test_get_client_ip_direct(self):
        """Test getting client IP from REMOTE_ADDR"""
        request = self.factory.get('/api/test/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '192.168.1.100')

    def test_get_client_ip_forwarded(self):
        """Test getting client IP from X-Forwarded-For header"""
        request = self.factory.get('/api/test/')
        request.META['HTTP_X_FORWARDED_FOR'] = '10.0.0.1, 192.168.1.1, 127.0.0.1'
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '10.0.0.1')  # Should return first IP

    def test_get_client_ip_no_ip(self):
        """Test get_client_ip when no IP is available"""
        request = self.factory.get('/api/test/')
        # Remove IP information
        request.META.pop('REMOTE_ADDR', None)
        
        ip = get_client_ip(request)
        self.assertIn(ip, ['', None])  # Can return either empty string or None

    def test_get_client_ip_exception(self):
        """Test get_client_ip handles exceptions gracefully"""
        request = Mock()
        request.META = Mock(side_effect=Exception("Test exception"))
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '')

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=False)
    def test_is_api_logger_enabled_false(self):
        """Test is_api_logger_enabled when both are disabled"""
        self.assertFalse(is_api_logger_enabled())

    @override_settings(DRF_API_LOGGER_DATABASE=True, DRF_API_LOGGER_SIGNAL=False)
    def test_is_api_logger_enabled_database(self):
        """Test is_api_logger_enabled when database is enabled"""
        self.assertTrue(is_api_logger_enabled())

    @override_settings(DRF_API_LOGGER_DATABASE=False, DRF_API_LOGGER_SIGNAL=True)
    def test_is_api_logger_enabled_signal(self):
        """Test is_api_logger_enabled when signal is enabled"""
        self.assertTrue(is_api_logger_enabled())

    @override_settings(DRF_API_LOGGER_DATABASE=True, DRF_API_LOGGER_SIGNAL=True)
    def test_is_api_logger_enabled_both(self):
        """Test is_api_logger_enabled when both are enabled"""
        self.assertTrue(is_api_logger_enabled())

    @override_settings(DRF_API_LOGGER_DATABASE=False)
    def test_database_log_enabled_false(self):
        """Test database_log_enabled when disabled"""
        self.assertFalse(database_log_enabled())

    @override_settings(DRF_API_LOGGER_DATABASE=True)
    def test_database_log_enabled_true(self):
        """Test database_log_enabled when enabled"""
        self.assertTrue(database_log_enabled())

    def test_mask_sensitive_data_dict(self):
        """Test masking sensitive data in dictionary"""
        data = {
            'username': 'john',
            'password': 'secret123',
            'token': 'abc123',
            'access': 'access_token',
            'refresh': 'refresh_token',
            'email': 'john@example.com'
        }
        
        masked = mask_sensitive_data(data)
        
        self.assertEqual(masked['username'], 'john')
        self.assertEqual(masked['email'], 'john@example.com')
        self.assertEqual(masked['password'], '***FILTERED***')
        self.assertEqual(masked['token'], '***FILTERED***')
        self.assertEqual(masked['access'], '***FILTERED***')
        self.assertEqual(masked['refresh'], '***FILTERED***')

    def test_mask_sensitive_data_nested_dict(self):
        """Test masking sensitive data in nested dictionary"""
        data = {
            'user': {
                'name': 'john',
                'password': 'secret',
                'profile': {
                    'token': 'nested_token'
                }
            }
        }
        
        masked = mask_sensitive_data(data)
        
        self.assertEqual(masked['user']['name'], 'john')
        self.assertEqual(masked['user']['password'], '***FILTERED***')
        self.assertEqual(masked['user']['profile']['token'], '***FILTERED***')

    def test_mask_sensitive_data_list(self):
        """Test masking sensitive data in list"""
        data = [
            {'password': 'pass1'},
            {'password': 'pass2'},
            {'username': 'user1'}
        ]
        
        masked = mask_sensitive_data(data)
        
        self.assertEqual(masked[0]['password'], '***FILTERED***')
        self.assertEqual(masked[1]['password'], '***FILTERED***')
        self.assertEqual(masked[2]['username'], 'user1')

    def test_mask_sensitive_data_mixed(self):
        """Test masking sensitive data in mixed structure"""
        data = {
            'users': [
                {'username': 'user1', 'password': 'pass1'},
                {'username': 'user2', 'token': 'token2'}
            ],
            'safe_key': 'safe_value'  # Use a key that's definitely not sensitive
        }
        
        masked = mask_sensitive_data(data)
        
        self.assertEqual(masked['users'][0]['username'], 'user1')
        self.assertEqual(masked['users'][0]['password'], '***FILTERED***')
        self.assertEqual(masked['users'][1]['token'], '***FILTERED***')
        # 'safe_key' is not in SENSITIVE_KEYS
        self.assertEqual(masked['safe_key'], 'safe_value')

    def test_mask_sensitive_data_string_url(self):
        """Test masking sensitive data in URL string"""
        url = 'https://api.example.com/auth?token=abc123&user=john&password=secret'
        
        masked = mask_sensitive_data(url, mask_api_parameters=True)
        
        self.assertIn('token=***FILTERED***', masked)
        self.assertIn('password=***FILTERED***', masked)
        self.assertIn('user=john', masked)

    def test_mask_sensitive_data_string_multiple_params(self):
        """Test masking multiple sensitive parameters in URL"""
        url = 'https://api.example.com?token=abc&access=def&refresh=ghi&data=xyz'
        
        masked = mask_sensitive_data(url, mask_api_parameters=True)
        
        self.assertIn('token=***FILTERED***', masked)
        self.assertIn('access=***FILTERED***', masked)
        self.assertIn('refresh=***FILTERED***', masked)
        self.assertIn('data=xyz', masked)

    def test_mask_sensitive_data_non_dict(self):
        """Test mask_sensitive_data with non-dict input"""
        # String without mask_api_parameters
        result = mask_sensitive_data("plain string")
        self.assertEqual(result, "plain string")
        
        # Number
        result = mask_sensitive_data(123)
        self.assertEqual(result, 123)
        
        # None
        result = mask_sensitive_data(None)
        self.assertIsNone(result)

    @override_settings(DRF_API_LOGGER_EXCLUDE_KEYS=['custom_secret', 'api_key'])
    def test_custom_sensitive_keys(self):
        """Test custom sensitive keys from settings"""
        # Re-import to get updated SENSITIVE_KEYS
        from importlib import reload
        import drf_api_logger.utils as utils_module
        reload(utils_module)
        
        data = {
            'custom_secret': 'should_be_masked',
            'api_key': 'should_be_masked',
            'password': 'should_be_masked',
            'normal_field': 'not_masked'
        }
        
        masked = utils_module.mask_sensitive_data(data)
        
        self.assertEqual(masked['custom_secret'], '***FILTERED***')
        self.assertEqual(masked['api_key'], '***FILTERED***')
        self.assertEqual(masked['password'], '***FILTERED***')
        self.assertEqual(masked['normal_field'], 'not_masked')

    def test_sensitive_keys_default(self):
        """Test default sensitive keys"""
        expected_keys = ['password', 'token', 'access', 'refresh']
        for key in expected_keys:
            self.assertIn(key, SENSITIVE_KEYS)