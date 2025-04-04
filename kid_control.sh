#!/bin/bash

# Source the configuration file
. /home/jacob/kid_control/prop.config

action=$1  # "startcounting" or "stopcounting"


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
start_hour=$(grep "^starting=" "$config_file" | cut -d'=' -f2)
end_hour=$(grep "^ending=" "$config_file" | cut -d'=' -f2)

# Get the current hour
current_hour=$(date +%H)

# Check if the current time exceeds the maximum allowed time or is outside the allowed hours
if [ "$action" = "startcounting" ]; then
    if [ "$total_minutes_used" -ge "$max_minutes" ]; then
        echo "Cannot start counting. The total minutes used today ($total_minutes_used) exceeds the maximum allowed ($max_minutes)." > "$error_file"
        exit 1
    elif [ "$current_hour" -lt "$start_hour" ] || [ "$current_hour" -ge "$end_hour" ]; then
        echo "Cannot start counting. The current time ($current_hour:00) is outside the allowed hours ($start_hour:00 - $end_hour:00)." > "$error_file"
        exit 1
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
        # Save the start time to kidcontrol_start_time.txt
        date +%s > "$start_time_file"
        left_minutes=$((max_minutes - total_minutes_used))
        logger "Kid_control: START counting - $left_minutes mins remaining +++"
    elif [ "$action" = "stopcounting" ]; then
        # Calculate the elapsed time
        start_time=$(cat "$start_time_file")
        current_time=$(date +%s)
        elapsed_time=$(( (current_time - start_time) / 60 ))  # Convert seconds to minutes
        
        # Update the current usage using manage_hours.sh
        "$manage_config_script" update "$elapsed_time"
        
        # Remove the start time file
        rm "$start_time_file"
        logger "Kid_control: STOP counting - $elapsed_time mins closed ---"
    fi
else
    logger "Kid_control: Rule '$rule_name' not found." > "$error_file"
fi