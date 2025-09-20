# Aggregate results form multiple logs
# Assume logs are from the same run

import argparse
import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import csv
from typing import List, Tuple, Optional


def parse_tcp_log(tcp_log: str) -> List:
    """
    Parse TCP log from parsed ss JSON and extract delivery_rate and cwnd data.

    Args:
        tcp_log: Path to the parsed ss JSON file

    Returns:
        List of tuples: [timestamp_ms, delivery_rate_bps, cwnd]
        delivery_rate_bps is None if not available, cwnd is None if not available
    """
    results = []

    with open(tcp_log, "r") as f:
        data = json.load(f)

    # Extract entries from the JSON
    entries = data.get("entries", [])

    for entry in entries:
        timestamp_ns = entry.get("timestamp_ns", 0)
        timestamp_ms = timestamp_ns // 1_000_000  # Convert nanoseconds to milliseconds

        socket_data = entry.get("socket_data", {})

        # Extract delivery_rate (in bps)
        delivery_rate = None
        if "delivery_rate" in socket_data:
            delivery_rate_data = socket_data["delivery_rate"]
            if isinstance(delivery_rate_data, dict) and "value" in delivery_rate_data:
                delivery_rate = delivery_rate_data["value"]

        # Extract cwnd (congestion window)
        cwnd = None
        if "cwnd" in socket_data:
            cwnd = socket_data["cwnd"]

        # Only add entry if we have at least one of the values
        if delivery_rate is not None or cwnd is not None:
            results.append((timestamp_ms, delivery_rate, cwnd))

    # Sort by timestamp
    results.sort(key=lambda x: x[0])

    return results


