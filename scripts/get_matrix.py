import numpy as np
from web3 import Web3
import time
from config import FACTORY_ADDRESS
import redis
import threading
from config import UPDATE_MATRIX_DELAY, INIT_CODE_HASH
from threading import Lock

REDIS = redis.Redis(host='redis', port=6379, decode_responses=True)

class Matrix:

	def __new__(cls):
		if not hasattr(cls, 'matrix'):
			cls.instance = super(Matrix, cls).__new__(cls)
			cls.__init_matrix__(cls)
		return cls.instance
	
	def __init_matrix__(cls):
		matrix, hash_table = cls.get_matrix()

		cls.instance.lock = Lock()
		cls.instance.matrix = matrix
		cls.instance.hash_table = hash_table

	def start_matrix_updater(cls):
		thread = threading.Thread(target=cls._matrix_updater)
		thread.start()

		return thread

	def _matrix_updater(cls):
		last_update_time = 0
		while True:

			current_time = time.time()

			if current_time - last_update_time < UPDATE_MATRIX_DELAY:
				continue
			
			matrix, hash_table = cls.get_matrix()

			cls.instance.lock.acquire()
			cls.instance.matrix, cls.instance.hash_table = matrix, hash_table
			cls.instance.lock.release()
			
			last_update_time = current_time


	@staticmethod
	def get_matrix():
			
			def _pair_for(tokenA, tokenB):
				def sort_tokens(tokenA, tokenB):
					return (tokenA, tokenB) if tokenA < tokenB else (tokenB, tokenA)

				tokenA, tokenB = Web3.toChecksumAddress(tokenA), Web3.toChecksumAddress(tokenB)
				(token0, token1) = sort_tokens(tokenA, tokenB)
				factory = FACTORY_ADDRESS
				
				# Calculate the CREATE2 address using keccak256
				# init_code_hash = '96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f'
				init_code_hash = INIT_CODE_HASH
				keccak_tokens = Web3.keccak(hexstr=f"{token0[2:]}{token1[2:]}").hex()[2:]
				keccak_input = f'ff{factory[2:]}{keccak_tokens}{init_code_hash}'
				create2_address = Web3.toChecksumAddress(Web3.keccak(hexstr=keccak_input).hex()[26:])        

				return create2_address
			
			tokens = REDIS.smembers('tokens')
			blacklisted_tokens = list(REDIS.smembers('blacklisted_tokens'))

			tokens = [token for token in tokens if token not in blacklisted_tokens]
			hash_table = {value: index for index, value in enumerate(tokens)}
			tokens = list(tokens)

			matrix = np.zeros((len(tokens), len(tokens)))

			for i in range(len(tokens)):
				for j in range(len(tokens)):
					if i == j:
						matrix[i, j] = np.inf
						continue

					pair_address = _pair_for(tokens[i], tokens[j])
					score = REDIS.zscore('pairs', pair_address)

					if score == None or score == 0:
						matrix[i, j] = np.inf
					else:
						matrix[i, j] = score

			return matrix, hash_table
	
		


matrix = Matrix()
matrix = matrix.instance