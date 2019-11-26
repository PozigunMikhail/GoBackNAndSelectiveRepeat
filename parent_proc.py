import random
import time
import math
import sys
from multiprocessing import Process

from ipc_manager_pipes import IPCManagerPipes
from node import Node
from designated_node import DesignatedNode
from sender import Sender
from receiver import Receiver
from utils import get_time_h_m_s
import transm_global_params
from transm_global_params import TopologyType


def ring_topology(points_number):
    coordinates_list = []
    delta_phi = 2 * math.pi / points_number
    phi = 0
    for i in range(points_number):
        coordinates_list.append((int(3 * math.cos(phi)), int(3 * math.sin(phi))))
        phi += delta_phi

    edges = []

    for i in range(points_number - 1):
        edges.append((i, i + 1))
    edges.append((points_number - 1, 0))

    return coordinates_list, edges


def star_topology(points_number):
    coordinates_list = [(0, 0)]
    delta_phi = 2 * math.pi / (points_number - 1)
    phi = 0
    for i in range(points_number - 1):
        coordinates_list.append((int(4 * math.cos(phi)), int(4 * math.sin(phi))))
        phi += delta_phi

    edges = []

    for i in range(1, points_number):
        edges.append((0, i))

    return coordinates_list, edges


def random_coordinates(points_number):
    coordinates_list = []
    upper = 10
    lower = 0
    for i in range(points_number):
        coordinates_list.append((random.randint(lower, upper), random.randint(lower, upper)))

    edges = []

    for i in range(len(coordinates_list)):
        for j in range(i + 1, len(coordinates_list)):
            if math.sqrt((coordinates_list[i][0] - coordinates_list[j][0]) ** 2
                         + (coordinates_list[i][1] - coordinates_list[j][1]) ** 2) <= \
                    transm_global_params.DISTANCE_THRESHOLD:
                edges.append((i, j))

    return coordinates_list, edges


def run_des_node(transmission_protocol, senders, receivers):
    node = DesignatedNode()

    for sender in senders:
        node.senders_.append(Sender(sender, transmission_protocol, verbose=False))
    for receiver in receivers:
        node.receivers_.append(Receiver(receiver, transmission_protocol, verbose=False))

    node.run()


def run_node(transmission_protocol, identifier, sender_ipc_topology, receiver_ipc_topology, senders_ipc_neighbor,
             receivers_ipc_neighbor):
    node = Node(identifier=identifier)
    node.sender_des_node_ = Sender(sender_ipc_topology, transmission_protocol, verbose=False)
    node.receiver_des_node_ = Receiver(receiver_ipc_topology, transmission_protocol, verbose=False)
    for i, ipc in senders_ipc_neighbor.items():
        node.senders_neighbors_[i] = Sender(ipc, transmission_protocol, verbose=False)
    for i, ipc in receivers_ipc_neighbor.items():
        node.receivers_neighbors_[i] = Receiver(ipc, transmission_protocol, verbose=False)

    node.run()


if __name__ == '__main__':

    coordinates = []
    edges = []
    if transm_global_params.TOPOLOGY_TYPE == TopologyType.TOPOLOGY_RING:
        coordinates, edges = ring_topology(transm_global_params.NODES_NUMBER)
    elif transm_global_params.TOPOLOGY_TYPE == TopologyType.TOPOLOGY_STAR:
        coordinates, edges = star_topology(transm_global_params.NODES_NUMBER)
    elif transm_global_params.TOPOLOGY_TYPE == TopologyType.TOPOLOGY_RANDOM:
        coordinates, edges = random_coordinates(transm_global_params.NODES_NUMBER)

    print("topology type:", transm_global_params.TOPOLOGY_TYPE)
    print("coordinates:", coordinates)
    print("edges:", edges)

    transmission_protocol = transm_global_params.TransmissionProtocol.ALGORITHM_TYPE_SR

    senders_ipc_managers_topology = []
    receivers_ipc_managers_topology = []
    senders_ipc_managers_neighbor = []
    receivers_ipc_managers_neighbor = []

    senders_ipc_managers_des_node = []
    receivers_ipc_managers_des_node = []
    for i in range(len(coordinates)):
        senders_ipc_managers_neighbor.append({})
        receivers_ipc_managers_neighbor.append({})
        senders_ipc_managers_topology.append(None)
        receivers_ipc_managers_topology.append(None)
        senders_ipc_managers_des_node.append(None)
        receivers_ipc_managers_des_node.append(None)

    for edge in edges:
        i = edge[0]
        j = edge[1]

        ipc_manager1 = IPCManagerPipes()
        ipc_manager2 = IPCManagerPipes()

        senders_ipc_managers_neighbor[i][j] = ipc_manager1
        receivers_ipc_managers_neighbor[i][j] = ipc_manager2

        senders_ipc_managers_neighbor[j][i] = ipc_manager2
        receivers_ipc_managers_neighbor[j][i] = ipc_manager1

    for i in range(transm_global_params.NODES_NUMBER):
        ipc_manager1 = IPCManagerPipes()
        ipc_manager2 = IPCManagerPipes()

        senders_ipc_managers_topology[i] = ipc_manager1
        receivers_ipc_managers_topology[i] = ipc_manager2

        senders_ipc_managers_des_node[i] = ipc_manager2
        receivers_ipc_managers_des_node[i] = ipc_manager1

    processes = [Process(target=run_des_node, args=(
        transmission_protocol,
        senders_ipc_managers_des_node,
        receivers_ipc_managers_des_node
    ))]

    for i in range(transm_global_params.NODES_NUMBER):
        processes.append(Process(target=run_node, args=(
            transmission_protocol,
            i,
            senders_ipc_managers_topology[i],
            receivers_ipc_managers_topology[i],
            senders_ipc_managers_neighbor[i],
            receivers_ipc_managers_neighbor[i]
        )))

    print("Network launch", get_time_h_m_s())

    for i in range(len(processes)):
        processes[i].start()

    # processes[0].start()
    # for i in range(2, len(processes) - 1):
    #     processes[i].start()
    # time.sleep(12)
    # processes[1].start()
    # processes[-1].start()

    time_begin = time.time()
    while time.time() - time_begin < transm_global_params.NETWORK_TIMEOUT:
        pass

    print("Network timeout, exiting", get_time_h_m_s())

    for p in processes:
        p.join()