def parse_abr_log(abr_log: str) -> List[Tuple[float, int]]:
    """
    Parse ABR log CSV and extract bitrate data.

    Args:
        abr_log: Path to the ABR server CSV file

    Returns:
        List of tuples: [timestamp_sec, bit_rate_kbps]
    """
    results = []

    with open(abr_log, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wall_time = float(row["wall_time"])
            bit_rate = int(row["bit_rate"])
            results.append((wall_time, bit_rate))

    return results


def get_all_peer_ports(ss_parsed_file: str) -> List[str]:
    """
    Get all unique peer ports from the ss_parsed.json file.

    Args:
        ss_parsed_file: Path to the ss_parsed.json file

    Returns:
        List of unique peer port strings
    """
    with open(ss_parsed_file, "r") as f:
        data = json.load(f)

    # Get peer ports from metadata if available
    metadata = data.get("metadata", {})
    peer_ports = metadata.get("peer_ports", [])

    if not peer_ports:
        # Fallback: extract from entries
        entries = data.get("entries", [])
        peer_ports_set = set()
        for entry in entries:
            socket_data = entry.get("socket_data", {})
            peer_address_port = socket_data.get("Peer_Address:Port", {})
            peer_port = peer_address_port.get("port")
            if peer_port:
                peer_ports_set.add(peer_port)
        peer_ports = sorted(list(peer_ports_set))

    return peer_ports


def filter_by_peer_port_and_extract_delivery_rate(
    ss_parsed_file: str, target_peer_port: str
) -> List[Tuple[int, float]]:
    """
    Filter entries by peer port and extract delivery_rate data.

    Args:
        ss_parsed_file: Path to the ss_parsed.json file
        target_peer_port: The peer port to filter by (as string, e.g., "9671")

    Returns:
        List of tuples: [timestamp_ms, delivery_rate_bps]
        Only includes entries that have delivery_rate data for the specified peer port
    """
    results = []

    with open(ss_parsed_file, "r") as f:
        data = json.load(f)

    # Extract entries from the JSON
    entries = data.get("entries", [])

    for entry in entries:
        timestamp_ns = entry.get("timestamp_ns", 0)
        timestamp_ms = timestamp_ns // 1_000_000  # Convert nanoseconds to milliseconds

        socket_data = entry.get("socket_data", {})

        # Check if this entry is for the target peer port
        peer_address_port = socket_data.get("Peer_Address:Port", {})
        peer_port = peer_address_port.get("port")

        if peer_port != target_peer_port:
            continue

        # Extract delivery_rate (in bps)
        delivery_rate = None
        if "delivery_rate" in socket_data:
            delivery_rate_data = socket_data["delivery_rate"]
            if isinstance(delivery_rate_data, dict) and "value" in delivery_rate_data:
                delivery_rate = delivery_rate_data["value"]

        # Only add entry if we have delivery_rate data
        if delivery_rate is not None:
            results.append((timestamp_ms, delivery_rate))

    # Sort by timestamp
    results.sort(key=lambda x: x[0])

    return results


def filter_by_peer_port_and_extract_bbr_bw(
    ss_parsed_file: str, target_peer_port: str
) -> List[Tuple[int, float]]:
    """
    Filter entries by peer port and extract BBR bandwidth data.

    Args:
        ss_parsed_file: Path to the ss_parsed.json file
        target_peer_port: The peer port to filter by (as string, e.g., "9671")

    Returns:
        List of tuples: [timestamp_ms, bbr_bw_bps]
        Only includes entries that have BBR bandwidth data for the specified peer port
    """
    results = []

    with open(ss_parsed_file, "r") as f:
        data = json.load(f)

    # Extract entries from the JSON
    entries = data.get("entries", [])

    for entry in entries:
        timestamp_ns = entry.get("timestamp_ns", 0)
        timestamp_ms = timestamp_ns // 1_000_000  # Convert nanoseconds to milliseconds

        socket_data = entry.get("socket_data", {})

        # Check if this entry is for the target peer port
        peer_address_port = socket_data.get("Peer_Address:Port", {})
        peer_port = peer_address_port.get("port")

        if peer_port != target_peer_port:
            continue

        # Extract BBR bandwidth (in bps)
        bbr_bw = None
        if "bbr" in socket_data:
            bbr_data = socket_data["bbr"]
            if isinstance(bbr_data, dict) and "bw" in bbr_data:
                bw_data = bbr_data["bw"]
                if isinstance(bw_data, dict) and "value" in bw_data:
                    bbr_bw = bw_data["value"]

        # Only add entry if we have BBR bandwidth data
        if bbr_bw is not None:
            results.append((timestamp_ms, bbr_bw))

    # Sort by timestamp
    results.sort(key=lambda x: x[0])

    return results


def filter_by_peer_port_and_extract_bbr_mrtt(
    ss_parsed_file: str, target_peer_port: str
) -> List[Tuple[int, float]]:
    """
    Filter entries by peer port and extract BBR mrtt (minimum RTT) data.

    Args:
        ss_parsed_file: Path to the ss_parsed.json file
        target_peer_port: The peer port to filter by (as string, e.g., "9671")

    Returns:
        List of tuples: [timestamp_ms, bbr_mrtt_ms]
        Only includes entries that have BBR mrtt data for the specified peer port
    """
    results = []

    with open(ss_parsed_file, "r") as f:
        data = json.load(f)

    entries = data.get("entries", [])

    for entry in entries:
        timestamp_ns = entry.get("timestamp_ns", 0)
        timestamp_ms = timestamp_ns // 1_000_000

        socket_data = entry.get("socket_data", {})

        peer_address_port = socket_data.get("Peer_Address:Port", {})
        peer_port = peer_address_port.get("port")

        if peer_port != target_peer_port:
            continue

        bbr_mrtt = None
        if "bbr" in socket_data and isinstance(socket_data["bbr"], dict):
            bbr_obj = socket_data["bbr"]
            # mrtt is directly a float in milliseconds (seen in sample)
            if "mrtt" in bbr_obj:
                bbr_mrtt = bbr_obj.get("mrtt")

        if bbr_mrtt is not None:
            results.append((timestamp_ms, float(bbr_mrtt)))

    results.sort(key=lambda x: x[0])
    return results


def plot_all_ports_delivery_rate_and_abr_bitrate(
    ss_parsed_file: str, abr_data: List[Tuple[float, int]], save_plot: bool = True
):
    """
    Plot delivery_rate for all peer ports, ABR bitrate, and BBR bandwidth against time with three subplots.

    Args:
        ss_parsed_file: Path to the ss_parsed.json file
        abr_data: List of tuples (timestamp_sec, bit_rate_kbps)
        save_plot: Whether to save the plot to a file
    """
    # Get all peer ports
    peer_ports = get_all_peer_ports(ss_parsed_file)
    print(f"Found peer ports: {peer_ports}")

    if not peer_ports:
        print("No peer ports found")
        return

    # Calculate total duration from the ss log
    with open(ss_parsed_file, "r") as f:
        data = json.load(f)

    # Get the first and last timestamps from all entries to calculate total duration
    all_entries = data.get("entries", [])
    if all_entries:
        first_timestamp_ns = all_entries[0].get("timestamp_ns", 0)
        last_timestamp_ns = all_entries[-1].get("timestamp_ns", 0)
        total_duration_ms = (last_timestamp_ns - first_timestamp_ns) // 1_000_000
        start_time_ms = first_timestamp_ns // 1_000_000
    else:
        total_duration_ms = 0
        start_time_ms = 0

    # Create figure with three subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

    # Color palette for different ports
    colors = [
        "blue",
        "red",
        "green",
        "orange",
        "purple",
        "brown",
        "pink",
        "gray",
        "olive",
        "cyan",
    ]

    # Plot delivery rate for each port (top subplot)
    delivery_rate_data_by_port = {}
    for i, peer_port in enumerate(peer_ports):
        delivery_rate_data = filter_by_peer_port_and_extract_delivery_rate(
            ss_parsed_file, peer_port
        )
        delivery_rate_data_by_port[peer_port] = delivery_rate_data

        if delivery_rate_data:
            timestamps_ms = [entry[0] for entry in delivery_rate_data]
            delivery_rates = [entry[1] for entry in delivery_rate_data]

            # Convert timestamps to relative time (0 to duration)
            relative_timestamps = [
                (ts - start_time_ms) / 1000.0 for ts in timestamps_ms
            ]  # Convert to seconds

            # Convert delivery rates from bps to Mbps
            delivery_rates_mbps = [rate / 1_000_000 for rate in delivery_rates]

            color = colors[i % len(colors)]
            ax1.plot(
                relative_timestamps,
                delivery_rates_mbps,
                color=color,
                linewidth=1.5,
                alpha=0.8,
                label=f"Port {peer_port}",
            )

            # Add statistics for this port (in Mbps)
            avg_rate_mbps = sum(delivery_rates_mbps) / len(delivery_rates_mbps)
            ax1.axhline(
                y=avg_rate_mbps, color=color, linestyle="--", alpha=0.5, linewidth=0.8
            )

    if delivery_rate_data_by_port:
        ax1.set_ylabel("Delivery Rate (Mbps)", fontsize=12)
        ax1.set_title("TCP delivery rate (goodput)", fontsize=14, fontweight="bold")
        ax1.grid(True, alpha=0.3)
        ax1.legend()

    # Plot ABR bitrate (middle subplot)
    if abr_data:
        abr_timestamps = [entry[0] for entry in abr_data]
        abr_bitrates = [entry[1] for entry in abr_data]

        # Convert ABR timestamps to relative time
        if delivery_rate_data_by_port and any(delivery_rate_data_by_port.values()):
            # Align ABR timestamps with ss log timestamps
            relative_abr_timestamps = [
                (ts * 1000 - start_time_ms) / 1000.0 for ts in abr_timestamps
            ]
        else:
            # If no delivery rate data, just use relative time from first ABR entry
            relative_abr_timestamps = [
                (ts - abr_timestamps[0]) for ts in abr_timestamps
            ]

        ax2.plot(
            relative_abr_timestamps,
            abr_bitrates,
            "g-",
            linewidth=2,
            alpha=0.8,
            marker="o",
            markersize=4,
            label="ABR Bitrate",
        )
        ax2.set_ylabel("ABR Bitrate (kbps)", fontsize=12)
        ax2.set_title("DASH bitrate per chunk", fontsize=14, fontweight="bold")
        ax2.grid(True, alpha=0.3)

        # Add statistics for ABR bitrate
        if abr_bitrates:
            avg_bitrate = sum(abr_bitrates) / len(abr_bitrates)
            max_bitrate = max(abr_bitrates)
            min_bitrate = min(abr_bitrates)

            ax2.axhline(
                y=avg_bitrate,
                color="orange",
                linestyle="--",
                alpha=0.7,
                label=f"ABR Average: {avg_bitrate:.0f} kbps",
            )
            ax2.legend()

            # Add text box with statistics
            abr_stats_text = f"Max: {max_bitrate} kbps\nMin: {min_bitrate} kbps\nAvg: {avg_bitrate:.0f} kbps\nSamples: {len(abr_bitrates)}"
            ax2.text(
                0.02,
                0.98,
                abr_stats_text,
                transform=ax2.transAxes,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.8),
            )

    # Plot BBR bandwidth for each port (bottom subplot)
    bbr_bw_data_by_port = {}
    bbr_mrtt_data_by_port = {}
    ax3b = ax3.twinx()
    for i, peer_port in enumerate(peer_ports):
        bbr_bw_data = filter_by_peer_port_and_extract_bbr_bw(ss_parsed_file, peer_port)
        bbr_mrtt_data = filter_by_peer_port_and_extract_bbr_mrtt(
            ss_parsed_file, peer_port
        )
        bbr_bw_data_by_port[peer_port] = bbr_bw_data
        bbr_mrtt_data_by_port[peer_port] = bbr_mrtt_data

        # Bandwidth series (solid lines, left axis)
        if bbr_bw_data:
            timestamps_ms = [entry[0] for entry in bbr_bw_data]
            bbr_bw_rates = [entry[1] for entry in bbr_bw_data]
            relative_timestamps = [
                (ts - start_time_ms) / 1000.0 for ts in timestamps_ms
            ]
            bbr_bw_mbps = [rate / 1_000_000 for rate in bbr_bw_rates]
            color = colors[i % len(colors)]
            ax3.plot(
                relative_timestamps,
                bbr_bw_mbps,
                color=color,
                linewidth=1.5,
                alpha=0.9,
                label=f"Port {peer_port}",
            )
            # avg_bw_mbps = sum(bbr_bw_mbps) / len(bbr_bw_mbps)
            # ax3.axhline(y=avg_bw_mbps, color=color, linestyle="--", alpha=0.4, linewidth=0.8)

        # mrtt series (dotted lines, right axis)
        if bbr_mrtt_data:
            ts_ms_mrtt = [entry[0] for entry in bbr_mrtt_data]
            mrtt_ms = [entry[1] for entry in bbr_mrtt_data]
            rel_ts_mrtt = [(ts - start_time_ms) / 1000.0 for ts in ts_ms_mrtt]
            color = colors[i % len(colors)]
            ax3b.plot(
                rel_ts_mrtt,
                mrtt_ms,
                color=color,
                linestyle="dotted",
                linewidth=1.3,
                alpha=1,
            )

    if bbr_bw_data_by_port:
        ax3.set_ylabel("BBR Bandwidth (Mbps)", fontsize=12)
        ax3b.set_ylabel("BBR min RTT (ms)", fontsize=12)
        ax3.set_title(
            "BBR: Bandwidth (solid, left axis) and min RTT (dotted, right axis)",
            fontsize=14,
            fontweight="bold",
        )
        ax3.grid(True, alpha=0.3)
        ax3.legend()

    # Set x-axis limits and labels
    duration_sec = total_duration_ms / 1000.0
    ax3.set_xlim(0, duration_sec)
    ax3.set_xlabel("Time (seconds)", fontsize=12)

    # Add overall duration to the figure
    fig.suptitle(
        f"Duration: {duration_sec:.1f}s",
        fontsize=16,
        fontweight="bold",
    )

    plt.tight_layout()

    if save_plot:
        filename = f"delivery_rate_and_abr_all_ports.png"
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        print(f"Plot saved as {filename}")

    plt.show()

    # Print summary statistics for each port
    print("\nSummary by Peer Port:")
    for peer_port in peer_ports:
        delivery_data = delivery_rate_data_by_port.get(peer_port, [])
        bbr_data = bbr_bw_data_by_port.get(peer_port, [])

        if delivery_data:
            rates = [entry[1] for entry in delivery_data]
            avg_rate = sum(rates) / len(rates)
            max_rate = max(rates)
            min_rate = min(rates)
            print(
                f"  Port {peer_port} (Delivery): {len(delivery_data)} samples, Avg: {avg_rate:.0f} bps, Max: {max_rate:.0f} bps, Min: {min_rate:.0f} bps"
            )

        if bbr_data:
            bbr_rates = [entry[1] for entry in bbr_data]
            avg_bbr = sum(bbr_rates) / len(bbr_rates)
            max_bbr = max(bbr_rates)
            min_bbr = min(bbr_rates)
            print(
                f"  Port {peer_port} (BBR): {len(bbr_data)} samples, Avg: {avg_bbr:.0f} bps, Max: {max_bbr:.0f} bps, Min: {min_bbr:.0f} bps"
            )


