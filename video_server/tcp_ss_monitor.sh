#!/usr/bin/env bash

# Check if all required arguments are provided
if [ $# -ne 3 ]; then
    echo "Error: This script requires exactly 3 arguments: ip port duration"
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
LOG_FILE="ss_$(date +%Y%m%d_%H%M%S).log"

# Function to check if required commands exist
check_dependencies() {
    for cmd in ss grep date; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            echo "Error: Required command '$cmd' not found"
            exit 1
        fi
    done
}

# Function to format and write log entry
write_log() {
    local timestamp="$1"
    local data="$2"

    if [ -z "$data" ]; then
        echo "time:$timestamp No_matching_connection:0" >> "$LOG_FILE"
    else
        echo "time:$timestamp $data" >> "$LOG_FILE"
    fi
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
        if [ -z "$TARGET_IP" ] && [ -z "$TARGET_PORT" ]; then
            # Monitor all IPs and all ports
            output=$(ss -it)
        elif [ -z "$TARGET_IP" ]; then
            # Monitor any IP for the target port
            output=$(ss -it | grep -E ":[0-9]+.*:${TARGET_PORT}[^0-9]" -A 1 | grep -v -E ":[0-9]+.*:${TARGET_PORT}[^0-9]")
        elif [ -z "$TARGET_PORT" ]; then
            # Monitor any port for the target IP
            output=$(ss -it | grep -F "${TARGET_IP}:" -A 1 | grep -v -F "${TARGET_IP}:")
        else
            # Monitor specific port for the target IP
            output=$(ss -it | grep -F "${TARGET_IP}:${TARGET_PORT}" -A 1 | grep -v -F "${TARGET_IP}:${TARGET_PORT}")
        fi

        # Write to log file
        write_log "$current_time" "$output"
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

# Check dependencies before starting
check_dependencies

# Start monitoring with error handling
monitor_connection
