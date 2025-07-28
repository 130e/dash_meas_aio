# Measurement pipeline

Scripts for running ABR streaming tests between mobile device and remote video server.

**TODOs:**

- [ ] Check tcpdump function
- [ ] Server side ss monitoring script?
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

- Unix timestamp (seconds since epoch) when logging
- bitrate(Kbps) selected for the video chunk
- size of the playback buffer(s) after downloading the chunk
- time(s) spent rebuffering (i.e., playback stalled) for this chunk
- size(bytes) of the video chunk that was just downloaded
- time(ms) it took to download the video chunk
- The reward value calculated by the ABR algorithm for this chunk

Here are the available metrics received by ABR server from custom dash.js

```js
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

We use pensieve implementation and linear QoE for fastmpc.

> Note: MPC involves solving an optimization problem for each bitrate decision which maximizes the QoE metric over the next 5 video chunks. The MPC [51] paper describes a method, fastMPC, which precomputes the solution to this optimization problem for a quantized set of input values (e.g., buffer size, throughput prediction, etc.). 
> Because the implementation of fastMPC is not publicly available, we implemented MPC using our ABR server as follows. 
> For each bitrate decision, we solve the optimization problem exactly on the ABR server by enumerating all possibilities for the next 5 chunks. 
> We found that the computation takes at most 27 ms for 6 bitrate levels and has negligible impact on QoE.
> -- [Pensieve](http://web.mit.edu/pensieve/)

## Server

Ideally, we can simply keep the video server and tcpdump running. We can always filter packets later.

### Prepare video

The template `video_index.html` is a dummy page, only providing the modified `dash.js`.

The client side script will access `videos/manifest.mpd` url to start the video player and initialize ABR server locally.

#### Precompute MPC table

For this experiment, we precompute the table for MPC algorithm according to the video, as specified in the paper.

- Generate `video_config.json`
```sh
python generate_video_config.py {manifest.mpd} {video_directory}
```
- Put the file in the `../client/abr_server/`

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