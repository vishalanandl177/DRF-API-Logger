import unittest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.conf import settings


class TestMediaURLIssue(TestCase):
    
    def setUp(self):
        from drf_api_logger.middleware.api_logger_middleware import APILoggerMiddleware
        self.get_response = Mock(return_value=Mock(status_code=200))
        self.middleware = APILoggerMiddleware(self.get_response)
    
    def test_media_url_not_set_should_not_skip_all_requests(self):
        """Test that when MEDIA_URL is not set, it shouldn't skip all requests"""
        
        # Test with MEDIA_URL not set (None)
        with patch.object(settings, 'MEDIA_URL', None, create=True):
            # This should NOT be treated as a media request
            self.assertFalse(self.middleware.is_static_or_media_request('/api/users/'))
            self.assertFalse(self.middleware.is_static_or_media_request('/admin/'))
            self.assertFalse(self.middleware.is_static_or_media_request('/'))
        
        # Test with MEDIA_URL set to '/' (should also not skip all)
        with patch.object(settings, 'MEDIA_URL', '/', create=True):
            # This should NOT be treated as a media request
            self.assertFalse(self.middleware.is_static_or_media_request('/api/users/'))
            self.assertFalse(self.middleware.is_static_or_media_request('/admin/'))
            self.assertFalse(self.middleware.is_static_or_media_request('/'))
    
    def test_media_url_set_properly(self):
        """Test that when MEDIA_URL is set, it works as expected"""
        
        with patch.object(settings, 'MEDIA_URL', '/media/', create=True):
            # These should be treated as media requests
            self.assertTrue(self.middleware.is_static_or_media_request('/media/image.jpg'))
            self.assertTrue(self.middleware.is_static_or_media_request('/media/files/doc.pdf'))
            
            # These should NOT be treated as media requests
            self.assertFalse(self.middleware.is_static_or_media_request('/api/users/'))
            self.assertFalse(self.middleware.is_static_or_media_request('/admin/'))
    
    def test_static_url_not_set_should_not_skip_all_requests(self):
        """Test that when STATIC_URL is not set, it shouldn't skip all requests"""
        
        # Test with STATIC_URL not set (None)
        with patch.object(settings, 'STATIC_URL', None, create=True):
            # This should NOT be treated as a static request
            self.assertFalse(self.middleware.is_static_or_media_request('/api/users/'))
            self.assertFalse(self.middleware.is_static_or_media_request('/admin/'))
            self.assertFalse(self.middleware.is_static_or_media_request('/'))
        
        # Test with STATIC_URL set to '/'
        with patch.object(settings, 'STATIC_URL', '/', create=True):
            # This should NOT be treated as a static request
            self.assertFalse(self.middleware.is_static_or_media_request('/api/users/'))
            self.assertFalse(self.middleware.is_static_or_media_request('/admin/'))
            self.assertFalse(self.middleware.is_static_or_media_request('/'))
    
    def test_static_url_set_properly(self):
        """Test that when STATIC_URL is set, it works as expected"""
        
        with patch.object(settings, 'STATIC_URL', '/static/', create=True):
            # These should be treated as static requests
            self.assertTrue(self.middleware.is_static_or_media_request('/static/css/style.css'))
            self.assertTrue(self.middleware.is_static_or_media_request('/static/js/app.js'))
            
            # These should NOT be treated as static requests
            self.assertFalse(self.middleware.is_static_or_media_request('/api/users/'))
            self.assertFalse(self.middleware.is_static_or_media_request('/admin/'))
    
    def test_both_urls_not_set(self):
        """Test when both STATIC_URL and MEDIA_URL are not set"""
        
        # Test with both URLs not set using patch
        with patch.object(settings, 'STATIC_URL', None, create=True):
            with patch.object(settings, 'MEDIA_URL', None, create=True):
                # No requests should be treated as static/media
                self.assertFalse(self.middleware.is_static_or_media_request('/'))
                self.assertFalse(self.middleware.is_static_or_media_request('/api/users/'))
                self.assertFalse(self.middleware.is_static_or_media_request('/admin/'))
                self.assertFalse(self.middleware.is_static_or_media_request('/static/test.css'))
                self.assertFalse(self.middleware.is_static_or_media_request('/media/test.jpg'))