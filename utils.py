import time
import random


def get_delta_ms(start, finish):
    diff = finish - start
    millis = diff.days * 24 * 60 * 60 * 1000
    millis += diff.seconds * 1000
    millis += diff.microseconds / 1000
    return millis


def get_time_h_m_s():
    strings = time.strftime("%Y,%m,%d,%H,%M,%S")
    t = strings.split(',')
    return "time: " + t[3] + ":" + t[4] + ":" + t[5]


def split_string(str, substr_count):
    substr_len = len(str) // substr_count
    for i in range(0, len(str), substr_len):
        yield str[i: i + substr_len]


def flip_biased_coin(p):
    return True if random.random() < p else False
