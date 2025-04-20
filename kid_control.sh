#!/bin/bash

# Source the configuration file
. /home/jacob/apps/kid_control/prop.config

action=$1  # "startcounting" or "stopcounting"

# Function to set a value in the time record file
set_time_record() {
    local key=$1
    local value=$2
    sed -i "/^$key=/d" "$time_record_file"  # Remove existing key if it exists
    echo "$key=$value" >> "$time_record_file"
}

# Function to get a value from the time record file
get_time_record() {
    local key=$1
    grep "^$key=" "$time_record_file" | cut -d'=' -f2
}

# Function to remove a value from the time record file
remove_time_record() {
    local key=$1
    sed -i "/^$key=/d" "$time_record_file"
}

# Ensure the time record file exists
if [ ! -f "$time_record_file" ]; then
    touch "$time_record_file"
fi

# Validate action parameter
if [ "$action" != "startcounting" ] && [ "$action" != "stopcounting" ] && [ "$action" != "check_status" ] && [ "$action" != "update" ]; then
    echo "Invalid action. Use 'startcounting', 'stopcounting', 'check_status', or 'update'." > "$error_file"
    exit 1
fi

# Handle the update action
if [ "$action" = "update" ]; then
    if [ "$2" = "current" ] && [[ "$3" =~ ^-?[0-9]+$ ]]; then
        "$manage_config_script" update "$3"
        logger "Kid_control: Updated current usage by $3 minutes."
    else
        echo "Invalid parameters for update current:$1,$2,$3 " > "$error_file"
        exit 1
    fi
    exit 0
fi

# Function to check if KidControl rule is disabled
check_kidcontrol_status() {
    rules=$(curl -s -u "$username:$password" "http://$router_ip/rest/ip/kid-control")
    rule_status=$(echo "$rules" | jq -r --arg rule_name "$rule_name" '.[] | select(.name == $rule_name) | .disabled')
    if [ "$rule_status" = "true" ]; then
        echo "disabled" > "$status_file"
    else
        echo "enabled" > "$status_file"
    fi
}

# Handle the check_status action
if [ "$action" = "check_status" ]; then
    check_kidcontrol_status
    "$manage_config_script" reset
    exit 0
fi

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

# Get the total minutes used today
total_minutes_used=$(get_total_minutes_used)

# Get the maximum minutes allowed for today
max_minutes=$(get_max_minutes_for_today)

# Get the start and end hours from the configuration file
defined_start_hour=$(grep "^starting=" "$config_file" | cut -d'=' -f2)
defined_end_hour=$(grep "^ending=" "$config_file" | cut -d'=' -f2)
defined_restime=$(grep "^restime=" "$config_file" | cut -d'=' -f2)
defined_period=$(grep "^period=" "$config_file" | cut -d'=' -f2)

# Get the current hour
current_hour=$(date +%H)

# Check if the current time exceeds the maximum allowed time or is outside the allowed hours
if [ "$action" = "startcounting" ]; then
    if [ "$total_minutes_used" -ge "$max_minutes" ]; then
        echo "Cannot start counting. The total minutes used today ($total_minutes_used) exceeds the maximum allowed ($max_minutes)." > "$error_file"
        exit 1
    elif [ "$current_hour" -lt "$defined_start_hour" ] || [ "$current_hour" -ge "$defined_end_hour" ]; then
        echo "Cannot start counting. The current time ($current_hour:00) is outside the allowed hours ($defined_start_hour:00 - $defined_end_hour:00)." > "$error_file"
        exit 1
    fi
fi

