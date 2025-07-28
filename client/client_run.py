import time
import csv
import base64
import json
import os
import sys
import subprocess
from time import sleep
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import socket
import signal
import atexit

# Run in termux shell
BIN_DIR = "/data/data/com.termux/files/usr/bin"
PYTHON_PATH = BIN_DIR + "/python"
CHROMEDRIVER_PATH = BIN_DIR + "/chromedriver"

DEBUG_SCRIPT_PATH = "js/debug.js"
PLAYER_SETUP_SCRIPT_PATH = "js/dash_player_setup.js"
PLAYER_STATUS_SCRIPT_PATH = "js/player_status.js"
PLAYBACK_CONTROL_SCRIPT_PATH = "js/playback_control.js"
VIDEO_STATUS_SCRIPT_PATH = "js/video_status.js"

ABR_PORT = 8333
VIDEO_SERVER_PORT = 5202

# Global variable to store tcpdump process
tcpdump_process = None


def load_js_file(filename):
    # Load a JavaScript file from the js directory and return its contents as a string.
    # js_dir = os.path.join(os.path.dirname(__file__), "js")
    # file_path = os.path.join(js_dir, filename)
    try:
        with open(filename, "r") as f:
            return f.read()
    except Exception as e:
        raise Exception(f"Error loading JavaScript file {filename}: {e}")


def start_tcpdump(interface="any", port=None, output_file=None, exp_id="0"):
    """
    Start tcpdump to capture network traffic.

    Args:
        interface (str): Network interface to capture (default: "any")
        port (int): Specific port to filter (optional)
        output_file (str): Output file path (optional)
        exp_id (str): Experiment ID for naming files

    Returns:
        subprocess.Popen: tcpdump process object
    """
    global tcpdump_process

    # Create output directory if it doesn't exist
    output_dir = f"captures/exp_{exp_id}"
    os.makedirs(output_dir, exist_ok=True)

    # Generate output filename if not provided
    if output_file is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = f"{output_dir}/tcpdump_{timestamp}.pcap"

    # Build tcpdump command
    cmd = ["tcpdump"]

    # Interface
    cmd.extend(["-i", interface])

    # Port filter
    if port:
        cmd.extend(["port", str(port)])

    # Truncate packets to 96 bytes
    cmd.extend(["-s", "96"])

    # Output file
    cmd.extend(["-w", output_file])

    # File size rollover
    cmd.extend(["-C", "1000"])

    try:
        print(f"Starting tcpdump with command: {' '.join(cmd)}")
        tcpdump_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,  # Create new process group
        )

        # Wait a moment to ensure tcpdump starts
        sleep(1)

        if tcpdump_process.poll() is None:
            print(f"tcpdump started successfully, capturing to: {output_file}")
            return tcpdump_process, output_file
        else:
            stdout, stderr = tcpdump_process.communicate()
            print(f"tcpdump failed to start!")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return None, None

    except Exception as e:
        print(f"Error starting tcpdump: {e}")
        return None, None


