import json
from collections import defaultdict
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


def load_dash_log(log_path, filter_range=None):
    # Handle potential file corruption by reading as binary first
    # and decoding with error handling
    # Sometimes browser logs are corrupted
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        print("Warning: File has encoding/parsing issues, attempting recovery...")
        print(f"  Original error: {type(e).__name__}: {str(e)[:100]}")
        # Read as binary and replace invalid UTF-8 bytes
        with open(log_path, "rb") as f:
            content = f.read()
        text = content.decode("utf-8", errors="replace")
        logs = json.loads(text)
        print(f"  Successfully recovered and loaded {len(logs)} entries")

    event_map = defaultdict(list)
    filtered_logs = []
    if filter_range is None:
        filter_range = (0, float("inf"))

    for i in range(len(logs)):
        rel_ts = logs[i]["perfTime"] / 1000.0
        if rel_ts < filter_range[0] or rel_ts >= filter_range[1]:
            continue

        event = logs[i]
        ts = event["wallTime"] / 1000.0
        readable_date = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        name = event["data"]["type"]

        # Assign new fields to the event
        event["relTime"] = rel_ts
        event["ts_ms"] = event["wallTime"]
        event["date"] = readable_date
        event["name"] = name
        event["index"] = i

        filtered_logs.append(event)
        event_map[name].append(event)
    return filtered_logs, event_map


def plot_quality(logs, event_map, ax):
    ax.set_ylabel("Rendered Quality")
    start_time = logs[0]["relTime"]
    end_time = logs[-1]["relTime"]
    x = []
    y = []
    prev_rep_id = -1
    first_old_rep_id = None
    qc_events = event_map["qualityChangeRendered"]
    if len(qc_events) == 0:
        print("Warning: no quality change data")
        return -1
    if qc_events[0]["data"]["oldRepresentation"] is not None:
        first_old_rep_id = int(qc_events[0]["data"]["oldRepresentation"]["id"])
    for ev in qc_events[1:]:
        old_rep_id = int(ev["data"]["oldRepresentation"]["id"])
        new_rep_id = int(ev["data"]["newRepresentation"]["id"])
        if prev_rep_id > 0 and old_rep_id != prev_rep_id:
            print("Warning: quality change parsing error")
            return -1
        prev_rep_id = new_rep_id
        x.append(ev["relTime"])
        y.append(new_rep_id)

    # Add dummy datapoint at filter_range[0] with first old_rep_id
    if first_old_rep_id is not None:
        x.insert(0, start_time)
        y.insert(0, first_old_rep_id)
    # Add dummy datapoint at filter_range[1] with last new_rep_id
    if len(y) > 0:
        x.append(end_time)
        y.append(y[-1])

    ax.step(x, y, where="post", marker="o", linestyle="dotted")


def plot_buffer_state(logs, event_map, ax):
    ax.set_ylabel("Buffer State")
    start_time = logs[0]["relTime"]
    end_time = logs[-1]["relTime"]

    # Collect buffer state changes
    buffer_times = []
    buffer_states = []
    for ev in event_map["bufferStateChanged"]:
        buffer_times.append(ev["relTime"])
        # Convert state to numeric: 0 = stalled, 1 = loaded
        state_val = 0 if ev["data"]["state"] == "bufferStalled" else 1
        buffer_states.append(state_val)

    if buffer_times:
        # Add dummy datapoint at filter_range[0] with opposite value from first
        first_state = buffer_states[0]
        dummy_state = 1 - first_state  # Opposite value (0->1, 1->0)
        buffer_times.insert(0, start_time)
        buffer_states.insert(0, dummy_state)
        # Add dummy datapoint at filter_range[1] with last state
        buffer_times.append(end_time)
        buffer_states.append(buffer_states[-1])

        # Plot buffer state as step function
        ax.step(
            buffer_times,
            buffer_states,
            marker="o",
            where="post",
            color="tab:red",
        )
        ax.set_ylim(-0.1, 1.1)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Stalled", "Loaded"])
        ax.grid(True, alpha=0.3)
    else:
        print("Warning: no buffer state data")
        return -1


