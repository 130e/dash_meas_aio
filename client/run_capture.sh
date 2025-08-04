#!/system/bin/sh

# Check if running as root
[ $(id -u) -ne 0 ] && echo "must run as root" && exit 1

# Check if SERVER_IP is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <SERVER_IP>"
    echo "Example: $0 192.168.1.100"
    exit 1
fi

SERVER_IP=$1
DATE=$(date +%Y%m%d_%H%M%S)

OUTPUT_DIR="./captures"
mkdir -p "$OUTPUT_DIR"

# Validate IP address format (basic check)
if ! echo "$SERVER_IP" | grep -E '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$' > /dev/null; then
    echo "Error: Invalid IP address format: $SERVER_IP"
    exit 1
fi

echo "Output file: $OUTPUT_DIR/$DATE.pcap"
echo "Ctrl+C to stop capture."

# Function to cleanup on exit
cleanup() {
    echo "Stopping capture..."
    if [ ! -z "$TCPDUMP_PID" ]; then
        kill $TCPDUMP_PID 2>/dev/null
    fi
    exit 0
}

# Set up signal handling
trap cleanup INT TERM

# Start tcpdump capture
tcpdump host $SERVER_IP -s 96 -C 1000 -w "$OUTPUT_DIR/$DATE.pcap" &
TCPDUMP_PID=$!

# Wait for tcpdump to start
sleep 2

# Check if tcpdump is still running
if ! kill -0 $TCPDUMP_PID 2>/dev/null; then
    echo "Error: Failed to start tcpdump"
    exit 1
fi

echo "Capture started successfully. PID: $TCPDUMP_PID"

# Wait for tcpdump to finish or for user to interrupt
wait $TCPDUMP_PID

# Option 2: Capture based on multiple interfaces (commented out)
# FIXME: no tcpdump was started when specifying multiple interfaces

# Get all active rmnet_data interfaces (UP + LOWER_UP)
# interfaces=$(ip -o link show | grep 'rmnet_data' | grep 'UP,LOWER_UP' | awk -F': ' '{print $2}' | cut -d'@' -f1)

# for iface in $interfaces; do
#     echo "Starting capture on $iface..."
#     tcpdump -i "$iface" -s 96 -C 1000 -w "$OUTPUT_DIR/$iface.pcap" &
# done

# echo "Capturing on: $interfaces"

# Trap Ctrl+C to kill all tcpdump
# trap 'echo "Stopping captures..."; killall tcpdump; exit' INT
# while true; do sleep 1; done