# if the stopped time file exists, check when it is stopped.
# if stopped time is only less than restime, then we'll shrow a warning
stop_time=$(get_time_record "stop_time")
total_rest_time=0
# if stop time is not empty, then we can check the elapsed time
if [ -n "$stop_time" ]; then
    # Calculate the elapsed time since the last stop
    current_time=$(date +%s)
    rest_time=$(( (current_time - stop_time) / 60 ))  # Convert seconds to minutes
    last_rest_time=$(get_time_record "rest_time")
    if [ -n "$last_rest_time" ]; then
        total_rest_time=$((rest_time + last_rest_time))
    else
        total_rest_time=$rest_time
    fi

    # check if the elapsed time is more than the defined period
    last_elapsed_time=$(get_time_record "elapsed_time")
    # calculate the stop times if how many times the defined period is in the last elapsed time
    stop_times=$((last_elapsed_time / defined_period))  # Integer division
    needed_rest_time=$((defined_period * defined_restime * stop_times / 100))

    if [ "$total_rest_time" -lt "$needed_rest_time" ]; then
        # if the last elasped time is less than period
        echo "儿，休息一下眼睛哦！ 已经看了$last_elapsed_time 分钟, 只休息$total_rest_time 分钟又要战斗？" > "$error_file"
        logger "Kid_control: Warning - Can't start as not enough restime: ($total_rest_time minutes) is less than the required rest time ($needed_rest_time minutes) as $stop_times stops for total $last_elapsed_time spent."
        exit 1
    else
        logger "Kid_control: total Rest: ($total_rest_time) > Required ($needed_rest_time) as $stop_times stops for total $last_elapsed_time."
    fi
fi


# Determine the value for the "disabled" field
if [ "$action" = "stopcounting" ]; then
    disabled_value="no"
else
    disabled_value="yes"
fi

# Get the list of KidControl rules
rules=$(curl -s -u "$username:$password" "http://$router_ip/rest/ip/kid-control")

# Debugging: Print the rules
#echo "Rules: $rules"

# Extract the rule ID for the specified rule name
rule_id=$(echo "$rules" | jq -r --arg rule_name "$rule_name" '.[] | select(.name == $rule_name) | .[".id"]')

# Check if the rule was found
if [ -n "$rule_id" ]; then
    # Modify the rule to change the "disabled" value and remove the "paused" and "blocked" parameters if they exist
    updated_rule=$(echo "$rules" | jq --arg rule_id "$rule_id" --arg disabled_value "$disabled_value" \
        'map(if .[".id"] == $rule_id then .disabled = $disabled_value | del(.paused) | del(.blocked) else . end)')
    #echo "Updated rule: $updated_rule"
    
    # Enable or disable the KidControl rule
    response=$(curl -s -u "$username:$password" -X PUT "http://$router_ip/rest/ip/kid-control/$rule_id" \
        -H "Content-Type: application/json" \
        -d "$(echo "$updated_rule" | jq -c '.[0]')")
    
    # Debugging: Print the response
    #echo "Response: $response"
    
    #echo "KidControl rule '$rule_name' has been $action."
    
    if [ "$action" = "startcounting" ]; then
        # Save the start time
        current_time=$(date +%s)
        set_time_record "start_time" "$current_time"

        # reset the needed time to just fine 
        #logger "Kid_control: New Rest: ($total_rest_time),Required: ($needed_rest_time) ."
        if [ -n "$total_rest_time" ]; then
            set_time_record "rest_time" "$total_rest_time"
        fi
        
        # Remove the stop time
        remove_time_record "stop_time"

        left_minutes=$((max_minutes - total_minutes_used))
        logger "Kid_control: START counting - $left_minutes mins remaining +++"
    elif [ "$action" = "stopcounting" ]; then

        # Retrieve the start time
        start_time=$(get_time_record "start_time")
        current_time=$(date +%s)

        # Calculate the elapsed time
        if [ "$current_time" -lt "$start_time" ]; then
            elapsed_time=0
        else
            elapsed_time=$(( (current_time - start_time) / 60 ))  # Convert seconds to minutes
        fi

        # Save the stop time
        set_time_record "stop_time" "$current_time"

        # Save the elapsed time
        last_elapsed_time=$(get_time_record "elapsed_time")
        if [ -n "$last_elapsed_time" ]; then
            last_elapsed_time=$((elapsed_time + last_elapsed_time))
        fi
        set_time_record "elapsed_time" "$last_elapsed_time"

        # Update the current usage
        "$manage_config_script" update "$elapsed_time"

        # Remove the start time
        remove_time_record "start_time"
        logger "Kid_control: STOP counting - $elapsed_time mins closed ---"

    fi
else
    logger "Kid_control: Rule '$rule_name' not found." > "$error_file"
fi