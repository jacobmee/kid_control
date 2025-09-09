import os
import json
from datetime import datetime
import logging
import logging.handlers

def setup_logger(name):
    """Configure and return a logger with syslog handler."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Remove any existing handlers
    logger.handlers = []

    # Create syslog handler
    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    syslog_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter('%(name)s: %(levelname)s - %(message)s')
    syslog_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(syslog_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger

# Get logger
logger = setup_logger('TIME.CONTROL')

class Config:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config = {
            'openwrt_ip': '192.168.0.1',
            'openwrt_user': 'root',
            'username': 'jacob',
            'password': 'Jac0bm!@#G',
            'rule_name': 'max',
            'network_check_ip': '192.168.0.10'
        }
        
        # File paths
        self.data_file = os.path.join(self.base_dir, 'data.json')
        
        # Initialize files if they don't exist
        self._initialize_files()
    
    def _initialize_files(self):
        """Initialize configuration files if they don't exist."""
        if not os.path.exists(self.data_file):
            initial_data = {
                'time_records': {},
                'network_status': '',
                'devices': [],
                'current_day': datetime.now().strftime('%Y-%m-%d'),
                'task_status': {},
                'settings': {
                    'period': 75,
                    'restime': 80,
                    'starting': '8:00',
                    'ending': '22:30',
                    'mon': 30,
                    'tue': 30,
                    'wed': 30,
                    'thu': 30,
                    'fri': 60,
                    'sat': 60,
                    'sun': 60,
                    'current': 0
                }
            }
            with open(self.data_file, 'w') as f:
                json.dump(initial_data, f, indent=4)
    
    def _load_data(self):
        """Load data from JSON file."""
        try:
            with open(self.data_file, 'r') as f:
                self.data = json.load(f)
                # Migrate old status to network_status if needed
                if 'status' in self.data:
                    self.data['network_status'] = self.data.pop('status')
                    self._save_data()
                # Migrate from old config file if needed
                if 'settings' not in self.data:
                    self.data['settings'] = {}
                    old_config_file = os.path.join(self.base_dir, 'kidcontrol.config')
                    if os.path.exists(old_config_file):
                        with open(old_config_file, 'r') as f:
                            for line in f:
                                if '=' in line:
                                    key, value = line.strip().split('=')
                                    self.data['settings'][key] = int(value)
                        self._save_data()
                        # Optionally remove the old config file
                        # os.remove(old_config_file)
        except Exception as e:
            logger.error(f"Error loading data file: {str(e)}")
            self.data = {
                'time_records': {},
                'network_status': '',
                'devices': [],
                'current_day': datetime.now().strftime('%Y-%m-%d'),
                'task_status': {},
                'settings': {
                    'period': 60,
                    'restime': 75,
                    'starting': '8:00',
                    'ending': '22:00',
                    'mon': 60,
                    'tue': 60,
                    'wed': 60,
                    'thu': 60,
                    'fri': 60,
                    'sat': 90,
                    'sun': 75,
                    'current': 0
                }
            }
    
    def get_data(self, key=None):
        """Get fresh data from file. If key is provided, return that specific key's value."""
        self._load_data()  # Always reload from file
        if key is not None:
            return self.data.get(key, {} if isinstance(self.data.get(key), dict) else '')
        return self.data
    
    def _save_data(self):
        """Save data to JSON file."""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving data file: {str(e)}")
    
    def get_network_status(self):
        """Get the current network status from data file."""
        data = self.get_data()
        return data.get('network_status', 'unknown')

    def set_network_status(self, status):
        """Set the current network status in data file."""
        data = self.get_data()
        data['network_status'] = status
        self.data = data
        self._save_data()
    
    def get_config_value(self, key):
        """Get a value from settings."""
        try:
            data = self.get_data()
            return str(data['settings'].get(key))
        except Exception as e:
            logger.error(f"Error reading config value for {key}: {str(e)}")
            return None
    
    def set_config_value(self, key, value):
        """Set a value in settings."""
        try:
            data = self.get_data()
            if key in ['starting', 'ending']:
                # Handle time format "hour:minutes"
                if ':' not in str(value):
                    # If no minutes specified, assume 0 minutes
                    value = f"{int(value)}:00"
                # Validate time format
                hours, minutes = map(int, str(value).split(':'))
                if not (0 <= hours < 24 and 0 <= minutes < 60):
                    raise ValueError(f"Invalid time format: {value}")
                data['settings'][key] = value
            else:
                data['settings'][key] = int(value)
            self.data = data
            self._save_data()
        except Exception as e:
            logger.error(f"Error setting config value for {key}: {str(e)}")
    
    def get_time_record(self, key):
        """Get a value from time records."""
        try:
            data = self.get_data()
            return str(data['time_records'].get(key, "0"))
        except Exception as e:
            logger.error(f"Error reading time record for {key}: {str(e)}")
            return "0"
    
    def set_time_record(self, key, value):
        """Set a value in time records."""
        try:
            data = self.get_data()
            data['time_records'][key] = value
            self.data = data
            self._save_data()
        except Exception as e:
            logger.error(f"Error setting time record for {key}: {str(e)}")
    
    def remove_time_record(self, key):
        """Remove a value from time records."""
        try:
            data = self.get_data()
            if key in data['time_records']:
                del data['time_records'][key]
                self.data = data
                self._save_data()
        except Exception as e:
            logger.error(f"Error removing time record for {key}: {str(e)}")
    
    def reset_current_usage(self):
        """Reset current usage and log the previous day's usage."""
        current_day = datetime.now().strftime('%Y-%m-%d')
        
        try:
            data = self.get_data()
            previous_day = data['current_day']
            
            if current_day != previous_day:
                # Reset all counters
                data['settings']['current'] = 0
                data['current_day'] = current_day
                data['time_records'] = {
                    'elapsed_time': '0',
                    'rest_time': '0'
                }
                self.data = data
                self._save_data()
                current_usage = self.get_config_value('current')
                logger.info(f"Kid_control: {current_day}: {current_usage} mins newly set")
               
        except Exception as e:
            logger.error(f"Error resetting current usage: {str(e)}")
    
    def update_current_usage(self, minutes):
        """Update the current usage in minutes."""
        try:
            current_usage = int(self.get_config_value('current') or '0')
            new_usage = int(minutes)
            total_usage = current_usage + new_usage
            self.set_config_value('current', str(total_usage))
            if new_usage < 0:
                logger.info(f"+++ [NEW TIME]: {current_usage} + ({new_usage} mins) +++")
        except ValueError as e:
            logger.error(f"Error updating current usage: {str(e)}")
            raise

    def get_devices(self):
        """Get the list of devices from data file."""
        data = self.get_data()
        return data.get('devices', [])

    def set_devices(self, devices):
        """Set the list of devices in data file."""
        data = self.get_data()
        data['devices'] = devices
        self.data = data
        self._save_data() 