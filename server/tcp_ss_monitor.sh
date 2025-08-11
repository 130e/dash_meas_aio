#!/usr/bin/env bash

# Check if all required arguments are provided
if [ $# -ne 3 ]; then
    help
    exit 1
fi

# Parse arguments
TARGET_IP="$1"
TARGET_PORT="$2"
DURATION="$3"

# Apply defaults for 0 or negative values
if [ "$TARGET_IP" -le 0 ] 2>/dev/null || [ "$TARGET_IP" = "0" ]; then
    TARGET_IP=""
fi

if [ "$TARGET_PORT" -le 0 ] 2>/dev/null || [ "$TARGET_PORT" = "0" ]; then
    TARGET_PORT=""
fi

if [ "$DURATION" -le 0 ] 2>/dev/null || [ "$DURATION" = "0" ]; then
    DURATION=0
fi

# Set the output log file with timestamp
LOG_DIR="captures"
LOG_FILE="${LOG_DIR}/ss_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$LOG_DIR"

help() {
    echo "Usage: $0 <remote_ip> <local_port> <duration_in_seconds>"
    echo "  remote_ip: Remote IP address to monitor (0 or negative = any IP)"
    echo "  local_port: Local port to monitor (0 or negative = any port)"
    echo "  duration_in_seconds: How long to monitor (0 or negative = indefinitely)"
    echo ""
    echo "Examples:"
    echo "  $0 0 0 0              # Monitor all remote IPs:all_local_ports indefinitely"
    echo "  $0 0 80 0             # Monitor any_remote_IP:80 indefinitely"
    echo "  $0 192.168.1.100 0 0  # Monitor 192.168.1.100:any_local_port indefinitely"
    echo "  $0 192.168.1.100 80 60 # Monitor 192.168.1.100:80 for 60 seconds"
}

# Function to check if required commands exist
check_dependencies() {
    for cmd in ss; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            echo "Error: Required command '$cmd' not found"
            exit 1
        fi
    done
}

# Main monitoring function
monitor_connection() {
    local start_time=$(date +%s%N)
    local end_time

    # Calculate end time if duration is specified
    if [ "$DURATION" -gt 0 ]; then
        end_time=$((start_time + (DURATION*1000000000)))
        echo "Monitoring for $DURATION seconds..."
    else
        echo "Monitoring indefinitely..."
    fi

    # format command
    if [ -z "$TARGET_IP" ] && [ -z "$TARGET_PORT" ]; then
        # Monitor all tcp
        prompt="ss -ito -nOH state established"
    elif [ -z "$TARGET_IP" ]; then
        # Monitor tcp to target port
        prompt="ss -ito -nOH state established '( sport = :${TARGET_PORT} )'"
    elif [ -z "$TARGET_PORT" ]; then
        # Monitor tcp from target IP
        prompt="ss -ito -nOH state established '( dst = ${TARGET_IP} )'"
    else
        # Monitor tcp from target IP to target port
        prompt="ss -ito -nOH state established '( dst = ${TARGET_IP} and sport = ${TARGET_PORT} )'"
    fi

    while true; do
        # Get current Unix timestamp in nano seconds
        # millisec: $(($(date +%s%N)/1000000))
        current_time=$(date +%s%N)

        # Check if monitoring duration has elapsed
        if [ "$DURATION" -gt 0 ] && [ "$current_time" -ge "$end_time" ]; then
            echo "Monitoring complete. Duration: $DURATION seconds"
            break
        fi

        # Run the command and capture output
        output=$(eval "$prompt")
        
        # Write to log file
        if [ -n "$output" ]; then
            printf "time:%s\n%s\n" "$current_time" "$output" >> "$LOG_FILE"
        fi
    done
}

# Show usage if -h or --help is provided
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "Usage: $0 <ip> <port> <duration_in_seconds>"
    echo "  ip: IP address to monitor (0 or negative = any IP)"
    echo "  port: Port to monitor (0 or negative = any port)"
    echo "  duration_in_seconds: How long to monitor (0 or negative = indefinitely)"
    echo ""
    echo "Examples:"
    echo "  $0 0 0 0              # Monitor all IPs:all_ports indefinitely"
    echo "  $0 0 80 0             # Monitor any_IP:80 indefinitely"
    echo "  $0 192.168.1.100 0 0  # Monitor 192.168.1.100:any_port indefinitely"
    echo "  $0 192.168.1.100 80 60 # Monitor 192.168.1.100:80 for 60 seconds"
    exit 0
fi

# Validate duration if provided
if [ -n "$DURATION" ] && ! [[ "$DURATION" =~ ^[0-9]+$ ]]; then
    echo "Error: Duration must be a non-negative number"
    exit 1
fi

# Check dependencies before starting
check_dependencies

echo "Starting connection monitoring..."
if [ -z "$TARGET_IP" ] && [ -z "$TARGET_PORT" ]; then
    echo "Target: all_IPs:all_ports"
elif [ -z "$TARGET_IP" ]; then
    echo "Target: any_IP:${TARGET_PORT}"
elif [ -z "$TARGET_PORT" ]; then
    echo "Target: ${TARGET_IP}:any_port"
else
    echo "Target: ${TARGET_IP}:${TARGET_PORT}"
fi
echo "Logging to: $LOG_FILE"

# Start monitoring with error handling
monitor_connection
