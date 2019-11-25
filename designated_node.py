import time
import threading

from utils import get_time_h_m_s
import transm_global_params


class DesignatedNode:
    def __init__(self):
        self.senders_ = []
        self.receivers_ = []
        self.adjacency_list_ = {}

    def receive_topology_update(self, stop_event, lock, receiver, node, sender_id):
        while not stop_event.is_set():
            is_connected = receiver.wait_for_connection()
            if is_connected:
                adj_list_update = receiver.receive()

                if adj_list_update is not None:
                    print("designated node :", "received update from node #", sender_id, adj_list_update[0],
                          get_time_h_m_s())
                    lock.acquire()

                    adj_list_update = adj_list_update[0]

                    for key in node.adjacency_list_:
                        node.adjacency_list_[key] = [i for i in node.adjacency_list_[key] if i[0] != sender_id]

                    if len(adj_list_update) == 0:
                        node.adjacency_list_[sender_id] = adj_list_update
                    else:
                        node.adjacency_list_[sender_id] = adj_list_update
                        for neighbor in adj_list_update:
                            index = neighbor[0]
                            weight = neighbor[1]
                            if index not in node.adjacency_list_.keys():
                                node.adjacency_list_[index] = [(sender_id, weight)]
                            else:
                                node.adjacency_list_[index].append((sender_id, weight))

                    lock.release()

    def send_topology(self, stop_event, stop_topology_send_event, sender, topology):
        resend_topology = False
        while not stop_event.is_set():
            if not stop_topology_send_event.is_set() and resend_topology:
                is_connected = sender.wait_for_connection()
                if is_connected:
                    is_sent = sender.send([topology])
                    if is_sent:
                        resend_topology = False
            elif stop_topology_send_event.is_set():
                resend_topology = True

    def run(self):
        threads_send = []
        threads_receive = []

        stop_node_event = threading.Event()
        stop_topology_send_event = threading.Event()
        stop_topology_send_event.set()

        for i in range(len(self.senders_)):
            threads_send.append(
                threading.Thread(target=self.send_topology,
                                 args=(
                                     stop_node_event, stop_topology_send_event, self.senders_[i],
                                     self.adjacency_list_)))

        lock = threading.Lock()

        for i in range(len(self.receivers_)):
            threads_receive.append(
                threading.Thread(target=self.receive_topology_update,
                                 args=(stop_node_event, lock, self.receivers_[i], self, i)))

        for thread in threads_send:
            thread.start()
        for thread in threads_receive:
            thread.start()

        start_time = time.time()
        time_since_last_topology_send = time.time()
        while time.time() - start_time < transm_global_params.DESIGNATED_NODE_LIFETIME:
            if time.time() - time_since_last_topology_send > transm_global_params.GRAPH_SYNC_TIME_INTERVAL:
                print("designated node :", "sending current topology to the nodes", get_time_h_m_s())
                stop_topology_send_event.clear()
                time.sleep(transm_global_params.GRAPH_SYNC_TIME)
                stop_topology_send_event.set()

        stop_node_event.set()

        for thread in threads_receive:
            thread.join()
        for thread in threads_send:
            thread.join()

        print("designated node :", "I'm out", get_time_h_m_s())
