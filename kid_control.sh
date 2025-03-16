#!/bin/bash

# Variables
router_ip="192.168.0.1"
username="jacob"
password="Jac0bm!@#G"
rule_name="max"
action=$1  # "startcounting" or "stopcounting"

# Validate action parameter
if [ "$action" != "startcounting" ] && [ "$action" != "stopcounting" ] && [ "$action" != "check_status" ]; then
    echo "Invalid action. Use 'startcounting', 'stopcounting', or 'check_status'."
    exit 1
fi

# Function to check if KidControl rule is disabled
check_kidcontrol_status() {
    rules=$(curl -s -u "$username:$password" "http://$router_ip/rest/ip/kid-control")
    rule_status=$(echo "$rules" | jq -r --arg rule_name "$rule_name" '.[] | select(.name == $rule_name) | .disabled')
    if [ "$rule_status" = "true" ]; then
        echo "disabled" > ./kidcontrol_status.txt
    else
        echo "enabled" > ./kidcontrol_status.txt
    fi
}

# Handle the check_status action
if [ "$action" = "check_status" ]; then
    check_kidcontrol_status
    exit 0
fi

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

# Get the total minutes used today
total_minutes_used=$(get_total_minutes_used)

# Get the maximum minutes allowed for today
max_minutes=$(get_max_minutes_for_today)

# Check if the current time exceeds the maximum allowed time
if [ "$action" = "startcounting" ] && [ "$total_minutes_used" -ge "$max_minutes" ]; then
    echo "Cannot start counting. The total minutes used today ($total_minutes_used) exceeds the maximum allowed ($max_minutes)." | tee -a "$log_file"
    exit 1
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
    
    echo "KidControl rule '$rule_name' has been $action."
    
    if [ "$action" = "startcounting" ]; then
        # Save the start time to kidcontrol_start_time.txt
        date +%s > ./kidcontrol_start_time.txt
    elif [ "$action" = "stopcounting" ]; then
        # Calculate the elapsed time
        start_time=$(cat ./kidcontrol_start_time.txt)
        current_time=$(date +%s)
        elapsed_time=$(( (current_time - start_time) / 60 ))  # Convert seconds to minutes
        
        # Get the current day
        current_day=$(date +%a | tr '[:upper:]' '[:lower:]')
        
        # Update the current usage using manage_hours.sh
        ./manage_hours.sh update "$current_day" "$elapsed_time"
        
        # Remove the start time file
        rm ./kidcontrol_start_time.txt
    fi
else
    echo "KidControl rule '$rule_name' not found."
fi