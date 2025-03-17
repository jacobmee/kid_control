#!/bin/bash

. /home/jacob/kid_control/prop.config

# Initialize the hours file if it doesn't exist
if [ ! -f "$config_file" ]; then
    echo "period=30" > "$config_file"
    echo "starting=8" >> "$config_file"
    echo "ending=22" >> "$config_file"
    echo -e "mon=120\ntue=120\nwed=120\nthu=120\nfri=120\nsat=300\nsun=300" >> "$config_file"
    echo "current=0" >> "$config_file"
fi

# Initialize the current day file if it doesn't exist
if [ ! -f "$current_day_file" ]; then
    date +%Y-%m-%d > "$current_day_file"
fi

# Function to set total minutes for each weekday
set_minutes() {
    local day=$1
    local minutes=$2
    sed -i "s/$day=[0-9]*/$day=$minutes/" "$config_file"
}

# Function to get the current usage in minutes
get_current_usage() {
    grep "current=" "$config_file" | cut -d'=' -f2
}

# Function to update the current usage in minutes
update_current_usage() {
    local new_usage=$1
    local current_usage=$(get_current_usage)
    
    # Debugging: Print current usage
    # echo "current_usage: $current_usage"
    
    # Check if current_usage is a valid number
    if ! [[ "$current_usage" =~ ^[0-9]+$ ]]; then
        echo "Error: Invalid current usage value: $current_usage"
        exit 1
    fi
    
    local total_usage=$((current_usage + new_usage))
    
    # Debugging: Print new usage and total usage
    #echo "total_usage: $total_usage"
    
    sed -i "s/current=[0-9]*/current=$total_usage/" "$config_file"
}

# Function to check if the maximum minutes have been reached
check_max_minutes() {
    local day=$1
    local max_minutes=$(grep "$day=" "$config_file" | cut -d'=' -f2)
    local current_usage=$(get_current_usage)

    if [ "$current_usage" -ge "$max_minutes" ]; then
        exit 1
    fi
}

# Function to reset current usage and log the previous day's usage
reset_current_usage() {
    local current_usage=$(get_current_usage)
    local current_day=$(date +%Y-%m-%d)
    local previous_day=$(cat "$current_day_file")

    if [ "$current_day" != "$previous_day" ]; then
        echo "$previous_day: $current_usage mins" >> "$log_file"
        sed -i "s/current=[0-9]*/current=0/" "$config_file"
        date +%Y-%m-%d > "$current_day_file"
    fi
}

# Command-line arguments
command=$1
day=$2
minutes=$3

case $command in
    set)
        set_minutes "$day" "$minutes"
        ;;
    check)
        check_max_minutes "$day"
        ;;
    update)
        reset_current_usage
        update_current_usage "$minutes"
        ;;
    get_current_usage)
        get_current_usage
        ;;
    reset)
        reset_current_usage
        ;;
    *)
        echo "Usage: $0 {set|check|update|get_current_usage|reset} [day] [minutes]"
        exit 1
        ;; 
esac