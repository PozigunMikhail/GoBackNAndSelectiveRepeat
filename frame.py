class Frame:
    def __init__(self, data, seq_num, is_last, is_corrupted):
        self.data_ = data
        self.seq_num_ = seq_num
        self.is_last_ = is_last
        self.is_corrupted_ = is_corrupted
