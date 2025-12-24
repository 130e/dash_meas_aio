import argparse
import code
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

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


def get_epoch_ms(date_time_str: str) -> int:
    """
    Get the epoch milliseconds from a date time string.
    """
    dt = datetime.strptime(date_time_str, "%Y %b %d %H:%M:%S.%f")
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000.0)


def json_find(obj, target_key, path=()):
    matches = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = path + (k,)

            if target_key in k:
                matches.append(new_path)

            matches.extend(json_find(v, target_key, new_path))

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            new_path = path + (i,)
            matches.extend(json_find(item, target_key, new_path))

    return matches


def json_get(obj, path):
    for p in path:
        obj = obj[p]
    return obj


@dataclass
class Entry:
    date: str  # YYYY MMM DD
    time: str  # HH:MM:SS.mmm
    ts_ms: int  # unix timestamp in milliseconds
    unknown: str  # Code in brackets [XX]
    log_code: str  # 0xXXXX
    log_type: str  # log type name corresponding to log code
    log_name: Optional[str] = None  # log name/description
    data: Optional[dict[str, Any]] = None


@dataclass
class Cell:
    cellIndex: int = None
    cellGroup: str = None  # "scg" or "mcg"
    physCellId: int = None
    dlCarrierFreq: int = None


@dataclass
class HOEvent:
    begin: str
    hoType: str  # intraLTE, intraSCG
    end: str = None
    added_cells: List[int] = field(default_factory=list)
    removed_cells: List[int] = field(default_factory=list)


class UESTAT:
    def __init__(self):
        self.measObj = []  # TODO
        self.pcell = Cell(cellGroup="mcg")
        self.mCells = {}
        self.sCells = {}
        self.scg_rev = "r10"
        self.mcg_freq_rev = "v9e0"
        self.event_keys = {
            "scg": {"add": "sCellToAddModList", "release": "sCellToReleaseList"},
            "mcg": {"ho": "mobilityControlInfo"},
        }
        self.ho_events = []

    def __repr__(self):
        stats = ["Stats ======"]
        stats.append(
            f"PCell(physCellId, dlCarrierFreq): {self.pcell.physCellId}, {self.pcell.dlCarrierFreq}"
        )
        stats.append("Scell(scgId, physCellId, dlCarrierFreq): ")
        for cid, cell in self.sCells.items():
            stats.append(f"{cid}, {cell.physCellId}, {cell.dlCarrierFreq}")
        stats.append(f"HO Events: {len(self.ho_events)}")
        # stats.append("HO Events (begin,end,hoType,added_cells,removed_cells):")
        # for ho in self.ho_events:
        #     removed_cells_str = ", ".join(map(str, ho.removed_cells))
        #     added_cells_str = ", ".join(map(str, ho.added_cells))
        #     stats.append(
        #         f"{ho.begin}, {ho.end}, {ho.hoType}, ({added_cells_str}), ({removed_cells_str})"
        #     )
        return "\n".join(stats)

    def add_rrc(self, entry: Entry):
        data_pdu = entry.data["Interpreted PDU"]

        # If RRCComplete, update the end time of the last HO event
        if entry.log_name == "UL_DCCH / RRCConnectionReconfigurationComplete":
            if self.ho_events:
                last_ho = self.ho_events[-1]
                if last_ho.end is None:
                    last_ho.end = entry.ts_ms

        added_cells = []
        removed_cells = []
        ho_type = None
        # MCG handover
        paths = json_find(data_pdu, self.event_keys["mcg"]["ho"])
        if paths:
            removed_cells.append(self.pcell.physCellId)
            p = paths[0]
            self.mcg_ho(json_get(data_pdu, p))
            # Log handover event
            ho_type_path = json_find(data_pdu, "handoverType")
            if not ho_type_path:
                print(
                    f"Error: handover type not found in {json.dumps(data_pdu, indent=2)}"
                )
                return -1
            else:
                ho_type = list(json_get(data_pdu, ho_type_path[0]).keys())[0]
                added_cells.append(self.pcell.physCellId)

        # Release SCGs first
        # NOTE: Seems like new scg reuse the same cell index as the released scg
        paths = json_find(data_pdu, self.event_keys["scg"]["release"])
        for p in paths:
            removed_cells.extend(self.rel_scg(json_get(data_pdu, p)))

        # Add new SCGs
        paths = json_find(data_pdu, self.event_keys["scg"]["add"])
        for p in paths:
            added_cells.extend(self.add_scg(json_get(data_pdu, p)))

        if added_cells or removed_cells:
            if self.ho_events and self.ho_events[-1].end is None:
                print(
                    "Warning: New HO event without a previous HO completion",
                    "Likely previous HO failed",
                )
                self.ho_events[-1].end = entry.ts_ms
                # code.interact(local=dict(globals(), **locals()))
            if ho_type is None:
                ho_type = "intraSCG"
            self.ho_events.append(
                HOEvent(
                    begin=entry.ts_ms,
                    end=None,
                    hoType=ho_type,
                    added_cells=added_cells,
                    removed_cells=removed_cells,
                )
            )

    def mcg_ho(self, data: Dict[str, Any]):
        # print(json.dumps(data, indent=2))
        # NOTE: HO timer t304
        pcell = Cell()
        pcell.cellGroup = "mcg"
        pcell.physCellId = int(data["targetPhysCellId"])
        pcell.dlCarrierFreq = int(
            data[f"carrierFreq-{self.mcg_freq_rev}"][
                f"dl-CarrierFreq-{self.mcg_freq_rev}"
            ]
        )
        self.pcell = pcell

    def add_scg(self, data: Dict[str, Any]) -> List[int]:
        added_cells = []
        for _, mod in data.items():
            cell = Cell()
            cid = int(mod[f"sCellIndex-{self.scg_rev}"])
            cell.cellIndex = cid
            cell.cellGroup = "scg"

            cidblock = mod.get(f"cellIdentification-{self.scg_rev}")
            if cidblock is not None:
                added_cells.append(cid)
                cell.physCellId = int(cidblock[f"physCellId-{self.scg_rev}"])
                cell.dlCarrierFreq = int(cidblock[f"dl-CarrierFreq-{self.scg_rev}"])
                self.sCells[cid] = cell
                print(
                    f"Added SCG {cid} {cell.physCellId} {cell.dlCarrierFreq} {cell.cellGroup}"
                )
            else:
                print(
                    f"Warning: adding scg {cid} w/o new config.",
                    "Likely reconfiguring same cell",
                )

        return added_cells

    def rel_scg(self, data: List[str]) -> List[int]:
        removed_cells = []
        for cellIndex in data:
            cid = int(cellIndex)
            removed_cells.append(cid)
            if cid in self.sCells:
                del self.sCells[cid]
            else:
                print(
                    f"Warning: Release scg {cid} not found in sCells.",
                    "Likely we missed the add event",
                )
            print(f"Released SCG {cid}")
        return removed_cells


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
        ts_ms=get_epoch_ms(f"{date} {time}"),
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
        pdu_dict = {}
        lines_parsed = asn1parse.parse_asn1(pdu_lines, pdu_dict)
        if lines_parsed < len(pdu_lines):
            result["extra_lines"] = pdu_lines[lines_parsed:]
        result["Interpreted PDU"] = pdu_dict
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


