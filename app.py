from flask import Flask, render_template, request, redirect, url_for, flash, make_response
import os
import calendar
import time
import json
import sys
from datetime import date

from config import Config, setup_logger
from time_control import TimeControl
from router_control import RouterControl

# Get logger
logger = setup_logger('KID.CONTROL')

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your actual secret key

# Initialize our Python classes
config = Config()
time_control = TimeControl()
router_control = RouterControl()

# Add after_request handler to prevent caching
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

def read_kidcontrol_config():
    hours = {}
    for key in ['period', 'restime', 'starting', 'ending', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun', 'current']:
        value = config.get_config_value(key)
        if value:
            hours[key] = int(value)
    return hours

def check_firewall_status():
    status = router_control.check_firewall_status()
    return status or "unknown"

def get_devices():
    if router_control.get_devices_under_max():
        with open(config.devices_file, 'r') as file:
            devices_output = file.read().strip().split('\n')
            devices = [device.split(':') for device in devices_output if device.strip()]
        return devices
    return []

def get_time(requested_key):
    return int(config.get_time_record(requested_key) or '0')

def get_elapsed_time():
    start_time = get_time('start_time')
    if start_time == 0:
        start_time = get_time('stop_time')  # If start_time is not set, use current time
    
    current_time = int(time.time())
    elapsed_time = (current_time - start_time) // 60  # Convert seconds to minutes
    return elapsed_time

def get_total_elapsed_time():
    return get_time('elapsed_time')

def get_total_rest_time():
    return get_time('rest_time')

@app.route('/')
def index():
    try:
        today = str(date.today())
        current_day = date.today().strftime('%A').lower()
        network_status = check_firewall_status()
        
        # Initialize task status file if it doesn't exist
        if not os.path.exists(config.task_status_file):
            logger.info("KID.CONTROL [INDEX] Creating new task status file")
            with open(config.task_status_file, 'w') as f:
                json.dump({}, f)
            
        try:
            with open(config.task_status_file, 'r') as f:
                task_status = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"KID.CONTROL [INDEX] Error reading task status: {str(e)}")
            task_status = {}
        
        # Get today's task status
        today_status = task_status.get(today, {})

        hours = read_kidcontrol_config()
        if not hours:
            logger.error("KID.CONTROL [INDEX] Failed to read kidcontrol config")
            flash("Error: Could not read configuration")
            return redirect(url_for('index'))

        # Set default values for all template variables
        template_vars = {
            'hours': {},
            'total_minutes_used': 0,
            'network_status': 'unknown',
            'elapsed_time': 0,
            'remaining_time': 0,
            'task_status': {},
            'current_day': current_day,
            'needed_rest_time': 0,
            'next_rest_time': 0
        }

        # Update with actual values
        total_minutes_used = hours.pop('current', 0)
        defined_period = hours.pop('period', 0)
        defined_restime = hours.pop('restime', 0)
        hours.pop('starting', 0)
        hours.pop('ending', 0)

        # Get the maximum minutes allowed for today
        max_minutes = hours.get(time.strftime('%a').lower(), 0)
        
        elapsed_time = get_elapsed_time()
        remaining_time = max_minutes - total_minutes_used
        
        # Map abbreviated weekday names to full names
        full_weekday_names = {day[:3].lower(): day for day in calendar.day_name}
        hours = {full_weekday_names.get(day, day): minutes for day, minutes in hours.items()}
        
        total_elapsed_time = get_total_elapsed_time()
        total_rest_time = get_total_rest_time()

        # Calculate the needed rest time
        stop_times = int(total_elapsed_time / defined_period) if defined_period > 0 else 0
        required_rest_time = int(stop_times * defined_restime * defined_period / 100) if defined_period > 0 else 0
        needed_rest_time = int(required_rest_time - total_rest_time - elapsed_time)

        next_rest_time = int(total_elapsed_time + elapsed_time) if network_status == 'enabled' else int(total_elapsed_time)
        next_rest_time = next_rest_time % defined_period if defined_period > 0 else 0
        if next_rest_time > 0:
            next_rest_time = defined_period - next_rest_time

        # Check for error message
        if os.path.exists(config.error_file):
            with open(config.error_file, 'r') as file:
                error_message = file.read().strip()
            if error_message:  # Only flash if there's actually a message
                flash(error_message)
            os.remove(config.error_file)

        # Update template variables
        template_vars.update({
            'hours': hours,
            'total_minutes_used': total_minutes_used,
            'network_status': network_status,
            'elapsed_time': elapsed_time,
            'remaining_time': remaining_time,
            'task_status': today_status,
            'needed_rest_time': needed_rest_time,
            'next_rest_time': next_rest_time
        })
        
        try:
            return render_template('index.html', **template_vars)
        except Exception as template_error:
            logger.error(f"KID.CONTROL [INDEX] Template rendering error: {str(template_error)}")
            logger.error(f"KID.CONTROL [INDEX] Template path: {app.template_folder}/index.html")
            raise
    except Exception as e:
        logger.error(f"KID.CONTROL [INDEX] Error loading page: {str(e)}")
        flash("An error occurred while loading the page")
        return redirect(url_for('index'))

@app.route('/adjust_time', methods=['POST'])
def adjust_time():
    task = request.form.get('task')
    today = str(date.today())

    # Load task status
    try:
        with open(config.task_status_file, 'r') as f:
            task_status = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        task_status = {}

    # Check if the task has already been completed today
    if task_status.get(today, {}).get(task):
        flash(f"You have already completed '{task}' today.")
        return redirect(url_for('index'))

    # Mark the task as completed for today
    if today not in task_status:
        task_status[today] = {}
    task_status[today][task] = True

    # Save the updated task status
    with open(config.task_status_file, 'w') as f:
        json.dump(task_status, f)

    # Adjust time based on task
    time_adjustments = {
        'homework': -30,
        'english': -15,
        'coding': -15,
        'noyelling': -15,
        'washes': -15,
        'outdoor': -60
    }

    if task in time_adjustments:
        minutes = time_adjustments[task]
        config.update_current_usage(minutes)
        flash(f"{abs(minutes)} minutes charged for finishing {task}.")

    return redirect(url_for('index'))

@app.route('/startcount', methods=['POST'])
def startcount():
    success, message = time_control.start_counting()
    if not success and message:  # Only flash if there's a message
        flash(message)
    return redirect(url_for('index'))

@app.route('/stopcount', methods=['POST'])
def stopcount():
    success, message = time_control.stop_counting()
    if not success and message:  # Only flash if there's a message
        flash(message)
    return redirect(url_for('index'))

@app.route('/edit', methods=['GET', 'POST'])
def edit_hours():
    if request.method == 'POST':
        # Save hours configuration
        hours = {key: value for key, value in request.form.items() if key != 'devices'}
        for day, minutes in hours.items():
            config.set_config_value(day, minutes)

        # Save devices information
        selected_devices = request.form.getlist('devices')
        with open(config.devices_file, 'w') as file:
            for device in get_devices():
                device_name = device[0]
                device_status = 'false' if device_name in selected_devices else 'true'
                file.write(f'{device_name}:{device_status}\n')
        
        router_control.update_devices_under_max()
        return redirect(url_for('edit_hours'))
    
    devices = get_devices()
    hours = read_kidcontrol_config()
    return render_template('edit.html', hours=hours, devices=devices)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
