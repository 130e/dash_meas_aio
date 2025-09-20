#!/usr/bin/env python3
import subprocess
import argparse
import os

# Renditions: resolution + target bitrate (average)
# Only specify 'bv', we'll calculate maxrate and bufsize
renditions = {
    "360":  {"size": "640x360",   "bv": "1500k"},
    "480":  {"size": "854x480",   "bv": "4000k"},
    "720":  {"size": "1280x720",  "bv": "7500k"},
    "1080": {"size": "1920x1080", "bv": "12000k"},
    "1440": {"size": "2560x1440", "bv": "24000k"},
    "2160": {"size": "3840x2160", "bv": "60M"},
    "4320": {"size": "7680x4320", "bv": "180M"},
}

def parse_bitrate(bv_str):
    """Convert '800k' or '120M' into integer bits per second."""
    if bv_str.lower().endswith("k"):
        return int(float(bv_str[:-1]) * 1000)
    elif bv_str.lower().endswith("m"):
        return int(float(bv_str[:-1]) * 1000000)
    else:
        return int(bv_str)

def fmt_bitrate(bps):
    """Format integer bps back into ffmpeg-friendly string (k or M)."""
    if bps % 1000000 == 0:
        return f"{bps // 1000000}M"
    else:
        return f"{bps // 1000}k"

def encode_variant(tag, settings, input_file, output_prefix):
    bv = parse_bitrate(settings["bv"])
    maxrate = int(bv * 1.07)     # +7%
    bufsize = int(bv * 1.5)      # 1.5x buffer

    output_file = f"{output_prefix}_{tag}.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-c:v", "libx264",
        "-b:v", settings["bv"],
        "-maxrate", fmt_bitrate(maxrate),
        "-bufsize", fmt_bitrate(bufsize),
        "-s", settings["size"],
        "-r", "60",
        "-preset", "slow",
        "-g", "240",
        "-keyint_min", "240",
        "-sc_threshold", "0",
        "-profile:v", "high",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_file
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

def main():
    parser = argparse.ArgumentParser(description="Convert video to DASH-compatible MP4 renditions")
    parser.add_argument("input_file", help="Input video file to convert")
    parser.add_argument("-o", "--output-prefix", default="output", 
                       help="Output file prefix (default: bbb)")
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not os.path.isfile(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist.")
        return 1
    
    print(f"Converting '{args.input_file}' to DASH renditions...")
    print(f"Output prefix: {args.output_prefix}")
    
    for tag, settings in renditions.items():
        print(f"Encoding {tag}p...")
        encode_variant(tag, settings, args.input_file, args.output_prefix)
    print("✅ All renditions generated.")
    return 0

if __name__ == "__main__":
    exit(main())
