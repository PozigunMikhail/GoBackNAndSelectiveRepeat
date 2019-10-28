from multiprocessing.managers import BaseManager
import queue

queue_s2r = queue.Queue()
queue_r2s = queue.Queue()


def get_queue_s2r():
    return queue_s2r


def get_queue_r2s():
    return queue_r2s


class IPCManager:

    def __init__(self, address):
        self.base_manager_ = None
        self.shared_queue_s2r_ = None
        self.shared_queue_r2s_ = None
        self.address_ = address

    def start(self):
        BaseManager.register('queue_s2r', callable=get_queue_s2r)
        BaseManager.register('queue_r2s', callable=get_queue_r2s)
        self.base_manager_ = BaseManager(address=self.address_, authkey=b'qwerty')
        self.base_manager_.start()

        self.shared_queue_s2r_ = self.base_manager_.queue_s2r()
        self.shared_queue_r2s_ = self.base_manager_.queue_r2s()

    def connect(self):
        BaseManager.register('queue_s2r')
        BaseManager.register('queue_r2s')
        self.base_manager_ = BaseManager(address=self.address_, authkey=b'qwerty')
        self.base_manager_.connect()

        self.shared_queue_s2r_ = self.base_manager_.queue_s2r()
        self.shared_queue_r2s_ = self.base_manager_.queue_r2s()

    def shutdown(self):
        if self.base_manager_ is not None:
            self.base_manager_.shutdown()

    def get_from_sender(self):
        if self.shared_queue_s2r_.empty():
            return None
        return self.shared_queue_s2r_.get()

    def get_from_receiver(self):
        if self.shared_queue_r2s_.empty():
            return None
        return self.shared_queue_r2s_.get()

    def send_to_receiver(self, msg):
        self.shared_queue_s2r_.put(msg)

    def send_to_sender(self, msg):
        self.shared_queue_r2s_.put(msg)
