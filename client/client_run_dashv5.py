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
CHROMEDRIVER_PATH = BIN_DIR + "/chromedriver"

PLAYER_SETUP_SCRIPT_PATH = "js/playback_dashv5.js"

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

    # Load dash.js player setup script
    player_setup_script = load_js_file(PLAYER_SETUP_SCRIPT_PATH)
    driver.execute_script(player_setup_script)

    sleep(run_time)

    # Cleanup
    print("quitting webdriver")
    driver.quit()


if __name__ == "__main__":
    main()
    main()
