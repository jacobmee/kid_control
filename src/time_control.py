#!/usr/bin/env python3

import time
from datetime import datetime, date
import subprocess
from config import Config, setup_logger
from router_control import RouterControl

# Get logger
logger = setup_logger('TIME.CONTROL')

def time_to_minutes(time_str):
    hours, minutes = map(int, time_str.split(':'))
    return hours * 60 + minutes

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
                logger.info("[Network Failure] Restarting networking service.")
                subprocess.run(['bash', '/home/jacob/bin/check_network.sh'])
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
        current_time = datetime.now().strftime('%H:%M')
        
        # Get start and end times
        start_time = self.config.get_config_value('starting')
        end_time = self.config.get_config_value('ending')
        
        # Convert all times to minutes for comparison
        # Moved to class level as it's a utility function that could be used elsewhere
        current_time_mins = time_to_minutes(current_time)
        start_time_mins = time_to_minutes(start_time)
        end_time_mins = time_to_minutes(end_time)
        
        if current_time_mins < start_time_mins or current_time_mins >= end_time_mins:
            return False, f"Current time ({current_time}) is outside allowed hours ({start_time} - {end_time})"
        
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

        # --- Rest time logic: record rest_time at start, but cap it at required rest time or proportional max ---
        saved_used_time = int(self.config.get_time_record('elapsed_time') or '0')
        saved_rest_time = int(self.config.get_time_record('rest_time') or '0')
        defined_period = int(self.config.get_config_value('period') or '0')
        defined_restime = int(self.config.get_config_value('restime') or '0')
        stop_times = int(saved_used_time / defined_period) if defined_period > 0 else 0
        required_rest_time = int(stop_times * defined_restime * defined_period / 100) if defined_period > 0 else 0
        this_time_required_rest_time = required_rest_time - saved_rest_time
        max_rest_time = int(saved_used_time * defined_restime / 100) if defined_period > 0 else 0
        stop_time = self.config.get_time_record('stop_time')

        if stop_time and stop_time != '0':
            current_time = int(time.time())
            rest_time = (current_time - int(stop_time)) // 60  # minutes
            add_rest = 0
            if this_time_required_rest_time > 0:
                add_rest = min(rest_time, this_time_required_rest_time)
            elif saved_used_time > 0:
                # Allow adding rest time, but cap total at max_rest_time
                add_rest = min(rest_time, max(0, max_rest_time - saved_rest_time))
            # else: add_rest remains 0
            logger.info(f"[REST] Adding {add_rest} mins to rest time, saved: {saved_rest_time}, required: {required_rest_time}, max: {max_rest_time}")
            self.config.set_time_record('rest_time', str(saved_rest_time + add_rest))

        # Get required rest time, and saved rest time and unsave_elapsed time
        left_minutes = self.get_max_minutes_for_today() - self.get_total_minutes_used()
        logger.info(f"+++ [START] counting - {left_minutes} mins remaining +++")

        # Set start time
        self.config.set_time_record('start_time', str(int(time.time())))
        self.config.remove_time_record('stop_time')

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
            used_time = int(self.config.get_time_record('elapsed_time') or '0')
            total_elapsed_time = used_time + elapsed_time
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

    def time_checking(self):
        # Check network stability
        self.check_network_stability()
        
        # Reset current usage if it's a new day
        today = str(date.today())
        data = self.config.get_data()
        last_reset_day = data['current_day']
        if last_reset_day != today:
            self.config.reset_current_usage()
        
        # Get current time
        current_time = int(time.time())
        
        # Get start and end times
        start_time = self.config.get_config_value('starting')
        end_time = self.config.get_config_value('ending')
        
        # Convert all times to minutes for comparison
        current_time_mins = time_to_minutes(datetime.now().strftime('%H:%M'))
        start_time_mins = time_to_minutes(start_time)
        end_time_mins = time_to_minutes(end_time)
        
        # Get configuration values
        start_time = self.config.get_time_record('start_time')
        stop_time = self.config.get_time_record('stop_time')
        
        # Get time limits
        total_minutes_used = int(self.config.get_config_value('current') or '0')
        current_day = datetime.now().strftime('%a').lower()
        max_minutes = int(self.config.get_config_value(current_day) or '0')
        
        # Get parameters
        defined_period = int(self.config.get_config_value('period') or '0')
        defined_restime = int(self.config.get_config_value('restime') or '0')
        
        # Get time records
        last_elapsed_time = int(self.config.get_time_record('elapsed_time') or '0')
        last_rest_time = int(self.config.get_time_record('rest_time') or '0')
        
        if start_time and start_time != '0':
            elapsed_time = (current_time - int(start_time)) // 60  # Convert seconds to minutes
            stop_times = elapsed_time // defined_period
            required_rest_time = (defined_period * defined_restime * stop_times) // 100
            
            # Check various conditions for stopping
            if total_minutes_used + elapsed_time >= max_minutes:
                logger.info(f"[FORCE STOP for time's up]: Elapsed: {elapsed_time} + Used: {total_minutes_used} > Max : {max_minutes}")
                self.stop_counting()
            elif required_rest_time > last_rest_time:
                logger.info(f"[FORCE STOP for resting]: {required_rest_time} > {last_rest_time}")
                self.stop_counting()
            elif current_time_mins >= end_time_mins:
                logger.info(f"[FORCE STOP for too late]: Current Hour: {current_time_mins} >= End Hour: {end_time_mins}")
                self.stop_counting()
            elif current_time_mins < start_time_mins:
                logger.info(f"[FORCE STOP for too early]: Current Hour: {current_time_mins} < Start Hour: {start_time_mins}")
                self.stop_counting()
            else:
                left_minutes = max_minutes - total_minutes_used
                logger.info(f"[UP]: {left_minutes-elapsed_time} mins open, S.Rest({last_rest_time}): S.Used({last_elapsed_time }) + U.Used({elapsed_time}) of ({defined_period * defined_restime // 100})")
                
        if stop_time and stop_time != '0':
            elapsed_time = (current_time - int(stop_time)) // 60  # Convert seconds to minutes
            stop_times = last_elapsed_time // defined_period
            required_rest_time = (defined_period * defined_restime * stop_times) // 100
            
            # Get updated values
            total_minutes_used = int(self.config.get_config_value('current') or '0')
            max_minutes = int(self.config.get_config_value(current_day) or '0')
            remaining_minutes = max_minutes - total_minutes_used
            if required_rest_time > last_rest_time + elapsed_time:
                logger.info(f"[DOWN]: {remaining_minutes} mins remaining. Waiting: {required_rest_time} mins <== S.Rest({last_rest_time}) + U.Rest({elapsed_time}) of ({defined_period * defined_restime // 100})")
            elif required_rest_time == last_rest_time + elapsed_time:
                logger.info(f"[DOWN]: {remaining_minutes} mins remaining. READY to start counting")

