import time

from ipc_manager import IPCManager
from frame import Frame
from utils import get_time_h_m_s
from utils import flip_biased_coin
import global_params


class Receiver:
    def __init__(self, ipc_manager):
        self.ipc_manager_ = ipc_manager

    def wait_for_connection(self):
        while True:
            req = self.ipc_manager_.get_from_sender()
            if req is None:
                continue
            if req.seq_num_ == global_params.ESTABLISH_CONNECTION_CODE:
                ack = Frame(None, global_params.ESTABLISH_CONNECTION_CODE, False, False)
                self.ipc_manager_.send_to_sender(ack)
                print("receiver: Connection established", get_time_h_m_s())
                break

    def receive_sel_repeat(self):
        out_data_list = []
        received_seq = []
        seq_num_expected = 0
        time_since_last_req = None
        is_last_seq = False

        print("receiver: Start transmission", get_time_h_m_s())

        while True:
            seq = self.ipc_manager_.get_from_sender()

            if is_last_seq:  # resend ack for each new seq after the last seq until timeout

                if seq is not None and not seq.is_corrupted_:
                    ack_frame = Frame(
                        data=None,
                        seq_num=seq_num_expected,
                        is_last=False,
                        is_corrupted=flip_biased_coin(global_params.ERROR_PROBABILITY)
                    )
                    print("receiver: Resend ack after obtaining all frames", seq_num_expected, "is corrupted:",
                          ack_frame.is_corrupted_, get_time_h_m_s())
                    self.ipc_manager_.send_to_sender(ack_frame)

                if time_since_last_req is not None:
                    if time.time() - time_since_last_req > global_params.TIMEOUT_RECEIVER:
                        print("receiver: Timeout on resending last ack, terminating", get_time_h_m_s())
                        break
                continue

            if seq is None:
                continue

            if seq.seq_num_ < seq_num_expected:
                ack_frame = Frame(
                    data=None,
                    seq_num=seq_num_expected,
                    is_last=False,
                    is_corrupted=flip_biased_coin(global_params.ERROR_PROBABILITY)
                )
                print("receiver: Send ack for seq num less than expected", seq_num_expected, "is corrupted:",
                      ack_frame.is_corrupted_, get_time_h_m_s())
                self.ipc_manager_.send_to_sender(ack_frame)
                continue

            if seq.is_corrupted_:  # without nack, receive re-sent frames after sender timeout
                print("receiver: Corrupted seq, ignoring", seq.seq_num_, get_time_h_m_s())
                continue

            if seq.seq_num_ == seq_num_expected:
                print("receiver: Received expected req", seq.seq_num_, get_time_h_m_s())

                if seq.is_last_:
                    is_last_seq = True

                seq_num_expected += 1
                out_data_list.append(seq.data_)

                ack_frame = Frame(
                    data=None,
                    seq_num=seq_num_expected,
                    is_last=False,
                    is_corrupted=flip_biased_coin(global_params.ERROR_PROBABILITY)
                )
                print("receiver: Send ack", seq_num_expected, "is corrupted:", ack_frame.is_corrupted_,
                      get_time_h_m_s())
                self.ipc_manager_.send_to_sender(ack_frame)

                prev_seq_num = seq.seq_num_
                while len(received_seq) != 0:
                    if received_seq[0].seq_num_ == prev_seq_num + 1:

                        if received_seq[0].is_last_:
                            is_last_seq = True

                        seq_num_expected += 1
                        out_data_list.append(received_seq[0].data_)

                        ack_frame_prev = Frame(
                            data=None,
                            seq_num=seq_num_expected,
                            is_last=False,
                            is_corrupted=flip_biased_coin(global_params.ERROR_PROBABILITY)
                        )
                        print("receiver: Send ack for previous seq", seq_num_expected, "is corrupted:",
                              ack_frame_prev.is_corrupted_, get_time_h_m_s())
                        self.ipc_manager_.send_to_sender(ack_frame_prev)

                        del received_seq[0]
                        prev_seq_num += 1
                    else:
                        break

            else:
                print("receiver: Received unexpected req", seq.seq_num_, get_time_h_m_s())
                if len(received_seq) != 0:
                    insertion_idx = 0
                    while insertion_idx < len(received_seq) and seq.seq_num_ > received_seq[insertion_idx].seq_num_:
                        insertion_idx += 1
                    if insertion_idx < len(received_seq) and received_seq[insertion_idx].seq_num_ != seq.seq_num_:
                        received_seq.insert(insertion_idx, seq)
                else:
                    received_seq.append(seq)

                ack_frame = Frame(
                    data=None,
                    seq_num=seq_num_expected,
                    is_last=False,
                    is_corrupted=flip_biased_coin(global_params.ERROR_PROBABILITY)
                )
                print("receiver: Send ack", seq_num_expected, "is corrupted:", ack_frame.is_corrupted_,
                      get_time_h_m_s())
                self.ipc_manager_.send_to_sender(ack_frame)

            if is_last_seq:
                print("receiver: Last frame is received", seq_num_expected, get_time_h_m_s())
                if time_since_last_req is None:
                    time_since_last_req = time.time()

        return out_data_list

    def receive_go_back_n(self):
        out_data_list = []
        seq_num_expected = 0
        time_since_last_req = None
        is_last_seq = False

        print("receiver: Start transmission", get_time_h_m_s())

        while True:
            seq = self.ipc_manager_.get_from_sender()

            if is_last_seq:  # resend ack for each new seq after the last seq until timeout
                if seq is not None and not seq.is_corrupted_:
                    ack_frame = Frame(
                        data=None,
                        seq_num=seq_num_expected,
                        is_last=False,
                        is_corrupted=flip_biased_coin(global_params.ERROR_PROBABILITY)
                    )
                    print("receiver: Send ack", seq_num_expected, "is corrupted:", ack_frame.is_corrupted_,
                          get_time_h_m_s())
                    self.ipc_manager_.send_to_sender(ack_frame)

                if time_since_last_req is not None:
                    if time.time() - time_since_last_req > global_params.TIMEOUT_RECEIVER:
                        print("receiver: Timeout on resending last ack, terminating", get_time_h_m_s())
                        break
                continue

            if seq is None:
                continue

            if seq.is_corrupted_:
                print("receiver: Corrupted seq, ignoring", seq.seq_num_, get_time_h_m_s())
                continue

            if seq.seq_num_ == seq_num_expected:
                print("receiver: Received expected req", seq.seq_num_, get_time_h_m_s())

                if seq.is_last_:
                    print("receiver: Last frame is received", seq_num_expected, get_time_h_m_s())
                    is_last_seq = True
                    if time_since_last_req is None:
                        time_since_last_req = time.time()

                seq_num_expected += 1
                out_data_list.append(seq.data_)
            else:
                print("receiver: Received unexpected req", seq.seq_num_, get_time_h_m_s())

            ack_frame = Frame(
                data=None,
                seq_num=seq_num_expected,
                is_last=False,
                is_corrupted=flip_biased_coin(global_params.ERROR_PROBABILITY)
            )
            print("receiver: Send ack", seq_num_expected, "is corrupted:", ack_frame.is_corrupted_, get_time_h_m_s())
            self.ipc_manager_.send_to_sender(ack_frame)

        return out_data_list


if __name__ == "__main__":
    m = IPCManager(('localhost', 5000))
    m.connect()

    receiver = Receiver(m)

    receiver.wait_for_connection()

    if global_params.ALGORITHM_TYPE == global_params.ALGORITHM_TYPE_GBN:
        print("receiver: GO BACK N")
        data = receiver.receive_go_back_n()
    else:
        print("receiver: SELECTIVE REPEAT")
        data = receiver.receive_sel_repeat()
    out_str = ""
    for s in data:
        out_str += s

    with open('output.txt', 'w') as file:
        file.write(out_str)
