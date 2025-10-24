#!/usr/bin/env python3
import argparse
import os
import subprocess

# Renditions: resolution + target bitrate (average)
renditions = {
    "360_1M": {"size": "640x360", "bv": "1500k"},
    "480_4M": {"size": "854x480", "bv": "4000k"},
    "720_8M": {"size": "1280x720", "bv": "7500k"},
    "1080_12M": {"size": "1920x1080", "bv": "12000k"},
    "1440_24M": {"size": "2560x1440", "bv": "24000k"},
    # "2160_60M": {"size": "3840x2160", "bv": "60M"},
    # "4320": {"size": "7680x4320", "bv": "180M"}, # 8K support is spotty
    # "2160_180M": {"size": "3840x2160", "bv": "180M"},  # Emulate 8K video
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
    if bps >= 1_000_000 and bps % 1_000_000 == 0:
        return f"{bps // 1_000_000}M"
    else:
        return f"{bps // 1000}k"


def encode_variant(tag, settings, input_file, output_file):
    if not os.path.isfile(input_file):
        print("Sanity check: input video not found")
        return None

    bv = parse_bitrate(settings["bv"])
    maxrate = int(bv * 1.2)  # max bitrate
    bufsize = int(bv * 2.0)  # buffer

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-hwaccel",
        "cuda",
        "-threads",
        "0",  # Let ffmpeg decide
        "-i",
        input_file,
        "-an",  # no audio (video-only)
        "-c:v",
        "h264_nvenc",
        "-preset",
        "p3",
        "-b:v",
        settings["bv"],
        "-maxrate",
        fmt_bitrate(maxrate),
        "-bufsize",
        fmt_bitrate(bufsize),
        "-s",
        settings["size"],
        "-r",
        "60",
        "-preset",
        "slow",
        "-g",
        "240",
        "-keyint_min",
        "240",
        "-sc_threshold",
        "0",
        "-profile:v",
        "high",
        "-movflags",
        "+faststart",
        output_file,
    ]
    print(f"Encoding {tag}p...")
    subprocess.run(cmd, check=True)
    return output_file


def extract_audio(input_file, output_dir, prefix):
    audio_file = os.path.join(output_dir, f"{prefix}_audio.mp4")
    if os.path.isfile(audio_file):
        print(f"Skipping audio extraction - {audio_file} already exists")
        return audio_file

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_file,
        "-vn",  # no video (audio-only)
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        audio_file,
    ]
    print("Extracting audio track...")
    subprocess.run(cmd, check=True)
    return audio_file


def package_dash(output_files, mpd_path, audio_file=None):
    print("Packaging DASH manifest...")
    cmd = [
        "MP4Box",
        "-dash",
        "4000",
        "-frag",
        "4000",
        "-rap",
        "-profile",
        "dashavc264:live",
        "-out",
        mpd_path,
    ]
    cmd.extend(output_files)
    if audio_file != None:
        cmd.append(audio_file)
    subprocess.run(cmd, check=True)
    print(f">> DASH manifest generated at {mpd_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Encode multiple DASH renditions and package with MP4Box."
    )
    parser.add_argument(
        "-i",
        "--input_video",
        help="Input video file (e.g. bbb_sunflower_native_60fps_normal.mp4)",
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        default="chunks",
        help="Output directory for generated files",
    )
    parser.add_argument(
        "-p",
        "--prefix",
        default="bbb_sunflower",
        help="Output file prefix (default: bbb_sunflower)",
    )
    parser.add_argument(
        "-m",
        "--mpd_name",
        default="manifest.mpd",
        help="MPD filename (default: output_dir/manifest.mpd)",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Encode to multiple resolutions
    if args.input_video:
        print(f"Encoding '{args.input_video}' -> '{args.output_dir}'")
    else:
        print(
            f"Reuse encoded videos with prefix '{args.prefix}' from {args.output_dir}"
        )
    # Encode all video renditions
    video_files = []
    for tag, settings in renditions.items():
        output_file = os.path.join(args.output_dir, f"{args.prefix}_{tag}.mp4")

        if os.path.isfile(output_file):
            print(f"Skipping {tag}p - {output_file} already exists")
        elif not encode_variant(tag, settings, args.input_video, output_file):
            raise ValueError("Encoding failed")

        video_files.append(output_file)

    # FIXME: min dash does not support audio
    # Extract single audio file
    # audio_file = extract_audio(args.input_video, args.output_dir, args.prefix)

    # Package into MPD
    mpd_path = os.path.join(args.output_dir, args.mpd_name)
    package_dash(video_files, mpd_path)


if __name__ == "__main__":
    main()
