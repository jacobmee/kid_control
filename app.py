from flask import Flask, render_template, request, redirect, url_for, flash
import subprocess
import os
import calendar
import time
import json
import logging
import sys

from datetime import date


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your actual secret key

# Source the configuration file
config_path = '/home/jacob/apps/kid_control/prop.config'
config = {}
with open(config_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            name, value = line.split('=', 1)
            config[name] = value

# Define paths using the sourced configuration
config_file = config['config_file']
status_file = config['status_file']
time_record_file = config['time_record_file']
kid_control_script = config['kid_control_script']
error_file = config['error_file']
task_status_file = config['task_status_file']

# Configure logging to output to the system log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

def read_kidcontrol_config():
    with open(config_file, 'r') as file:
        data = file.readlines()
    hours = {}
    for line in data:
        key, value = line.strip().split('=')
        hours[key] = int(value)
    return hours

def check_kidcontrol_status():
    subprocess.run(['sh', kid_control_script, 'check_status'])
    with open(status_file, 'r') as file:
        status = file.read().strip()
    return status

def get_time(requested_key):
    if os.path.exists(time_record_file):
        with open(time_record_file, 'r') as file:
            config_data = file.readlines()
        # Filter out empty or invalid lines
        config = {}
        for line in config_data:
            line = line.strip()  # Remove leading/trailing whitespace
            if '=' in line:  # Ensure the line contains a key-value pair
                key, value = line.split('=', 1)
                try:
                    config[key] = int(value)  # Convert value to integer
                except ValueError:
                    continue  # Skip lines with invalid integer values
        
        # Check if start_time exists in the config
        if requested_key in config:
            return config[requested_key]

    return 0

def get_elapsed_time():
    start_time = get_time('start_time')
    if start_time == 0:
        start_time = get_time('stop_time') # If start_time is not set, use current time
    
    current_time = int(time.time())
    elapsed_time = (current_time - start_time) // 60  # Convert seconds to minutes
    return elapsed_time

def get_total_elapsed_time():
    return get_time('elapsed_time')

def get_total_rest_time():
    return get_time('rest_time')

@app.route('/')
def index():
    
    today = str(date.today())
    # Load task status

    current_day = date.today().strftime('%A').lower()  # Get the current day (e.g., "saturday", "sunday")
    counting_status = check_kidcontrol_status()

# Initialize task status file if it doesn't exist
    if not os.path.exists(task_status_file):
        with open(task_status_file, 'w') as f:
            json.dump({}, f)
            
    with open(task_status_file, 'r') as f:
        task_status = json.load(f)
    
    # Get today's task status
    today_status = task_status.get(today, {})

    hours = read_kidcontrol_config()
    total_minutes_used = hours.pop('current', 0)  # Get 'current' from hours

    defined_period = hours.pop('period', 0)  # Remove 'period' from hours and get its value
    defined_restime = hours.pop('restime', 0)  # Remove 'ending' from hours and get its value
    hours.pop('starting', 0)  # Remove 'starting' from hours and get its value
    hours.pop('ending', 0)  # Remove 'ending' from hours and get its value

    # Get the maximum minutes allowed for today from the hours dictionary
    max_minutes = hours.get(time.strftime('%a').lower(), 0)  # Use the current day to get the max minutes
    
    elapsed_time = get_elapsed_time()
    # Calculate remaining time
    remaining_time = max_minutes - total_minutes_used
    # Map abbreviated weekday names to full names
    full_weekday_names = {day[:3].lower(): day for day in calendar.day_name}
    hours = {full_weekday_names.get(day, day): minutes for day, minutes in hours.items()}
    
    total_elapsed_time= get_total_elapsed_time()
    total_rest_time= get_total_rest_time()
    # Calculate the needed rest time

    stop_times = total_elapsed_time / defined_period
    required_rest_time = stop_times * defined_restime * defined_period / 100 
    needed_rest_time = int(required_rest_time - total_rest_time - elapsed_time)

    #logging.info(f"Total elapsed time: {total_elapsed_time}, Total rest time: {total_rest_time}, Elapsed time: {elapsed_time}, Needed rest time: {needed_rest_time}")

    next_rest_time = int(total_elapsed_time + elapsed_time) if counting_status == 'disabled' else int(total_elapsed_time)
    next_rest_time = next_rest_time % defined_period 
    if next_rest_time > 0:
        next_rest_time = defined_period - next_rest_time

    #logging.info(f"next_rest_time: {next_rest_time}")
    # Check for error message
    if os.path.exists(error_file):
        with open(error_file, 'r') as file:
            error_message = file.read().strip()
        flash(error_message)
        os.remove(error_file)
        
    return render_template('index.html', hours=hours, total_minutes_used=total_minutes_used, counting_status=counting_status, elapsed_time=elapsed_time, remaining_time=remaining_time,task_status=today_status,current_day=current_day, needed_rest_time=needed_rest_time, next_rest_time=next_rest_time)

@app.route('/adjust_time', methods=['POST'])
def adjust_time():
    task = request.form.get('task')
    today = str(date.today())

    # Load task status
    with open(task_status_file, 'r') as f:
        task_status = json.load(f)

    # Check if the task has already been completed today
    if task_status.get(today, {}).get(task):
        flash(f"You have already completed '{task}' today.")
        return redirect(url_for('index'))

    # Mark the task as completed for today
    if today not in task_status:
        task_status[today] = {}
    task_status[today][task] = True

    # Save the updated task status
    with open(task_status_file, 'w') as f:
        json.dump(task_status, f)

    # Call the kid_control script to adjust time
    if task == 'homework':
        subprocess.run([kid_control_script, 'update', 'current', '-30'])
        flash("30 minutes charged for finishing homework.")
    elif task == 'english':
        subprocess.run([kid_control_script, 'update', 'current', '-15'])
        flash("15 minutes charged for finishing english homework.")
    elif task == 'coding':
        subprocess.run([kid_control_script, 'update', 'current', '-15'])
        flash("15 minutes charged for finishing coding.")
    elif task == 'noyelling':
        subprocess.run([kid_control_script, 'update', 'current', '-15'])
        flash("15 minutes charged for being a gentleman.")
    elif task == 'washes':
        subprocess.run([kid_control_script, 'update', 'current', '-15'])
        flash("15 minutes charged for finishing washes.")
    elif task == 'outdoor':
        subprocess.run([kid_control_script, 'update', 'current', '-60'])
        flash("60 minutes charged for finishing outdoor.")
    return redirect(url_for('index'))


@app.route('/startcount', methods=['POST'])
def startcount():
    subprocess.run(['sh', kid_control_script, 'startcounting'])
    return redirect(url_for('index'))

@app.route('/stopcount', methods=['POST'])
def stopcount():
    subprocess.run(['sh', kid_control_script, 'stopcounting'])
    return redirect(url_for('index'))

@app.route('/edit', methods=['GET', 'POST'])
def edit_hours():
    if request.method == 'POST':
        hours = request.form.to_dict()
        with open(config_file, 'w') as file:
            for day, minutes in hours.items():
                file.write(f'{day}={minutes}\n')
        return redirect(url_for('index'))
    
    hours = read_kidcontrol_config()
    return render_template('edit.html', hours=hours)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
