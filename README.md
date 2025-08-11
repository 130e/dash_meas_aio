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
  - [ ] Add chunk index to the log
- [x] MPC tables compute script
- [ ] Cellular full function test
   - [ ] LTE RRC
   - [ ] 5G RRC version issue
- [ ] Post processing scripts
   - [ ] Cellular logs
   - [x] TCP ss
   - [ ] QUIC
   - [x] ABR logs
- [x] Use HTTP/2/3 to multiplexing over single connection
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
   sudo ./cellular_monitor -p /dev/ttyUSB0 -b 9600 -s on output.txt
   
   # Offline mode
   sudo ./cellular_monitor -p /dev/ttyUSB0 -b 9600 -s off raw.log
   ```
4. **Create new Termux session** (use hamburger button near ESC key)
5. **Run experiment** (assuming remote video server is running):
   ```bash
   python client_run.py -a {bola|fastmpc} -t tcp -s {SERVER_IP} {EXPERIMENT_ID}
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
Run tests to verify setup:
```bash
# Test browser functionality
# This opens a website and saves a page screenshot to `~/storage/downloads/screenshot.png`
python client_browser_func_test.py
# Test browser https functionality
# Check Caddy server logs for https requests
python client_browser_https_test.py
```

### Server Setup

Navigate to `server` directory.

#### 1. Prepare Video Content
- The `video_server/video_index.html` template provides a dummy page with modified `dash.js`
- Create a `video_server/videos` folder for manifest and video chunks
- Client scripts will access `video_server/videos/manifest.mpd` to start the video player
- ABR server is initialized locally on the client

#### 2. Precompute MPC Table
For FastMPC experiments, precompute the optimization table:
```bash
python generate_video_config.py {manifest.mpd} {video_directory}
```
Place the generated `video_config.json` in `client/abr_server/` in **client device**.

#### 3. Start Video Server
```bash
# Start Caddy server
caddy run --config ./Caddyfile
```

#### 4. Start Network Monitoring
```bash
# Create captures directory
mkdir -p ./captures

# Start tcpdump capture
sudo tcpdump tcp -s 96 -C 1000 -Z $USER -w ./captures/server_$(date +%Y%m%d_%H%M%S).pcap

# Monitor TCP socket statistics
sudo ./tcp_ss_monitor.sh 0 5202 0
```

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
Note for implementing custom abr server. 
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

## Time Synchronization

### Manual NTP Offset Extraction
Currently, we manually extract the timing offset between the mobile device and the same ntp server that the server is using.
The assumption is that clock don't drift too much between during experiment.
Usually the differnce between the offset to ntp server is >20ms.

#### Video Server
```bash
# Check if video server is using ntp server (e.g., systemd-timesyncd)
sudo systemctl status systemd-timesyncd.service
# Query offset (e.g., 2.time.constant.com)
ntpdate -q 2.time.constant.com
```
#### Client
In termux, install `chrony` and configure it to use the same ntp server as the video server. Then manually check the offset.
**TODO:** no systemd on termux thus we cannot run chrony as a service to sync time in rooted phone.
```bash
# Install chrony
pkg install chrony
# Configure chrony
mkdir -p ~/.config/chrony
vim ~/.config/chrony/chrony.conf
# Add the following lines
server 2.time.constant.com iburst
makestep 0.1 3

# Manually check offset
chronyd -f ~/.config/chrony/chrony.conf -d -Q
```

### Automatic Time Synchronization
**TODO:** add a script to automatically sync time and extract offset.

## Acknowledgments

- ABR algorithms and DASH.js modifications are based on the [Pensieve](http://web.mit.edu/pensieve/) repository.