def stop_tcpdump():
    """Stop the tcpdump process gracefully."""
    global tcpdump_process

    if tcpdump_process and tcpdump_process.poll() is None:
        try:
            # Send SIGTERM to the process group
            os.killpg(os.getpgid(tcpdump_process.pid), signal.SIGTERM)

            # Wait for graceful termination
            try:
                tcpdump_process.wait(timeout=5)
                print("tcpdump stopped gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't stop gracefully
                os.killpg(os.getpgid(tcpdump_process.pid), signal.SIGKILL)
                print("tcpdump force killed")

        except Exception as e:
            print(f"Error stopping tcpdump: {e}")
            # Try to terminate the process directly
            try:
                tcpdump_process.terminate()
                tcpdump_process.wait(timeout=2)
            except:
                tcpdump_process.kill()


def cleanup_tcpdump():
    """Cleanup function to ensure tcpdump is stopped on exit."""
    stop_tcpdump()


# Register cleanup function
atexit.register(cleanup_tcpdump)


def setup_chrome_options(protocol):
    """Setup Chrome options based on transport protocol"""
    chrome_options = Options()
    # TCP-specific options from tcp_selenium.py
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--ignore-ssl-errors")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--headless")
    # chrome_options.add_argument("--enable-logging")

    # Allow autoplay in headless mode
    chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")

    # Set preferences to allow autoplay
    chrome_options.add_experimental_option(
        "prefs",
        {
            "profile.default_content_setting_values.media_stream_mic": 1,
            "profile.default_content_setting_values.media_stream_camera": 1,
            "profile.default_content_setting_values.geolocation": 1,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.media_stream": 2,
            "profile.default_content_setting_values.plugins": 1,
            "profile.default_content_setting_values.popups": 2,
            "profile.default_content_setting_values.geolocation": 2,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "profile.default_content_setting_values.mixed_script": 1,
            "profile.default_content_setting_values.media_stream_mic": 2,
            "profile.default_content_setting_values.media_stream_camera": 2,
            "profile.default_content_setting_values.protocol_handlers": 2,
            "profile.default_content_setting_values.midi_sysex": 2,
            "profile.default_content_setting_values.push_messaging": 2,
            "profile.default_content_setting_values.ssl_cert_decisions": 2,
            "profile.default_content_setting_values.metro_switch_to_desktop": 2,
            "profile.default_content_setting_values.protected_media_identifier": 2,
            "profile.default_content_setting_values.app_banner": 2,
            "profile.default_content_setting_values.site_engagement": 2,
            "profile.default_content_setting_values.durable_storage": 2,
        },
    )

    return chrome_options


