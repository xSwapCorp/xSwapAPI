from get_matrix import matrix as _matrix
import heapq
import numpy as np
import json
from config import ROUTER_ADDRESS, NODE_URI, FACTORY_ADDRESS
from web3 import Web3

with open('scripts/ABI/xSwapV2Router.json') as f:
        router_abi = json.loads(f.read())

with open('scripts/ABI/xSwapV2Factory.json') as f:
        factory_abi = json.loads(f.read())

with open("scripts/ABI/xSwapV2Pair.json") as f:
     pair_abi = json.loads(f.read())

NODE_URI = f"https://{NODE_URI}"

def get_path(token0, token1, amount_in):
    lock = _matrix.lock

    if lock.locked():
        while lock.locked():
             continue
        
    matrix = _matrix.matrix
    indexes = _matrix.hash_table

    try:
        path = []
        
        index_token0 = indexes[token0]
        index_token1 = indexes[token1]
    
        path_indexes = find_path(matrix, index_token0, index_token1)

        reverted_indexes = list(indexes.keys())
        for i in path_indexes:
            path.append(reverted_indexes[i])


        if len(path) <= 1:
            path = None
    except:
        path = None
    
    w3 = Web3(Web3.HTTPProvider(NODE_URI, request_kwargs={'timeout': 240}))

    router = w3.eth.contract(ROUTER_ADDRESS, abi = router_abi)
    factory = w3.eth.contract(FACTORY_ADDRESS, abi=factory_abi)

    pair = factory.functions.getPair(token0, token1).call()

    if pair == "0x0000000000000000000000000000000000000000":
        return path
    

    if path == None and pair != "0x0000000000000000000000000000000000000000":
        pair_contract = w3.eth.contract(pair, abi=pair_abi)
        reserve0, reserve1, _ = pair_contract.functions.getReserves().call()
        
        if reserve0 == 0 or reserve1 == 0:
             return None

        else : 
            return [token0, token1]
    try:
        amount_out_0 = router.functions.getAmountsOut(amount_in, [token0, token1]).call()
        amount_out_1 = router.functions.getAmountsOut(amount_in, path).call()
    except Exception as ex:
        raise ValueError(f'{ex}')

    if amount_out_0[-1] >= amount_out_1[-1]:
         return [token0, token1]
    

    return path


def find_path(distance_matrix, start, end):
    num_vertices = len(distance_matrix)
    
    distances = np.full(num_vertices, float('inf'))
    distances[start] = 0
    predecessors = np.full(num_vertices, None)

    priority_queue = [(0, start)]

    while priority_queue:
        current_distance, current_vertex = heapq.heappop(priority_queue)

        if current_vertex == end:
            break

        if current_distance > distances[current_vertex]:
            continue

        for neighbor in range(num_vertices):
            distance = current_distance + distance_matrix[current_vertex, neighbor]

            if distance < distances[neighbor]:
                distances[neighbor] = distance
                predecessors[neighbor] = current_vertex
                heapq.heappush(priority_queue, (distance, neighbor))

    path = []
    current_vertex = end
    while current_vertex is not None:
        path.insert(0, current_vertex)
        current_vertex = predecessors[current_vertex]
    return path
