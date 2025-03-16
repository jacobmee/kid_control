#!/bin/bash

# Source the configuration file
. /home/jacob/kid_control/prop.config

# Function to get the total minutes used today from kidcontrol.config
get_total_minutes_used() {
    current_minutes=$(grep "^current=" "$config_file" | cut -d'=' -f2)
    echo "$current_minutes"
}

# Function to get the maximum minutes allowed for today from kidcontrol.config
get_max_minutes_for_today() {
    current_day=$(date +%a | tr '[:upper:]' '[:lower:]')
    max_minutes=$(grep "^$current_day=" "$config_file" | cut -d'=' -f2)
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
    fi
}

# Rotate the log file if necessary
rotate_log_file

# Check network stability
check_network_stability

# Function to get a parameter value from kidcontrol.config
get_config() {
    param_name=$1
    param_value=$(grep "^$param_name=" "$config_file" | cut -d'=' -f2)
    if [ -z "$param_value" ]; then
        echo "Error: Parameter '$param_name' not found in kidcontrol.config" >&2
        exit 1
    fi
    echo "$param_value"
}

# Get the start time
if [ -f "$start_time_file" ]; then
    start_time=$(cat "$start_time_file")
    current_time=$(date +%s)
    elapsed_time=$(( (current_time - start_time) / 60 ))  # Convert seconds to minutes

    # Get the total minutes used today
    total_minutes_used=$(get_total_minutes_used)
    # Get the maximum minutes allowed for today
    max_minutes=$(get_max_minutes_for_today)
    # Get parameters from kidcontrol.config
    max_elapsed_time=$(get_config "period")
    stop_hour=$(get_config "ending")
    start_hour=$(get_config "starting")
    
    # Check if the total exceeds the maximum minutes, if elapsed time exceeds max_elapsed_time, or if it's after stop_hour or before start_hour
    current_hour=$(date +%H)
    if [ $((total_minutes_used + elapsed_time)) -ge $max_minutes ]; then
        echo "$(date): [STOPPED for time's up]: Elapsed: $elapsed_time + Used: $total_minutes_used > Max : $max_minutes" >> "$log_file"
        "$kid_control_script" stopcounting
    elif [ $elapsed_time -gt "$max_elapsed_time" ]; then
        echo "$(date): [STOPPED for resting]: Elapsed: $elapsed_time > Max Elapsed: $max_elapsed_time" >> "$log_file"
        "$kid_control_script" stopcounting
    elif [ "$current_hour" -ge "$stop_hour" ]; then
        echo "$(date): [STOPPED for too late]: Current Hour: $current_hour >= Stop Hour: $stop_hour" >> "$log_file"
        "$kid_control_script" stopcounting
    elif [ "$current_hour" -lt "$start_hour" ]; then
        echo "$(date): [STOPPED for too early]: Current Hour: $current_hour < Start Hour: $start_hour" >> "$log_file"
        "$kid_control_script" stopcounting
    else
        left_minutes=$((max_minutes - total_minutes_used - elapsed_time))
        if [ $((left_minutes % 10)) -eq 0 ]; then
            echo "$(date): $left_minutes minutes left." >> "$log_file"
        fi
    fi
else   
    # Get the total minutes used today
    total_minutes_used=$(get_total_minutes_used)
    # Get the maximum minutes allowed for today
    max_minutes=$(get_max_minutes_for_today)
    remaining_minutes=$((max_minutes - total_minutes_used))
    echo "$(date): Not started yet, and still have $remaining_minutes minutes left."
fi