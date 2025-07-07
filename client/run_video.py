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

# Run in termux shell

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
    chrome_options.add_argument("--enable-logging")
    
    # Allow autoplay in headless mode
    chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    
    # Set preferences to allow autoplay
    chrome_options.add_experimental_option("prefs", {
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
        "profile.default_content_setting_values.durable_storage": 2
    })

    return chrome_options

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Watch and save video with specified transport protocol')
    # parser.add_argument('protocol', choices=['tcp', 'quic'], 
    #                    help='Transport protocol to use (tcp or quic)')
    args = parser.parse_args()

    # NOTE: testing
    args.protocol = "tcp"
    run_time = 200 # seconds
    
    # Setup ABR algorithm server
    abr_algo = "fastMPC"
    exp_id = "0"
    command = 'exec /data/data/com.termux/files/usr/bin/python ./rl_server/mpc_server.py ' + exp_id
    print(f"Starting MPC server with command: {command}")
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, bufsize=1, universal_newlines=True)
    sleep(2)

    # Check if the process is still running
    if proc.poll() is None:
        print("MPC server started successfully")
        
        # Verify the server is listening on port 8333
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', 8333))
            sock.close()
            if result == 0:
                print("MPC server is listening on port 8333")
            else:
                print("WARNING: MPC server is not listening on port 8333")
        except Exception as e:
            print(f"Error checking port 8333: {e}")
    else:
        # Process has terminated, get the output
        stdout, stderr = proc.communicate()
        print(f"MPC server failed to start!")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")
        print("Exiting...")
        exit(1)

    # Setup Chrome options based on protocol
    chrome_options = setup_chrome_options(args.protocol)
    
    # Setup Chrome driver
    # service = Service("/opt/homebrew/bin/chromedriver")
    service = Service("/data/data/com.termux/files/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_script_timeout(180)  # up to 3 minutes for async JS
    
    # Get target URL based on protocol
    # NOTE: testing
    # target_url = get_target_url(args.protocol)
    # target_url = "http://45.76.170.255:5201/index.html"
    target_url = "http://45.76.170.255:5201/myindex_fastMPC.html"
    
    # Navigate & load page
    driver.set_page_load_timeout(10)
    driver.get(target_url)
    
    # Add JavaScript debugging to see what's happening with dash.js
    debug_script = """
    // Override console.log to capture all logs
    var originalLog = console.log;
    console.log = function() {
        originalLog.apply(console, arguments);
        // Also log to a global variable for us to access
        if (!window.dashDebugLogs) window.dashDebugLogs = [];
        window.dashDebugLogs.push(Array.prototype.slice.call(arguments).join(' '));
    };
    
    // Monitor network requests to port 8333
    var originalFetch = window.fetch;
    window.fetch = function(url, options) {
        console.log('FETCH REQUEST:', url, options);
        return originalFetch.apply(this, arguments).then(function(response) {
            console.log('FETCH RESPONSE:', url, response.status, response.statusText);
            return response;
        }).catch(function(error) {
            console.log('FETCH ERROR:', url, error);
            throw error;
        });
    };
    
    // Monitor XMLHttpRequest to port 8333
    var originalXHROpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url, async, user, password) {
        console.log('XHR REQUEST:', method, url);
        return originalXHROpen.apply(this, arguments);
    };
    
    var originalXHRSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(data) {
        console.log('XHR SEND:', data);
        return originalXHRSend.apply(this, arguments);
    };
    
    // Monitor dash.js events
    if (window.dashjs && window.dashjs.MediaPlayer) {
        console.log('Dash.js found, version:', window.dashjs.VERSION || 'unknown');
        
        // Try to get player info
        try {
            var player = window.dashjs.MediaPlayer().create();
            console.log('Player created:', player);
            
            // Monitor player events
            if (player.on) {
                player.on('ready', function() { console.log('Player ready'); });
                player.on('play', function() { console.log('Player play'); });
                player.on('pause', function() { console.log('Player pause'); });
                player.on('error', function(e) { console.log('Player error:', e); });
                player.on('fragmentLoadingCompleted', function(e) { console.log('Fragment loaded:', e); });
                player.on('qualityChanged', function(e) { console.log('Quality changed:', e); });
            }
        } catch (e) {
            console.log('Error creating player:', e);
        }
    } else {
        console.log('Dash.js not found');
    }
    
    console.log('Dash.js debugging enabled');
    """
    
    driver.execute_script(debug_script)
    
    # Wait a bit for the page to load and dash.js to initialize
    sleep(5)
    
    # Check dash.js logs
    logs = driver.execute_script("return window.dashDebugLogs || [];")
    print("Dash.js logs:")
    for log in logs:
        print(f"  {log}")
    
    # Check if dash.js player is initialized
    player_status = driver.execute_script("""
        try {
            if (window.dashjs && window.dashjs.MediaPlayer) {
                // In dash.js 2.3.0, we need to get the player differently
                var player = null;
                if (window.dashjs.MediaPlayer().getAllMediaPlayers) {
                    var players = window.dashjs.MediaPlayer().getAllMediaPlayers();
                    if (players.length > 0) {
                        player = players[0];
                    }
                } else {
                    // Fallback for older versions
                    player = window.dashjs.MediaPlayer().create();
                }
                
                if (player) {
                    return {
                        isReady: player.isReady ? player.isReady() : 'unknown',
                        isPlaying: player.isPlaying ? player.isPlaying() : 'unknown',
                        currentTime: player.time ? player.time() : 'unknown',
                        duration: player.duration ? player.duration() : 'unknown',
                        abrAlgorithm: player.getAbrAlgorithm ? player.getAbrAlgorithm() : 'unknown',
                        currentQuality: player.getTopQualityIndexFor ? player.getTopQualityIndexFor('video') : 'unknown',
                        bufferLength: player.getBufferLength ? player.getBufferLength('video') : 'unknown'
                    };
                }
            }
            return { error: 'dashjs not found or player not initialized' };
        } catch (e) {
            return { error: 'JavaScript error: ' + e.message };
        }
    """)
    print(f"Player status: {player_status}")
    
    # Also check the video element directly
    video_status = driver.execute_script("""
        var video = document.getElementById('videoPlayer');
        if (video) {
            return {
                src: video.src,
                currentSrc: video.currentSrc,
                readyState: video.readyState,
                networkState: video.networkState,
                paused: video.paused,
                currentTime: video.currentTime,
                duration: video.duration,
                buffered: video.buffered ? video.buffered.length : 0,
                error: video.error ? video.error.message : null
            };
        }
        return { error: 'video element not found' };
    """)
    print(f"Video element status: {video_status}")
    
    # Start video playback programmatically to bypass autoplay restrictions
    print("Starting video playback...")
    start_result = driver.execute_script("""
        try {
            var video = document.getElementById('videoPlayer');
            if (video) {
                // Set muted to true to bypass autoplay restrictions
                video.muted = true;
                video.volume = 0;
                
                // Try to play the video
                var playPromise = video.play();
                if (playPromise !== undefined) {
                    playPromise.then(function() {
                        console.log('Video started playing successfully');
                    }).catch(function(error) {
                        console.log('Video play failed:', error);
                        // Try again with a different approach
                        setTimeout(function() {
                            video.play().catch(function(e) {
                                console.log('Second play attempt failed:', e);
                            });
                        }, 1000);
                    });
                }
                return { success: true, message: 'Play command sent' };
            }
            return { error: 'Video element not found' };
        } catch (e) {
            return { error: 'Failed to start video: ' + e.message };
        }
    """)
    print(f"Video start result: {start_result}")
    
    # Wait a bit for the video to start and try again if needed
    sleep(3)
    
    # Check if video is actually playing
    playback_status = driver.execute_script("""
        var video = document.getElementById('videoPlayer');
        if (video) {
            return {
                paused: video.paused,
                currentTime: video.currentTime,
                readyState: video.readyState,
                networkState: video.networkState
            };
        }
        return { error: 'Video element not found' };
    """)
    print(f"Playback status after start: {playback_status}")
    
    # If still paused, try one more time
    if playback_status.get('paused', True):
        print("Video still paused, trying again...")
        driver.execute_script("""
            var video = document.getElementById('videoPlayer');
            if (video) {
                video.muted = true;
                video.volume = 0;
                video.play().catch(function(e) {
                    console.log('Final play attempt failed:', e);
                });
            }
        """)
        sleep(2)
    
    # Monitor the video playback and ABR decisions during the test
    print("Starting video playback monitoring...")
    for i in range(0, run_time, 10):  # Check every 10 seconds
        sleep(10)
        
        # Get current logs
        current_logs = driver.execute_script("return window.dashDebugLogs || [];")
        new_logs = current_logs[len(logs):]  # Get only new logs
        logs = current_logs
        
        if new_logs:
            print(f"New logs at {i+10}s:")
            for log in new_logs:
                print(f"  {log}")
        
        # Check player status
        current_status = driver.execute_script("""
            try {
                if (window.dashjs && window.dashjs.MediaPlayer) {
                    // In dash.js 2.3.0, we need to get the player differently
                    var player = null;
                    if (window.dashjs.MediaPlayer().getAllMediaPlayers) {
                        var players = window.dashjs.MediaPlayer().getAllMediaPlayers();
                        if (players.length > 0) {
                            player = players[0];
                        }
                    } else {
                        // Fallback for older versions
                        player = window.dashjs.MediaPlayer().create();
                    }
                    
                    if (player) {
                        return {
                            isReady: player.isReady ? player.isReady() : 'unknown',
                            isPlaying: player.isPlaying ? player.isPlaying() : 'unknown',
                            currentTime: player.time ? player.time() : 'unknown',
                            duration: player.duration ? player.duration() : 'unknown',
                            abrAlgorithm: player.getAbrAlgorithm ? player.getAbrAlgorithm() : 'unknown',
                            currentQuality: player.getTopQualityIndexFor ? player.getTopQualityIndexFor('video') : 'unknown',
                            bufferLength: player.getBufferLength ? player.getBufferLength('video') : 'unknown'
                        };
                    }
                }
                return { error: 'no player found' };
            } catch (e) {
                return { error: 'JavaScript error: ' + e.message };
            }
        """)
        print(f"Status at {i+10}s: {current_status}")
        
        # Check if video is stuck
        if current_status.get('isPlaying') == False and i > 30:
            print("WARNING: Video appears to be stuck!")
            break
    
    # Cleanup
    print("quitting webdriver")
    driver.quit()

    # Cleanup ABR algorithm server
    print("terminating abr server")
    proc.terminate()
    proc.wait()

if __name__ == "__main__":
    main()