def plot_buffer_level(logs, event_map, ax):
    ax.set_ylabel("Buffer Level")
    start_time = logs[0]["relTime"]
    end_time = logs[-1]["relTime"]

    # Collect buffer level updates
    buffer_times = []
    buffer_levels = []
    for ev in event_map["bufferLevelUpdated"]:
        buffer_times.append(ev["relTime"])
        buffer_levels.append(ev["data"]["bufferLevel"])

    if buffer_times:
        # Add dummy datapoint at start with first value
        buffer_times.insert(0, start_time)
        buffer_levels.insert(0, buffer_levels[0])
        # Add dummy datapoint at end with last value
        buffer_times.append(end_time)
        buffer_levels.append(buffer_levels[-1])

        # Plot buffer level as step function
        ax.step(
            buffer_times,
            buffer_levels,
            # marker="o",
            where="post",
            color="tab:blue",
        )
        ax.grid(True, alpha=0.3)
    else:
        print("Warning: no buffer level data")
        return -1


def plot_chunk_loading(logs, event_map, ax):
    ax.set_ylabel("Chunk Index")

    # Chunk loading analysis
    print("Checking chunks...")
    chunks = []
    for i, ev in enumerate(logs):
        # chunk loading
        if ev["name"] == "fragmentLoadingStarted":
            chk_i = ev["data"]["request"]["index"]
            if chk_i is None:
                chk_i = 0
            else:
                chk_i = int(chk_i) + 1
            rep_id = ev["data"]["request"]["representation"]["id"]
            # search for chunk loading result
            status = "unknown"
            j = i + 1
            while j < len(logs):
                if logs[j]["name"] == "fragmentLoadingCompleted":
                    # Normalize index for comparison (None -> 0, otherwise int + 1)
                    comp_chk_i = logs[j]["data"]["request"]["index"]
                    if comp_chk_i is None:
                        comp_chk_i = 0
                    else:
                        comp_chk_i = int(comp_chk_i) + 1
                    if (
                        logs[j]["data"]["request"]["representation"]["id"] == rep_id
                        and comp_chk_i == chk_i
                    ):
                        status = "completed"
                        break
                elif logs[j]["name"] == "fragmentLoadingAbandoned":
                    # Normalize index for comparison (None -> 0, otherwise int + 1)
                    comp_chk_i = logs[j]["data"]["request"]["index"]
                    if comp_chk_i is None:
                        comp_chk_i = 0
                    else:
                        comp_chk_i = int(comp_chk_i) + 1
                    if (
                        logs[j]["data"]["request"]["representation"]["id"] == rep_id
                        and comp_chk_i == chk_i
                    ):
                        status = "abandoned"
                        break
                j += 1
            if j == len(logs):
                j = i
            chunks.append((chk_i, ev["relTime"], logs[j]["relTime"], rep_id, status))
    print(f"Chunk download attempts: {len(chunks)}")

    unique_rep_ids = sorted(set(chk[3] for chk in chunks))
    colors = plt.cm.tab10(range(len(unique_rep_ids)))
    colors_map = {rep_id: colors[i] for i, rep_id in enumerate(unique_rep_ids)}

    for chk in chunks:
        if chk[0] == 0:
            # ignore dashinit
            continue
        rep_id = chk[3]
        if chk[4] == "completed":
            ax.plot(
                [chk[1], chk[2]],
                [chk[0], chk[0]],
                color=colors_map[rep_id],
                linewidth=2,
            )
        else:
            ax.plot(chk[1], chk[0], marker="x", color=colors_map[rep_id], markersize=8)

    # Create fixed legend with colored lines
    if unique_rep_ids:
        legend_elements = [
            Line2D([0], [0], color=colors_map[rep_id], label=f"Quality {rep_id}")
            for rep_id in unique_rep_ids
        ]
        ax.legend(handles=legend_elements, loc="upper left")
    ax.grid(True, alpha=0.3)


def plot_handover(ho_events, ax, color="tab:gray"):
    for start, end in ho_events:
        ax.axvspan(start, end, color=color, alpha=0.3)
