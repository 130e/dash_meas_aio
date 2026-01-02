import argparse
import csv
import os
import subprocess
import sys


def run_tshark(pcap_file):
    """
    Run tshark to extract TCP fields from pcap file.
    Returns list of packet data dictionaries.
    """
    fields = [
        "frame.time_epoch",
        "ip.src",
        "ip.dst",
        "tcp.srcport",
        "tcp.dstport",
        "tcp.len",
        "tcp.seq",
        "tcp.ack",
        "tcp.flags",
        "tcp.analysis.ack_rtt",
        "tcp.analysis.retransmission",
        "tcp.analysis.duplicate_ack",
        "tcp.analysis.lost_segment",
    ]

    cmd = [
        "tshark",
        "-r",
        pcap_file,
        "-T",
        "fields",
        "-E",
        "separator=|",
    ]

    for field in fields:
        cmd.extend(["-e", field])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running tshark: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: tshark not found. Please install Wireshark.", file=sys.stderr)
        sys.exit(1)

    packets = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) < len(fields):
            parts.extend([""] * (len(fields) - len(parts)))

        packet = {}
        for i, field in enumerate(fields):
            packet[field] = parts[i] if i < len(parts) else ""
        packets.append(packet)

    return packets


def analyze_packets(packets, server_ip, server_port):
    if not packets:
        return None, [], [], []

    start_time = float(packets[0]["frame.time_epoch"])

    ack_events = []
    retrans_events = []
    rtt_events = []

    flow_last_ack = {}

    for pkt in packets:
        try:
            timestamp = float(pkt["frame.time_epoch"])
        except (ValueError, KeyError):
            continue

        relative_time = timestamp - start_time

        src_ip = pkt["ip.src"]
        dst_ip = pkt["ip.dst"]
        src_port = pkt["tcp.srcport"]
        dst_port = pkt["tcp.dstport"]

        is_from_server = src_ip == server_ip and src_port == str(server_port)
        is_from_client = dst_ip == server_ip and dst_port == str(server_port)

        if is_from_client:
            try:
                ack_num = int(pkt["tcp.ack"]) if pkt["tcp.ack"] else 0
                if ack_num > 0:
                    flow_key = (src_ip, pkt["tcp.srcport"], pkt["tcp.dstport"])

                    if flow_key in flow_last_ack:
                        last_ack = flow_last_ack[flow_key]
                        if ack_num > last_ack:
                            bytes_acked = ack_num - last_ack
                            if bytes_acked < 10_000_000:
                                ack_events.append((relative_time, bytes_acked))
                        elif ack_num < last_ack and last_ack > 0xF0000000:
                            bytes_acked = (0xFFFFFFFF - last_ack) + ack_num
                            if bytes_acked < 10_000_000:
                                ack_events.append((relative_time, bytes_acked))

                    flow_last_ack[flow_key] = ack_num
            except ValueError:
                pass

            if pkt["tcp.analysis.ack_rtt"]:
                try:
                    rtt = float(pkt["tcp.analysis.ack_rtt"])
                    rtt_events.append((relative_time, rtt))
                except ValueError:
                    pass

        elif is_from_server:
            if pkt["tcp.analysis.retransmission"]:
                retrans_events.append(relative_time)

    return start_time, ack_events, retrans_events, rtt_events


