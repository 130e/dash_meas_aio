# Common constants and functions for ABR servers
# On importing this file, it loads the video configuration from the JSON file
# and sets all global variables

import sys
import json
import os

LOG_DIR = "./results"
LOG_PREFIX = "abr_server"

PORT = 8333

RANDOM_SEED = 42  # ensure reproducibility

# fastmpc
S_INFO = 5  # bit_rate, buffer_size, rebuffering_time, bandwidth_measurement, chunk_til_video_end
S_LEN = 8  # take how many frames in the past
MPC_FUTURE_CHUNK_COUNT = 5  # number of chunks to look ahead
BUFFER_NORM_FACTOR = 10.0  # normalize buffer size
M_IN_K = 1000.0
DEFAULT_QUALITY = 0  # default video quality without agent
SMOOTH_PENALTY = 1
CHUNK_LENGTH = 4  # TODO: this should not be hardcoded

# Video specific configuration - will be loaded from JSON file
VIDEO_BIT_RATE = []
TOTAL_VIDEO_CHUNKS = 0
CHUNK_TIL_VIDEO_END_CAP = 0.0
CHUNK_SIZES = {}

# Used by fastmpc
REBUF_PENALTY = 0  # 1 sec rebuffering -> this number of Mbps
# mpc with QoE_hd
BITRATE_REWARD = []
BITRATE_REWARD_MAP = {}


