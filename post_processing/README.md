# Post-Processing Scripte for DASH Measurement Pipeline

This directory contains scripts for parsing and analyzing network measurement data collected during DASH streaming experiments.

## Overview

### `parse_ss.py` - SS Command Output Parser

Parses the output of the `ss` command (captured by `tcp_ss_monitor.sh`) into structured JSON format.

- Parses TCP socket statistic reported by `ss` including bbr, cubic internal parameters
- Throws an error if unknown fields are found in the ss output
- Save result into JSON

**Usage:**
```bash
python parse_ss.py <input.log> <output.json>
```

**Input Format:**
The parser expects the log format produced by `tcp_ss_monitor.sh` (2 lines per entry):
```
# Line 1
time:1754776664023490865
# Line 2
0      398200 [::ffff:140.82.23.101]:5202 [::ffff:137.25.146.88]:56512 timer:(on,078ms,0) ts sack bbr wscale:6,10 rto:237 rtt:36.788/3.994 ato:40 mss:1448 pmtu:1500 rcvmss:536 advmss:1448 cwnd:44 bytes_sent:128872 bytes_acked:66608 bytes_received:37 segs_out:90 segs_in:12 data_segs_out:89 data_segs_in:1 bbr:(bw:4762104bps,mrtt:30.236,pacing_gain:2.88672,cwnd_gain:2.88672) send 13854953bps lastsnd:2 lastrcv:132 lastack:3 pacing_rate 13609384bps delivery_rate 4762720bps delivered:47 busy:132ms unacked:43 rcv_space:14600 rcv_ssthresh:42230 notsent:335936 minrtt:30.236 snd_wnd:128192
```

- `rtt:<rtt>/<rttvar>`: rtt is the average round trip time, rttvar is the mean deviation of rtt, their units are millisecond
- `rto:<icsk_rto>`: tcp re-transmission timeout value, the unit is millisecond
- `backoff:<icsk_backoff>`: used for exponential backoff re-transmission, the actual re-transmission timeout value is `icsk_rto << icsk_backoff`

- `cwnd`: congestion window size (MSS)
- `app_limited`: connection isn’t sending because app has no data ready

- `snd_wnd`: This is actually the **rwnd** (bytes) advertised by remote host (after window scaling)
- `pacing_rate <pacing_rate>bps/<max_pacing_rate>bps`: the pacing rate and max pacing rate
- `delivery_rate <delivery_rate>bps`: the actual goodput
- `send`: egress bps. The actual sending rate, factoring everything

- `bbr`: BBR congestion control parameters
  - `bw`: estimated bottleneck bandwidth bps
  - `mrtt`: minimum RTT seen (ms)
  - `pacing_gain/cwnd_gain`: bbr internal gain values

- `cubic`: cubic congestion control parameters (TODO)


Refer to `ss` [manpage](https://man7.org/linux/man-pages/man8/ss.8.html) for more details.