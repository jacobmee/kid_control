#!/usr/bin/env python3

import time
from datetime import datetime, date
import subprocess
from config import Config, setup_logger
from router_control import RouterControl

# Get logger
logger = setup_logger('TIME.CONTROL')

class TimeControl:
    def __init__(self):
        self.config = Config()
        self.router = RouterControl()
    
    def check_network_stability(self):
        """Check network stability by pinging the network check IP."""
        try:
            result = subprocess.run(
                ['ping', '-c', '1', self.config.config['network_check_ip']],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            if result.returncode != 0:
                logger.info("[NETWORK] failed. Restarting networking service.")
                subprocess.run(['systemctl', 'restart', 'networking'])
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking network stability: {str(e)}")
            return False
    
    def get_total_minutes_used(self):
        """Get the total minutes used today from kidcontrol.config."""
        return int(self.config.get_config_value('current') or '0')
    
    def get_max_minutes_for_today(self):
        """Get the maximum minutes allowed for today from kidcontrol.config."""
        current_day = datetime.now().strftime('%a').lower()
        return int(self.config.get_config_value(current_day) or '0')
    
    def check_time_limits(self):
        """Check if current time is within allowed hours and limits."""
        current_hour = int(datetime.now().strftime('%H'))
        start_hour = int(self.config.get_config_value('starting') or '0')
        end_hour = int(self.config.get_config_value('ending') or '0')
        
        if current_hour < start_hour or current_hour >= end_hour:
            return False, f"Current time ({current_hour}:00) is outside allowed hours ({start_hour}:00 - {end_hour}:00)"
        
        total_minutes_used = self.get_total_minutes_used()
        max_minutes = self.get_max_minutes_for_today()
        
        if total_minutes_used >= max_minutes:
            return False, f"Total minutes used today ({total_minutes_used}) exceeds maximum allowed ({max_minutes})"
        
        return True, None
    
    def check_rest_time(self):
        """Check if enough rest time has been taken."""
        stop_time = self.config.get_time_record('stop_time')
        if not stop_time or stop_time == '0':
            return True, None
        
        current_time = int(time.time())
        rest_time = (current_time - int(stop_time)) // 60  # Convert to minutes
        last_rest_time = int(self.config.get_time_record('rest_time') or '0')
        total_rest_time = rest_time + last_rest_time
        
        last_elapsed_time = int(self.config.get_time_record('elapsed_time') or '0')
        defined_period = int(self.config.get_config_value('period') or '0')
        defined_restime = int(self.config.get_config_value('restime') or '0')
        
        stop_times = last_elapsed_time // defined_period
        needed_rest_time = (defined_period * defined_restime * stop_times) // 100  

        if total_rest_time < needed_rest_time:
            return False, f"Not enough rest time: {total_rest_time} minutes taken, {needed_rest_time} minutes required"
        
        if total_rest_time >= needed_rest_time:
            total_rest_time = needed_rest_time
        
        self.config.set_time_record('rest_time', str(total_rest_time))  

        return True, None
    
    def start_counting(self):
        """Start counting time."""
        # Check network stability
        if not self.check_network_stability():
            return False, "Network check failed"
        
        # Check time limits
        time_ok, time_msg = self.check_time_limits()
        if not time_ok:
            return False, time_msg
        
        # Check rest time
        rest_ok, rest_msg = self.check_rest_time()
        if not rest_ok:
            return False, rest_msg
        
        # Update router rule
        if not self.router.update_rule_status(True):
            return False, "Failed to update router rule"


        # Set start time
        self.config.set_time_record('start_time', str(int(time.time())))
        self.config.remove_time_record('stop_time')

        left_minutes = self.get_max_minutes_for_today() - self.get_total_minutes_used()
        logger.info(f"+++ [START] counting - {left_minutes} mins remaining +++")

        return True, "Started counting time"
    
    def stop_counting(self):
        """Stop counting time."""
        # Update router rule
        if not self.router.update_rule_status(False):
            return False, "Failed to update router rule"
        
        # Initialize elapsed_time
        elapsed_time = 0
        
        # Get start time and calculate elapsed time
        start_time = self.config.get_time_record('start_time')
        if start_time and start_time != '0':
            current_time = int(time.time())
            elapsed_time = (current_time - int(start_time)) // 60  # Convert to minutes
 
            # Update elapsed time
            last_elapsed_time = int(self.config.get_time_record('elapsed_time') or '0')
            total_elapsed_time = last_elapsed_time + elapsed_time
            self.config.set_time_record('elapsed_time', str(total_elapsed_time))
            
            # Update current usage
            self.config.update_current_usage(elapsed_time)
        
        # Set stop time
        self.config.set_time_record('stop_time', str(int(time.time())))
        self.config.remove_time_record('start_time')

        logger.info(f"--- [STOP] counting - {elapsed_time} mins closed ---")

        return True, "Stopped counting time"
    
    def check_status(self):
        """Check the current status of time tracking."""
        self.router.check_firewall_status()
        self.config.reset_current_usage()
        return True, "Status checked and updated"

def time_checking():
    config = Config()
    time_control = TimeControl()
    
    # Check network stability
    time_control.check_network_stability()
    
    # Reset current usage if it's a new day
    today = str(date.today())
    data = config.get_data()
    last_reset_day = data['current_day']
    if last_reset_day != today:
        config.reset_current_usage()
        logger.info(f"[NEW DAY]: Reset current usage for new day: {today}")
    
    # Get current time
    current_time = int(time.time())
    current_hour = int(datetime.now().strftime('%H'))
    
    # Get configuration values
    start_time = config.get_time_record('start_time')
    stop_time = config.get_time_record('stop_time')
    
    # Get time limits
    total_minutes_used = int(config.get_config_value('current') or '0')
    current_day = datetime.now().strftime('%a').lower()
    max_minutes = int(config.get_config_value(current_day) or '0')
    
    # Get parameters
    defined_period = int(config.get_config_value('period') or '0')
    defined_restime = int(config.get_config_value('restime') or '0')
    stop_hour = int(config.get_config_value('ending') or '0')
    start_hour = int(config.get_config_value('starting') or '0')
    
    # Get time records
    last_elapsed_time = int(config.get_time_record('elapsed_time') or '0')
    last_rest_time = int(config.get_time_record('rest_time') or '0')
    
    if start_time and start_time != '0':
        elapsed_time = (current_time - int(start_time)) // 60  # Convert seconds to minutes
        stop_times = (last_elapsed_time + elapsed_time) // defined_period
        required_rest_time = (defined_period * defined_restime * stop_times) // 100
        
        # Check various conditions for stopping
        if total_minutes_used + elapsed_time >= max_minutes:
            logger.info(f"[FORCE STOP for time's up]: Elapsed: {elapsed_time} + Used: {total_minutes_used} > Max : {max_minutes}")
            time_control.stop_counting()
        elif required_rest_time > last_rest_time:
            logger.info(f"[FORCE STOP for resting]: {required_rest_time} > {last_rest_time}")
            time_control.stop_counting()
        elif current_hour >= stop_hour:
            logger.info(f"[FORCE STOP for too late]: Current Hour: {current_hour} >= Stop Hour: {stop_hour}")
            time_control.stop_counting()
        elif current_hour < start_hour:
            logger.info(f"[FORCE STOP for too early]: Current Hour: {current_hour} < Start Hour: {start_hour}")
            time_control.stop_counting()
        else:
            left_minutes = max_minutes - total_minutes_used
            logger.info(f"[UP]: {left_minutes-elapsed_time} mins open, TO REST: R({last_rest_time})+E({elapsed_time}) => {required_rest_time} mins")
    
    if stop_time and stop_time != '0':
        elapsed_time = (current_time - int(stop_time)) // 60  # Convert seconds to minutes
        stop_times = last_elapsed_time // defined_period
        required_rest_time = (defined_period * defined_restime * stop_times) // 100
        
        # Get updated values
        total_minutes_used = int(config.get_config_value('current') or '0')
        max_minutes = int(config.get_config_value(current_day) or '0')
        remaining_minutes = max_minutes - total_minutes_used

        logger.info(f"[DOWN]: {remaining_minutes} mins remaining. RESTING: {required_rest_time} mins => R({last_rest_time})+E({elapsed_time})")

if __name__ == "__main__":
    time_checking() 