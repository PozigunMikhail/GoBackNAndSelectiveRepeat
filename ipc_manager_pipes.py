from multiprocessing import Pipe


class IPCManagerPipes:
    def __init__(self):
        self.s2r_conn_r_, self.s2r_conn_w_ = Pipe()
        self.r2s_conn_r_, self.r2s_conn_w_ = Pipe()

    # def connect(self):
    #     pass

    # def start(self):
    #     pass

    # def shutdown(self):
    #     pass

    def get_from_sender(self):
        if not self.s2r_conn_r_.poll():
            return None
        return self.s2r_conn_r_.recv()

    def get_from_receiver(self):
        if not self.r2s_conn_r_.poll():
            return None
        return self.r2s_conn_r_.recv()

    def send_to_receiver(self, msg):
        self.s2r_conn_w_.send(msg)

    def send_to_sender(self, msg):
        self.r2s_conn_w_.send(msg)
