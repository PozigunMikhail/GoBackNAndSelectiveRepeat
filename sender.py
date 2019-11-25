import time
import datetime
import sys

from ipc_manager import IPCManager
from frame import Frame
from utils import split_string
from utils import get_time_h_m_s
from utils import flip_biased_coin
from utils import get_delta_ms
from transm_global_params import TransmissionProtocol
import transm_global_params


class Sender:
    def __init__(self, ipc_manager, transmission_protocol, verbose=False):
        self.ipc_manager_ = ipc_manager
        self.transmission_protocol_ = transmission_protocol
        if transmission_protocol == TransmissionProtocol.ALGORITHM_TYPE_GBN:
            if verbose:
                print("sender: GO BACK N")
        elif transmission_protocol == TransmissionProtocol.ALGORITHM_TYPE_SR:
            if verbose:
                print("sender: SELECTIVE REPEAT")
        self.VERBOSE = verbose

        self.total_sent_ = 0
        self.total_received_ack_ = 0

    def wait_for_connection(self):
        time_start = time.time()
        time_since_last_try = time.time()
        while time.time() - time_start < transm_global_params.CONNECTION_TIMEOUT:

            if time.time() - time_since_last_try > transm_global_params.CONNECTION_ESTABLISHMENT_INTERVAL:
                if self.VERBOSE:
                    print("sender: Trying to connect", get_time_h_m_s())
                frame = Frame(None, transm_global_params.ESTABLISH_CONNECTION_CODE, False, False)
                self.ipc_manager_.send_to_receiver(frame)
                time_since_last_try = time.time()

            ack = self.ipc_manager_.get_from_receiver()
            if ack is None:
                continue
            if ack.seq_num_ == transm_global_params.ESTABLISH_CONNECTION_CODE:
                if self.VERBOSE:
                    print("sender: Connection established", get_time_h_m_s())
                return True
        return False

    def send(self, data_list):
        if self.transmission_protocol_ == TransmissionProtocol.ALGORITHM_TYPE_GBN:
            return self.send_go_back_n(data_list)
        elif self.transmission_protocol_ == TransmissionProtocol.ALGORITHM_TYPE_SR:
            return self.send_sel_repeat(data_list)

    def send_sel_repeat(self, data_list):
        seq_num_first = 0
        seq_num_last = 0

        cur_data_block_idx = 0
        is_waiting_last_ack = False

        # last_frame_timeout_start = 0

        sent_frames = []
        timers = []

        if self.VERBOSE:
            print("sender: Start transmission", get_time_h_m_s())

        start_transmission_time = time.time()
        while True:
            if time.time() - start_transmission_time > transm_global_params.TRANSMISSION_TIMEOUT:
                return False
            if seq_num_last < seq_num_first + transm_global_params.WINDOW_SIZE and not is_waiting_last_ack:
                frame = Frame(
                    data=data_list[cur_data_block_idx],
                    seq_num=seq_num_last,
                    is_last=True if cur_data_block_idx == len(data_list) - 1 else False,
                    is_corrupted=flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                )

                if self.VERBOSE:
                    print("sender: Send frame", seq_num_last, "is corrupted:", frame.is_corrupted_, get_time_h_m_s())
                self.ipc_manager_.send_to_receiver(frame)
                self.total_sent_ += 1
                cur_data_block_idx += 1

                if cur_data_block_idx == len(data_list):
                    if self.VERBOSE:
                        print("sender: Wait last ack, no new frame", get_time_h_m_s())
                    is_waiting_last_ack = True
                    # last_frame_timeout_start = time.time()

                sent_frames.append(frame)
                timers.append(time.time())
                seq_num_last += 1

            ack = self.ipc_manager_.get_from_receiver()
            if ack is not None and not ack.is_corrupted_:
                self.total_received_ack_ += 1
                if seq_num_first < ack.seq_num_ <= seq_num_last:
                    if self.VERBOSE:
                        print("sender: Received ack", ack.seq_num_, get_time_h_m_s())

                    idx_del = 0
                    for i in range(len(sent_frames)):
                        if sent_frames[i] is not None and ack.seq_num_ - 1 == sent_frames[i].seq_num_:
                            idx_del = i
                            break

                    sent_frames[idx_del] = None
                    timers[idx_del] = None

                    if idx_del == 0:
                        while len(sent_frames) != 0 and sent_frames[0] is None:
                            del sent_frames[0]
                            del timers[0]
                            seq_num_first += 1

                if is_waiting_last_ack and len(sent_frames) == 0:
                    if self.VERBOSE:
                        print("sender: Received last ack, terminate transmission", get_time_h_m_s())
                    return True

            if ack is not None and ack.is_corrupted_:
                if self.VERBOSE:
                    print("sender: Corrupted ack, ignoring", ack.seq_num_, get_time_h_m_s())

            for i in range(len(timers)):
                if timers[i] is None:
                    continue
                cur_time = time.time()
                if cur_time - timers[i] > transm_global_params.TIMEOUT_SEL_REPEAT_SENDER:
                    sent_frames[i].is_corrupted_ = flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                    self.ipc_manager_.send_to_receiver(sent_frames[i])
                    self.total_sent_ += 1

                    timers[i] = time.time()
                    if self.VERBOSE:
                        print("sender: Timeout, retransmit", sent_frames[i].seq_num_, "is corrupted:",
                              sent_frames[i].is_corrupted_, get_time_h_m_s())

            # if is_waiting_last_ack:
            #     if time.time() - last_frame_timeout_start > transm_global_params.TIMEOUT_LAST_PACKET_SENDER:
            #         if self.VERBOSE:
            #             print("sender: Last frame re-sending timeout, terminating", get_time_h_m_s())
            #         break

    def send_go_back_n(self, data_list):
        seq_num_first = 0
        seq_num_last = 0

        time_since_last_ack = time.time()

        cur_data_block_idx = 0
        is_waiting_last_ack = False

        # last_frame_timeout_start = 0

        sent_frames = []

        if self.VERBOSE:
            print("sender: Start transmission", get_time_h_m_s())

        start_transmission_time = time.time()
        while True:
            if time.time() - start_transmission_time > transm_global_params.TRANSMISSION_TIMEOUT:
                return False
            if seq_num_last < seq_num_first + transm_global_params.WINDOW_SIZE and not is_waiting_last_ack:
                frame = Frame(
                    data=data_list[cur_data_block_idx],
                    seq_num=seq_num_last,
                    is_last=True if cur_data_block_idx == len(data_list) - 1 else False,
                    is_corrupted=flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                )

                if self.VERBOSE:
                    print("sender: Send frame", seq_num_last, "is corrupted:", frame.is_corrupted_, get_time_h_m_s())
                self.ipc_manager_.send_to_receiver(frame)
                self.total_sent_ += 1
                cur_data_block_idx += 1

                if cur_data_block_idx == len(data_list):
                    if self.VERBOSE:
                        print("sender: Wait last ack, no new frame", get_time_h_m_s())
                    is_waiting_last_ack = True
                    # last_frame_timeout_start = time.time()

                sent_frames.append(frame)
                seq_num_last += 1

            ack = self.ipc_manager_.get_from_receiver()

            if ack is not None and not ack.is_corrupted_:
                self.total_received_ack_ += 1
                if seq_num_first < ack.seq_num_ <= seq_num_last:
                    if self.VERBOSE:
                        print("sender: Received ack", ack.seq_num_, get_time_h_m_s())
                    while seq_num_first < ack.seq_num_:
                        seq_num_first += 1
                        time_since_last_ack = time.time()
                        del sent_frames[0]
                    if is_waiting_last_ack and len(sent_frames) == 0:
                        if self.VERBOSE:
                            print("sender: Received last ack, terminate transmission", get_time_h_m_s())
                        return True
            else:
                if ack is not None and ack.is_corrupted_:
                    if self.VERBOSE:
                        print("sender: Corrupted ack, ignoring", ack.seq_num_, get_time_h_m_s())
                if time.time() - time_since_last_ack > transm_global_params.TIMEOUT_GO_BACK_N_SENDER:
                    if self.VERBOSE:
                        print("sender: Timeout, resend entire window", get_time_h_m_s())
                    for frame in sent_frames:
                        frame.is_corrupted_ = flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                        self.ipc_manager_.send_to_receiver(frame)
                        self.total_sent_ += 1

                    time_since_last_ack = time.time()

            # if is_waiting_last_ack and len(sent_frames) == 1:
            #     if time.time() - last_frame_timeout_start > transm_global_params.TIMEOUT_LAST_PACKET_SENDER:
            #         if self.VERBOSE:
            #             print("sender: Last frame re-sending limit is reached, terminating", get_time_h_m_s())
            #         break


