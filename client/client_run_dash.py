import argparse
import os
import json
import time
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from chrome_setup import CHROMEDRIVER_PATH, build_chrome_options

# Run in termux shell
DEFAULT_VIDEO_SERVER_PORT = 5202
DEFAULT_VIDEO_SERVER_HOSTNAME = "vodtest.local"
DEFAULT_DURATION = 635 * 2  # 2x duration
RERUN_DELAY_SECONDS = 10


def setup_chrome_options(protocol, server_hostname, server_ip):
    """Setup Chrome options based on transport protocol"""
    chrome_options = build_chrome_options(
        ignore_cert_errors=True,
        disable_quic=(protocol == "tcp"),
        host_resolver_map=f"{server_hostname} {server_ip}",
        autoplay=True,
    )
    chrome_options.add_argument("--disable-http-cache")  # Optional for testing
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")

    return chrome_options


def parse_args():
    parser = argparse.ArgumentParser(description="Run video with ABR algorithm")
    parser.add_argument(
        "-i",
        "--exp_id",
        default="0",
        type=str,
        help="Experiment ID (any arbitrary string)",
    )
    parser.add_argument(
        "-r",
        "--rerun",
        action="store_true",
        help="Enable infinite auto-rerun mode (5s between runs)",
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
    parser.add_argument(
        "--log_collection_interval",
        default=30,
        type=int,
        help="Interval in seconds for periodic log collection during playback",
    )
    return parser.parse_args()


def make_run_exp_id(base_exp_id, used_ids):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = f"{base_exp_id}_{ts}"
    if candidate not in used_ids:
        used_ids.add(candidate)
        return candidate

    suffix = 1
    while True:
        with_suffix = f"{candidate}_{suffix}"
        if with_suffix not in used_ids:
            used_ids.add(with_suffix)
            return with_suffix
        suffix += 1


def run_once(args, exp_id):
    print(f"Starting experiment run: {exp_id}")

    duration = args.duration

    # Selenium setup
    chrome_options = setup_chrome_options(
        args.transport_protocol, args.hostname, args.server_ip
    )
    service = Service(CHROMEDRIVER_PATH)
    driver = None
    event_log = []
    last_collected_index = 0
    status = "unknown_error"

    try:
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
            status = "page_load_error"
            return status

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

        log_collection_interval = args.log_collection_interval

        def collect_new_logs():
            """Collect new log entries since last collection"""
            nonlocal last_collected_index, event_log
            try:
                current_length = driver.execute_script(
                    "return window.dashEventLog.length;"
                )
                if current_length > last_collected_index:
                    new_count = current_length - last_collected_index
                    # Collect in small chunks to avoid timeout
                    chunk_size = 500
                    for start_idx in range(
                        last_collected_index, current_length, chunk_size
                    ):
                        end_idx = min(start_idx + chunk_size, current_length)
                        chunk = driver.execute_script(
                            f"return JSON.stringify(window.dashEventLog.slice({start_idx}, {end_idx}));"
                        )
                        if chunk:
                            event_log.extend(json.loads(chunk))
                    last_collected_index = current_length
                    print(
                        f"Collected {new_count} new log entries (total: {len(event_log)})"
                    )
            except Exception as e:
                print(f"Warning: Error during periodic log collection: {e}")

        # Wait for playback to end with periodic log collection
        print("Waiting for playback to end (collecting logs periodically)...")
        start_time = time.time()
        playback_ended = False

        try:
            while not playback_ended and (time.time() - start_time) < duration:
                # Check if playback ended
                try:
                    playback_ended = driver.execute_script(
                        "return window.dashPlaybackEnded === true;"
                    )
                except Exception:
                    pass

                # Collect logs periodically
                collect_new_logs()

                if not playback_ended:
                    time.sleep(log_collection_interval)

            if playback_ended:
                print("Playback ended")
                status = "success"
            else:
                print("Timeout reached while waiting for playback to end")
                status = "timeout"
        except Exception as e:
            print(f"Error while waiting for playback to end: {e}")
            status = "playback_wait_error"

        # Collect any remaining logs after playback ends
        print("Collecting final event logs...")
        driver.set_script_timeout(3600)  # Large timeout for final collection
        try:
            final_length = driver.execute_script("return window.dashEventLog.length;")
            if final_length > last_collected_index:
                remaining_count = final_length - last_collected_index
                print(f"Collecting {remaining_count} remaining log entries...")
                # Use small chunks for final collection
                chunk_size = 500
                for start_idx in range(last_collected_index, final_length, chunk_size):
                    end_idx = min(start_idx + chunk_size, final_length)
                    chunk = driver.execute_script(
                        f"return JSON.stringify(window.dashEventLog.slice({start_idx}, {end_idx}));"
                    )
                    if chunk:
                        event_log.extend(json.loads(chunk))
                print(f"Final log collection complete (total: {len(event_log)} entries)")
            else:
                print(f"All logs already collected (total: {len(event_log)} entries)")
        except Exception as e:
            print(f"Error during final log collection: {e}")
            # Try to get at least the count
            try:
                final_length = driver.execute_script("return window.dashEventLog.length;")
                print(
                    f"Warning: Could not collect all logs. Expected {final_length}, got {len(event_log)}"
                )
            except Exception:
                pass

        # Create captures directory if it doesn't exist
        os.makedirs("captures", exist_ok=True)
        event_log_path = f"captures/{exp_id}.json"
        print("Writing event log to file...")
        with open(event_log_path, "w") as f:
            json.dump(event_log, f, indent=2)
            print(f"Event log saved to {event_log_path}")
    except Exception as e:
        print(f"Unexpected error in run {exp_id}: {e}")
        status = "run_exception"
    finally:
        if driver is not None:
            print("Quitting webdriver")
            driver.quit()

    print(f"Experiment {exp_id} finished with status: {status}")
    return status


def main():
    args = parse_args()
    used_ids = set()

    if not args.rerun:
        run_exp_id = make_run_exp_id(args.exp_id, used_ids)
        run_once(args, run_exp_id)
        return

    print(
        f"Auto-rerun enabled: experiment will run continuously until interrupted (delay={RERUN_DELAY_SECONDS}s)"
    )
    run_count = 0
    try:
        while True:
            run_count += 1
            run_exp_id = make_run_exp_id(args.exp_id, used_ids)
            print(f"\n--- Run #{run_count} ---")
            run_once(args, run_exp_id)
            print(f"Sleeping {RERUN_DELAY_SECONDS}s before next run...")
            time.sleep(RERUN_DELAY_SECONDS)
    except KeyboardInterrupt:
        print("\nAuto-rerun interrupted by user. Exiting.")


if __name__ == "__main__":
    main()
