import time
from ipc_manager import IPCManager
from frame import Frame
from utils import split_string
from utils import get_time_h_m_s
from utils import flip_biased_coin
from transm_global_params import TransmissionProtocol
import transm_global_params


class Sender:
    def __init__(self, ipc_manager, transmission_protocol):
        self.ipc_manager_ = ipc_manager
        self.transmission_protocol_ = transmission_protocol
        if transmission_protocol == TransmissionProtocol.ALGORITHM_TYPE_GBN:
            print("sender: GO BACK N")
        elif transmission_protocol == TransmissionProtocol.ALGORITHM_TYPE_SR:
            print("sender: SELECTIVE REPEAT")

    def wait_for_connection(self):
        time_since_last_try = time.time()
        while True:

            if time.time() - time_since_last_try > transm_global_params.CONNECTION_ESTABLISHMENT_INTERVAL:
                print("sender: Trying to connect", get_time_h_m_s())
                frame = Frame(None, transm_global_params.ESTABLISH_CONNECTION_CODE, False, False)
                self.ipc_manager_.send_to_receiver(frame)
                time_since_last_try = time.time()

            ack = self.ipc_manager_.get_from_receiver()
            if ack is None:
                continue
            if ack.seq_num_ == transm_global_params.ESTABLISH_CONNECTION_CODE:
                print("sender: Connection established", get_time_h_m_s())
                break

    def send(self, data_list):
        if self.transmission_protocol_ == TransmissionProtocol.ALGORITHM_TYPE_GBN:
            self.send_go_back_n(data_list)
        elif self.transmission_protocol_ == TransmissionProtocol.ALGORITHM_TYPE_SR:
            self.send_sel_repeat(data_list)

    def send_sel_repeat(self, data_list):
        seq_num_first = 0
        seq_num_last = 0

        cur_data_block_idx = 0
        is_waiting_last_ack = False

        last_frame_resend_counter = 0

        sent_frames = []
        timers = []

        print("sender: Start transmission", get_time_h_m_s())

        while True:
            if seq_num_last < seq_num_first + transm_global_params.WINDOW_SIZE and not is_waiting_last_ack:
                frame = Frame(
                    data=data_list[cur_data_block_idx],
                    seq_num=seq_num_last,
                    is_last=True if cur_data_block_idx == len(data_list) - 1 else False,
                    is_corrupted=flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                )

                print("sender: Send frame", seq_num_last, "is corrupted:", frame.is_corrupted_, get_time_h_m_s())
                self.ipc_manager_.send_to_receiver(frame)
                cur_data_block_idx += 1

                if cur_data_block_idx == len(data_list):
                    print("sender: Wait last ack, no new frame", get_time_h_m_s())
                    is_waiting_last_ack = True

                sent_frames.append(frame)
                timers.append(time.time())
                seq_num_last += 1

            ack = self.ipc_manager_.get_from_receiver()
            if ack is not None and not ack.is_corrupted_:
                if seq_num_first < ack.seq_num_ <= seq_num_last:
                    print("sender: Received ack", ack.seq_num_, get_time_h_m_s())
                    seq_num_first += 1
                    del sent_frames[0]
                    del timers[0]

                if is_waiting_last_ack and len(sent_frames) == 0:
                    print("sender: Received last ack, terminate transmission", get_time_h_m_s())
                    break

            if ack is not None and ack.is_corrupted_:
                print("sender: Corrupted ack, ignoring", ack.seq_num_, get_time_h_m_s())

            cur_time = time.time()
            for i in range(len(timers)):
                if cur_time - timers[i] > transm_global_params.TIMEOUT_SEL_REPEAT_SENDER:
                    sent_frames[i].is_corrupted_ = flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                    self.ipc_manager_.send_to_receiver(sent_frames[i])

                    if is_waiting_last_ack and len(sent_frames) == 1:
                        last_frame_resend_counter += 1
                    if last_frame_resend_counter == transm_global_params.MAX_LAST_PACKET_SENDING:
                        print("sender: Last frame re-sending limit is reached, terminating", get_time_h_m_s())
                        break

                    timers[i] = time.time()
                    print("sender: Timeout, retransmit", sent_frames[i].seq_num_, "is corrupted:",
                          sent_frames[i].is_corrupted_, get_time_h_m_s())

    def send_go_back_n(self, data_list):
        seq_num_first = 0
        seq_num_last = 0

        time_since_last_ack = time.time()

        cur_data_block_idx = 0
        is_waiting_last_ack = False

        last_frame_resend_counter = 0

        sent_frames = []

        print("sender: Start transmission", get_time_h_m_s())

        while True:
            if seq_num_last < seq_num_first + transm_global_params.WINDOW_SIZE and not is_waiting_last_ack:
                frame = Frame(
                    data=data_list[cur_data_block_idx],
                    seq_num=seq_num_last,
                    is_last=True if cur_data_block_idx == len(data_list) - 1 else False,
                    is_corrupted=flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                )

                print("sender: Send frame", seq_num_last, "is corrupted:", frame.is_corrupted_, get_time_h_m_s())
                self.ipc_manager_.send_to_receiver(frame)
                cur_data_block_idx += 1

                if cur_data_block_idx == len(data_list):
                    print("sender: Wait last ack, no new frame", get_time_h_m_s())
                    is_waiting_last_ack = True

                sent_frames.append(frame)
                seq_num_last += 1

            ack = self.ipc_manager_.get_from_receiver()

            if ack is not None and not ack.is_corrupted_:

                if seq_num_first < ack.seq_num_ <= seq_num_last:
                    print("sender: Received ack", ack.seq_num_, get_time_h_m_s())
                    while seq_num_first < ack.seq_num_:
                        seq_num_first += 1
                        time_since_last_ack = time.time()
                        del sent_frames[0]
                    if is_waiting_last_ack and len(sent_frames) == 0:
                        print("sender: Received last ack, terminate transmission", get_time_h_m_s())
                        break
            else:
                if ack is not None and ack.is_corrupted_:
                    print("sender: Corrupted ack, ignoring", ack.seq_num_, get_time_h_m_s())
                if time.time() - time_since_last_ack > transm_global_params.TIMEOUT_GO_BACK_N_SENDER:
                    print("sender: Timeout, resend entire window", get_time_h_m_s())
                    for frame in sent_frames:
                        frame.is_corrupted_ = flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                        self.ipc_manager_.send_to_receiver(frame)

                    if is_waiting_last_ack and len(sent_frames) == 1:
                        last_frame_resend_counter += 1
                    if last_frame_resend_counter == transm_global_params.MAX_LAST_PACKET_SENDING:
                        print("sender: Last frame re-sending limit is reached, terminating", get_time_h_m_s())
                        break

                    time_since_last_ack = time.time()


if __name__ == "__main__":
    frames_count = 10

    m = IPCManager(('localhost', 5000))
    m.start()
    # m.connect()

    with open('input.txt', 'r') as file:
        data = file.read()

    sender = Sender(m, transm_global_params.TRANSMISSION_PROTOCOL_TYPE)

    sender.wait_for_connection()

    sender.send(list(split_string(data, frames_count)))

    print("sender: Wait a little", get_time_h_m_s())
    time.sleep(6)

    m.shutdown()
