import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

supported_logs = {
    "0xB0C0": {
        "DL_DCCH / RRCConnectionReconfiguration",
        "UL_DCCH / RRCConnectionReconfigurationComplete",
    },
    "0xB821": {"RRC_RECONFIG", "RRC_RECONFIG_COMPLETE"},
}


@dataclass
class Entry:
    date: str  # YYYY MMM DD
    time: str  # HH:MM:SS.mmm
    ts_ms: int  # unix timestamp in milliseconds
    unknown: str  # Code in brackets [XX]
    log_code: str  # 0xXXXX
    log_name: str  # log name corresponding to log code
    log_subname: Optional[str] = None  # log subname/description
    data: Optional[dict[str, Any]] = None


def _get_indentation_level(line: str) -> int:
    """Calculate indentation level (number of leading spaces/tabs)"""
    stripped = line.lstrip()
    if not stripped:
        return -1  # Empty line
    indent = len(line) - len(stripped)
    return indent // 2


def _parse_pdu_line(line: str) -> List[str]:
    """Parse the content of a line"""
    # Remove braces
    line = line.replace("{", "").replace("}", "")
    # Strip and remove trailing commas
    line = line.strip().rstrip(",")
    # colon values
    colon_splits = [v.strip() for v in line.split(":") if v.strip()]
    # At most two values, separated by one space
    values = []
    for part in colon_splits:
        values.extend(part.split(" ", 1))
    return values


