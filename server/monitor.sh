#!/usr/bin/env bash

# Check if running as root
[ $(id -u) -ne 0 ] && echo "must run as root" && exit 1

# Check if all required arguments are provided
if [ $# -ne 2 ]; then
    echo "Require arguments: <port> <test_id>"
    echo "Example: $0 5202 test0"
    exit 1
fi

# Parse arguments
PORT="$1"
TEST_ID="$2"

OUTPUT_DIR="captures"
# Check if output directory exists
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Please manually create output directory: $OUTPUT_DIR"
    exit 1
fi
# Convert to absolute path
OUTPUT_DIR=$(cd "$OUTPUT_DIR" && pwd)
# Get the owner of the output directory
DIR_OWNER=$(stat -c '%U' "$OUTPUT_DIR" 2>/dev/null || echo "")
if [ -z "$DIR_OWNER" ]; then
    echo "Error: Failed to get directory owner"
    exit 1
fi

date_str=$(date +%Y%m%d_%H%M%S)

pcap_file="$OUTPUT_DIR/${TEST_ID}_pcap_server_${date_str}.pcap"

# Remove existing file if it exists (in case of permission issues)
[ -f "$pcap_file" ] && rm -f "$pcap_file"

ss_cmd="ss -ito -nOH state established '( sport = :${PORT} )'"

ss_log_file="$OUTPUT_DIR/${TEST_ID}_ss_${date_str}.log"

monitor_connection() {
    local cmd="$1"
    local log_file="$2"
    while true; do
        current_time=$(date +%s%N)
        output=$(eval "$cmd")
        if [ -n "$output" ]; then
            printf "time:%s\n%s\n" "$current_time" "$output" >> "$log_file"
        fi
    done
}

# Cleanup function to kill both processes
cleanup() {
    echo "Cleaning up..."
    [ -n "$tcpdump_pid" ] && kill $tcpdump_pid 2>/dev/null
    [ -n "$ss_pid" ] && kill $ss_pid 2>/dev/null
    exit
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM EXIT

# Run tcpdump in background
tcpdump tcp port ${PORT} -s 96 -C 1000 -Z "$DIR_OWNER" -w "$pcap_file" &
tcpdump_pid=$!

# Run ss monitoring in background
monitor_connection "$ss_cmd" "$ss_log_file" &
ss_pid=$!

# Wait for both processes
wait $tcpdump_pid $ss_pid