import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterator, List, Optional

import asn1parse


def is_timestamp_line(line: str) -> bool:
    """
    Check if a line starts with a timestamp pattern (YYYY MMM DD).

    Args:
        line: Line to check

    Returns:
        True if line starts with timestamp pattern
    """
    # Pattern: YYYY MMM DD (e.g., "2025 Dec 17  20:34:04.165")
    return bool(re.match(r"^\d{4}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}", line))


@dataclass
class Entry:
    date: str  # YYYY MMM DD
    time: str  # HH:MM:SS.mmm
    unknown: str  # Code in brackets [XX]
    log_code: str  # 0xXXXX
    log_type: str  # log type name corresponding to log code
    log_name: Optional[str] = None  # log name/description
    data: Optional[dict[str, Any]] = None


def parse_entry(text_lines: list[str]) -> Optional[Entry]:
    """
    Parse the text lines of a log entry and return an Entry object.

    Format: YYYY MMM DD  HH:MM:SS.mmm  [XX]  0xXXXX  Log Name [-- Description]

    Args:
        text_lines: The text lines of a log entry

    Returns:
        Entry object with text lines, or None if parsing fails
    """
    # Process header line

    # Pattern to match: YYYY MMM DD  HH:MM:SS.mmm  [XX]  0xXXXX  ...
    pattern = r"^(\d{4})\s+([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2}\.\d{3})\s+\[([0-9A-F]{2})\]\s+(0x[0-9A-F]{4})\s+(.+)$"

    match = re.match(pattern, text_lines[0])
    if not match:
        return None

    year, month, day, time, unknown, log_code, rest = match.groups()

    # Construct date string
    date = f"{year} {month} {day}"

    # Parse the rest: "Log Name" or "Log Name  --  Description"
    if "  --  " in rest:
        log_type, log_name = rest.split("  --  ", 1)
        log_type = log_type.strip()
        log_name = log_name.strip()
    else:
        log_type = None
        log_name = rest.strip()

    entry = Entry(
        date=date,
        time=time,
        unknown=unknown,
        log_code=log_code,
        log_type=log_type,
        log_name=log_name,
    )

    # Process content lines if supported
    if len(text_lines) > 1:
        data_lines = text_lines[1:]
        if entry.log_code == "0xB0C0":
            entry.data = parse_packet(data_lines)

    return entry


def parse_packet(lines: list[str]) -> dict[str, Any]:
    """
    Parse a packet from the data lines.

    Parses key-value pairs until "Interpreted PDU:" is found.
    After that, stores remaining lines under "Interpreted PDU" key.

    Args:
        lines: List of data lines from the packet

    Returns:
        Dictionary with parsed key-value pairs and "Interpreted PDU" content
    """
    result = {}
    interpreted_pdu_start = None

    # Find where "Interpreted PDU:" starts
    for i, line in enumerate(lines):
        if line.strip() == "Interpreted PDU:":
            interpreted_pdu_start = i
            break

    # Parse key-value pairs before "Interpreted PDU:"
    parse_lines = (
        lines[:interpreted_pdu_start] if interpreted_pdu_start is not None else lines
    )

    for line in parse_lines:
        line = line.strip()
        if not line:
            continue

        # Handle lines with multiple key-value pairs separated by commas
        # Example: "Radio Bearer ID = 0, Physical Cell ID = 241"
        # Split by comma, but be careful with commas in values
        parts = []
        current_part = ""
        paren_depth = 0

        for char in line:
            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
            elif char == "," and paren_depth == 0:
                parts.append(current_part.strip())
                current_part = ""
                continue
            current_part += char

        if current_part:
            parts.append(current_part.strip())

        # Parse each part as key-value pair
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                key = key.strip()
                value = value.strip()
                result[key] = value

    # Add "Interpreted PDU" section if found
    if interpreted_pdu_start is not None:
        # Skip the "Interpreted PDU:" line and any empty line after it
        pdu_lines = lines[interpreted_pdu_start + 1 :]
        # Remove leading empty lines
        while pdu_lines and not pdu_lines[0].strip():
            pdu_lines = pdu_lines[1:]
        result["Interpreted PDU"], lines_parsed = asn1parse.parse_asn1(pdu_lines)
        if lines_parsed != len(pdu_lines):
            # print(f"Failed to parse Interpreted PDU data: {result}")
            result["extra_lines"] = pdu_lines[lines_parsed:]
    return result


