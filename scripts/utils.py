from web3 import Web3
from config import FACTORY_ADDRESS
import json
import redis
from config import INIT_CODE_HASH
from itertools import combinations
import logger, traceback

REDIS = redis.Redis(host='redis', port=6379, decode_responses=True)


def _pair_for(tokenA, tokenB):
    def sort_tokens(tokenA, tokenB):
        return (tokenA, tokenB) if tokenA < tokenB else (tokenB, tokenA)

    tokenA, tokenB = Web3.toChecksumAddress(tokenA), Web3.toChecksumAddress(tokenB)
    (token0, token1) = sort_tokens(tokenA, tokenB)
    factory = FACTORY_ADDRESS

    init_code_hash = INIT_CODE_HASH
    keccak_tokens = Web3.keccak(hexstr=f"{token0[2:]}{token1[2:]}").hex()[2:]
    keccak_input = f'ff{factory[2:]}{keccak_tokens}{init_code_hash}'
    create2_address = Web3.toChecksumAddress(Web3.keccak(hexstr=keccak_input).hex()[26:])        

    return create2_address


def get_pairs_data():    
    response = {}

    tokens = list(REDIS.smembers('tokens'))
    blacklisted_tokens = list(REDIS.smembers('blacklisted_tokens'))
    tokens = [token for token in tokens if token not in blacklisted_tokens]

    for tokenA, tokenB in combinations(tokens, 2):
        pair_address = _pair_for(tokenA, tokenB)
        if pair_address not in response: 
            score = REDIS.zscore('pairs', pair_address)
            if score is not None:  
                response[pair_address] = {'token0': min(tokenA, tokenB), 'token1': max(tokenA, tokenB)}              
                
    return response


def get_tokens_data():    
    response = []

    all_tokens_data = REDIS.hgetall('tokens_data')
    blacklisted_tokens = list(REDIS.smembers('blacklisted_tokens'))

    for address, data in all_tokens_data.items():
        if address not in blacklisted_tokens:
            response.append({"address": address, 'data': json.loads(data)})

    return response

def get_tokens():
    tokens = list(REDIS.smembers('tokens'))
    blacklisted_tokens = list(REDIS.smembers('blacklisted_tokens'))
    response = [{"address": token} for token in tokens if token not in blacklisted_tokens]

    return response


def add_to_blacklist(token):
    try:
        REDIS.sadd('blacklisted_tokens', token)
        return True
    except Exception as ex:
        logger.error(f'Error adding token to blacklist: {ex}')
        logger.error(traceback.format_exc())
        return False


def remove_from_blacklist(token):
    try:
        REDIS.srem('blacklisted_tokens', token)
        return True
    except Exception as ex:
        logger.error(f'Error removing token from blacklist: {ex}')
        logger.error(traceback.format_exc())

        return False
