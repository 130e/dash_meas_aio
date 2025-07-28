#!/usr/bin/env python3
"""
Script to automatically generate video-specific configuration for ABR servers
by reading DASH manifest.mpd and analyzing video files.
"""

import os
import sys
import xml.etree.ElementTree as ET
import glob
import json
from pathlib import Path


def parse_manifest(mpd_path):
    """Parse DASH manifest.mpd file to extract video information."""
    try:
        tree = ET.parse(mpd_path)
        root = tree.getroot()

        # Define namespace
        ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}

        print(f"Root tag: {root.tag}")
        print(f"Root attributes: {root.attrib}")

        # Get video representations
        representations = []
        adaptation_sets = root.findall(".//mpd:AdaptationSet", ns)
        print(f"Found {len(adaptation_sets)} adaptation sets")

        for i, adaptation_set in enumerate(adaptation_sets):
            print(f"AdaptationSet {i}: {adaptation_set.attrib}")

            # Check if this adaptation set contains video (either by mimeType on AdaptationSet or on Representation)
            is_video = False
            if adaptation_set.get("mimeType", "").startswith("video/"):
                is_video = True
                print(f"  -> Video adaptation set (mimeType on AdaptationSet)")
            else:
                # Check if any representation in this adaptation set is video
                representations_in_set = adaptation_set.findall(
                    ".//mpd:Representation", ns
                )
                print(f"  -> Found {len(representations_in_set)} representations")
                for j, representation in enumerate(representations_in_set):
                    mime_type = representation.get("mimeType", "")
                    print(f"    Representation {j}: {representation.attrib}")
                    if mime_type.startswith("video/"):
                        is_video = True
                        print(f"      -> Video representation found")
                        break

            if is_video:
                for representation in adaptation_set.findall(
                    ".//mpd:Representation", ns
                ):
                    rep_info = {
                        "id": representation.get("id"),
                        "bandwidth": int(representation.get("bandwidth", 0)),
                        "width": int(representation.get("width", 0)),
                        "height": int(representation.get("height", 0)),
                    }
                    representations.append(rep_info)
                    print(f"  -> Added representation: {rep_info}")

        # Sort by bandwidth (quality)
        representations.sort(key=lambda x: x["bandwidth"])

        # Get segment template info
        segment_template = root.find(".//mpd:SegmentTemplate", ns)
        if segment_template is not None:
            timescale = int(segment_template.get("timescale", 90000))
            duration = int(segment_template.get("duration", 0))
            start_number = int(segment_template.get("startNumber", 1))
        else:
            timescale = 90000
            duration = 0
            start_number = 1

        # Get presentation duration
        duration_attr = root.get("mediaPresentationDuration", "PT0S")
        # Parse ISO 8601 duration (simplified)
        if "PT" in duration_attr:
            duration_str = duration_attr.replace("PT", "").replace("S", "")
            try:
                presentation_duration = float(duration_str)
            except ValueError:
                presentation_duration = 0
        else:
            presentation_duration = 0

        return {
            "representations": representations,
            "timescale": timescale,
            "duration": duration,
            "start_number": start_number,
            "presentation_duration": presentation_duration,
        }
    except Exception as e:
        print(f"Error parsing manifest: {e}")
        return None


def analyze_video_files(video_dir, representations):
    """Analyze video files to get chunk sizes and count."""
    video_dir = Path(video_dir)

    # Map representation IDs to quality levels
    quality_map = {}
    for i, rep in enumerate(representations):
        quality_map[rep["id"]] = i

    # Get chunk sizes for each quality level
    chunk_sizes = {}
    total_chunks = 0

    for rep in representations:
        rep_id = rep["id"]
        quality_level = quality_map[rep_id]

        # Look for chunk files - try multiple patterns based on common DASH naming
        chunk_patterns = [
            video_dir / rep_id / "*.m4s",  # Standard pattern
            video_dir / f"*{rep_id}*.m4s",  # Pattern with quality in filename
            video_dir / "*.m4s",  # All m4s files (fallback)
        ]

        chunk_files = []
        for pattern in chunk_patterns:
            chunk_files = sorted(glob.glob(str(pattern)))
            if chunk_files:
                print(f"Found {len(chunk_files)} chunk files using pattern: {pattern}")
                break

        if not chunk_files:
            print(f"Warning: No chunk files found for {rep_id}")
            # Try to list what files are actually in the directory
            try:
                all_files = list(video_dir.glob("*"))
                print(
                    f"Available files in {video_dir}: {[f.name for f in all_files[:10]]}"
                )
            except Exception as e:
                print(f"Could not list directory contents: {e}")
            continue

        # Get file sizes
        sizes = []
        for chunk_file in chunk_files:
            try:
                size = os.path.getsize(chunk_file)
                sizes.append(size)
            except OSError:
                print(f"Warning: Could not get size for {chunk_file}")
                sizes.append(0)

        chunk_sizes[quality_level] = sizes
        total_chunks = max(total_chunks, len(sizes))

    return chunk_sizes, total_chunks, quality_map


