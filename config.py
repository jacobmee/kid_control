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
logger = setup_logger('config')

class Config:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config = {
            'router_ip': '192.168.0.1',
            'username': 'jacob',
            'password': 'Jac0bm!@#G',
            'rule_name': 'max',
            'network_check_ip': '192.168.0.10'
        }
        
        # File paths
        self.config_file = os.path.join(self.base_dir, 'kidcontrol.config')
        self.time_record_file = os.path.join(self.base_dir, 'time_record.txt')
        self.status_file = os.path.join(self.base_dir, 'status.txt')
        self.devices_file = os.path.join(self.base_dir, 'devices.txt')
        self.current_day_file = os.path.join(self.base_dir, 'current_day.txt')
        self.error_file = os.path.join(self.base_dir, 'error_message.txt')
        self.task_status_file = os.path.join(self.base_dir, 'task_status.json')
        
        # Initialize files if they don't exist
        self._initialize_files()
    
    def _initialize_files(self):
        """Initialize configuration files if they don't exist."""
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                f.write("period=60\n")
                f.write("restime=75\n")
                f.write("starting=8\n")
                f.write("ending=22\n")
                f.write("mon=60\n")
                f.write("tue=60\n")
                f.write("wed=60\n")
                f.write("thu=60\n")
                f.write("fri=60\n")
                f.write("sat=90\n")
                f.write("sun=75\n")
                f.write("current=0\n")
        
        if not os.path.exists(self.current_day_file):
            with open(self.current_day_file, 'w') as f:
                f.write(datetime.now().strftime('%Y-%m-%d'))
        
        # Create empty files if they don't exist
        for file_path in [self.time_record_file, self.status_file, 
                         self.devices_file, self.error_file, 
                         self.task_status_file]:
            if not os.path.exists(file_path):
                open(file_path, 'w').close()
    
    def get_config_value(self, key):
        """Get a value from the configuration file."""
        try:
            with open(self.config_file, 'r') as f:
                for line in f:
                    if line.startswith(f"{key}="):
                        return line.strip().split('=')[1]
            return None
        except Exception as e:
            logger.error(f"Error reading config value for {key}: {str(e)}")
            return None
    
    def set_config_value(self, key, value):
        """Set a value in the configuration file."""
        try:
            with open(self.config_file, 'r') as f:
                lines = f.readlines()
            
            found = False
            with open(self.config_file, 'w') as f:
                for line in lines:
                    if line.startswith(f"{key}="):
                        f.write(f"{key}={value}\n")
                        found = True
                    else:
                        f.write(line)
                if not found:
                    f.write(f"{key}={value}\n")
        except Exception as e:
            logger.error(f"Error setting config value for {key}: {str(e)}")
    
    def get_time_record(self, key):
        """Get a value from the time record file."""
        try:
            with open(self.time_record_file, 'r') as f:
                for line in f:
                    if line.startswith(f"{key}="):
                        return line.strip().split('=')[1]
            return "0"
        except Exception as e:
            logger.error(f"Error reading time record for {key}: {str(e)}")
            return "0"
    
    def set_time_record(self, key, value):
        """Set a value in the time record file."""
        try:
            with open(self.time_record_file, 'r') as f:
                lines = f.readlines()
            
            found = False
            with open(self.time_record_file, 'w') as f:
                for line in lines:
                    if line.startswith(f"{key}="):
                        f.write(f"{key}={value}\n")
                        found = True
                    else:
                        f.write(line)
                if not found:
                    f.write(f"{key}={value}\n")
        except Exception as e:
            logger.error(f"Error setting time record for {key}: {str(e)}")
    
    def remove_time_record(self, key):
        """Remove a value from the time record file."""
        try:
            with open(self.time_record_file, 'r') as f:
                lines = f.readlines()
            
            with open(self.time_record_file, 'w') as f:
                for line in lines:
                    if not line.startswith(f"{key}="):
                        f.write(line)
        except Exception as e:
            logger.error(f"Error removing time record for {key}: {str(e)}")
    
    def reset_current_usage(self):
        """Reset current usage and log the previous day's usage."""
        current_usage = self.get_config_value('current')
        current_day = datetime.now().strftime('%Y-%m-%d')
        
        try:
            with open(self.current_day_file, 'r') as f:
                previous_day = f.read().strip()
            
            if current_day != previous_day:
                logger.info(f"Kid_control: {current_day}: {current_usage} mins newly set")
                
                # Reset all counters
                self.set_config_value('current', '0')
                with open(self.current_day_file, 'w') as f:
                    f.write(current_day)
                
                self.set_time_record('elapsed_time', '0')
                self.set_time_record('rest_time', '0')
                self.remove_time_record('start_time')
                self.remove_time_record('stop_time')
        except Exception as e:
            logger.error(f"Error resetting current usage: {str(e)}")
    
    def update_current_usage(self, minutes):
        """Update the current usage in minutes."""
        try:
            current_usage = int(self.get_config_value('current') or '0')
            new_usage = int(minutes)
            total_usage = current_usage + new_usage
            self.set_config_value('current', str(total_usage))
        except ValueError as e:
            logger.error(f"Error updating current usage: {str(e)}")
            raise 