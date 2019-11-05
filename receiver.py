import time

from ipc_manager import IPCManager
from frame import Frame
from utils import get_time_h_m_s
from utils import flip_biased_coin
from transm_global_params import TransmissionProtocol
import transm_global_params


class Receiver:
    def __init__(self, ipc_manager, transmission_protocol):
        self.ipc_manager_ = ipc_manager
        self.transmission_protocol_ = transmission_protocol
        if transmission_protocol == TransmissionProtocol.ALGORITHM_TYPE_GBN:
            print("receiver: GO BACK N")
        elif transmission_protocol == TransmissionProtocol.ALGORITHM_TYPE_SR:
            print("receiver: SELECTIVE REPEAT")

    def wait_for_connection(self):
        while True:
            req = self.ipc_manager_.get_from_sender()
            if req is None:
                continue
            if req.seq_num_ == transm_global_params.ESTABLISH_CONNECTION_CODE:
                ack = Frame(None, transm_global_params.ESTABLISH_CONNECTION_CODE, False, False)
                self.ipc_manager_.send_to_sender(ack)
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

        print("receiver: Start transmission", get_time_h_m_s())

        while True:
            frame = self.ipc_manager_.get_from_sender()

            if is_last_frame:  # resend ack for each new frame after the last frame until timeout

                if frame is not None and not frame.is_corrupted_:
                    ack_frame = Frame(
                        data=None,
                        seq_num=seq_num_expected,
                        is_last=False,
                        is_corrupted=flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                    )
                    print("receiver: Resend ack after obtaining all frames", seq_num_expected, "is corrupted:",
                          ack_frame.is_corrupted_, get_time_h_m_s())
                    self.ipc_manager_.send_to_sender(ack_frame)

                if time_since_last_frame is not None:
                    if time.time() - time_since_last_frame > transm_global_params.TIMEOUT_RECEIVER:
                        print("receiver: Timeout on resending last ack, terminating", get_time_h_m_s())
                        break
                continue

            if frame is None:
                continue

            if frame.seq_num_ < seq_num_expected:
                ack_frame = Frame(
                    data=None,
                    seq_num=seq_num_expected,
                    is_last=False,
                    is_corrupted=flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                )
                print("receiver: Send ack for seq num less than expected", seq_num_expected, "is corrupted:",
                      ack_frame.is_corrupted_, get_time_h_m_s())
                self.ipc_manager_.send_to_sender(ack_frame)
                continue

            if frame.is_corrupted_:  # without nack, receive re-sent frames after sender timeout
                print("receiver: Corrupted frame, ignoring", frame.seq_num_, get_time_h_m_s())
                continue

            if frame.seq_num_ == seq_num_expected:
                print("receiver: Received expected frame", frame.seq_num_, get_time_h_m_s())

                if frame.is_last_:
                    is_last_frame = True

                seq_num_expected += 1
                out_data_list.append(frame.data_)

                ack_frame = Frame(
                    data=None,
                    seq_num=seq_num_expected,
                    is_last=False,
                    is_corrupted=flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                )
                print("receiver: Send ack", seq_num_expected, "is corrupted:", ack_frame.is_corrupted_,
                      get_time_h_m_s())
                self.ipc_manager_.send_to_sender(ack_frame)

                prev_seq_num = frame.seq_num_
                while len(received_frames) != 0:
                    if received_frames[0].seq_num_ == prev_seq_num + 1:

                        if received_frames[0].is_last_:
                            is_last_frame = True

                        seq_num_expected += 1
                        out_data_list.append(received_frames[0].data_)

                        ack_frame_prev = Frame(
                            data=None,
                            seq_num=seq_num_expected,
                            is_last=False,
                            is_corrupted=flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                        )
                        print("receiver: Send ack for previous frame", seq_num_expected, "is corrupted:",
                              ack_frame_prev.is_corrupted_, get_time_h_m_s())
                        self.ipc_manager_.send_to_sender(ack_frame_prev)

                        del received_frames[0]
                        prev_seq_num += 1
                    else:
                        break

            else:
                print("receiver: Received unexpected frame", frame.seq_num_, get_time_h_m_s())
                if len(received_frames) != 0:
                    insertion_idx = 0
                    while insertion_idx < len(received_frames) and frame.seq_num_ > received_frames[
                        insertion_idx].seq_num_:
                        insertion_idx += 1
                    if insertion_idx < len(received_frames) and received_frames[
                        insertion_idx].seq_num_ != frame.seq_num_:
                        received_frames.insert(insertion_idx, frame)
                else:
                    received_frames.append(frame)

                ack_frame = Frame(
                    data=None,
                    seq_num=seq_num_expected,
                    is_last=False,
                    is_corrupted=flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                )
                print("receiver: Send ack", seq_num_expected, "is corrupted:", ack_frame.is_corrupted_,
                      get_time_h_m_s())
                self.ipc_manager_.send_to_sender(ack_frame)

            if is_last_frame:
                print("receiver: Last frame is received", seq_num_expected, get_time_h_m_s())
                if time_since_last_frame is None:
                    time_since_last_frame = time.time()

        return out_data_list

    def receive_go_back_n(self):
        out_data_list = []
        seq_num_expected = 0
        time_since_last_frame = None
        is_last_frame = False

        print("receiver: Start transmission", get_time_h_m_s())

        while True:
            frame = self.ipc_manager_.get_from_sender()

            if is_last_frame:  # resend ack for each new frame after the last frame until timeout
                if frame is not None and not frame.is_corrupted_:
                    ack_frame = Frame(
                        data=None,
                        seq_num=seq_num_expected,
                        is_last=False,
                        is_corrupted=flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
                    )
                    print("receiver: Send ack", seq_num_expected, "is corrupted:", ack_frame.is_corrupted_,
                          get_time_h_m_s())
                    self.ipc_manager_.send_to_sender(ack_frame)

                if time_since_last_frame is not None:
                    if time.time() - time_since_last_frame > transm_global_params.TIMEOUT_RECEIVER:
                        print("receiver: Timeout on resending last ack, terminating", get_time_h_m_s())
                        break
                continue

            if frame is None:
                continue

            if frame.is_corrupted_:
                print("receiver: Corrupted frame, ignoring", frame.seq_num_, get_time_h_m_s())
                continue

            if frame.seq_num_ == seq_num_expected:
                print("receiver: Received expected frame", frame.seq_num_, get_time_h_m_s())

                if frame.is_last_:
                    print("receiver: Last frame is received", seq_num_expected, get_time_h_m_s())
                    is_last_frame = True
                    if time_since_last_frame is None:
                        time_since_last_frame = time.time()

                seq_num_expected += 1
                out_data_list.append(frame.data_)
            else:
                print("receiver: Received unexpected req", frame.seq_num_, get_time_h_m_s())

            ack_frame = Frame(
                data=None,
                seq_num=seq_num_expected,
                is_last=False,
                is_corrupted=flip_biased_coin(transm_global_params.ERROR_PROBABILITY)
            )
            print("receiver: Send ack", seq_num_expected, "is corrupted:", ack_frame.is_corrupted_, get_time_h_m_s())
            self.ipc_manager_.send_to_sender(ack_frame)

        return out_data_list


if __name__ == "__main__":
    m = IPCManager(('localhost', 5000))
    m.connect()

    receiver = Receiver(m, transm_global_params.TRANSMISSION_PROTOCOL_TYPE)

    receiver.wait_for_connection()

    data = receiver.receive()

    out_str = ""
    for s in data:
        out_str += s

    with open('output.txt', 'w') as file:
        file.write(out_str)
