"""
Test cases for signal system and background processing
"""
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from drf_api_logger.events import EventTypes
from drf_api_logger import API_LOGGER_SIGNAL


class TestSignalSystem(TestCase):
    """Test cases for the signal system"""

    def setUp(self):
        """Set up test fixtures"""
        # Clear any existing listeners
        API_LOGGER_SIGNAL.listen = EventTypes()
        self.signal_data = []
        
    def signal_listener(self, **kwargs):
        """Test signal listener"""
        self.signal_data.append(kwargs)
        
    def test_signal_listener_registration(self):
        """Test registering a signal listener"""
        API_LOGGER_SIGNAL.listen += self.signal_listener
        
        # Check that listener is registered
        self.assertEqual(len(API_LOGGER_SIGNAL.listen._listeners), 1)
        
    def test_signal_listener_unregistration(self):
        """Test unregistering a signal listener"""
        API_LOGGER_SIGNAL.listen += self.signal_listener
        API_LOGGER_SIGNAL.listen -= self.signal_listener
        
        # Check that listener is removed
        self.assertEqual(len(API_LOGGER_SIGNAL.listen._listeners), 0)
        
    def test_multiple_signal_listeners(self):
        """Test multiple signal listeners"""
        listener2_data = []
        
        def listener2(**kwargs):
            listener2_data.append(kwargs)
            
        API_LOGGER_SIGNAL.listen += self.signal_listener
        API_LOGGER_SIGNAL.listen += listener2
        
        # Trigger signal
        test_data = {'test': 'data'}
        API_LOGGER_SIGNAL.listen(test_data)
        
        # Both listeners should receive data
        self.assertEqual(len(self.signal_data), 1)
        self.assertEqual(len(listener2_data), 1)
        self.assertEqual(self.signal_data[0], test_data)
        self.assertEqual(listener2_data[0], test_data)

    def test_signal_with_api_data(self):
        """Test signal with typical API data"""
        API_LOGGER_SIGNAL.listen += self.signal_listener
        
        api_data = {
            'api': '/api/test/',
            'method': 'GET',
            'status_code': 200,
            'headers': '{"Content-Type": "application/json"}',
            'body': '',
            'response': '{"result": "success"}',
            'client_ip_address': '127.0.0.1',
            'execution_time': 0.123,
            'added_on': timezone.now(),
            'tracing_id': 'test-trace-123'
        }
        
        API_LOGGER_SIGNAL.listen(api_data)
        
        self.assertEqual(len(self.signal_data), 1)
        received_data = self.signal_data[0]
        self.assertEqual(received_data['api'], '/api/test/')
        self.assertEqual(received_data['method'], 'GET')
        self.assertEqual(received_data['status_code'], 200)
        self.assertEqual(received_data['tracing_id'], 'test-trace-123')

    def test_signal_exception_handling(self):
        """Test that exceptions in listeners don't break the system"""
        def failing_listener(**kwargs):
            raise Exception("Listener failed")
            
        API_LOGGER_SIGNAL.listen += self.signal_listener
        API_LOGGER_SIGNAL.listen += failing_listener
        
        # This should not raise an exception
        test_data = {'test': 'data'}
        API_LOGGER_SIGNAL.listen(test_data)
        
        # Working listener should still receive data
        self.assertEqual(len(self.signal_data), 1)


