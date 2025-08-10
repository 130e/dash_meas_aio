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
    
    # Parse connection info (first part before timer)
    # Format: recv_q send_q local_addr:port remote_addr:port
    connection_match = re.match(r'(\d+)\s+(\d+)\s+([^:]+):(\d+)\s+([^:]+):(\d+)', line)
    if connection_match:
        result.update({
            'recv_q': int(connection_match.group(1)),
            'send_q': int(connection_match.group(2)),
            'local_addr': connection_match.group(3),
            'local_port': int(connection_match.group(4)),
            'remote_addr': connection_match.group(5),
            'remote_port': int(connection_match.group(6))
        })
    
    # Parse timer information
    timer_match = re.search(r'timer:\(([^)]+)\)', line)
    if timer_match:
        timer_parts = timer_match.group(1).split(',')
        result['timer'] = {
            'state': timer_parts[0] if len(timer_parts) > 0 else None,
            'timeout_ms': int(timer_parts[1].replace('ms', '')) if len(timer_parts) > 1 and 'ms' in timer_parts[1] else None,
            'retrans': int(timer_parts[2]) if len(timer_parts) > 2 else None
        }
    
    # Parse TCP flags
    flags_match = re.search(r'(ts|sack|bbr|wscale:\d+,\d+)', line)
    if flags_match:
        flags = flags_match.group(1).split()
        result['tcp_flags'] = flags
    
    # Parse window scaling
    wscale_match = re.search(r'wscale:(\d+),(\d+)', line)
    if wscale_match:
        result['wscale'] = {
            'send': int(wscale_match.group(1)),
            'recv': int(wscale_match.group(2))
        }
    
    # Parse RTO and RTT
    rto_match = re.search(r'rto:(\d+)', line)
    if rto_match:
        result['rto_ms'] = int(rto_match.group(1))
    
    rtt_match = re.search(r'rtt:([\d.]+)/([\d.]+)', line)
    if rtt_match:
        result['rtt'] = {
            'current_ms': float(rtt_match.group(1)),
            'min_ms': float(rtt_match.group(2))
        }
    
    # Parse ATO
    ato_match = re.search(r'ato:(\d+)', line)
    if ato_match:
        result['ato_ms'] = int(ato_match.group(1))
    
    # Parse MSS and PMTU
    mss_match = re.search(r'mss:(\d+)', line)
    if mss_match:
        result['mss'] = int(mss_match.group(1))
    
    pmtu_match = re.search(r'pmtu:(\d+)', line)
    if pmtu_match:
        result['pmtu'] = int(pmtu_match.group(1))
    
    # Parse receive MSS
    rcvmss_match = re.search(r'rcvmss:(\d+)', line)
    if rcvmss_match:
        result['rcvmss'] = int(rcvmss_match.group(1))
    
    # Parse advertised MSS
    advmss_match = re.search(r'advmss:(\d+)', line)
    if advmss_match:
        result['advmss'] = int(advmss_match.group(1))
    
    # Parse congestion window
    cwnd_match = re.search(r'cwnd:(\d+)', line)
    if cwnd_match:
        result['cwnd'] = int(cwnd_match.group(1))
    
    # Parse bytes sent/received
    bytes_sent_match = re.search(r'bytes_sent:(\d+)', line)
    if bytes_sent_match:
        result['bytes_sent'] = int(bytes_sent_match.group(1))
    
    bytes_received_match = re.search(r'bytes_received:(\d+)', line)
    if bytes_received_match:
        result['bytes_received'] = int(bytes_received_match.group(1))
    
    # Parse segments sent/received
    segs_out_match = re.search(r'segs_out:(\d+)', line)
    if segs_out_match:
        result['segs_out'] = int(segs_out_match.group(1))
    
    segs_in_match = re.search(r'segs_in:(\d+)', line)
    if segs_in_match:
        result['segs_in'] = int(segs_in_match.group(1))
    
    # Parse data segments
    data_segs_out_match = re.search(r'data_segs_out:(\d+)', line)
    if data_segs_out_match:
        result['data_segs_out'] = int(data_segs_out_match.group(1))
    
    data_segs_in_match = re.search(r'data_segs_in:(\d+)', line)
    if data_segs_in_match:
        result['data_segs_in'] = int(data_segs_in_match.group(1))
    
    # Parse BBR information
    bbr_match = re.search(r'bbr:\(bw:([^,]+),mrtt:([\d.]+)\)', line)
    if bbr_match:
        result['bbr'] = {
            'bandwidth': bbr_match.group(1),
            'min_rtt_ms': float(bbr_match.group(2))
        }
    
    # Parse send buffer
    send_match = re.search(r'send\s+(\d+)bps', line)
    if send_match:
        result['send_rate_bps'] = int(send_match.group(1))
    
    # Parse last send/receive/ack times
    lastsnd_match = re.search(r'lastsnd:(\d+)', line)
    if lastsnd_match:
        result['lastsnd'] = int(lastsnd_match.group(1))
    
    lastrcv_match = re.search(r'lastrcv:(\d+)', line)
    if lastrcv_match:
        result['lastrcv'] = int(lastrcv_match.group(1))
    
    lastack_match = re.search(r'lastack:(\d+)', line)
    if lastack_match:
        result['lastack'] = int(lastack_match.group(1))
    
    # Parse pacing rate
    pacing_match = re.search(r'pacing_rate\s+(\d+)bps', line)
    if pacing_match:
        result['pacing_rate_bps'] = int(pacing_match.group(1))
    
    # Parse delivered
    delivered_match = re.search(r'delivered:(\d+)', line)
    if delivered_match:
        result['delivered'] = int(delivered_match.group(1))
    
    # Parse app_limited
    app_limited_match = re.search(r'app_limited', line)
    if app_limited_match:
        result['app_limited'] = True
    
    # Parse busy time
    busy_match = re.search(r'busy:(\d+)ms', line)
    if busy_match:
        result['busy_ms'] = int(busy_match.group(1))
    
    # Parse unacked
    unacked_match = re.search(r'unacked:(\d+)', line)
    if unacked_match:
        result['unacked'] = int(unacked_match.group(1))
    
    # Parse receive space
    rcv_space_match = re.search(r'rcv_space:(\d+)', line)
    if rcv_space_match:
        result['rcv_space'] = int(rcv_space_match.group(1))
    
    # Parse receive slow start threshold
    rcv_ssthresh_match = re.search(r'rcv_ssthresh:(\d+)', line)
    if rcv_ssthresh_match:
        result['rcv_ssthresh'] = int(rcv_ssthresh_match.group(1))
    
    # Parse minimum RTT
    minrtt_match = re.search(r'minrtt:([\d.]+)', line)
    if minrtt_match:
        result['minrtt_ms'] = float(minrtt_match.group(1))
    
    # Parse send window
    snd_wnd_match = re.search(r'snd_wnd:(\d+)', line)
    if snd_wnd_match:
        result['snd_wnd'] = int(snd_wnd_match.group(1))
    
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
    
    with open(input_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Check if this is a timestamp line
            if line.startswith('time:'):
                current_timestamp = int(line.split(':', 1)[1])
                continue
            
            # Parse the ss output line
            if current_timestamp is not None:
                parsed_data = parse_ss_line(line)
                if parsed_data:
                    entry = {
                        'timestamp_ns': current_timestamp,
                        'timestamp_iso': datetime.fromtimestamp(current_timestamp / 1e9).isoformat(),
                        'socket_data': parsed_data
                    }
                    entries.append(entry)
    
    # Write to JSON file
    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'source_file': input_file,
                'total_entries': len(entries),
                'parsed_at': datetime.now().isoformat()
            },
            'entries': entries
        }, f, indent=2)
    
    print(f"Parsed {len(entries)} entries from {input_file} to {output_file}")


def main():
    """Main function to handle command line arguments and execute parsing."""
    if len(sys.argv) != 3:
        print("Usage: python parse_ss.py <input.log> <output.json>")
        print("Example: python parse_ss.py ss_20241201_143022.log parsed_ss.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
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