def _cleanup_empty_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cleanup empty dictionaries from the nested dictionary.
    """
    is_value_list = False
    for k, v in d.items():
        if isinstance(v, dict) and len(v) == 0:
            is_value_list = True
            break
    if is_value_list:
        result = []
        for k, v in d.items():
            if len(v) == 0:
                result.append(k)
            else:
                result.append({k: _cleanup_empty_dict(v)})
        if len(result) == 1:
            result = result[0]
    else:
        result = {k: _cleanup_empty_dict(v) for k, v in d.items()}
    return result


def _get_epoch_ms(date_time_str: str) -> int:
    """
    Get the epoch milliseconds from a date time string.
    """
    dt = datetime.strptime(date_time_str, "%Y %b %d %H:%M:%S.%f")
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000.0)


def parse_nested_pdu(lines: List[str], begin: int, root: Dict[str, Any]) -> int:
    """
    Parse nested PDU lines and build a nested dictionary structure.
    """
    i = begin
    # Handle first line of PDU
    values = []
    level = 0
    root_key = None
    body = {}
    # consume empty lines till message header
    while i < len(lines) and len(values) == 0:
        line = lines[i].replace("::=", " ")
        values = _parse_pdu_line(line)
        level = _get_indentation_level(line)
        i += 1
    if len(values) == 2:
        root_key = values[1]
    else:
        print(f"Invalid root line: {line}")
        i -= 1
        return i - begin

    # Parse rest of PDU lines and build tree
    stack = [(level, body)]
    while i < len(lines):
        line = lines[i]
        values = _parse_pdu_line(line)
        if not values:
            i += 1
            continue
        level = _get_indentation_level(line)
        while stack and stack[-1][0] >= level:
            stack.pop()
        if not stack:
            break

        # Check if implicit nesting is needed
        while level - stack[-1][0] > 1:
            enumerate_key = chr(0x30 + len(stack[-1][1]))
            stack[-1][1][enumerate_key] = {}
            stack.append((stack[-1][0] + 1, stack[-1][1][enumerate_key]))
        for v in values:
            stack[-1][1][v] = {}
            stack.append((level, stack[-1][1][v]))
            level += 1
        i += 1

    # Cleanup empty dictionaries
    body = _cleanup_empty_dict(body)
    root[root_key] = body

    # Return the number of lines parsed
    return i - begin


def parse_interpreted_pdu(lines: List[str], begin: int, root: Dict[str, Any]) -> int:
    """
    Parse interpreted PDU lines and return a nested dictionary structure.
    """
    i = begin
    while i < len(lines):
        line = lines[i].strip()
        if line:
            if line.startswith("Interpreted PDU:"):
                root["Interpreted PDU"] = {}
                i += 1
                parsed = parse_nested_pdu(lines, i, root["Interpreted PDU"])
                return parsed + i - begin
            else:
                break
        i += 1
    return i - begin


def parse_further_decoding_pdu(
    lines: List[str], begin: int, root: Dict[str, Any]
) -> int:
    """
    Parse further decoding PDU lines and return a nested dictionary structure.
    """
    to_match = ["====", "Further", "===="]
    matched = []
    i = begin
    while i < len(lines) and len(to_match) > 0:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if not line.startswith(to_match[-1]):
            break
        else:
            matched.append(line)
            i += 1
            to_match.pop()
    if len(to_match) == 0:
        key = matched[1]
        # Aggressive matching nested PDU header
        # "Interpreted PDU" line not guaranteed to be present
        root[key] = {}
        while i < len(lines):
            if "::=" in lines[i]:
                parsed = parse_nested_pdu(lines, i, root[key])
                return parsed + i - begin
            elif "Interpreted PDU:" in lines[i]:
                parsed = parse_interpreted_pdu(lines, i, root[key])
                return parsed + i - begin
            i += 1
    # Rollback
    return i - len(matched) - begin


def parse_value_pair_lines(lines: list[str], begin: int, root: Dict[str, Any]) -> int:
    """
    Parse metadata lines (key-value pairs) and return a dictionary.
    """
    i = begin
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if "=" not in line or "====" in line:
            break
        parts = line.split(",")
        for part in parts:
            values = part.split("=")
            if len(values) != 2:
                print(f"Invalid value pair line: {line}")
                continue
            root[values[0].strip()] = values[1].strip()
        i += 1
    return i - begin


def parse_asn1_packet_text(text: str) -> Dict[str, Any]:
    """
    Parse ASN.1 notation text and return a nested dictionary structure.
    """
    lines = text.splitlines()
    return parse_asn1_packet(lines)


def parse_asn1_packet(lines: List[str]) -> Dict[str, Any]:
    """
    Parse ASN.1 packet and return a nested dictionary structure.
    """
    result = {}
    lines_parsed = 0

    while lines_parsed < len(lines):
        parsed = 0
        parsed += parse_value_pair_lines(lines, lines_parsed + parsed, result)
        parsed += parse_interpreted_pdu(lines, lines_parsed + parsed, result)
        parsed += parse_further_decoding_pdu(lines, lines_parsed + parsed, result)
        lines_parsed += parsed
        if parsed == 0:
            # TODO: handle unknown objects
            print(f"Unknown object at line {lines_parsed}")
            print(lines[lines_parsed:])
            break

    if lines_parsed < len(lines):
        result["extra_lines"] = lines[lines_parsed:]

    return result


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
        log_name, log_subname = rest.split("  --  ", 1)
        log_name = log_name.strip()
        log_subname = log_subname.strip()
    else:
        log_name = rest.strip()
        log_subname = None

    entry = Entry(
        date=date,
        time=time,
        ts_ms=_get_epoch_ms(f"{date} {time}"),
        unknown=unknown,
        log_code=log_code,
        log_name=log_name,
        log_subname=log_subname,
        data=None,
    )

    # TODO: Process content lines if supported
    if len(text_lines) > 1:
        if entry.log_code in supported_logs:
            entry.data = parse_asn1_packet(text_lines[1:])
    return entry


def _split_entries(file_path: str) -> Iterator[List[Entry]]:
    """
    Parse link-layer log file and yield individual log entries.

    1. Metadata lines (starting with %) are skipped.
    2. Log entry format:
    date time [A-Z] log_code_hex log_name -- log_subname
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

    def _is_timestamp_line(line: str) -> bool:
        return bool(
            re.match(r"^\d{4}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}", line)
        )

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
            if next_non_empty and _is_timestamp_line(next_non_empty):
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


def process_file(file_path: str) -> List[Entry]:
    """
    Parse a link-layer log file and return a list of Entry objects.
    """
    result = []
    raw_entries = _split_entries(file_path)
    for text_lines in raw_entries:
        entry = parse_entry(text_lines)
        if entry:
            result.append(entry)
    return result


if __name__ == "__main__":
    print("Example usage:")
    print("import asn1parse")
    print("entries = asn1parse.process_file('path/to/log.txt')")