def load_video_config(config_file="video_config.json"):
    """Load video configuration from JSON file."""
    global VIDEO_BIT_RATE, BITRATE_REWARD, BITRATE_REWARD_MAP, TOTAL_VIDEO_CHUNKS, CHUNK_TIL_VIDEO_END_CAP, CHUNK_SIZES, REBUF_PENALTY

    try:
        with open(config_file, "r") as f:
            config = json.load(f)

        VIDEO_BIT_RATE = config.get("video_bit_rate", [])
        BITRATE_REWARD = config.get("bitrate_reward", [])
        BITRATE_REWARD_MAP = config.get("bitrate_reward_map", {})
        TOTAL_VIDEO_CHUNKS = config.get("total_video_chunks", 0)
        CHUNK_TIL_VIDEO_END_CAP = config.get("chunk_til_video_end_cap", 0.0)
        CHUNK_SIZES = config.get("chunk_sizes", {})
        REBUF_PENALTY = (
            max(VIDEO_BIT_RATE) / 1000
        )  # 1 sec rebuffering -> this number of Mbps

        print(
            f"Loaded video config: {len(VIDEO_BIT_RATE)} quality levels, {TOTAL_VIDEO_CHUNKS} chunks"
        )
        return True

    except FileNotFoundError:
        # Fall back to values for EnvivioDash3
        print(f"Config file {config_file} not found. Using default values.")
        VIDEO_BIT_RATE = [300, 750, 1200, 1850, 2850, 4300]  # Kbps
        BITRATE_REWARD = [1, 2, 3, 12, 15, 20]
        BITRATE_REWARD_MAP = {
            0: 0,
            300: 1,
            750: 2,
            1200: 3,
            1850: 12,
            2850: 15,
            4300: 20,
        }
        TOTAL_VIDEO_CHUNKS = 48
        CHUNK_TIL_VIDEO_END_CAP = 48.0
        REBUF_PENALTY = 4.3

        size_video1 = [
            2354772,
            2123065,
            2177073,
            2160877,
            2233056,
            1941625,
            2157535,
            2290172,
            2055469,
            2169201,
            2173522,
            2102452,
            2209463,
            2275376,
            2005399,
            2152483,
            2289689,
            2059512,
            2220726,
            2156729,
            2039773,
            2176469,
            2221506,
            2044075,
            2186790,
            2105231,
            2395588,
            1972048,
            2134614,
            2164140,
            2113193,
            2147852,
            2191074,
            2286761,
            2307787,
            2143948,
            1919781,
            2147467,
            2133870,
            2146120,
            2108491,
            2184571,
            2121928,
            2219102,
            2124950,
            2246506,
            1961140,
            2155012,
            1433658,
        ]
        size_video2 = [
            1728879,
            1431809,
            1300868,
            1520281,
            1472558,
            1224260,
            1388403,
            1638769,
            1348011,
            1429765,
            1354548,
            1519951,
            1422919,
            1578343,
            1231445,
            1471065,
            1491626,
            1358801,
            1537156,
            1336050,
            1415116,
            1468126,
            1505760,
            1323990,
            1383735,
            1480464,
            1547572,
            1141971,
            1498470,
            1561263,
            1341201,
            1497683,
            1358081,
            1587293,
            1492672,
            1439896,
            1139291,
            1499009,
            1427478,
            1402287,
            1339500,
            1527299,
            1343002,
            1587250,
            1464921,
            1483527,
            1231456,
            1364537,
            889412,
        ]
        size_video3 = [
            1034108,
            957685,
            877771,
            933276,
            996749,
            801058,
            905515,
            1060487,
            852833,
            913888,
            939819,
            917428,
            946851,
            1036454,
            821631,
            923170,
            966699,
            885714,
            987708,
            923755,
            891604,
            955231,
            968026,
            874175,
            897976,
            905935,
            1076599,
            758197,
            972798,
            975811,
            873429,
            954453,
            885062,
            1035329,
            1026056,
            943942,
            728962,
            938587,
            908665,
            930577,
            858450,
            1025005,
            886255,
            973972,
            958994,
            982064,
            830730,
            846370,
            598850,
        ]
        size_video4 = [
            668286,
            611087,
            571051,
            617681,
            652874,
            520315,
            561791,
            709534,
            584846,
            560821,
            607410,
            594078,
            624282,
            687371,
            526950,
            587876,
            617242,
            581493,
            639204,
            586839,
            601738,
            616206,
            656471,
            536667,
            587236,
            590335,
            696376,
            487160,
            622896,
            641447,
            570392,
            620283,
            584349,
            670129,
            690253,
            598727,
            487812,
            575591,
            605884,
            587506,
            566904,
            641452,
            599477,
            634861,
            630203,
            638661,
            538612,
            550906,
            391450,
        ]
        size_video5 = [
            450283,
            398865,
            350812,
            382355,
            411561,
            318564,
            352642,
            437162,
            374758,
            362795,
            353220,
            405134,
            386351,
            434409,
            337059,
            366214,
            360831,
            372963,
            405596,
            350713,
            386472,
            399894,
            401853,
            343800,
            359903,
            379700,
            425781,
            277716,
            400396,
            400508,
            358218,
            400322,
            369834,
            412837,
            401088,
            365161,
            321064,
            361565,
            378327,
            390680,
            345516,
            384505,
            372093,
            438281,
            398987,
            393804,
            331053,
            314107,
            255954,
        ]
        size_video6 = [
            181801,
            155580,
            139857,
            155432,
            163442,
            126289,
            153295,
            173849,
            150710,
            139105,
            141840,
            156148,
            160746,
            179801,
            140051,
            138313,
            143509,
            150616,
            165384,
            140881,
            157671,
            157812,
            163927,
            137654,
            146754,
            153938,
            181901,
            111155,
            153605,
            149029,
            157421,
            157488,
            143881,
            163444,
            179328,
            159914,
            131610,
            124011,
            144254,
            149991,
            147968,
            161857,
            145210,
            172312,
            167025,
            160064,
            137507,
            118421,
            112270,
        ]

        CHUNK_SIZES = {
            "video1": size_video1,
            "video2": size_video2,
            "video3": size_video3,
            "video4": size_video4,
            "video5": size_video5,
            "video6": size_video6,
        }
        return False

    except json.JSONDecodeError as e:
        print(f"Error parsing config file: {e}")
        return False


def get_chunk_size(quality, index):
    """Get chunk size for given quality and index."""
    if index < 0 or index >= TOTAL_VIDEO_CHUNKS:
        return 0

    # Map quality level to video key (inverted mapping)
    # Quality 0 = lowest bitrate, Quality N-1 = highest bitrate
    # Video1 = highest bitrate, VideoN = lowest bitrate
    num_qualities = len(VIDEO_BIT_RATE)
    if num_qualities == 0:
        return 0

    video_key = f"video{num_qualities - quality}"

    if video_key in CHUNK_SIZES and index < len(CHUNK_SIZES[video_key]):
        return CHUNK_SIZES[video_key][index]
    else:
        return 0


# Load configuration on import
load_video_config()
