#!/usr/bin/env python3
"""
Test video configuration for abr_server
"""

from abr_cfg import *

def main():
    print("=== Video Configuration Test ===")
    
    # The configuration is automatically loaded when importing abr_cfg
    print(f"Number of quality levels: {len(VIDEO_BIT_RATE)}")
    print(f"Video bitrates (Kbps): {VIDEO_BIT_RATE}")
    print(f"Bitrate rewards: {BITRATE_REWARD}")
    print(f"Total video chunks: {TOTAL_VIDEO_CHUNKS}")
    print(f"Chunk til video end cap: {CHUNK_TIL_VIDEO_END_CAP}")
    print(f"Chunk length: {CHUNK_LENGTH}")
    print(f"Rebuffer penalty: {REBUF_PENALTY}")
    
    print("\n=== Quality Level Mapping ===")
    for i, bitrate in enumerate(VIDEO_BIT_RATE):
        print(f"Quality {i}: {bitrate} Kbps (reward: {BITRATE_REWARD[i]})")
    
    print("\n=== Chunk Size Examples ===")
    # Show chunk sizes for first few chunks at different qualities
    for quality in range(min(3, len(VIDEO_BIT_RATE))):
        print(f"Quality {quality} chunk sizes (first 5 chunks):")
        for chunk_idx in range(min(5, TOTAL_VIDEO_CHUNKS)):
            size = get_chunk_size(quality, chunk_idx)
            print(f"  Chunk {chunk_idx}: {size} bytes")
        print()
    
    print("=== Configuration Source ===")
    if os.path.exists("video_config.json"):
        print("✓ Using video_config.json")
    else:
        print("✗ Using default configuration (video_config.json not found)")
        print("  Run: python generate_video_config.py <manifest.mpd> <video_directory>")
        print("  to generate a video_config.json file")

if __name__ == "__main__":
    main() 