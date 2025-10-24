import argparse
import atexit
import base64
import csv
import json
import os
import signal
import socket
import subprocess
import sys
import time
from time import sleep

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

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
VIDEO_SERVER_HOST = "vodtest.local"
DURATION = 660


def load_js_file(filename):
    # Load a JavaScript file from the js directory and return its contents as a string.
    # js_dir = os.path.join(os.path.dirname(__file__), "js")
    # file_path = os.path.join(js_dir, filename)
    try:
        with open(filename, "r") as f:
            return f.read()
    except Exception as e:
        raise Exception(f"Error loading JavaScript file {filename}: {e}")


def setup_chrome_options(protocol, server_ip):
    """Setup Chrome options based on transport protocol"""
    chrome_options = Options()

    # Disable QUIC (HTTP/3)
    if protocol == "tcp":
        chrome_options.add_argument("--disable-quic")
        chrome_options.add_argument("--disable-features=HTTP3")
        chrome_options.add_argument("--enable-features=NetworkService,AllowHTTP2")

    chrome_options.add_argument("--disable-http-cache")  # Optional for testing
    chrome_options.add_argument(
        f"--host-resolver-rules=MAP {VIDEO_SERVER_HOST} {server_ip}"
    )

    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--ignore-ssl-errors")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--headless=new")

    # Allow autoplay in headless mode
    chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")

    # Set preferences to allow autoplay
    # chrome_options.add_experimental_option(
    #     "prefs",
    #     {
    #         "profile.default_content_setting_values.media_stream_mic": 1,
    #         "profile.default_content_setting_values.media_stream_camera": 1,
    #         "profile.default_content_setting_values.geolocation": 1,
    #         "profile.default_content_settings.popups": 0,
    #         "profile.managed_default_content_settings.images": 2,
    #         "profile.default_content_setting_values.notifications": 2,
    #         "profile.default_content_setting_values.media_stream": 2,
    #         "profile.default_content_setting_values.plugins": 1,
    #         "profile.default_content_setting_values.popups": 2,
    #         "profile.default_content_setting_values.geolocation": 2,
    #         "profile.default_content_setting_values.automatic_downloads": 1,
    #         "profile.default_content_setting_values.mixed_script": 1,
    #         "profile.default_content_setting_values.media_stream_mic": 2,
    #         "profile.default_content_setting_values.media_stream_camera": 2,
    #         "profile.default_content_setting_values.protocol_handlers": 2,
    #         "profile.default_content_setting_values.midi_sysex": 2,
    #         "profile.default_content_setting_values.push_messaging": 2,
    #         "profile.default_content_setting_values.ssl_cert_decisions": 2,
    #         "profile.default_content_setting_values.metro_switch_to_desktop": 2,
    #         "profile.default_content_setting_values.protected_media_identifier": 2,
    #         "profile.default_content_setting_values.app_banner": 2,
    #         "profile.default_content_setting_values.site_engagement": 2,
    #         "profile.default_content_setting_values.durable_storage": 2,
    #     },
    # )

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
        default="127.0.0.1",
        help="Server IP address",
    )
    parser.add_argument(
        "-p",
        "--server_port",
        default=VIDEO_SERVER_PORT,
        help="Server port",
    )
    parser.add_argument(
        "-d",
        "--duration",
        default=DURATION,
        help="Duration",
    )

    args = parser.parse_args()

    # BBB sunflower 10min 34s
    run_time = args.duration

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

    # Selenium setup
    # ================================================
    chrome_options = setup_chrome_options(args.transport_protocol, args.server_ip)
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_script_timeout(180)  # up to 3 minutes for async JS

    # Get target URL
    target_url = f"https://{VIDEO_SERVER_HOST}:{args.server_port}/video_index.html"

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
            "abrAlgorithm": 0,  # Default: not sure what this is
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

    # Cleanup ABR algorithm server
    print("terminating abr server")
    proc.terminate()
    proc.wait()


if __name__ == "__main__":
    main()
    main()