def plot_delivery_rate_and_abr_bitrate(
    delivery_rate_data: List[Tuple[int, float]],
    abr_data: List[Tuple[float, int]],
    peer_port: str,
    ss_parsed_file: str,
    save_plot: bool = True,
):
    """
    Plot delivery_rate and ABR bitrate against time with two subplots.

    Args:
        delivery_rate_data: List of tuples (timestamp_ms, delivery_rate_bps)
        abr_data: List of tuples (timestamp_sec, bit_rate_kbps)
        peer_port: The peer port being plotted (for title)
        ss_parsed_file: Path to the ss_parsed.json file to get total duration
        save_plot: Whether to save the plot to a file
    """
    if not delivery_rate_data and not abr_data:
        print("No data to plot")
        return

    # Calculate total duration from the ss log
    with open(ss_parsed_file, "r") as f:
        data = json.load(f)

    # Get the first and last timestamps from all entries to calculate total duration
    all_entries = data.get("entries", [])
    if all_entries:
        first_timestamp_ns = all_entries[0].get("timestamp_ns", 0)
        last_timestamp_ns = all_entries[-1].get("timestamp_ns", 0)
        total_duration_ms = (last_timestamp_ns - first_timestamp_ns) // 1_000_000
        start_time_ms = first_timestamp_ns // 1_000_000
    else:
        total_duration_ms = 0
        start_time_ms = 0

    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    # Plot delivery rate (top subplot)
    if delivery_rate_data:
        timestamps_ms = [entry[0] for entry in delivery_rate_data]
        delivery_rates = [entry[1] for entry in delivery_rate_data]

        # Convert timestamps to relative time (0 to duration)
        relative_timestamps = [
            (ts - start_time_ms) / 1000.0 for ts in timestamps_ms
        ]  # Convert to seconds

        ax1.plot(relative_timestamps, delivery_rates, "b-", linewidth=1, alpha=0.8)
        ax1.set_ylabel("Delivery Rate (bps)", fontsize=12)
        ax1.set_title(
            f"Server TCP delivery rate - Port {peer_port}",
            fontsize=14,
            fontweight="bold",
        )
        ax1.grid(True, alpha=0.3)

        # Add statistics for delivery rate
        avg_rate = sum(delivery_rates) / len(delivery_rates)
        max_rate = max(delivery_rates)
        min_rate = min(delivery_rates)

        ax1.axhline(
            y=avg_rate,
            color="r",
            linestyle="--",
            alpha=0.7,
            label=f"Average: {avg_rate:.0f} bps",
        )
        ax1.legend()

        # Add text box with statistics
        stats_text = f"Max: {max_rate:.0f} bps\nMin: {min_rate:.0f} bps\nAvg: {avg_rate:.0f} bps\nSamples: {len(delivery_rates)}"
        ax1.text(
            0.02,
            0.98,
            stats_text,
            transform=ax1.transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
        )

    # Plot ABR bitrate (bottom subplot)
    if abr_data:
        abr_timestamps = [entry[0] for entry in abr_data]
        abr_bitrates = [entry[1] for entry in abr_data]

        # Convert ABR timestamps to relative time (assuming they're in seconds since epoch)
        # We need to convert the first ABR timestamp to milliseconds and align with ss log
        if delivery_rate_data and abr_data:
            # Align ABR timestamps with ss log timestamps
            first_abr_ms = abr_timestamps[0] * 1000  # Convert to milliseconds
            relative_abr_timestamps = [
                (ts * 1000 - start_time_ms) / 1000.0 for ts in abr_timestamps
            ]
        else:
            # If no delivery rate data, just use relative time from first ABR entry
            relative_abr_timestamps = [
                (ts - abr_timestamps[0]) for ts in abr_timestamps
            ]

        ax2.plot(
            relative_abr_timestamps,
            abr_bitrates,
            "g-",
            linewidth=2,
            alpha=0.8,
            marker="o",
            markersize=4,
        )
        ax2.set_ylabel("ABR Bitrate (kbps)", fontsize=12)
        ax2.set_title("Client ABR chunk selection bitrate", fontsize=14, fontweight="bold")
        ax2.grid(True, alpha=0.3)

        # Add statistics for ABR bitrate
        if abr_bitrates:
            avg_bitrate = sum(abr_bitrates) / len(abr_bitrates)
            max_bitrate = max(abr_bitrates)
            min_bitrate = min(abr_bitrates)

            ax2.axhline(
                y=avg_bitrate,
                color="orange",
                linestyle="--",
                alpha=0.7,
                label=f"Average: {avg_bitrate:.0f} kbps",
            )
            ax2.legend()

            # Add text box with statistics
            abr_stats_text = f"Max: {max_bitrate} kbps\nMin: {min_bitrate} kbps\nAvg: {avg_bitrate:.0f} kbps\nSamples: {len(abr_bitrates)}"
            ax2.text(
                0.02,
                0.98,
                abr_stats_text,
                transform=ax2.transAxes,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.8),
            )

    # Set x-axis limits and labels
    duration_sec = total_duration_ms / 1000.0
    ax2.set_xlim(0, duration_sec)
    ax2.set_xlabel("Time (seconds)", fontsize=12)

    # Add overall duration to the figure
    # fig.suptitle(
    #     f"Network Performance Analysis - Total Duration: {duration_sec:.1f}s",
    #     fontsize=16,
    #     fontweight="bold",
    # )

    plt.tight_layout()

    if save_plot:
        filename = f"delivery_rate_and_abr_port_{peer_port}.png"
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        print(f"Plot saved as {filename}")

    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--tcp_log", type=str, required=True)
    parser.add_argument("-a", "--abr_log", type=str, required=True)
    parser.add_argument(
        "-p",
        "--peer_port",
        type=str,
        help="Filter by specific peer port (e.g., '9671')",
    )
    parser.add_argument(
        "--all_ports",
        action="store_true",
        help="Plot all peer ports in the same figure",
    )
    parser.add_argument(
        "--no_plot", action="store_true", help="Skip plotting (just print data)"
    )
    args = parser.parse_args()

    # Parse tcp
    tcp_summary = parse_tcp_log(args.tcp_log)

    # Parse ABR log
    abr_data = parse_abr_log(args.abr_log)
    print(f"Parsed {len(abr_data)} ABR entries")

    # If all_ports flag is set, plot all ports
    if args.all_ports:
        plot_all_ports_delivery_rate_and_abr_bitrate(args.tcp_log, abr_data)
    # If peer port is specified, filter and extract delivery_rate for that port
    elif args.peer_port:
        delivery_rate_data = filter_by_peer_port_and_extract_delivery_rate(
            args.tcp_log, args.peer_port
        )
        print(
            f"Found {len(delivery_rate_data)} entries with delivery_rate for peer port {args.peer_port}"
        )

        # Print first few entries as example
        if delivery_rate_data:
            print("First 5 delivery rate entries:")
            for i, (timestamp_ms, delivery_rate) in enumerate(delivery_rate_data[:5]):
                print(
                    f"  {i+1}: timestamp={timestamp_ms}ms, delivery_rate={delivery_rate} bps"
                )

        if abr_data:
            print("First 5 ABR entries:")
            for i, (timestamp_sec, bit_rate) in enumerate(abr_data[:5]):
                print(f"  {i+1}: timestamp={timestamp_sec}s, bit_rate={bit_rate} kbps")

            # Plot both delivery rate and ABR bitrate
            if not args.no_plot:
                plot_delivery_rate_and_abr_bitrate(
                    delivery_rate_data, abr_data, args.peer_port, args.tcp_log
                )
    else:
        # Default: plot all ports
        plot_all_ports_delivery_rate_and_abr_bitrate(args.tcp_log, abr_data)
