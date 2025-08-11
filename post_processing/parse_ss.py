#!/usr/bin/env python3
"""
Parse ss command output to JSON format.

The ss command output contains complex TCP socket statistics that need to be
parsed into a structured format for analysis. This script handles the parsing
of all ss output fields including connection info, timing, congestion control,
and buffer statistics.

Usage:
    python parse_ss.py input.log output.json
"""

import json
import re
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
import code

# Here are the ommited headers from ss
ss_headers = [
    "Recv-Q",
    "Send-Q",
    "Local Address:Port",
    "Peer Address:Port",
    # "Process", # we don't enable this
    "tcp_socket_info_fields",
]


def parse_address_port(address_port: str) -> Dict[str, str]:
    """
    Parse an address:port string into separate address and port components.
    
    Args:
        address_port: String like "[::ffff:140.82.23.101]:5202" or "127.0.0.1:8080"
        
    Returns:
        Dictionary with "address" and "port" keys
    """
    # Handle IPv6 addresses in brackets: [::ffff:140.82.23.101]:5202
    if address_port.startswith("[") and "]" in address_port:
        # Find the closing bracket
        bracket_end = address_port.find("]")
        address = address_port[1:bracket_end]  # Remove brackets
        port = address_port[bracket_end + 2:]  # Skip "]:"
    else:
        # Handle IPv4 addresses: 127.0.0.1:8080
        if ":" in address_port:
            address, port = address_port.rsplit(":", 1)
        else:
            # No port specified
            address = address_port
            port = ""
    
    return {"address": address, "port": port}


def parse_socket_info_item(item: str) -> Dict[str, Any]:
    """
    Parse a single socket info item into a structured format.

    Args:
        item: Single socket info item string

    Returns:
        Dictionary containing parsed item data
    """
    result = {}

    # Handle timer items like "timer:(on,243ms,0)"
    if item.startswith("timer:"):
        timer_match = re.match(r"timer:\(([^,]+),([^,]+),(\d+)\)", item)
        if timer_match:
            result["timer"] = [
                timer_match.group(1),
                parse_value_with_unit(timer_match.group(2)),
                int(timer_match.group(3)),
            ]
        return result

    # Handle BBR congestion control info like "bbr:(bw:0bps,mrtt:44.801)" or "bbr:(bw:292752bps,mrtt:39.496,pacing_gain:2.88672,cwnd_gain:2.88672)"
    if item.startswith("bbr:"):
        # Extract the content inside parentheses
        bbr_content = item[4:]  # Remove "bbr:"
        if bbr_content.startswith("(") and bbr_content.endswith(")"):
            bbr_content = bbr_content[1:-1]  # Remove parentheses

            # Parse the key-value pairs
            bbr_data = {}
            pairs = bbr_content.split(",")
            for pair in pairs:
                if ":" in pair:
                    key, value = pair.split(":", 1)
                    bbr_data[key] = parse_value_with_unit(value)

            result["bbr"] = bbr_data
        return result

    # Handle items with colon that split into key-value pairs
    if ":" in item and not item.endswith(":"):
        key, value = item.split(":", 1)
        result[key] = parse_value_with_unit(value)
    else:
        # Handle boolean flags and simple values
        if item in ["ts", "sack", "bbr", "send", "app_limited", "pacing_rate"]:
            result[item] = True
        else:
            # Other values
            result[item] = True

    return result


def parse_value_with_unit(value: str) -> Any:
    """
    Parse a value that may have units or be a list of values.

    Args:
        value: String value to parse

    Returns:
        Parsed value (int, float, list, or dict with unit info)
    """
    # Handle values with units (bps, Mbps, ms, etc.)
    unit_pattern = r"^([\d.]+)([a-zA-Z]+)$"
    unit_match = re.match(unit_pattern, value)
    if unit_match:
        numeric_value = unit_match.group(1)
        unit = unit_match.group(2)

        # Try to convert to int first, then float
        try:
            if "." in numeric_value:
                parsed_value = float(numeric_value)
            else:
                parsed_value = int(numeric_value)
        except ValueError:
            return value  # Return as string if conversion fails

        return {"value": parsed_value, "unit": unit}

    # Handle slash-separated values (like RTT: current/average)
    additional_symbols = ["/", ","]
    for symbol in additional_symbols:
        if symbol in value:
            parts = value.split(symbol)
            try:
                return [float(part) if "." in part else int(part) for part in parts]
            except ValueError:
                return parts  # Return as strings if conversion fails

    # Handle simple numeric values
    try:
        if "." in value:
            return float(value)
        else:
            return int(value)
    except ValueError:
        return value  # Return as string if not numeric


