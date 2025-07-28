#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
import base64
import urllib.parse
import sys
import os
import json
import time
import argparse
import logging
import csv

os.environ["CUDA_VISIBLE_DEVICES"] = ""

import numpy as np
import time
import itertools

from abr_cfg import *


CHUNK_COMBO_OPTIONS = []


def make_request_handler(input_dict):

    class Request_Handler(BaseHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            self.input_dict = input_dict
            self.log_file = input_dict["log_file"]
            self.csv_writer = input_dict["csv_writer"]
            # self.saver = input_dict['saver']
            self.s_batch = input_dict["s_batch"]
            # self.a_batch = input_dict['a_batch']
            # self.r_batch = input_dict['r_batch']
            BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

        def do_POST(self):
            content_length = int(self.headers["Content-Length"])
            post_data = json.loads(self.rfile.read(content_length))
            print(post_data)

            if "pastThroughput" in post_data:
                # @Hongzi: this is just the summary of throughput/quality at the end of the load
                # so we don't want to use this information to send back a new quality
                print("Summary: ", post_data)
            else:
                # option 1. reward for just quality
                # reward = post_data['lastquality']
                # option 2. combine reward for quality and rebuffer time
                #           tune up the knob on rebuf to prevent it more
                # reward = post_data['lastquality'] - 0.1 * (post_data['RebufferTime'] - self.input_dict['last_total_rebuf'])
                # option 3. give a fixed penalty if video is stalled
                #           this can reduce the variance in reward signal
                # reward = post_data['lastquality'] - 10 * ((post_data['RebufferTime'] - self.input_dict['last_total_rebuf']) > 0)

                # option 4. use the metric in SIGCOMM MPC paper
                rebuffer_time = float(
                    post_data["RebufferTime"] - self.input_dict["last_total_rebuf"]
                )

                # --linear reward--
                reward = (
                    VIDEO_BIT_RATE[post_data["lastquality"]] / M_IN_K
                    - REBUF_PENALTY * rebuffer_time / M_IN_K
                    - SMOOTH_PENALTY
                    * np.abs(
                        VIDEO_BIT_RATE[post_data["lastquality"]]
                        - self.input_dict["last_bit_rate"]
                    )
                    / M_IN_K
                )

                # --log reward--
                # log_bit_rate = np.log(VIDEO_BIT_RATE[post_data['lastquality']] / float(VIDEO_BIT_RATE[0]))
                # log_last_bit_rate = np.log(self.input_dict['last_bit_rate'] / float(VIDEO_BIT_RATE[0]))

                # reward = log_bit_rate \
                #          - 4.3 * rebuffer_time / M_IN_K \
                #          - SMOOTH_PENALTY * np.abs(log_bit_rate - log_last_bit_rate)

                # --hd reward--
                # reward = BITRATE_REWARD[post_data['lastquality']] \
                #         - 8 * rebuffer_time / M_IN_K - np.abs(BITRATE_REWARD[post_data['lastquality']] - BITRATE_REWARD_MAP[self.input_dict['last_bit_rate']])

                self.input_dict["last_bit_rate"] = VIDEO_BIT_RATE[
                    post_data["lastquality"]
                ]
                self.input_dict["last_total_rebuf"] = post_data["RebufferTime"]

                # retrieve previous state
                if len(self.s_batch) == 0:
                    state = [np.zeros((S_INFO, S_LEN))]
                else:
                    state = np.array(self.s_batch[-1], copy=True)

                # compute bandwidth measurement
                video_chunk_fetch_time = (
                    post_data["lastChunkFinishTime"] - post_data["lastChunkStartTime"]
                )
                video_chunk_size = post_data["lastChunkSize"]

                # compute number of video chunks left
                video_chunk_remain = (
                    TOTAL_VIDEO_CHUNKS - self.input_dict["video_chunk_coount"]
                )
                self.input_dict["video_chunk_coount"] += 1

                # dequeue history record
                state = np.roll(state, -1, axis=1)

                # this should be S_INFO number of terms
                try:
                    state[0, -1] = VIDEO_BIT_RATE[post_data["lastquality"]] / float(
                        np.max(VIDEO_BIT_RATE)
                    )
                    state[1, -1] = post_data["buffer"] / BUFFER_NORM_FACTOR
                    state[2, -1] = rebuffer_time / M_IN_K
                    state[3, -1] = (
                        float(video_chunk_size) / float(video_chunk_fetch_time) / M_IN_K
                    )  # kilo byte / ms
                    state[4, -1] = np.minimum(
                        video_chunk_remain, CHUNK_TIL_VIDEO_END_CAP
                    ) / float(CHUNK_TIL_VIDEO_END_CAP)
                except ZeroDivisionError:
                    # this should occur VERY rarely (1 out of 3000), should be a dash issue
                    # in this case we ignore the observation and roll back to an eariler one
                    if len(self.s_batch) == 0:
                        state = [np.zeros((S_INFO, S_LEN))]
                    else:
                        state = np.array(self.s_batch[-1], copy=True)

                # log wall_time, bit_rate, buffer_size, rebuffer_time, video_chunk_size, download_time, reward
                self.csv_writer.writerow(
                    [
                        time.time(),
                        VIDEO_BIT_RATE[post_data["lastquality"]],
                        post_data["buffer"],
                        rebuffer_time / M_IN_K,
                        video_chunk_size,
                        video_chunk_fetch_time,
                        reward,
                    ]
                )
                self.log_file.flush()

                # pick bitrate according to MPC
                # first get harmonic mean of last 5 bandwidths
                past_bandwidths = state[3, -5:]
                while past_bandwidths[0] == 0.0:
                    past_bandwidths = past_bandwidths[1:]
                # if ( len(state) < 5 ):
                #    past_bandwidths = state[3,-len(state):]
                # else:
                #    past_bandwidths = state[3,-5:]
                bandwidth_sum = 0
                for past_val in past_bandwidths:
                    bandwidth_sum += 1 / float(past_val)
                future_bandwidth = 1.0 / (bandwidth_sum / len(past_bandwidths))

                # future chunks length (try 4 if that many remaining)
                last_index = int(post_data["lastRequest"])
                future_chunk_length = MPC_FUTURE_CHUNK_COUNT
                if TOTAL_VIDEO_CHUNKS - last_index < 4:
                    future_chunk_length = TOTAL_VIDEO_CHUNKS - last_index

                # all possible combinations of 5 chunk bitrates (9^5 options)
                # iterate over list and for each, compute reward and store max reward combination
                max_reward = -100000000
                best_combo = ()
                start_buffer = float(post_data["buffer"])
                # start = time.time()
                for full_combo in CHUNK_COMBO_OPTIONS:
                    combo = full_combo[0:future_chunk_length]
                    # calculate total rebuffer time for this combination (start with start_buffer and subtract
                    # each download time and add 2 seconds in that order)
                    curr_rebuffer_time = 0
                    curr_buffer = start_buffer
                    bitrate_sum = 0
                    smoothness_diffs = 0
                    last_quality = int(post_data["lastquality"])
                    for position in range(0, len(combo)):
                        chunk_quality = combo[position]
                        index = (
                            last_index + position + 1
                        )  # e.g., if last chunk is 3, then first iter is 3+0+1=4
                        download_time = (
                            get_chunk_size(chunk_quality, index) / 1000000.0
                        ) / future_bandwidth  # this is MB/MB/s --> seconds
                        if curr_buffer < download_time:
                            curr_rebuffer_time += download_time - curr_buffer
                            curr_buffer = 0
                        else:
                            curr_buffer -= download_time
                        curr_buffer += CHUNK_LENGTH

                        # linear reward
                        bitrate_sum += VIDEO_BIT_RATE[chunk_quality]
                        smoothness_diffs += abs(
                            VIDEO_BIT_RATE[chunk_quality] - VIDEO_BIT_RATE[last_quality]
                        )

                        # log reward
                        # log_bit_rate = np.log(VIDEO_BIT_RATE[chunk_quality] / float(VIDEO_BIT_RATE[0]))
                        # log_last_bit_rate = np.log(VIDEO_BIT_RATE[last_quality] / float(VIDEO_BIT_RATE[0]))
                        # bitrate_sum += log_bit_rate
                        # smoothness_diffs += abs(log_bit_rate - log_last_bit_rate)

                        # hd reward
                        # bitrate_sum += BITRATE_REWARD[chunk_quality]
                        # smoothness_diffs += abs(
                        #     BITRATE_REWARD[chunk_quality] - BITRATE_REWARD[last_quality]
                        # )

                        last_quality = chunk_quality
                    # compute reward for this combination (one reward per 5-chunk combo)
                    # bitrates are in Mbits/s, rebuffer in seconds, and smoothness_diffs in Mbits/s

                    # linear reward
                    reward = (
                        (bitrate_sum / 1000.0)
                        - (REBUF_PENALTY * curr_rebuffer_time)
                        - (smoothness_diffs / 1000.0)
                    )

                    # log reward
                    # reward = (bitrate_sum) - (REBUF_PENALTY*curr_rebuffer_time) - (smoothness_diffs)

                    # hd reward
                    # reward = bitrate_sum - (8 * curr_rebuffer_time) - (smoothness_diffs)

                    if reward > max_reward:
                        max_reward = reward
                        best_combo = combo
                # send data to html side (first chunk of best combo)
                send_data = (
                    0  # no combo had reward better than -1000000 (ERROR) so send 0
                )
                if best_combo != ():  # some combo was good
                    send_data = str(best_combo[0])

                end = time.time()
                # print("TOOK: " + str(end-start))

                end_of_video = False
                if post_data["lastRequest"] == TOTAL_VIDEO_CHUNKS:
                    send_data = "REFRESH"
                    end_of_video = True
                    self.input_dict["last_total_rebuf"] = 0
                    self.input_dict["last_bit_rate"] = DEFAULT_QUALITY
                    self.input_dict["video_chunk_coount"] = 0
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

                # record [state, action, reward]
                # put it here after training, notice there is a shift in reward storage

                if end_of_video:
                    self.s_batch = [np.zeros((S_INFO, S_LEN))]
                else:
                    self.s_batch.append(state)

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

    np.random.seed(RANDOM_SEED)

    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    # make chunk combination options
    num_qualities = len(VIDEO_BIT_RATE)
    for combo in itertools.product(range(num_qualities), repeat=5):
        CHUNK_COMBO_OPTIONS.append(combo)

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

        s_batch = [np.zeros((S_INFO, S_LEN))]

        last_bit_rate = DEFAULT_QUALITY
        last_total_rebuf = 0
        # need this storage, because observation only contains total rebuffering time
        # we compute the difference to get

        video_chunk_count = 0

        input_dict = {
            "log_file": log_file,
            "csv_writer": csv_writer,
            "last_bit_rate": last_bit_rate,
            "last_total_rebuf": last_total_rebuf,
            "video_chunk_coount": video_chunk_count,
            "s_batch": s_batch,
        }

        # interface to abr_rl server
        handler_class = make_request_handler(input_dict=input_dict)

        server_address = ("localhost", port)
        httpd = server_class(server_address, handler_class)
        print("Listening on port " + str(port))
        httpd.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("id", type=str)
    args = parser.parse_args()
    abr = "fastmpc"
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
