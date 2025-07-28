#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
import base64
import urllib.parse
import sys
import os
import logging
import json
import csv

from collections import deque
import numpy as np
import time
import argparse

from abr_cfg import *


def make_request_handler(input_dict):

    class Request_Handler(BaseHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            self.input_dict = input_dict
            self.log_file = input_dict["log_file"]
            self.csv_writer = input_dict["csv_writer"]
            BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

        def do_POST(self):
            content_length = int(self.headers["Content-Length"])
            post_data = json.loads(self.rfile.read(content_length))

            print(post_data)
            send_data = ""

            if "lastquality" in post_data:
                rebuffer_time = float(
                    post_data["RebufferTime"] - self.input_dict["last_total_rebuf"]
                )
                reward = (
                    VIDEO_BIT_RATE[post_data["lastquality"]] / M_IN_K
                    - REBUF_PENALTY
                    * (post_data["RebufferTime"] - self.input_dict["last_total_rebuf"])
                    / M_IN_K
                    - SMOOTH_PENALTY
                    * np.abs(
                        VIDEO_BIT_RATE[post_data["lastquality"]]
                        - self.input_dict["last_bit_rate"]
                    )
                    / M_IN_K
                )
                # reward = BITRATE_REWARD[post_data['lastquality']] \
                #         - 8 * rebuffer_time / M_IN_K - np.abs(BITRATE_REWARD[post_data['lastquality']] - BITRATE_REWARD_MAP[self.input_dict['last_bit_rate']])

                video_chunk_fetch_time = (
                    post_data["lastChunkFinishTime"] - post_data["lastChunkStartTime"]
                )
                video_chunk_size = post_data["lastChunkSize"]

                # log wall_time, bit_rate, buffer_size, rebuffer_time, video_chunk_size, download_time, reward
                self.csv_writer.writerow(
                    [
                        time.time(),
                        VIDEO_BIT_RATE[post_data["lastquality"]],
                        post_data["buffer"],
                        float(
                            post_data["RebufferTime"]
                            - self.input_dict["last_total_rebuf"]
                        )
                        / M_IN_K,
                        video_chunk_size,
                        video_chunk_fetch_time,
                        reward,
                    ]
                )
                self.log_file.flush()

                self.input_dict["last_total_rebuf"] = post_data["RebufferTime"]
                self.input_dict["last_bit_rate"] = VIDEO_BIT_RATE[
                    post_data["lastquality"]
                ]

                if post_data["lastRequest"] == TOTAL_VIDEO_CHUNKS:
                    send_data = "REFRESH"
                    self.input_dict["last_total_rebuf"] = 0
                    self.input_dict["last_bit_rate"] = DEFAULT_QUALITY
                    self.log_file.write(
                        "\n"
                    )  # so that in the log we know where video ends

            encoded_data = send_data.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", len(encoded_data))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(encoded_data)

        def do_GET(self):
            print("GOT REQ", file=sys.stderr)
            response = "console.log('here');"
            self.send_response(200)
            # self.send_header('Cache-Control', 'Cache-Control: no-cache, no-store, must-revalidate max-age=0')
            self.send_header("Cache-Control", "max-age=3000")
            self.send_header("Content-Length", len(response))
            self.end_headers()
            self.wfile.write(response.encode("utf-8"))

        def log_message(self, format, *args):
            return

    return Request_Handler


def run(server_class, port, log_file_path):

    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    with open(log_file_path, "w", newline="") as log_file:
        csv_writer = csv.writer(log_file)
        csv_writer.writerow(
            [
                "wall_time",
                "bit_rate",
                "buffer_size",
                "rebuffer_time",
                "video_chunk_size",
                "download_time",
                "reward",
            ]
        )

        last_bit_rate = DEFAULT_QUALITY
        last_total_rebuf = 0
        input_dict = {
            "log_file": log_file,
            "csv_writer": csv_writer,
            "last_bit_rate": last_bit_rate,
            "last_total_rebuf": last_total_rebuf,
        }

        handler_class = make_request_handler(input_dict=input_dict)

        server_address = ("localhost", port)
        httpd = server_class(server_address, handler_class)
        print("Listening on port " + str(port))
        httpd.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("id", type=str)
    args = parser.parse_args()
    abr = "bola"
    try:
        run(
            server_class=HTTPServer,
            port=PORT,
            log_file_path=f"{LOG_DIR}/{LOG_PREFIX}_{abr}_{args.id}.csv",
        )
    except KeyboardInterrupt:
        logging.debug("Keyboard interrupted.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