# TODO: Reuse pensieve mapping. Not sure if this is correct.
def generate_bitrate_rewards(representations):
    """Generate bitrate rewards mapping. Refer to QoE_hd in Pensieve"""
    # Simple logarithmic reward based on bitrate
    max_bandwidth = max(rep["bandwidth"] for rep in representations)
    rewards = []

    for rep in representations:
        # Normalize by max bandwidth and scale
        normalized = rep["bandwidth"] / max_bandwidth
        reward = int(normalized * 19) + 1
        rewards.append(reward)

    return rewards


def generate_config_json(manifest_info, chunk_sizes, total_chunks, quality_map):
    """Generate the configuration as JSON."""

    representations = manifest_info["representations"]
    bitrates = [rep["bandwidth"] // 1000 for rep in representations]  # Convert to Kbps
    rewards = generate_bitrate_rewards(representations)

    # Generate bitrate reward map
    reward_map = {}
    for i, rep in enumerate(representations):
        reward_map[rep["bandwidth"]] = rewards[i]
    reward_map[0] = 0  # Default case

    # Generate size arrays
    size_arrays = {}
    for i in range(len(representations)):
        if i in chunk_sizes:
            sizes = chunk_sizes[i]
            # Pad with zeros if needed
            while len(sizes) < total_chunks:
                sizes.append(0)
            size_arrays[f"video{i+1}"] = sizes
        else:
            size_arrays[f"video{i+1}"] = [0] * total_chunks

    config = {
        "video_bit_rate": bitrates,  # Kbps
        "bitrate_reward": rewards,
        "bitrate_reward_map": reward_map,
        "total_video_chunks": total_chunks,
        "chunk_til_video_end_cap": float(total_chunks),
        "chunk_sizes": size_arrays,
        "representations": [
            {
                "id": rep["id"],
                "bandwidth": rep["bandwidth"],
                "width": rep["width"],
                "height": rep["height"],
                "quality_level": i,
            }
            for i, rep in enumerate(representations)
        ],
    }

    return config


def load_video_config(config_file="video_config.json"):
    """Load video configuration from JSON file."""
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(
            f"Config file {config_file} not found. Please run generate_video_config.py first."
        )
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing config file: {e}")
        return None


def main():
    if len(sys.argv) != 3:
        print("Usage: python generate_video_config.py <manifest.mpd> <video_directory>")
        print(
            "Example: python generate_video_config.py ../reference/video_server/Manifest.mpd ../reference/video_server/videos/"
        )
        sys.exit(1)

    mpd_path = sys.argv[1]
    video_dir = sys.argv[2]

    print(f"Reading manifest: {mpd_path}")
    manifest_info = parse_manifest(mpd_path)

    if not manifest_info:
        print("Failed to parse manifest file")
        sys.exit(1)

    print(f"Found {len(manifest_info['representations'])} video representations:")
    for rep in manifest_info["representations"]:
        print(f"  {rep['id']}: {rep['bandwidth']} bps ({rep['width']}x{rep['height']})")

    if len(manifest_info["representations"]) == 0:
        print("No video representations found! Check the manifest file structure.")
        sys.exit(1)

    print(f"\nAnalyzing video files in: {video_dir}")
    chunk_sizes, total_chunks, quality_map = analyze_video_files(
        video_dir, manifest_info["representations"]
    )

    print(f"Found {total_chunks} chunks per quality level")

    if total_chunks == 0:
        print("No chunk files found! Check the video directory structure.")
        sys.exit(1)

    # Generate configuration
    config = generate_config_json(manifest_info, chunk_sizes, total_chunks, quality_map)

    # Write to JSON file
    output_file = "video_config.json"
    with open(output_file, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nQuality range: range({len(manifest_info['representations'])})")


if __name__ == "__main__":
    main()
