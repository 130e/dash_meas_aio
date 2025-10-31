import argparse
import json
import time
from time import sleep

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Run in termux shell
BIN_DIR = "/data/data/com.termux/files/usr/bin"
CHROMEDRIVER_PATH = BIN_DIR + "/chromedriver"

DEFAULT_VIDEO_SERVER_PORT = 5202
DEFAULT_VIDEO_SERVER_HOSTNAME = "vodtest.local"  # Don't need to change this
DEFAULT_DURATION = 660


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
        help="Server hostname (no need to be real)",
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
        default=DEFAULT_VIDEO_SERVER_PORT,
        help="Server port",
    )
    parser.add_argument(
        "-d",
        "--duration",
        default=DEFAULT_DURATION,
        help="Duration",
    )

    args = parser.parse_args()

    # BBB sunflower 10min 34s
    run_time = args.duration

    # Selenium setup
    chrome_options = setup_chrome_options(
        args.transport_protocol, args.hostname, args.server_ip
    )
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_script_timeout(180)  # up to 3 minutes for async JS

    # Get target URL
    target_url = f"https://{args.hostname}:{args.server_port}/index_dashv5.html"

    # Navigate & load page
    driver.set_page_load_timeout(10)
    driver.get(target_url)

    # Load dash.js player setup script
    # script_path = "js/playback_dashv5.js"
    # with open(script_path, "r") as f:
    #     player_setup_script = f.read()
    #     driver.execute_script(player_setup_script)
    player_setup_script = """
    window.player = dashjs.MediaPlayer().create();
    player.initialize(document.querySelector("#videoPlayer"), "chunks/manifest.mpd", true);
    
    // Set up QoE metrics collection
    window.qoeMetrics = {
        startupTime: performance.now(),
        rebuffering: {
            count: 0,
            totalDuration: 0,
            lastStarted: null
        },
        quality: {
            switches: [],
            current: null,
            timeSpent: {},
            lastChange: performance.now()
        },
        network: {
            requests: [],
            errors: 0
        },
        errors: [],
        samples: []
    };

    // Track startup time
    const video = document.querySelector("#videoPlayer");
    video.addEventListener('playing', () => {
        if (!window.qoeMetrics.firstPlaying) {
            window.qoeMetrics.firstPlaying = performance.now();
            window.qoeMetrics.startupDelay = window.qoeMetrics.firstPlaying - window.qoeMetrics.startupTime;
        }
    });

    // Track rebuffering
    video.addEventListener('waiting', () => {
        if (!window.qoeMetrics.rebuffering.lastStarted) {
            window.qoeMetrics.rebuffering.lastStarted = performance.now();
            window.qoeMetrics.rebuffering.count++;
        }
    });
    
    video.addEventListener('playing', () => {
        if (window.qoeMetrics.rebuffering.lastStarted) {
            const duration = performance.now() - window.qoeMetrics.rebuffering.lastStarted;
            window.qoeMetrics.rebuffering.totalDuration += duration;
            window.qoeMetrics.rebuffering.lastStarted = null;
        }
    });

    // Track quality changes
    player.on(dashjs.MediaPlayer.events.QUALITY_CHANGE_RENDERED, (e) => {
        const now = performance.now();
        const newQuality = e.newQuality;
        const bitrateList = player.getBitrateInfoListFor('video');
        const newBitrate = bitrateList[newQuality] ? bitrateList[newQuality].bitrate / 1000 : null;
        
        if (window.qoeMetrics.quality.current !== null) {
            const duration = now - window.qoeMetrics.quality.lastChange;
            window.qoeMetrics.quality.timeSpent[window.qoeMetrics.quality.current] = 
                (window.qoeMetrics.quality.timeSpent[window.qoeMetrics.quality.current] || 0) + duration;
        }
        
        window.qoeMetrics.quality.switches.push({
            timestamp: now,
            from: window.qoeMetrics.quality.current,
            to: newQuality,
            bitrate: newBitrate
        });
        
        window.qoeMetrics.quality.current = newQuality;
        window.qoeMetrics.quality.lastChange = now;
    });

    // Track errors
    video.addEventListener('error', (e) => {
        window.qoeMetrics.errors.push({
            timestamp: performance.now(),
            error: e.error,
            message: e.message
        });
    });

    // Initialize current quality
    window.qoeMetrics.quality.current = player.getQualityFor('video');
    """
    driver.execute_script(player_setup_script)

    # wait a bit
    sleep(5)

    # Initialize metrics storage
    all_metrics = []
    start_time = time.time()

    # Collect metrics every X secs
    for i in range(0, run_time, 1):
        print(f"Logging time:{i}/{run_time}s")

        # Collect current metrics
        metrics = driver.execute_script("""
            const video = document.getElementById('videoPlayer');
            const bufferLevel = player.getDashMetrics().getCurrentBufferLevel('video');
            const bitrateList = player.getBitrateInfoListFor('video');
            const currentQuality = player.getQualityFor('video');
            const currentBitrate = bitrateList[currentQuality] ? bitrateList[currentQuality].bitrate / 1000 : null;
            
            // Get video playback quality if available
            let playbackQuality = {};
            if (video.getVideoPlaybackQuality) {
                const quality = video.getVideoPlaybackQuality();
                playbackQuality = {
                    droppedFrames: quality.droppedVideoFrames,
                    totalFrames: quality.totalVideoFrames
                };
            }
            
            // Collect current sample
            const sample = {
                timestamp: performance.now(),
                playback_time: video.currentTime,
                buffer_level: bufferLevel,
                current_bitrate: currentBitrate,
                resolution: {
                    width: video.videoWidth,
                    height: video.videoHeight
                },
                playback_quality: playbackQuality
            };
            
            window.qoeMetrics.samples.push(sample);
            
            return {
                current: sample,
                qoeMetrics: window.qoeMetrics
            };
        """)

        # Store metrics with timestamp
        all_metrics.append({"timestamp": time.time() - start_time, "metrics": metrics})

        print("Playback time:", metrics["current"]["playback_time"])
        print("Buffer level:", metrics["current"]["buffer_level"])
        print("Current bitrate:", metrics["current"]["current_bitrate"], "kbps")
        print("Resolution:", metrics["current"]["resolution"])
        print()

        sleep(10)

    # Save all metrics to JSON file
    exp_id = args.exp_id
    output_file = f"qoe_metrics_{exp_id}_{int(time.time())}.json"
    print(f"Saving metrics to {output_file}")
    with open(output_file, "w") as f:
        json.dump(
            {
                "experiment_info": {
                    "id": args.exp_id,
                    "transport_protocol": args.transport_protocol,
                    "server_hostname": args.hostname,
                    "server_ip": args.server_ip,
                    "server_port": args.server_port,
                    "duration": args.duration,
                    "start_time": start_time,
                },
                "metrics": all_metrics,
            },
            f,
            indent=2,
        )

    # Cleanup
    print("quitting webdriver")
    driver.quit()


if __name__ == "__main__":
    main()
