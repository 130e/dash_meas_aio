# JavaScript Files for DASH Video Testing

This directory contains JavaScript files used by the `run_video.py` script for automated DASH video streaming testing.

## Files

### `debug.js`
Sets up comprehensive debugging and monitoring for dash.js video streaming:
- Overrides `console.log` to capture all browser logs
- Monitors network requests (fetch and XMLHttpRequest)
- Sets up dash.js player event listeners
- Captures logs in `window.dashDebugLogs` for Python access

### `player_status.js`
Checks the status of the dash.js media player:
- Detects dash.js version and player instance
- Returns player state (ready, playing, current time, duration)
- Provides ABR algorithm information
- Reports current quality level and buffer status

### `video_status.js`
Directly inspects the HTML video element:
- Checks video element properties (src, readyState, networkState)
- Reports playback state (paused, currentTime, duration)
- Monitors buffer status and any video errors

### `playback_control.js`
Controls video playback with autoplay bypass:
- Provides functions to start video playback
- Handles autoplay restrictions by muting video
- Includes retry logic for failed play attempts
- Exports functions via `window.videoControl` object

### `dash_player_setup.js`
Handles dash.js player initialization (replaces HTML inline script):
- Configurable player setup with different ABR algorithms
- Dynamic configuration based on algorithm type (MPC, BOLA, etc.)
- Buffer management and RL ABR settings
- Exports `window.setupDashPlayer()` function

## Usage

The JavaScript files are loaded by the Python script using the built-in `load_js_file()` function:

```python
# Load and execute a single file
debug_script = load_js_file('debug.js')
driver.execute_script(debug_script)

# Load player setup and configure
player_setup_script = load_js_file('dash_player_setup.js')
driver.execute_script(player_setup_script)

# Configure player with specific settings
player_config = {
    "manifestUrl": "/Manifest.mpd",
    "abrAlgorithm": 4,  # MPC
    "enableRLABR": True
}
setup_result = driver.execute_script(f"""
    return window.setupDashPlayer({json.dumps(player_config)});
""")
```