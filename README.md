# Measurement pipeline

Scripts for running ABR streaming tests between mobile device and remote video server.

## Client

Require android device.

- Install Termux. All client side commands are executed inside termux shell
- Install dependency in Termux and set up repo
```sh
# Allow termux to access download folder
termux-setup-storage
# NOTE: better restart Termux
pkg update
pkg upgrade
# NOTE: unsure if pip prepackaged
pip install selenium, numpy
```
- Run experiment
```sh
python run_video.py {abr} {}
```

## Acknowledgement

ABR algorithms and dash.js are modified from [Pensieve](http://web.mit.edu/pensieve/) repository.