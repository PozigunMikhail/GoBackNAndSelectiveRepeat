import datetime
import time
import sys

from ipc_manager import IPCManager
from frame import Frame
from utils import get_time_h_m_s
from utils import flip_biased_coin
from utils import get_delta_ms
from transm_global_params import TransmissionProtocol
import transm_global_params


class Receiver:
    def __init__(self, ipc_manager, transmission_protocol, verbose=False):
        self.ipc_manager_ = ipc_manager
        self.transmission_protocol_ = transmission_protocol
        if transmission_protocol == TransmissionProtocol.ALGORITHM_TYPE_GBN:
            if verbose:
                print("receiver: GO BACK N")
        elif transmission_protocol == TransmissionProtocol.ALGORITHM_TYPE_SR:
            if verbose:
                print("receiver: SELECTIVE REPEAT")

        self.VERBOSE = verbose

        self.total_received_ = 0
        self.total_sent_ack_ = 0

    def wait_for_connection(self):
        while True:
            req = self.ipc_manager_.get_from_sender()
            if req is None:
                continue
            if req.seq_num_ == transm_global_params.ESTABLISH_CONNECTION_CODE:
                ack = Frame(None, transm_global_params.ESTABLISH_CONNECTION_CODE, False, False)
                self.ipc_manager_.send_to_sender(ack)
                if self.VERBOSE:
                    print("receiver: Connection established", get_time_h_m_s())
                break

    def receive(self):
        if self.transmission_protocol_ == TransmissionProtocol.ALGORITHM_TYPE_GBN:
            return self.receive_go_back_n()
        elif self.transmission_protocol_ == TransmissionProtocol.ALGORITHM_TYPE_SR:
            return self.receive_sel_repeat()

    def receive_sel_repeat(self):
        out_data_list = []
        received_frames = []
        seq_num_expected = 0
        time_since_last_frame = None
        is_last_frame = False

        if self.VERBOSE:
            print("receiver: Start transmission", get_time_h_m_s())

        while True:
            frame = self.ipc_manager_.get_from_sender()

            if is_last_frame:  # resend ack for each new frame after the last frame until timeout

                if frame is not None and not frame.is_corrupted_:
                    self.total_received_ += 1
                    ack_frame = Frame(
                        data=None,
                        seq_num=seq_num_expected,
                        is_last=False,
                        is_corrupted=False  # flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                    )
                    if self.VERBOSE:
                        print("receiver: Resend ack after obtaining all frames", seq_num_expected, get_time_h_m_s())
                    self.ipc_manager_.send_to_sender(ack_frame)
                    self.total_sent_ack_ += 1

                if time_since_last_frame is not None:
                    if time.time() - time_since_last_frame > transm_global_params.TIMEOUT_RECEIVER:
                        if self.VERBOSE:
                            print("receiver: Timeout on resending last ack, terminating", get_time_h_m_s())
                        break
                continue

            if frame is None:
                continue

            if frame.is_corrupted_:  # without nack, receive re-sent frames after sender timeout
                if self.VERBOSE:
                    print("receiver: Corrupted frame, ignoring", frame.seq_num_, get_time_h_m_s())
                continue

            self.total_received_ += 1

            if frame.seq_num_ < seq_num_expected:
                ack_frame = Frame(
                    data=None,
                    seq_num=seq_num_expected,
                    is_last=False,
                    is_corrupted=False  # flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                )
                if self.VERBOSE:
                    print("receiver: Send ack for seq num less than expected", seq_num_expected, "is corrupted:",
                          ack_frame.is_corrupted_, get_time_h_m_s())
                self.ipc_manager_.send_to_sender(ack_frame)
                self.total_sent_ack_ += 1
                continue

            if frame.seq_num_ == seq_num_expected:
                if self.VERBOSE:
                    print("receiver: Received expected frame", frame.seq_num_, get_time_h_m_s())

                if frame.is_last_:
                    is_last_frame = True

                seq_num_expected += 1
                out_data_list.append(frame.data_)

                ack_frame = Frame(
                    data=None,
                    seq_num=seq_num_expected,
                    is_last=False,
                    is_corrupted=False  # flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                )
                if self.VERBOSE:
                    print("receiver: Send ack", seq_num_expected, get_time_h_m_s())
                self.ipc_manager_.send_to_sender(ack_frame)
                self.total_sent_ack_ += 1

                prev_seq_num = frame.seq_num_
                while len(received_frames) != 0:
                    if received_frames[0].seq_num_ == prev_seq_num + 1:

                        if received_frames[0].is_last_:
                            is_last_frame = True

                        seq_num_expected += 1
                        out_data_list.append(received_frames[0].data_)

                        # ack_frame_prev = Frame(
                        #     data=None,
                        #     seq_num=seq_num_expected,
                        #     is_last=False,
                        #     is_corrupted=False  # flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                        # )
                        # if self.VERBOSE:
                        #     print("receiver: Send ack for previous frame", seq_num_expected, "is corrupted:",
                        #       ack_frame_prev.is_corrupted_, get_time_h_m_s())
                        # self.ipc_manager_.send_to_sender(ack_frame_prev)
                        # self.total_sent_ack_ += 1

                        del received_frames[0]
                        prev_seq_num += 1
                    else:
                        break

            else:
                if self.VERBOSE:
                    print("receiver: Received unexpected frame", frame.seq_num_, get_time_h_m_s())
                if len(received_frames) != 0:
                    insertion_idx = 0
                    while insertion_idx < len(received_frames) and frame.seq_num_ > received_frames[
                        insertion_idx].seq_num_:
                        insertion_idx += 1
                    if insertion_idx < len(received_frames) and received_frames[
                        insertion_idx].seq_num_ != frame.seq_num_:
                        received_frames.insert(insertion_idx, frame)
                    elif insertion_idx == len(received_frames):
                        received_frames.append(frame)
                else:
                    received_frames.append(frame)

                ack_frame = Frame(
                    data=None,
                    seq_num=frame.seq_num_ + 1,
                    is_last=False,
                    is_corrupted=False  # flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                )
                if self.VERBOSE:
                    print("receiver: Send ack", frame.seq_num_ + 1, get_time_h_m_s())
                self.ipc_manager_.send_to_sender(ack_frame)
                self.total_sent_ack_ += 1

            if is_last_frame:
                if self.VERBOSE:
                    print("receiver: Last frame is received", seq_num_expected, get_time_h_m_s())
                if time_since_last_frame is None:
                    time_since_last_frame = time.time()

        return out_data_list

    def receive_go_back_n(self):
        out_data_list = []
        seq_num_expected = 0
        time_since_last_frame = None
        is_last_frame = False

        if self.VERBOSE:
            print("receiver: Start transmission", get_time_h_m_s())

        while True:
            frame = self.ipc_manager_.get_from_sender()

            if is_last_frame:  # resend ack for each new frame after the last frame until timeout
                if frame is not None and not frame.is_corrupted_:
                    self.total_received_ += 1
                    ack_frame = Frame(
                        data=None,
                        seq_num=seq_num_expected,
                        is_last=False,
                        is_corrupted=False  # flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                    )
                    if self.VERBOSE:
                        print("receiver: Send ack", seq_num_expected, get_time_h_m_s())
                    self.ipc_manager_.send_to_sender(ack_frame)
                    self.total_sent_ack_ += 1

                if time_since_last_frame is not None:
                    if time.time() - time_since_last_frame > transm_global_params.TIMEOUT_RECEIVER:
                        if self.VERBOSE:
                            print("receiver: Timeout on resending last ack, terminating", get_time_h_m_s())
                        break
                continue

            if frame is None:
                continue

            if frame.is_corrupted_:
                if self.VERBOSE:
                    print("receiver: Corrupted frame, ignoring", frame.seq_num_, get_time_h_m_s())
                continue

            self.total_received_ += 1

            if frame.seq_num_ == seq_num_expected:
                if self.VERBOSE:
                    print("receiver: Received expected frame", frame.seq_num_, get_time_h_m_s())

                if frame.is_last_:
                    if self.VERBOSE:
                        print("receiver: Last frame is received", seq_num_expected, get_time_h_m_s())
                    is_last_frame = True
                    if time_since_last_frame is None:
                        time_since_last_frame = time.time()

                seq_num_expected += 1
                out_data_list.append(frame.data_)
            else:
                if self.VERBOSE:
                    print("receiver: Received unexpected frame", frame.seq_num_, get_time_h_m_s())

            ack_frame = Frame(
                data=None,
                seq_num=seq_num_expected,
                is_last=False,
                is_corrupted=False  # flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
            )
            if self.VERBOSE:
                print("receiver: Send ack", seq_num_expected, get_time_h_m_s())
            self.ipc_manager_.send_to_sender(ack_frame)
            self.total_sent_ack_ += 1

        return out_data_list


if __name__ == "__main__":
    m = IPCManager(('localhost', 5000))
    m.connect()

    receiver = Receiver(m, transm_global_params.TRANSMISSION_PROTOCOL_TYPE, True)

    receiver.wait_for_connection()

    start_time = datetime.datetime.now()

    data = receiver.receive()

    finish_time = datetime.datetime.now()

    out_str = ""
    for s in data:
        out_str += s

    output_path = "output.txt"
    if len(sys.argv) > 1:
        output_path = sys.argv[1]

    with open(output_path, 'w') as file:
        file.write(out_str)

    # with open('input.txt', 'r') as file:
    #     data_gt = file.read()
    #
    # are_equal_strings = data_gt == out_str
    #
    # with open('receiver_results.txt', 'a') as file:
    #     file.write(
    #         str(transm_global_params.TRANSMISSION_PROTOCOL_TYPE)
    #         + " "
    #         + str(transm_global_params.ERROR_PROBABILITY)
    #         + " "
    #         + str(get_delta_ms(start_time, finish_time))
    #         + " ms"
    #         + " total_sent_ack: "
    #         + str(receiver.total_sent_ack_)
    #         + " total_received: "
    #         + str(receiver.total_received_)
    #         + " win size: "
    #         + str(transm_global_params.WINDOW_SIZE)
    #         + " successful transmission: "
    #         + str(are_equal_strings)
    #         + "\n"
    #     )