if __name__ == "__main__":
    frames_count = 100

    m = IPCManager(('localhost', 5000))
    m.start()
    # m.connect()

    input_path = "input.txt"
    if len(sys.argv) > 1:
        input_path = sys.argv[1]

    with open(input_path, 'r') as file:
        data = file.read()

    sender = Sender(m, transm_global_params.TRANSMISSION_PROTOCOL_TYPE, True)

    sender.wait_for_connection()

    start_time = datetime.datetime.now()

    sender.send(list(split_string(data, frames_count)))

    finish_time = datetime.datetime.now()

    # with open('sender_results.txt', 'a') as file:
    #     file.write(
    #         str(transm_global_params.TRANSMISSION_PROTOCOL_TYPE)
    #         + " "
    #         + str(transm_global_params.ERROR_PROBABILITY)
    #         + " "
    #         + str(get_delta_ms(start_time, finish_time))
    #         + " ms"
    #         + " total_sent: "
    #         + str(sender.total_sent_)
    #         + " total_received_ack: "
    #         + str(sender.total_received_ack_)
    #         + " win size: "
    #         + str(transm_global_params.WINDOW_SIZE)
    #         + "\n"
    #     )

    print("sender: Wait before shutdown connection", get_time_h_m_s())
    time.sleep(2)

    m.shutdown()
