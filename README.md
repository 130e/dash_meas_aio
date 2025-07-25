# Measurement pipeline

Scripts for running ABR streaming tests between mobile device and remote video server.

**TODOs:**

- [ ] Check tcpdump function
- [ ] Check metrics
- [ ] Check BBB movie streaming
- [ ] Server side ss monitoring script
- [ ] QUIC logging
- [ ] Check cellninja log
- [ ] Parsers
- [ ] HTTP multiplexing?
- [ ] For QUIC, we need to modify implementation to capture packets.
- [ ] ADB or temux?

## Client

Require android device as UE.

- Install Termux. UE commands are executed inside termux shell

- Install dependency in Termux and set up repo. Then we are ready to start
```sh
# Allow termux to access download folder
# Then restart Termux
termux-setup-storage

# https://wiki.termux.com/wiki/Python
pkg update
pkg upgrade
pkg install python
pkg install python-numpy

# chromium
pkg install x11-repo
pkg install tur-repo
pkg install chromium

# selenium
pip install selenium

# tcpdump if applicable
pkg install root-repo
pkg install tcpdump

# download scripts
pkg install git
git clone {THIS REPO}
```

- Optional. Run a test. It opens a website and save page screenshot to ~/storage/downloads/screenshot.png
```sh
python client_browser_test.py
```

- Connect UE to PC and start cellular capturer(*)

- Start experiment
```sh
python client_run.py -a bola -t tcp -s {SERVER_IP} -p {SERVER_PORT} {EXPERIMENT_ID}
# -d with tcpdump
```

### Logging

ABR server scripts log following metrics in `results` folder. 

- The Unix timestamp (seconds since epoch) when the log entry was recorded
- The bitrate (in Kbps) selected for the video chunk
- The size of the playback buffer (in seconds) after downloading the chunk
- The amount of time (in seconds) spent rebuffering (i.e., playback stalled) for this chunk
- The size (in bytes) of the video chunk that was just downloaded
- The time (in seconds) it took to download the video chunk
- The reward value calculated by the ABR algorithm for this chunk

## Server

Ideally, we can simply keep the video server and tcpdump running. We can always filter packets later.

### Prepare video

The template `video_index.html` is a dummy page, only providing the modified `dash.js`.

The client side script will access `videos/manifest.mpd` url to start the video player and initialize ABR server locally.

### Serving videos

```sh
# tcp server
python3 -m http.server 5202 --bind 0.0.0.0
```

### Logging

```sh
sudo tcpdump -i enp1s0 tcp -s 96 -C 1000 -w ~/pcap/tcp_capture_%Y-%m-%d_%H-%M-%S.pcap
```


## Acknowledgement

- ABR algorithms and dash.js are modified from [Pensieve](http://web.mit.edu/pensieve/) repository.