supported_logs = {
    "0xB0C0": {
        # "UL_DCCH / MeasurementReport",
        "DL_DCCH / RRCConnectionReconfiguration",
        "UL_DCCH / RRCConnectionReconfigurationComplete",
    },
}


def process_logs(
    file_path: str, filter_range: Optional[Tuple[int, int]] = None
) -> UESTAT:
    if filter_range is None:
        filter_range = (0, float("inf"))
    raw_entries = get_entries(file_path)
    uestat = UESTAT()
    for text_lines in raw_entries:
        entry = parse_entry(text_lines)
        if filter_range[0] <= entry.ts_ms < filter_range[1]:
            if (
                entry.log_code in supported_logs
                and entry.log_name in supported_logs[entry.log_code]
            ):
                uestat.add_rrc(entry)
    return uestat


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

    # Testing full
    uestat = UESTAT()
    for ho in handover_events:
        print("-" * 100)
        if ho[0] is not None:
            print("measReport", ho[0].date, ho[0].time)
        print()
        if ho[1] is not None:
            print("RRCReconfig", ho[1].date, ho[1].time)
            uestat.add_rrc(ho[1])
        print()
        if ho[2] is not None:
            print("RRCReconfigComplete", ho[2].date, ho[2].time)
            uestat.add_rrc(ho[2])
        print()
        print(uestat)
        print("-" * 100)

    ho_times = []
    for ho in uestat.ho_events:
        ho_times.append((ho.begin, ho.end))

    print("Avg ho time: ", sum(map(lambda x: x[1] - x[0], ho_times)) / len(ho_times))

    # Debug
    code.interact(local=dict(globals(), **locals()))


if __name__ == "__main__":
    main()