@override_settings(DRF_API_LOGGER_DATABASE=True)
class TestBackgroundThread(TestCase):
    """Test cases for background thread processing"""

    def setUp(self):
        """Set up test fixtures"""
        pass

    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_insert_log_thread_creation(self, mock_model):
        """Test creating InsertLogIntoDatabase thread"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        thread = InsertLogIntoDatabase()
        self.assertIsInstance(thread, threading.Thread)
        self.assertIsNotNone(thread._queue)
        
    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_put_log_data(self, mock_model):
        """Test putting log data into queue"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        thread = InsertLogIntoDatabase()
        
        log_data = {
            'api': '/api/test/',
            'method': 'GET',
            'status_code': 200,
            'headers': '{}',
            'body': '',
            'response': '{}',
            'client_ip_address': '127.0.0.1',
            'execution_time': 0.1,
            'added_on': timezone.now()
        }
        
        # Put data in queue
        thread.put_log_data(log_data)
        
        # Check queue size
        self.assertEqual(thread._queue.qsize(), 1)

    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_bulk_insertion_trigger(self, mock_model):
        """Test that bulk insertion triggers when queue is full"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        with patch.object(InsertLogIntoDatabase, 'DRF_LOGGER_QUEUE_MAX_SIZE', 2):
            thread = InsertLogIntoDatabase()
            
            with patch.object(thread, '_start_bulk_insertion') as mock_bulk:
                log_data = {
                    'api': '/api/test/',
                    'method': 'GET',
                    'status_code': 200,
                    'headers': '{}',
                    'body': '',
                    'response': '{}',
                    'client_ip_address': '127.0.0.1',
                    'execution_time': 0.1,
                    'added_on': timezone.now()
                }
                
                # Fill queue to trigger bulk insertion
                thread.put_log_data(log_data)
                thread.put_log_data(log_data)
                
                # Bulk insertion should be called
                mock_bulk.assert_called()

    @override_settings(DRF_LOGGER_QUEUE_MAX_SIZE=10)
    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_custom_queue_size_setting(self, mock_model):
        """Test custom queue size setting"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        thread = InsertLogIntoDatabase()
        self.assertEqual(thread.DRF_LOGGER_QUEUE_MAX_SIZE, 10)

    @override_settings(DRF_LOGGER_INTERVAL=5)
    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_custom_interval_setting(self, mock_model):
        """Test custom interval setting"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        thread = InsertLogIntoDatabase()
        self.assertEqual(thread.DRF_LOGGER_INTERVAL, 5)

    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_invalid_queue_size_setting(self, mock_model):
        """Test invalid queue size setting raises exception"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        with override_settings(DRF_LOGGER_QUEUE_MAX_SIZE=0):
            with self.assertRaises(Exception) as context:
                InsertLogIntoDatabase()
            self.assertIn("DRF_LOGGER_QUEUE_MAX_SIZE must be greater than 0", str(context.exception))

    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_invalid_interval_setting(self, mock_model):
        """Test invalid interval setting raises exception"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        with override_settings(DRF_LOGGER_INTERVAL=0):
            with self.assertRaises(Exception) as context:
                InsertLogIntoDatabase()
            self.assertIn("DRF_LOGGER_INTERVAL must be greater than 0", str(context.exception))

    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_database_insertion_success(self, mock_model):
        """Test successful database insertion"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        mock_manager = Mock()
        mock_model.objects = mock_manager
        mock_manager.using.return_value.bulk_create.return_value = None
        
        thread = InsertLogIntoDatabase()
        bulk_items = [Mock(), Mock(), Mock()]
        
        # Should not raise exception
        thread._insert_into_data_base(bulk_items)
        
        # Check that bulk_create was called
        mock_manager.using.assert_called_with(thread.DRF_API_LOGGER_DEFAULT_DATABASE)
        mock_manager.using.return_value.bulk_create.assert_called_with(bulk_items)

    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_database_insertion_operational_error(self, mock_model):
        """Test database insertion with OperationalError"""
        from django.db.utils import OperationalError
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        mock_manager = Mock()
        mock_model.objects = mock_manager
        mock_manager.using.return_value.bulk_create.side_effect = OperationalError()
        
        thread = InsertLogIntoDatabase()
        bulk_items = [Mock()]
        
        with self.assertRaises(Exception) as context:
            thread._insert_into_data_base(bulk_items)
        self.assertIn("Model does not exist", str(context.exception))

    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    @patch('builtins.print')
    def test_database_insertion_generic_error(self, mock_print, mock_model):
        """Test database insertion with generic error"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        mock_manager = Mock()
        mock_model.objects = mock_manager
        mock_manager.using.return_value.bulk_create.side_effect = Exception("Generic error")
        
        thread = InsertLogIntoDatabase()
        bulk_items = [Mock()]
        
        # Should not raise, but should print error
        thread._insert_into_data_base(bulk_items)
        mock_print.assert_called_with('DRF API LOGGER EXCEPTION:', mock_manager.using.return_value.bulk_create.side_effect)

    @override_settings(DRF_API_LOGGER_DEFAULT_DATABASE='custom_db')
    @patch('drf_api_logger.insert_log_into_database.APILogsModel')
    def test_custom_database_setting(self, mock_model):
        """Test custom database setting"""
        from drf_api_logger.insert_log_into_database import InsertLogIntoDatabase
        
        thread = InsertLogIntoDatabase()
        self.assertEqual(thread.DRF_API_LOGGER_DEFAULT_DATABASE, 'custom_db')


class TestAppConfig(TestCase):
    """Test cases for Django app configuration"""

    @patch('drf_api_logger.apps.database_log_enabled')
    @patch('os.environ.get')
    def test_app_ready_with_run_main_true(self, mock_environ, mock_db_enabled):
        """Test app.ready() when RUN_MAIN is true"""
        mock_environ.return_value = 'true'
        mock_db_enabled.return_value = True
        
        from drf_api_logger.apps import LoggerConfig
        
        with patch('drf_api_logger.apps.InsertLogIntoDatabase') as mock_thread_class:
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread
            
            with patch('threading.enumerate', return_value=[]):
                config = LoggerConfig('drf_api_logger', Mock())
                config.ready()
                
                # Thread should be created and started
                mock_thread_class.assert_called_once()
                mock_thread.start.assert_called_once()

    @patch('drf_api_logger.apps.database_log_enabled')
    @patch('os.environ.get')
    def test_app_ready_with_run_main_none(self, mock_environ, mock_db_enabled):
        """Test app.ready() when RUN_MAIN is None (production)"""
        mock_environ.return_value = None
        mock_db_enabled.return_value = True
        
        from drf_api_logger.apps import LoggerConfig
        
        with patch('drf_api_logger.apps.InsertLogIntoDatabase') as mock_thread_class:
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread
            
            with patch('threading.enumerate', return_value=[]):
                config = LoggerConfig('drf_api_logger', Mock())
                config.ready()
                
                # Thread should be created and started
                mock_thread_class.assert_called_once()
                mock_thread.start.assert_called_once()

    @patch('drf_api_logger.apps.database_log_enabled')
    @patch('os.environ.get')
    def test_app_ready_with_run_main_false(self, mock_environ, mock_db_enabled):
        """Test app.ready() when RUN_MAIN is false"""
        mock_environ.return_value = 'false'
        mock_db_enabled.return_value = True
        
        from drf_api_logger.apps import LoggerConfig
        
        with patch('drf_api_logger.apps.InsertLogIntoDatabase') as mock_thread_class:
            config = LoggerConfig('drf_api_logger', Mock())
            config.ready()
            
            # Thread should not be created
            mock_thread_class.assert_not_called()

    @patch('drf_api_logger.apps.database_log_enabled')
    @patch('os.environ.get')
    def test_app_ready_thread_already_exists(self, mock_environ, mock_db_enabled):
        """Test app.ready() when thread already exists"""
        mock_environ.return_value = 'true'
        mock_db_enabled.return_value = True
        
        existing_thread = Mock()
        existing_thread.name = 'insert_log_into_database'
        
        from drf_api_logger.apps import LoggerConfig
        
        with patch('drf_api_logger.apps.InsertLogIntoDatabase') as mock_thread_class:
            with patch('threading.enumerate', return_value=[existing_thread]):
                config = LoggerConfig('drf_api_logger', Mock())
                config.ready()
                
                # New thread should not be created
                mock_thread_class.assert_not_called()