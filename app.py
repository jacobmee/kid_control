from flask import Flask, render_template, request, redirect, url_for
import subprocess
import os
import calendar
import time

app = Flask(__name__)

def read_kidcontrol_hours():
    with open('./kidcontrol_hours.txt', 'r') as file:
        data = file.readlines()
    hours = {}
    for line in data:
        key, value = line.strip().split('=')
        hours[key] = int(value)
    return hours

def check_kidcontrol_status():
    subprocess.run(['sh', './kid_control.sh', 'check_status'])
    with open('./kidcontrol_status.txt', 'r') as file:
        status = file.read().strip()
    #print("load:",status)
    return status

def get_elapsed_time():
    if os.path.exists('./kidcontrol_start_time.txt'):
        with open('./kidcontrol_start_time.txt', 'r') as file:
            start_time = int(file.read().strip())
        current_time = int(time.time())
        elapsed_time = (current_time - start_time) // 60  # Convert seconds to minutes
        return elapsed_time
    return 0

@app.route('/')
def index():
    hours = read_kidcontrol_hours()
    total_minutes_used = hours.pop('current', 0)  # Remove 'current' from hours and get its value
    counting_status = check_kidcontrol_status()
    elapsed_time = get_elapsed_time() if counting_status == 'disabled' else 0
    
    # Map abbreviated weekday names to full names
    full_weekday_names = {day[:3].lower(): day for day in calendar.day_name}
    hours = {full_weekday_names.get(day, day): minutes for day, minutes in hours.items()}
    
    return render_template('index.html', hours=hours, total_minutes_used=total_minutes_used, counting_status=counting_status, elapsed_time=elapsed_time)

@app.route('/startcount', methods=['POST'])
def startcount():
    subprocess.run(['sh', './kid_control.sh', 'startcounting'])
    return redirect(url_for('index'))

@app.route('/stopcount', methods=['POST'])
def stopcount():
    subprocess.run(['sh', './kid_control.sh', 'stopcounting'])
    return redirect(url_for('index'))

@app.route('/edit', methods=['GET', 'POST'])
def edit_hours():
    if request.method == 'POST':
        hours = request.form.to_dict()
        with open('./kidcontrol_hours.txt', 'w') as file:
            for day, minutes in hours.items():
                file.write(f'{day}={minutes}\n')
        return redirect(url_for('index'))
    
    hours = read_kidcontrol_hours()
    return render_template('edit.html', hours=hours)


if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0')