def main():
    parser = argparse.ArgumentParser(description="Run video with ABR algorithm")
    parser.add_argument(
        "-i",
        "--exp_id",
        default="0",
        help="Experiment ID (any arbitrary string)",
    )
    parser.add_argument(
        "-a",
        "--abr",
        choices=["bola", "fastmpc"],
        default="bola",
        help="ABR algorithm to use (bola, fastmpc)",
    )
    parser.add_argument(
        "-t",
        "--transport_protocol",
        choices=["tcp", "quic"],
        default="tcp",
        help="Transport protocol to use (tcp or quic)",
    )
    parser.add_argument(
        "-s",
        "--server_ip",
        default="localhost",
        help="Server IP address",
    )
    parser.add_argument(
        "-p",
        "--server_port",
        default=VIDEO_SERVER_PORT,
        help="Server port",
    )

    # FIXME: using sudo causes chromium to crash; su doesn't have termux path
    # tcpdump
    # parser.add_argument(
    #     "-d",
    #     "--tcpdump",
    #     action="store_true",
    #     help="Enable tcpdump capture",
    # )
    # parser.add_argument(
    #     "--tcpdump_interface",
    #     default="any",
    #     help="Network interface for tcpdump (default: any)",
    # )
    # parser.add_argument(
    #     "--tcpdump_port",
    #     type=int,
    #     default=None,
    #     help="Specific port to capture with tcpdump (optional)",
    # )

    args = parser.parse_args()

    # BBB movie 193s
    run_time = 200

    # Setup ABR algorithm server
    # ================================================
    abr = args.abr.lower()
    command = f"exec {PYTHON_PATH} ./abr_server/{abr}_server.py {args.exp_id}"
    print(f"Starting ABR server with command: {command}")
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        bufsize=1,
        universal_newlines=True,
    )
    sleep(2)

    # ABR server check
    if proc.poll() is None:
        print("ABR server started successfully")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("localhost", ABR_PORT))
            sock.close()
            if result == 0:
                print(f"ABR server listening on port {ABR_PORT}")
            else:
                print(f"WARNING: server is not listening on port {ABR_PORT}")
        except Exception as e:
            print(f"Error checking port {ABR_PORT}: {e}")
    else:
        stdout, stderr = proc.communicate()
        print(f"ABR server failed to start!")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")
        exit(1)

    # Start tcpdump if requested
    # ================================================
    # FIXME: using sudo causes chromium to crash; su doesn't have termux path
    tcpdump_process = None
    tcpdump_output = None

    if args.tcpdump:
        print("Starting tcpdump capture...")
        tcpdump_process, tcpdump_output = start_tcpdump(
            interface=args.tcpdump_interface, port=args.tcpdump_port, exp_id=args.exp_id
        )

        if tcpdump_process is None:
            print("WARNING: tcpdump failed to start, continuing without capture")
        else:
            print(f"tcpdump capture started: {tcpdump_output}")

    # Selenium setup
    # ================================================
    chrome_options = setup_chrome_options(args.transport_protocol)
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_script_timeout(180)  # up to 3 minutes for async JS

    # Get target URL based on protocol
    server_ip = args.server_ip
    server_port = args.server_port
    if args.transport_protocol == "tcp":
        target_url = f"http://{server_ip}:{server_port}/video_index.html"
    elif args.transport_protocol == "quic":
        target_url = f"https://{server_ip}:{server_port}/video_index.html"
    else:
        raise ValueError(f"Invalid transport protocol: {args.transport_protocol}")

    # Navigate & load page
    driver.set_page_load_timeout(10)
    driver.get(target_url)

    # Load JavaScript debugging script
    debug_script = load_js_file(DEBUG_SCRIPT_PATH)
    driver.execute_script(debug_script)

    # Load dash.js player setup script
    player_setup_script = load_js_file(PLAYER_SETUP_SCRIPT_PATH)
    driver.execute_script(player_setup_script)

    # Wait a bit for the page to load and dash.js to initialize
    sleep(5)

    # Initialize the dash.js player with configuration
    print("Initializing dash.js player...")

    # Configure player based on ABR algorithm
    # ================================================
    if abr == "fastmpc":
        player_config = {
            "abrAlgorithm": 4,  # MPC
        }
    elif abr == "bola":
        player_config = {
            "abrAlgorithm": 6,  # BOLA
        }
    else:
        player_config = {
            "abrAlgorithm": 0,  # Default
        }

    # Call dash.js player setup function to pass config
    setup_result = driver.execute_script(
        f"""
        return window.setupDashPlayer({json.dumps(player_config)});
    """
    )
    print(f"Player setup result: {setup_result}")

    # (Optional) dash.js player logs
    # ================================================
    logs = driver.execute_script("return window.dashDebugLogs || [];")
    print("Dash.js logs:")
    for log in logs:
        print(f"  {log}")

    # Check if dash.js player is initialized
    player_status = driver.execute_script(load_js_file(PLAYER_STATUS_SCRIPT_PATH))
    print(f"Player status: {player_status}")

    # Also check the video element directly
    video_status = driver.execute_script(load_js_file(VIDEO_STATUS_SCRIPT_PATH))
    print(f"Video element status: {video_status}")

    # Start video playback
    # ================================================

    # Load playback control script
    driver.execute_script(load_js_file(PLAYBACK_CONTROL_SCRIPT_PATH))

    # Start video playback programmatically to bypass autoplay restrictions
    print("Starting video playback...")
    start_result = driver.execute_script("return window.videoControl.startPlayback();")
    print(f"Video start result: {start_result}")

    # Wait a bit for the video to start and try again if needed
    sleep(3)

    # Check if video is actually playing
    playback_status = driver.execute_script("return window.videoControl.getStatus();")
    print(f"Playback status after start: {playback_status}")

    # Monitor the video playback and ABR decisions during the test
    print("Starting video playback monitoring...")
    for i in range(0, run_time, 10):  # Check every 10 seconds
        sleep(10)

        # Get current logs
        current_logs = driver.execute_script("return window.dashDebugLogs || [];")
        new_logs = current_logs[len(logs) :]  # Get only new logs
        logs = current_logs

        if new_logs:
            print(f"New logs at {i+10}s:")
            for log in new_logs:
                print(f"  {log}")

        # FIXME: Bug returning None
        # Check player status
        # current_status = driver.execute_script(load_js_file("player_status.js"))
        # print(f"Status at {i+10}s: {current_status}")
        # Check if video is stuck
        # if current_status.get("isPlaying") == False and i > 30:
        #     print("WARNING: Video appears to be stuck!")
        #     break

    # Cleanup
    print("quitting webdriver")
    driver.quit()

    # Stop tcpdump if running
    if args.tcpdump and tcpdump_process:
        print("stopping tcpdump capture")
        stop_tcpdump()

    # Cleanup ABR algorithm server
    print("terminating abr server")
    proc.terminate()
    proc.wait()


if __name__ == "__main__":
    main()
