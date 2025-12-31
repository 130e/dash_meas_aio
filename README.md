# DASH Measurement Pipeline

Measurement pipeline for running ABR (Adaptive Bitrate) streaming tests between mobile devices and remote video servers.

## Overview

This project provides scripts and tools for conducting adaptive bitrate streaming experiments.

**Video Server**

- DASH encoded videos, `ffmpeg`, `mp4box`
- [dashjs](https://dashjs.org/) over HTTP server (`Caddy`)
- `tcpdump`, `ss` scripts

**Android Device (video client)**

- Python script that loads DASH video
- Log DASH metrics
- (if rooted) `tcpdump` script
- 5G log processing

## Installation

### Server Setup

Navigate to `server` directory. The server serves the `video_server/index.html`

#### Prepare Video Content

Encode one max quality video to multiple quality representations, then convert to dash chunks:

```shell
python convert_dash.py ~/bbb_sunflower_native_60fps_normal.mp4 -o chunks -p bbb_sunflower -m manifest.mpd
```

By default, encoded chunks and manifest are `video_server/chunks`.

#### Install server & dash

- Install Caddy and lsquic.
- Get a dashjs and put into `video_server/js` (included ESM debug version `5.0.0`)

### Client Setup

Setup Termux in Android.

- Install Termux. Then inside a termux terminal,

```shell
# Allow Termux to access download folder, then restart Termux
termux-setup-storage
# Update package manager
pkg update && pkg upgrade
# Install Python and dependencies
pkg install python python-numpy
# Install Chromium for browser automation
pkg install x11-repo tur-repo
pkg install chromium
# Install Selenium for web automation
pip install selenium
# (Optional) Install tcpdump for network capture
pkg install root-repo tcpdump
# Install Git and clone repository
pkg install git
git clone {THIS_REPO}
```

- (Optional) test

```shell
# Test browser functionality
# This opens a website and saves a page screenshot to `~/storage/downloads/screenshot.png`
python client_browser_func_test.py

# Test browser https functionality
# (Note: Start the Caddy server first!)
# Check Caddy server logs for https requests
python client_browser_https_test.py {SERVER_IP}
```

## Run

### Server

#### Start Video Server

The Caddy server serves two ports, HTTP at `5203` and HTTPS default.

```bash
# Start Caddy server
caddy run --config ./Caddyfile
```

**HTTPS Note**:
We use self-signed tls and it would not work unless the client explicitly trusts it (our script handles that).
We need HTTPS to enforce HTTP2, which uses TCP connection multiplexing.

#### Start Network Monitoring

```bash
# Create captures directory
mkdir -p ./captures

# Start network monitoring
sudo ./monitor.sh 5202 test0
```

### Client

- Connect to logger tool
- Start video streaming. Inside termux,

```shell
python client_run_dash.py -s={SERVER_IP} -i={LOG_ID}
```

The scripts collect log [events](https://cdn.dashjs.org/latest/jsdoc/MediaPlayerEvents.html) exposed by dash player into `captures/*.json`.

## Post-processing

**TODO** Calculate QoE metrics.

- **Timestamp**: Unix timestamp (seconds since epoch)
- **Bitrate**: Selected bitrate (Kbps) for the video chunk
- **Buffer Size**: Playback buffer size after downloading the chunk
- **Rebuffer Time**: Time spent rebuffering (playback stalled) for this chunk
- **Chunk Size**: Size (bytes) of the downloaded video chunk
- **Download Time**: Time (ms) to download the video chunk

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
