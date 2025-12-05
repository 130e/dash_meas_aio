import argparse
import json
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

# Run in termux shell
BIN_DIR = "/data/data/com.termux/files/usr/bin"
CHROMEDRIVER_PATH = BIN_DIR + "/chromedriver"

DEFAULT_VIDEO_SERVER_PORT = 5202
DEFAULT_VIDEO_SERVER_HOSTNAME = "vodtest.local"
DEFAULT_DURATION = 635 * 2  # 2x duration


def setup_chrome_options(protocol, server_hostname, server_ip):
    """Setup Chrome options based on transport protocol"""
    chrome_options = Options()

    # Disable QUIC (HTTP/3)
    if protocol == "tcp":
        chrome_options.add_argument("--disable-quic")
        chrome_options.add_argument("--disable-features=HTTP3")
        chrome_options.add_argument("--enable-features=NetworkService,AllowHTTP2")

    chrome_options.add_argument("--disable-http-cache")  # Optional for testing
    chrome_options.add_argument(
        f"--host-resolver-rules=MAP {server_hostname} {server_ip}"
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
        type=str,
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
        "--hostname",
        default=DEFAULT_VIDEO_SERVER_HOSTNAME,
        type=str,
        help="Server hostname",
    )
    parser.add_argument(
        "-s",
        "--server_ip",
        default="127.0.0.1",
        type=str,
        help="Server IP address",
    )
    parser.add_argument(
        "-p",
        "--server_port",
        default=DEFAULT_VIDEO_SERVER_PORT,
        type=int,
        help="Server port",
    )
    parser.add_argument(
        "-d",
        "--duration",
        default=DEFAULT_DURATION,
        type=int,
        help="Maximum time this script would wait",
    )
    parser.add_argument(
        "--page_timeout",
        default=120,
        type=int,
        help="Maximum time to wait for page to load",
    )

    args = parser.parse_args()

    duration = args.duration
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_id = f"{args.exp_id}_{ts}"

    # Selenium setup
    chrome_options = setup_chrome_options(
        args.transport_protocol, args.hostname, args.server_ip
    )
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_script_timeout(120)

    # Get target URL
    target_url = f"https://{args.hostname}:{args.server_port}/index.html"

    # Navigate & load page
    driver.set_page_load_timeout(args.page_timeout)
    print(f"Navigating to {target_url}...")
    try:
        driver.get(target_url)
        print("Page loaded successfully")
    except Exception as e:
        print(f"Error loading page: {e}")
        driver.quit()
        return

    # Wait for page script to initialize (module scripts load asynchronously)
    print("Waiting for page script to initialize...")
    try:
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script(
                "return typeof window.dashPlaybackEnded !== 'undefined';"
            )
        )
        print("Page script initialized")
    except TimeoutException:
        print("Warning: Page script may not have initialized properly")
    except Exception as e:
        print(f"Error waiting for script initialization: {e}")

    # Wait for playback to end
    print("Waiting for playback to end...")
    try:
        WebDriverWait(driver, duration).until(
            lambda d: d.execute_script("return window.dashPlaybackEnded === true;")
        )
        print("Playback ended")
    except TimeoutException:
        print("Timeout reached while waiting for playback to end")
    except Exception as e:
        print(f"Error while waiting for playback to end: {e}")

    # Collect logs
    event_log = driver.execute_script("return window.dashEventLog;")
    event_log_path = f"captures/{exp_id}.json"

    # Cleanup
    print("Quitting webdriver")
    driver.quit()

    with open(event_log_path, "w") as f:
        json.dump(event_log, f, indent=2)
        print(f"Event log saved to {event_log_path}")


if __name__ == "__main__":
    main()