def compute_statistics(ack_events, retrans_events, rtt_events, window_ms=1000):
    if not ack_events and not retrans_events and not rtt_events:
        return []

    # Determine duration
    max_time = 0
    if ack_events:
        max_time = max(max_time, max(t for t, _ in ack_events))
    if retrans_events:
        max_time = max(max_time, max(retrans_events))
    if rtt_events:
        max_time = max(max_time, max(t for t, _ in rtt_events))

    max_second = int(max_time)
    half_window = window_ms / 1000 / 2

    results = []

    for second in range(max_second + 1):
        window_start = second - half_window
        window_end = second + half_window

        bytes_in_window = sum(
            b for t, b in ack_events if window_start <= t < window_end
        )
        throughput_bytes_per_sec = bytes_in_window * (1000 / window_ms)
        throughput_mbps = (throughput_bytes_per_sec * 8) / 1_000_000

        packet_loss = sum(1 for t in retrans_events if second <= t < second + 1)

        rtt_in_second = [rtt for t, rtt in rtt_events if second <= t < second + 1]
        avg_rtt_ms = (
            (sum(rtt_in_second) / len(rtt_in_second) * 1000) if rtt_in_second else 0
        )

        results.append(
            {
                "time_second": second,
                "throughput_mbps": round(throughput_mbps, 4),
                "packet_loss": packet_loss,
                "mean_rtt": round(avg_rtt_ms, 4),
            }
        )

    return results


def write_csv(results, output_file):
    """Write results to CSV file."""
    if not results:
        print("No data to write.", file=sys.stderr)
        return

    fieldnames = [
        "time_second",
        "throughput_mbps",
        "packet_loss",
        "mean_rtt",
    ]

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Output written to: {output_file}")


def print_summary(results):
    """Print a summary of the analysis."""
    if not results:
        print("No data found in pcap file.")
        return

    total_seconds = len(results)
    total_loss = sum(r["packet_loss"] for r in results)
    avg_throughput = (
        sum(r["throughput_mbps"] for r in results) / total_seconds
        if total_seconds > 0
        else 0
    )

    rtt_values = [r["mean_rtt"] for r in results if r["mean_rtt"] > 0]
    avg_rtt = sum(rtt_values) / len(rtt_values) if rtt_values else 0

    print(f"\n{'=' * 60}")
    print(f"Duration:           {total_seconds} seconds")
    print(f"Avg throughput:     {avg_throughput:.2f} Mbps")
    print(f"Total packet loss:  {total_loss} retransmissions")
    print(f"Avg RTT:            {avg_rtt:.2f} ms")
    print(f"{'=' * 60}\n")


def process_file(pcap_file, server_ip, server_port):
    packets = run_tshark(pcap_file)

    start_time, ack_events, retrans_events, rtt_events = analyze_packets(
        packets, server_ip, server_port
    )

    results = compute_statistics(ack_events, retrans_events, rtt_events)

    return results, start_time


def main():
    parser = argparse.ArgumentParser(
        description="Analyze TCP pcap files and output client-side metrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Output columns:
  time_second     - Time interval (seconds from start)
  throughput_bytes - Bytes acked by client per second
  throughput_mbps  - Throughput in Mbps
  packet_loss     - Server retransmissions (packets client missed)
  avg_rtt_ms      - Average RTT in milliseconds
        """,
    )
    parser.add_argument("pcap_file", help="Input pcap file")
    parser.add_argument(
        "--server-ip",
        required=True,
        help="Server IP address (to determine packet direction)",
    )
    parser.add_argument(
        "--server-port",
        type=int,
        required=True,
        help="Server port (to filter specific flow)",
    )
    parser.add_argument(
        "output_file", nargs="?", help="Output CSV file (default: <input>_analysis.csv)"
    )

    args = parser.parse_args()

    if not os.path.exists(args.pcap_file):
        print(f"Error: File not found: {args.pcap_file}", file=sys.stderr)
        sys.exit(1)

    if args.output_file:
        output_file = args.output_file
    else:
        base = os.path.splitext(args.pcap_file)[0]
        output_file = f"{base}.csv"

    print(f"Analyzing: {args.pcap_file}")
    print(f"Server: {args.server_ip}:{args.server_port}")
    print("Extracting packets with tshark...")

    packets = run_tshark(args.pcap_file)
    print(f"Found {len(packets)} packets")

    print("Computing per-second client-side metrics...")
    start_time, ack_events, retrans_events, rtt_events = analyze_packets(
        packets, args.server_ip, args.server_port
    )

    results = compute_statistics(ack_events, retrans_events, rtt_events)

    print_summary(results)

    write_csv(results, output_file)


if __name__ == "__main__":
    main()