def get_entries(file_path: str) -> Iterator[List[str]]:
    """
    Parse link-layer log file and yield individual log entries.

    1. Metadata lines (starting with %) are skipped.
    2. Log entry format:
    date time [A-Z] log_code_hex log_name -- log_description
        content_lines...
    Example:
    2025 Dec 17  20:34:04.165  [EC]  0x1FF0  Diagnostic Response Status  --  Log Config
        CMD Code  = 115...
    The boundary of an entry should be determined by the timestamp line till next timestamp line.

    Args:
        file_path: Path to the link-layer log file

    Yields:
        List of lines representing a single log entry
    """
    current_entry = []
    in_metadata = True
    lines = []

    # Read all lines first to enable lookahead
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            # Strip line endings (handles both \n and \r\n)
            line = line.rstrip("\r\n")
            lines.append(line)

    # Process lines with lookahead capability
    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip metadata lines (starting with %)
        if line.startswith("%"):
            i += 1
            continue

        # Once we see a non-metadata line, we're past the header
        if in_metadata and line.strip():
            in_metadata = False

        # Empty line - check if next non-empty line is a timestamp
        if not line.strip():
            # Look ahead to find next non-empty line
            next_non_empty = None
            j = i + 1
            while j < len(lines):
                if lines[j].strip() and not lines[j].startswith("%"):
                    next_non_empty = lines[j]
                    break
                j += 1

            # If next non-empty line is a timestamp, end current entry
            if next_non_empty and is_timestamp_line(next_non_empty):
                if current_entry:
                    yield current_entry
                    current_entry = []
            else:
                # Empty line is part of current entry (e.g., before "Log Codes Enabled:")
                current_entry.append(line)
        else:
            # Add line to current entry
            current_entry.append(line)

        i += 1

    # Yield the last entry if file doesn't end with empty line
    if current_entry:
        yield current_entry


def main():
    parser = argparse.ArgumentParser(description="Parse link-layer log entries")
    parser.add_argument("-i", "--input", help="input link-layer log file")

    args = parser.parse_args()

    raw_entries = get_entries(args.input)

    # selected_log_codes = {"0xB0C0", "0xB821"}
    selected_log_codes = {"0xB0C0"}

    log_map = defaultdict(lambda: defaultdict(list))
    handover_events = [
        [None, None, None]
    ]  # list of [measReport, RRCReconfig, RRCReconfigComplete]
    for text_lines in raw_entries:
        entry = parse_entry(text_lines)
        if entry and entry.log_code in selected_log_codes:
            # print(entry.log_name)
            log_map[entry.log_code][entry.log_name].append(entry)
            if entry.log_name == "UL_DCCH / MeasurementReport":
                handover_events[-1][0] = entry
            elif entry.log_name == "DL_DCCH / RRCConnectionReconfiguration":
                handover_events[-1][1] = entry
            elif entry.log_name == "UL_DCCH / RRCConnectionReconfigurationComplete":
                handover_events[-1][2] = entry
                handover_events.append([None, None, None])

    debug_search = ("physCellId-r10", "171")
    # TODO:
    # 1. in sCellToAddModList-r10, locate and match the physCellId-r10 with the sCellIndex-r10
    # 2.
    for ho in handover_events:
        print("-" * 100)
        if ho[0] is not None:
            print(ho[0].date, ho[0].time)
            print(ho[0].data["Interpreted PDU"])
        print()
        if ho[1] is not None:
            print(ho[1].date, ho[1].time)
            print(ho[1].data["Interpreted PDU"])
        print()
        if ho[2] is not None:
            print(ho[2].date, ho[2].time)
            print(ho[2].data["Interpreted PDU"])
        print("-" * 100)
        # paths = asn1parse.find_paths(
        #     ho[1].data["Interpreted PDU"], debug_search[0], debug_search[1]
        # )
        # if paths:
        #     for path in paths:
        #         print(" -> ".join(path))
        # else:
        #     print("No path found")

        input("Press Enter to continue...")

    import code

    code.interact(local=dict(globals(), **locals()))


if __name__ == "__main__":
    main()
