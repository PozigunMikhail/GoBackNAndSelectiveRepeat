import time
import math
from queue import PriorityQueue
import threading

from utils import get_time_h_m_s
from utils import split_string
import transm_global_params


class Node:
    def __init__(self, identifier):
        self.id_ = identifier
        self.senders_neighbors_ = {}
        self.receivers_neighbors_ = {}
        self.sender_des_node_ = None
        self.receiver_des_node_ = None
        self.adjacency_list_ = {}
        self.neighbor_ids_ = []
        self.shortest_paths_ = {}

    def find_shortest_path(self, start_id, finish_id):
        distances = {}
        is_visited = {}
        for i in self.adjacency_list_.keys():
            is_visited[i] = False
            distances[i] = math.inf
        distances[start_id] = 0
        prev = {}
        q = PriorityQueue()
        q.put((0, start_id))

        while not q.empty():
            cur_node = q.get()[1]

            if cur_node == finish_id:
                break

            is_visited[cur_node] = True
            for neighbor in self.adjacency_list_[cur_node]:
                neighbor_id = neighbor[0]
                edge_weight = neighbor[1]

                if not is_visited[neighbor_id]:
                    if distances[neighbor_id] > edge_weight + distances[cur_node]:
                        distances[neighbor_id] = edge_weight + distances[cur_node]
                        prev[neighbor_id] = cur_node
                    q.put((distances[neighbor_id], neighbor_id))

        if finish_id not in prev.keys():
            print("node #", start_id, ":", "node #", finish_id, "is unreachable", get_time_h_m_s())
            return []
        prev_id = prev[finish_id]
        path = [finish_id]
        while prev_id != start_id:
            path.append(prev_id)
            prev_id = prev[prev_id]
        path.append(start_id)
        path.reverse()
        return path

    def send_hello(self, stop_event, sender):
        while not stop_event.is_set():
            is_connected = sender.wait_for_connection()
            if is_connected:
                sender.send(["hello"])

    def receive_hello(self, stop_event, locks, receiver, node, neighbor_id_weight):
        time_since_last_hello = time.time()
        while not stop_event.is_set():
            is_connected = receiver.wait_for_connection()
            if not is_connected:
                if time.time() - time_since_last_hello > transm_global_params.HELLO_TIMEOUT:
                    locks[0].acquire()
                    if neighbor_id_weight in node.neighbor_ids_:
                        print("node #", node.id_, ":", "node #", neighbor_id_weight[0],
                              "seems to be dead, excluding from neighbors",
                              get_time_h_m_s())
                        node.neighbor_ids_.remove(neighbor_id_weight)
                    locks[0].release()
                continue

            hello = receiver.receive()
            if hello is not None:
                time_since_last_hello = time.time()
                locks[1].acquire()

                if neighbor_id_weight not in node.neighbor_ids_:
                    print("node #", node.id_, ":", "node #", neighbor_id_weight[0],
                          "discovered, appending to neighbors",
                          get_time_h_m_s())
                    node.neighbor_ids_.append(neighbor_id_weight)

                locks[1].release()

    def send_topology_update(self, stop_event, sender, node):
        prev_eighbors_count = len(node.neighbor_ids_)
        while not stop_event.is_set():
            if len(node.neighbor_ids_) != prev_eighbors_count:
                print("node #", node.id_, ":", "send neighbors list update to the designated node",
                      get_time_h_m_s())

                is_connected = sender.wait_for_connection()
                if is_connected:
                    is_sent_successfully = sender.send([node.neighbor_ids_])
                    if is_sent_successfully:
                        prev_eighbors_count = len(node.neighbor_ids_)
                    else:
                        print("node #", node.id_, ":", "timeout while sending neighbors", get_time_h_m_s())

    def receive_topology(self, stop_event, receiver, node):
        while not stop_event.is_set():
            is_connected = receiver.wait_for_connection()
            if is_connected:
                adj_list_updated = receiver.receive()
                if adj_list_updated is not None:
                    node.adjacency_list_ = adj_list_updated[0]
                    print("node #", node.id_, ":", "successfully received updated topology, rebuilding shortest paths",
                          # node.adjacency_list_,
                          get_time_h_m_s())
                    if node.id_ in node.adjacency_list_.keys() and len(node.adjacency_list_[node.id_]) != 0:
                        for i in node.adjacency_list_:
                            if i != node.id_:
                                node.shortest_paths_[i] = node.find_shortest_path(node.id_, i)
                        print("node #", node.id_, ":", "shortest paths have been rebuilt", get_time_h_m_s())
                    else:
                        node.shortest_paths_ = {}
                        print("node #", node.id_, ":", "node isolated from other, can't determine paths",
                              get_time_h_m_s())

    def run(self):
        threads_send_hello = []
        threads_receive_hello = []

        stop_node_event = threading.Event()

        for i in self.senders_neighbors_:
            threads_send_hello.append(
                threading.Thread(target=self.send_hello,
                                 args=(stop_node_event, self.senders_neighbors_[i])))

        locks = [threading.Lock(), threading.Lock()]

        for i in self.receivers_neighbors_:
            threads_receive_hello.append(
                threading.Thread(target=self.receive_hello,
                                 args=(stop_node_event, locks, self.receivers_neighbors_[i], self, (i, 1))))

        thread_send_topology_update = threading.Thread(target=self.send_topology_update,
                                                       args=(stop_node_event, self.sender_des_node_, self))

        thread_receive_topology = threading.Thread(target=self.receive_topology,
                                                   args=(stop_node_event, self.receiver_des_node_, self))

        thread_send_topology_update.start()
        thread_receive_topology.start()

        for thread in threads_send_hello:
            thread.start()
        for thread in threads_receive_hello:
            thread.start()

        time.sleep(transm_global_params.NODE_LIFETIME)
        stop_node_event.set()

        for thread in threads_receive_hello:
            thread.join()
        for thread in threads_send_hello:
            thread.join()

        thread_send_topology_update.join()
        thread_receive_topology.join()

        print("node #", self.id_, ":", "I'm out, saving paths and topology", get_time_h_m_s())
        with open(str(self.id_) + "_outfile.txt", "w") as file:
            file.write(str(self.adjacency_list_))
            file.write("\n")
            file.write(str(self.shortest_paths_))
