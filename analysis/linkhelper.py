import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import asn1parse
from asn1parse import Entry


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
        return "\n".join(stats)

    def add_rrc(self, entry: Entry):
        data_pdu = entry.data["Interpreted PDU"]

        # If RRCComplete, update the end time of the last HO event
        if entry.log_subname == "UL_DCCH / RRCConnectionReconfigurationComplete":
            if self.ho_events:
                last_ho = self.ho_events[-1]
                if last_ho.end is None:
                    last_ho.end = entry.ts

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
                self.ho_events[-1].end = entry.ts
                # code.interact(local=dict(globals(), **locals()))
            if ho_type is None:
                ho_type = "intraSCG"
            self.ho_events.append(
                HOEvent(
                    begin=entry.ts,
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


# TODO: WIP
def process_logs(
    file_path: str, filter_range: Optional[Tuple[int, int]] = None
) -> UESTAT:
    if filter_range is None:
        filter_range = (0, float("inf"))
    parsed_entries = asn1parse.process_file(file_path)
    uestat = UESTAT()
    for entry in parsed_entries:
        if filter_range[0] <= entry.ts < filter_range[1]:
            uestat.add_rrc(entry)
    return uestat


if __name__ == "__main__":
    print("WIP: under development")
