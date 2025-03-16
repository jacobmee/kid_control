#!/bin/bash

# Variables
router_ip="192.168.0.1"
username="jacob"
password="Jac0bm!@#G"
rule_name="max"
log_file="/home/jacob/kid_control/time_checking.log"
max_log_size=1048576  # 1MB in bytes
network_check_ip="192.168.0.10"

# Function to get the total minutes used today from kidcontrol_hours.txt
get_total_minutes_used() {
    current_minutes=$(grep "^current=" /home/jacob/kid_control/kidcontrol_hours.txt | cut -d'=' -f2)
    echo "$current_minutes"
}

# Function to get the maximum minutes allowed for today from kidcontrol_hours.txt
get_max_minutes_for_today() {
    current_day=$(date +%a | tr '[:upper:]' '[:lower:]')
    max_minutes=$(grep "^$current_day=" /home/jacob/kid_control/kidcontrol_hours.txt | cut -d'=' -f2)
    echo "$max_minutes"
}

# Function to rotate the log file if it exceeds the maximum size
rotate_log_file() {
    if [ -f "$log_file" ]; then
        log_size=$(stat -c%s "$log_file")
        if [ "$log_size" -ge "$max_log_size" ]; then
            mv "$log_file" "$log_file.bak"
            echo "$(date): Log file rotated." > "$log_file"
        fi
    fi
}

# Function to check network stability
check_network_stability() {
    if ! ping -c 1 "$network_check_ip" &> /dev/null; then
        echo "$(date): Network check failed. Restarting networking service." >> "$log_file"
        systemctl restart networking
    else
        echo "$(date): Network check successful." >> "$log_file"
    fi
}

# Rotate the log file if necessary
rotate_log_file

# Check network stability
check_network_stability

# Get the start time
if [ -f /home/jacob/kid_control/kidcontrol_start_time.txt ]; then
    start_time=$(cat /home/jacob/kid_control/kidcontrol_start_time.txt)
    current_time=$(date +%s)
    elapsed_time=$(( (current_time - start_time) / 60 ))  # Convert seconds to minutes

    # Get the total minutes used today
    total_minutes_used=$(get_total_minutes_used)

    # Get the maximum minutes allowed for today
    max_minutes=$(get_max_minutes_for_today)

    # Check if the total exceeds the maximum minutes or if elapsed time exceeds 30 minutes
    if [ $((total_minutes_used + elapsed_time)) -ge $max_minutes ] || [ $elapsed_time -gt 30 ]; then
        echo "$(date): Elapsed: $elapsed_time + Used: $total_minutes_used > Max : $max_minutes or Elapsed > 30" >> "$log_file"
        /home/jacob/kid_control/kid_control.sh stopcounting
    else
        echo "$(date): Elapsed: $elapsed_time + Used: $total_minutes_used < Max : $max_minutes and Elapsed <= 30" >> "$log_file"
    fi
else
    echo "$(date): Start time file not found." >> "$log_file"
fi