import argparse

import helper
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Process DASH log file")
    parser.add_argument(
        "--log", "-l", required=True, type=str, help="Path to DASH log file"
    )
    parser.add_argument(
        "--range",
        "-r",
        required=False,
        type=str,
        help="Filter time range in seconds (e.g., 500,600)",
    )
    args = parser.parse_args()

    if args.range is not None:
        filter_range = tuple(map(int, args.range.split(",")))
    else:
        filter_range = None
    # load dash logs
    logs, event_map = helper.load_dash_log(args.log, filter_range=filter_range)

    # Plot
    # =========================
    plot_functions = [
        helper.plot_quality,
        helper.plot_buffer_state,
        helper.plot_buffer_level,
        helper.plot_chunk_loading,
    ]
    fig_w = 10
    fig_h = 4 * len(plot_functions)
    fig, axes = plt.subplots(
        len(plot_functions), 1, sharex=True, figsize=(fig_w, fig_h)
    )

    for ax, plot_function in zip(axes, plot_functions):
        plot_function(logs, event_map, ax)
        ax.set_xlabel("Time (s)")

    plt.tight_layout()
    plt.savefig("plot.png", dpi=300)
    plt.close()

    return 0


if __name__ == "__main__":
    main()
