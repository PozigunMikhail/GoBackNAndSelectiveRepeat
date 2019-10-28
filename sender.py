import time
from ipc_manager import IPCManager
from frame import Frame
from utils import split_string
from utils import get_time_h_m_s
from utils import flip_biased_coin
import global_params


class Sender:
    def __init__(self, ipc_manager):
        self.ipc_manager_ = ipc_manager

    def wait_for_connection(self):
        time_since_last_try = time.time()
        while True:

            if time.time() - time_since_last_try > global_params.CONNECTION_ESTABLISHMENT_INTERVAL:
                print("sender: Trying to connect", get_time_h_m_s())
                frame = Frame(None, global_params.ESTABLISH_CONNECTION_CODE, False, False)
                self.ipc_manager_.send_to_receiver(frame)
                time_since_last_try = time.time()

            ack = self.ipc_manager_.get_from_receiver()
            if ack is None:
                continue
            if ack.seq_num_ == global_params.ESTABLISH_CONNECTION_CODE:
                print("sender: Connection established", get_time_h_m_s())
                break

    def send_sel_repeat(self, data_list):
        seq_first = 0
        seq_last = 0

        cur_packet_idx = 0
        is_waiting_last_ack = False

        sent_frames = []
        timers = []

        print("sender: Start transmission", get_time_h_m_s())

        while True:
            if seq_last < seq_first + global_params.WINDOW_SIZE and not is_waiting_last_ack:
                frame = Frame(
                    data=data_list[cur_packet_idx],
                    seq_num=seq_last,
                    is_last=True if cur_packet_idx == len(data_list) - 1 else False,
                    is_corrupted=flip_biased_coin(global_params.ERROR_PROBABILITY)
                )

                print("sender: Send frame", seq_last, "is corrupted:", frame.is_corrupted_, get_time_h_m_s())
                self.ipc_manager_.send_to_receiver(frame)
                cur_packet_idx += 1

                if cur_packet_idx == len(data_list):
                    print("sender: Wait last ack, no new seq", get_time_h_m_s())
                    is_waiting_last_ack = True

                sent_frames.append(frame)
                timers.append(time.time())
                seq_last += 1

            ack = self.ipc_manager_.get_from_receiver()
            if ack is not None and not ack.is_corrupted_:
                if seq_first < ack.seq_num_ <= seq_last:
                    print("sender: Received ack", ack.seq_num_, get_time_h_m_s())
                    seq_first += 1
                    del sent_frames[0]
                    del timers[0]

                if is_waiting_last_ack and len(sent_frames) == 0:
                    print("sender: Received last ack, terminate transmission", get_time_h_m_s())
                    break

            if ack is not None and ack.is_corrupted_:
                print("sender: Corrupted ack, ignoring", ack.seq_num_, get_time_h_m_s())

            cur_time = time.time()
            for i in range(len(timers)):
                if cur_time - timers[i] > global_params.TIMEOUT_SEL_REPEAT_SENDER:
                    sent_frames[i].is_corrupted_ = flip_biased_coin(global_params.ERROR_PROBABILITY)
                    self.ipc_manager_.send_to_receiver(sent_frames[i])
                    timers[i] = time.time()
                    print("sender: Timeout, retransmit", sent_frames[i].seq_num_, "is corrupted:",
                          sent_frames[i].is_corrupted_, get_time_h_m_s())

    def send_go_back_n(self, data_list):
        seq_first = 0
        seq_last = 0

        time_since_last_ack = time.time()

        cur_packet_idx = 0
        is_waiting_last_ack = False

        sent_frames = []

        print("sender: Start transmission", get_time_h_m_s())

        while True:
            if seq_last < seq_first + global_params.WINDOW_SIZE and not is_waiting_last_ack:
                frame = Frame(
                    data=data_list[cur_packet_idx],
                    seq_num=seq_last,
                    is_last=True if cur_packet_idx == len(data_list) - 1 else False,
                    is_corrupted=flip_biased_coin(global_params.ERROR_PROBABILITY)
                )

                print("sender: Send frame", seq_last, "is corrupted:", frame.is_corrupted_, get_time_h_m_s())
                self.ipc_manager_.send_to_receiver(frame)
                cur_packet_idx += 1

                if cur_packet_idx == len(data_list):
                    print("sender: Wait last ack, no new seq", get_time_h_m_s())
                    is_waiting_last_ack = True

                sent_frames.append(frame)
                seq_last += 1

            ack = self.ipc_manager_.get_from_receiver()

            if ack is not None and not ack.is_corrupted_:

                if seq_first < ack.seq_num_ <= seq_last:
                    print("sender: Received ack", ack.seq_num_, get_time_h_m_s())
                    while seq_first < ack.seq_num_:
                        seq_first += 1
                        time_since_last_ack = time.time()
                        del sent_frames[0]
                    if is_waiting_last_ack and len(sent_frames) == 0:
                        print("sender: Received last ack, terminate transmission", get_time_h_m_s())
                        break
            else:
                if ack is not None and ack.is_corrupted_:
                    print("sender: Corrupted ack, ignoring", ack.seq_num_, get_time_h_m_s())
                if time.time() - time_since_last_ack > global_params.TIMEOUT_GO_BACK_N_SENDER:
                    print("sender: Timeout, resend entire window", get_time_h_m_s())
                    for frame in sent_frames:
                        frame.is_corrupted_ = flip_biased_coin(global_params.ERROR_PROBABILITY)
                        self.ipc_manager_.send_to_receiver(frame)
                    time_since_last_ack = time.time()


if __name__ == "__main__":
    frames_count = 10

    m = IPCManager(('localhost', 5000))
    m.start()

    with open('input.txt', 'r') as file:
        data = file.read()

    sender = Sender(m)

    sender.wait_for_connection()

    if global_params.ALGORITHM_TYPE == global_params.ALGORITHM_TYPE_GBN:
        print("sender: GO BACK N")
        sender.send_go_back_n(list(split_string(data, frames_count)))
    else:
        print("sender: SELECTIVE REPEAT")
        sender.send_sel_repeat(list(split_string(data, frames_count)))

    print("sender: Wait a little", get_time_h_m_s())
    time.sleep(6)

    m.shutdown()
