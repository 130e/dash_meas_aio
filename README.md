# Measurement pipeline

Scripts for running ABR streaming tests between mobile device and remote video server.

## Client

Require android device.

1. Install Termux. All future client side command are executed inside termux.
1. Install dependency in Ter  

```sh
pip install selenium, numpy

$ python run_video.py {abr} {run_time} {repeat time}
```

## Acknowledgement

ABR algorithms and dash.js are modified from [Pensieve](http://web.mit.edu/pensieve/) repository.