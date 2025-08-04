# DASH Measurement Pipeline

Measurement pipeline for running ABR (Adaptive Bitrate) streaming tests between mobile devices and remote video servers.

## Overview

This project provides scripts and tools for conducting adaptive bitrate streaming experiments, including:
- Client-side measurement collection on Android devices
- Server-side video streaming with ABR algorithms
- Network capture and analysis tools
- Custom DASH.js implementation with ABR algorithms

## Project Status

- [x] Headless Dash streaming scripts
- [x] Server and Client network capture
- [x] TCP measurements
- [ ] QUIC measurements
- [x] BOLA and FastMPC ABR algorithms
- [x] MPC tables compute script
- [ ] Full cellular capture test
- [ ] Post processing scripts
- [ ] HTTP multiplexing analysis
- [ ] Fix occasional broken pipe bug when requesting chunks
- [ ] Migrate to state-of-art dash.js

## Quick Start

### Prerequisites

- Android device with Termux installed
- Python 3.x on both client and server
- Network access between client and server
- Root access for network capture tools

### Running Experiments

1. **Start server-side captures** (see Server Setup section)
2. **Connect to mobile device** and run client-side capture:
   ```bash
   sudo ./run_capture.sh {SERVER_IP}
   ```
3. **Connect laptop to UE** and run cellular capture:
   ```bash
   # Online mode (for debugging)
   sudo ./x_desktop -p /dev/ttyUSB0 -b 9600 -s on output.txt
   
   # Offline mode
   sudo ./x_desktop -p /dev/ttyUSB0 -b 9600 -s off raw.log
   ```
4. **Create new Termux session** (use hamburger button near ESC key)
5. **Run experiment** (assuming remote video server is running):
   ```bash
   python client_run.py -a {bola|fastmpc} -t tcp -s {SERVER_IP} -p {SERVER_PORT} {EXPERIMENT_ID}
   ```

## Installation

### Client Setup (Android Device)

#### 1. Install Termux
- Download and install Termux from F-Droid or Google Play
- The client commands in this section are executed inside the Termux shell

#### 2. Install Dependencies
```bash
# Allow Termux to access download folder, then restart Termux
termux-setup-storage

# Update package manager
pkg update && pkg upgrade

# Install Python and dependencies
pkg install python python-numpy

# Install Chromium for browser automation
pkg install x11-repo tur-repo chromium

# Install Selenium for web automation
pip install selenium

# Install tcpdump for network capture (if applicable)
pkg install root-repo tcpdump

# Install Git and clone repository
pkg install git
git clone {THIS_REPO}
```

#### 3. Test Installation (Optional)
Run a test to verify setup:
```bash
python client_browser_test.py
```
This opens a website and saves a page screenshot to `~/storage/downloads/screenshot.png`.

### Server Setup

#### 1. Prepare Video Content
- The `video_index.html` template provides a dummy page with modified `dash.js`
- Create a `videos` folder for manifest and video chunks
- Client scripts will access `videos/manifest.mpd` to start the video player
- ABR server is initialized locally on the client

#### 2. Precompute MPC Table
For FastMPC experiments, precompute the optimization table:
```bash
python generate_video_config.py {manifest.mpd} {video_directory}
```
Place the generated `video_config.json` in `../client/abr_server/`

#### 3. Start Video Server
```bash
python3 -m http.server {SERVER_PORT} --bind 0.0.0.0
```

#### 4. Start Network Monitoring
```bash
# Create captures directory
mkdir -p ./captures

# Start tcpdump capture
sudo tcpdump tcp -s 96 -C 1000 -Z $USER -w ./captures/server_$(date +%Y%m%d_%H%M%S).pcap

# Monitor TCP socket statistics
sudo ./tcp_ss_monitor.sh {TARGET_IP} {TARGET_PORT} {DURATION}
```

**Note:** You can leave captures running continuously and perform post-processing later.

## Metrics and Logging

### ABR Server Metrics
The ABR server scripts log the following metrics in the `results` folder:

- **Timestamp**: Unix timestamp (seconds since epoch)
- **Bitrate**: Selected bitrate (Kbps) for the video chunk
- **Buffer Size**: Playback buffer size after downloading the chunk
- **Rebuffer Time**: Time spent rebuffering (playback stalled) for this chunk
- **Chunk Size**: Size (bytes) of the downloaded video chunk
- **Download Time**: Time (ms) to download the video chunk
- **Reward**: QoE value calculated by the ABR algorithm

### Custom DASH.js Metrics
The modified DASH.js implementation provides these additional metrics:

```javascript
var data = {
  'nextChunkSize': next_chunk_size(lastRequested+1),
  'Type': 'BB',
  'lastquality': lastQuality,
  'buffer': buffer,
  'bufferAdjusted': bufferLevelAdjusted,
  'bandwidthEst': bandwidthEst,
  'lastRequest': lastRequested,
  'RebufferTime': rebuffer,
  'lastChunkFinishTime': lastHTTPRequest._tfinish.getTime(),
  'lastChunkStartTime': lastHTTPRequest.tresponse.getTime(),
  'lastChunkSize': last_chunk_size(lastHTTPRequest)
};
```

## ABR Algorithms

### BOLA
Basic implementation of the BOLA (Buffer Occupancy based Lyapunov Algorithm) ABR algorithm.

### FastMPC
Implementation of Model Predictive Control (MPC) with optimization:

> **Note:** MPC involves solving an optimization problem for each bitrate decision to maximize QoE over the next 5 video chunks. The FastMPC paper describes a method that precomputes solutions for quantized input values. Since the original FastMPC implementation is not publicly available, we implemented MPC by solving the optimization problem exactly on the ABR server by enumerating all possibilities for the next 5 chunks. Computation takes at most 27ms for 6 bitrate levels with negligible impact on QoE.
> 
> — [Pensieve](http://web.mit.edu/pensieve/)

## Project Structure

```
dash_meas_aio/
├── client/                 # Client-side scripts and tools
│   ├── abr_server/        # ABR algorithm implementations
│   ├── js/               # Custom DASH.js modifications
│   └── results/          # Client-side measurement results
├── video_server/         # Server-side video streaming
│   ├── js/              # DASH.js library
│   └── videos/          # Video content and manifests
└── reference/           # Reference materials and documentation
```

## TODO

- Broken pipe errors: Occasional connection issues when requesting chunks
- QUIC capture
- HTTP multiplexing test
- Post processing scripts

## Acknowledgments

- ABR algorithms and DASH.js modifications are based on the [Pensieve](http://web.mit.edu/pensieve/) repository.