def parse_ss_line(line: str) -> Dict[str, Any]:
    """
    Parse a single line of ss command output into a structured dictionary.

    Args:
        line: Raw ss command output line

    Returns:
        Dictionary containing parsed socket statistics
    """
    if not line.strip():
        return {}

    # Initialize result dictionary
    result = {}

    items = line.split()
    result["Recv-Q"] = int(items[0])
    result["Send-Q"] = int(items[1])
    
    # Parse address and port fields
    local_address_port = items[2]
    peer_address_port = items[3]
    
    result["Local_Address:Port"] = parse_address_port(local_address_port)
    result["Peer_Address:Port"] = parse_address_port(peer_address_port)

    socket_info = items[4:]
    
    # Parse each socket info item, handling special cases
    i = 0
    while i < len(socket_info):
        item = socket_info[i]
        parsed_item = parse_socket_info_item(item)
        
        # Handle special cases where a key is followed by a bandwidth value
        if (
            (item == "send" or item == "pacing_rate")
            and i + 1 < len(socket_info)
            and socket_info[i + 1].endswith("bps")
        ):
            parsed_item = parse_socket_info_item(item + ":" + socket_info[i + 1])
            i += 1  # Skip the next item since we've processed it

        result.update(parsed_item)

        i += 1

    return result


def parse_ss_log(input_file: str, output_file: str) -> None:
    """
    Parse ss command log file and convert to JSON format.

    Args:
        input_file: Path to input ss log file
        output_file: Path to output JSON file
    """
    entries = []
    current_timestamp = None
    
    # Track unique addresses and ports for metadata
    unique_peer_addresses = set()
    unique_peer_ports = set()
    unique_local_addresses = set()
    unique_local_ports = set()

    with open(input_file, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Check if this is a timestamp line
            if line.startswith("time:"):
                current_timestamp = int(line.split(":", 1)[1])
                continue

            # Parse the ss output line
            if current_timestamp is not None:
                try:
                    parsed_data = parse_ss_line(line)
                    if parsed_data:
                        # Collect unique addresses and ports
                        if "Local_Address:Port" in parsed_data:
                            local_addr_data = parsed_data["Local_Address:Port"]
                            unique_local_addresses.add(local_addr_data["address"])
                            if local_addr_data["port"]:
                                unique_local_ports.add(local_addr_data["port"])
                        
                        if "Peer_Address:Port" in parsed_data:
                            peer_addr_data = parsed_data["Peer_Address:Port"]
                            unique_peer_addresses.add(peer_addr_data["address"])
                            if peer_addr_data["port"]:
                                unique_peer_ports.add(peer_addr_data["port"])
                        
                        entry = {
                            "timestamp_ns": current_timestamp,
                            "timestamp_iso": datetime.fromtimestamp(
                                current_timestamp / 1e9
                            ).isoformat(),
                            "socket_data": parsed_data,
                        }
                        entries.append(entry)
                except ValueError as e:
                    print(f"Error parsing line {line_num}: {e}")
                    print(f"Line content: {line}")
                    raise  # Re-raise the error to stop processing

    # Write to JSON file
    with open(output_file, "w") as f:
        json.dump(
            {
                "metadata": {
                    "source_file": input_file,
                    "total_entries": len(entries),
                    "start_time": entries[0]["timestamp_iso"],
                    "end_time": entries[-1]["timestamp_iso"],
                    "unique_local_addresses": len(unique_local_addresses),
                    "unique_local_ports": len(unique_local_ports),
                    "unique_peer_addresses": len(unique_peer_addresses),
                    "unique_peer_ports": len(unique_peer_ports),
                    "local_addresses": sorted(list(unique_local_addresses)),
                    "peer_addresses": sorted(list(unique_peer_addresses)),
                    "local_ports": sorted(list(unique_local_ports)),
                    "peer_ports": sorted(list(unique_peer_ports)),
                },
                "entries": entries,
            },
            f,
            indent=2,
        )

    print(f"Parsed {len(entries)} entries from {input_file} to {output_file}")
    print(f"Found {len(unique_peer_addresses)} unique peer addresses and {len(unique_peer_ports)} unique peer ports")


def main():
    """Main function to handle command line arguments and execute parsing."""
    if len(sys.argv) < 2:
        print("Usage: python parse_ss.py <input.log> <output.json>")
        print("Example: python parse_ss.py ss_20241201_143022.log parsed_ss.json")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "parsed_ss.json"

    try:
        parse_ss_log(input_file, output_file)
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
