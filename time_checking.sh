#!/bin/bash

# Source the configuration file
. /home/jacob/apps/kid_control/prop.config

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

# Function to check network stability
check_network_stability() {
    if ! ping -c 1 "$network_check_ip" &> /dev/null; then
        logger "Time_checking: Network check failed. Restarting networking service."
        systemctl restart networking
    fi
}

# Check network stability
check_network_stability

# Function to get a value from the time record file
get_time_record() {
    local key=$1
    grep "^$key=" "$time_record_file" | cut -d'=' -f2
}

# Function to get a parameter value from kidcontrol.config
get_config() {
    param_name=$1
    param_value=$(grep "^$param_name=" "$config_file" | cut -d'=' -f2)
    if [ -z "$param_value" ]; then
        logger "Time_checking: Error Parameter '$param_name' not found in kidcontrol.config" >&2
        exit 1
    fi
    echo "$param_value"
}

# Get the start time
start_time=$(grep "^start_time=" "$time_record_file" | cut -d'=' -f2)
#logger "Time_checking: Start time: $start_time"

if [ -n "$start_time" ]; then
    current_time=$(date +%s)
    elapsed_time=$(( (current_time - start_time) / 60 ))  # Convert seconds to minutes

    # Get the total minutes used today
    total_minutes_used=$(get_total_minutes_used)
    # Get the maximum minutes allowed for today
    max_minutes=$(get_max_minutes_for_today)
    # Get parameters from kidcontrol.config
    defined_period=$(get_config "period")
    defined_restime=$(get_config "restime")
    stop_hour=$(get_config "ending")
    start_hour=$(get_config "starting")

    # check if the elapsed time is more than the defined period
    last_elapsed_time=$(get_time_record "elapsed_time")
        if [ -n "$last_elapsed_time" ]; then
            last_elapsed_time=$((elapsed_time + last_elapsed_time))
        fi

    # calculate the stop times if how many times the defined period is in the last elapsed time
    stop_times=$((last_elapsed_time / defined_period))  # Integer division
    needed_rest_time=$((defined_period * defined_restime * stop_times / 100))

    last_rest_time=$(get_time_record "rest_time")
    
    # Check if the total exceeds the maximum minutes, if elapsed time exceeds max_elapsed_time, or if it's after stop_hour or before start_hour
    current_hour=$(date +%H)
    if [ $((total_minutes_used + elapsed_time)) -ge $max_minutes ]; then
        logger "Time_checking: [FORCE STOP for time's up]: Elapsed: $elapsed_time + Used: $total_minutes_used > Max : $max_minutes" 
        "$kid_control_script" stopcounting
    elif [ "$needed_rest_time" -gt "$last_rest_time" ]; then
        logger "Time_checking: [FORCE STOP for resting]: Elapsed: $last_elapsed_time > Max Elapsed: $needed_rest_time"
        "$kid_control_script" stopcounting
    elif [ "$current_hour" -ge "$stop_hour" ]; then
        logger "Time_checking: [FORCE STOP for too late]: Current Hour: $current_hour >= Stop Hour: $stop_hour"
        "$kid_control_script" stopcounting
    elif [ "$current_hour" -lt "$start_hour" ]; then
        logger "Time_checking: [FORCE STOP for too early]: Current Hour: $current_hour < Start Hour: $start_hour"
        "$kid_control_script" stopcounting
    else
        left_minutes=$((max_minutes - total_minutes_used))
        if [ $((elapsed_time % 10)) -eq 0 ] && [ "$elapsed_time" -ne 0 ]; then
            logger "Time_checking: COUNTING ($left_minutes - $elapsed_time) minutes."
        fi
    fi
else   
    # Get the total minutes used today
    total_minutes_used=$(get_total_minutes_used)
    # Get the maximum minutes allowed for today
    max_minutes=$(get_max_minutes_for_today)
    remaining_minutes=$((max_minutes - total_minutes_used))
    logger "Time_checking: Not started yet, and still have $remaining_minutes minutes left."
fi
