import numpy as np
from web3 import Web3
import redis
import json, time, asyncio
import threading
import traceback, sys
from config import FACTORY_ADDRESS, NODE_URI, UPDATE_DB_DELAY
from logger import logger

class EventMonitor:
    REDIS = redis.Redis(host='redis', port=6379, decode_responses=True)

    WS_URL = f"wss://{NODE_URI}"
    HTTP_URL = f"https://{NODE_URI}"
    
    with open('scripts/ABI/xSwapV2Factory.json') as f:
        factoryABI = json.loads(f.read())

    with open('scripts/ABI/xSwapV2Pair.json') as f:
        pairABI = json.loads(f.read())

    with open('scripts/ABI/ERC20.json') as f:
        tokenABI = json.loads(f.read())


    def __init__(self, factory_address=FACTORY_ADDRESS, factory_abi=factoryABI):
        # self.ws_w3 = Web3(Web3.WebsocketProvider(self.WS_URL, websocket_kwargs={'timeout': 240}))
        self.w3 = Web3(Web3.HTTPProvider(self.HTTP_URL, request_kwargs={'timeout': 240}))
        self.factory = self.w3.eth.contract(address=Web3.toChecksumAddress(factory_address), abi=factory_abi)
        self.pair_contract = self.w3.eth.contract(abi=self.pairABI)
        self.erc20_token = self.w3.eth.contract(abi=self.tokenABI)

        # self.event_filter = self._get_new_filter()
        self.last_update_timestamp = time.time()
        self.stop_event = threading.Event()
        self.main_thread = self.threading_manager()


    def is_synced(self):
        stored_pairs_length = int(self.REDIS.zcard('pairs'))
        onchain_pairs_length = self.factory.functions.allPairsLength().call()
        return stored_pairs_length == onchain_pairs_length
    
    def start_in_thread(func):
        def wrapper(self, *args, **kwargs):
            target_args = (self, *args)
            thread = threading.Thread(target=func, args=target_args, kwargs=kwargs)
            thread.start()
            return thread
        return wrapper
    


    @start_in_thread
    def threading_manager(self):
        print('Thread monitor is started...')
        logger.info('Thread monitor is started...')
        try:
            self.stop_event.clear()
            listen_thread = self.listen()
            update_thread = self.update()
            
            while not self.stop_event.is_set():
                if not listen_thread.is_alive():
                    listen_thread = self.listen()

                if not self.is_synced():
                    sync_thread = self.sync()
                    sync_thread.join()

                if not update_thread.is_alive():
                    update_thread = self.update()
                
                time.sleep(10)

        except threading.ThreadError as ex:
            traceback.print_exc()
            logger.error(f'Got exception in Thread Monitor: {ex}')
            print(f'Got exception in Thread Monitor: {ex}')

        finally:
            print('Thread monitor is stopped...')
            logger.info('Thread monitor is stopped...')


    @start_in_thread
    def listen(self):
        print("Listener is started...")
        logger.info("Listener is started...")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop = asyncio.get_event_loop()
            async def log_loop(event_filter, poll_interval):
                while not self.stop_event.is_set():

                    for event in event_filter.get_new_entries():
                        self._handle_event(event)                    

                    await asyncio.sleep(poll_interval)
            try:
                event_filter = self._get_new_filter()
                print(event_filter)
                loop.run_until_complete(
                    asyncio.gather(
                        log_loop(event_filter, 2)
                    ))
                
            except ValueError as ex:
                logger.error(f'Got error with filter ID!\n{ex}\nArgs: {ex.args}')

                # if ex.args[0]['code'] == '-3200':
                #     # self.event_filter = self._get_new_filter()
                #     print('Got error with filter!')
                #     logger.error('Got error with filter!')

            finally:
                loop.close()
                return

        except Exception as ex:
            self.stop_event.set()
            traceback.print_exc()
            print(f'Got exception during Listening: {ex}')
            logger.info(f'Got exception during Listening: {ex}')


    @start_in_thread
    def sync(self):
        print('Start syncing...')
        logger.info('Start syncing...')
        try:
            stored_pairs_length = int(self.REDIS.zcard('pairs'))
            onchain_pairs_length = self.factory.functions.allPairsLength().call()

            for current_length in range(stored_pairs_length, onchain_pairs_length):
                pair_address = self.factory.functions.allPairs(current_length).call()
                self._add_pair(pair_address)

                print(f'pair with index {current_length} - stored!')
                logger.info(f'pair with index {current_length} - stored!')

            print('Sync is finished')
            logger.info('Sync is finished')
            self.last_update_timestamp = time.time()

        except Exception as ex:
            self.stop_event.set()
            traceback.print_exc()
            print(f'Got exception during syncing: {ex}')
            logger.error(f'Got exception during syncing: {ex}')


    @start_in_thread
    def update(self):
        print('Updater is started...')
        logger.info('Updater is started...')
        try:
            while not self.stop_event.is_set():
                if self.is_synced():
                    timestamp = time.time()

                    if self.last_update_timestamp + UPDATE_DB_DELAY < timestamp :
                        asyncio.run(self._sync_reserves())
                        print(f'reserves updated {time.time() - timestamp}')
                        logger.info(f'reserves updated {time.time() - timestamp}')

                        self.last_update_timestamp = time.time()
                        time.sleep(10)

                time.sleep(10)
        except Exception as ex:
            self.stop_event.set()
            traceback.print_exc()
            logger.error(f'Got exception during Updating DB: {ex}')
            print(f'Got exception during Updating DB: {ex}')


    def _handle_event(self, event):
        print(f"New event: {event}\n\n\n")
        logger.info(f"New event: {event}\n\n\n")

        args = self.factory.events.PairCreated().processLog(event)['args']
        self._add_pair(args['pair'], args['token0'], args['token1'])


    def _add_pair(self, pair_address, token0=None, token1=None):
        pair = self.pair_contract(address=Web3.toChecksumAddress(pair_address))
        reserves = pair.functions.getReserves().call()

        if token0 == None and token1 == None:
            token0 = pair.functions.token0().call()
            token1 = pair.functions.token1().call()

        tokens_data = self._get_tokens_data((token0, token1))
        decimals0 = tokens_data[token0]['decimals']
        decimals1 = tokens_data[token1]['decimals']
        
        weight = 0
        k = (reserves[0] / (10 ** decimals0)) * (reserves[1] / (10 ** decimals1))
        if k != 0 :
            weight = (10**12) / k

        self.REDIS.sadd('tokens', token0, token1)
        self.REDIS.zadd('pairs', mapping={pair_address: weight})
    

    def _get_tokens_data(self, tokens):
        result = {}
        for token in tokens:
            if self.REDIS.hexists('token_data', token):
                data = json.loads(
                    self.REDIS('token_data', token)
                )
                try:
                    decimals = data['decimals']
                    symbol = data['symbol']
                    name = data['name']
                except Exception as ex:
                    print(f'Got exception during getting data from DB. Exception: {ex}\nCheck tokens_data - {token}')


            else:
                try:
                    decimals = self.erc20_token(address=Web3.toChecksumAddress(token)).functions.decimals().call()
                except Exception as ex:
                    print(f'Got exception while getting decimals. Exception: {ex}\nLet decimals be 18')
                    logger.error(f'Got exception while getting decimals. Exception: {ex}\nLet decimals be 18')
                    decimals = 18

                try:
                    symbol = self.erc20_token(address=Web3.toChecksumAddress(token)).functions.symbol().call()
                except Exception as ex:
                    print(f'Got exception while getting symbols. Exception: {ex}\nSymbol -> None')
                    logger.error(f'Got exception while getting symbols. Exception: {ex}\nSymbol -> None')
                    symbol = None
                
                try:
                    name = self.erc20_token(address=Web3.toChecksumAddress(token)).functions.name().call()
                except Exception as ex:
                    print(f'Got exception while getting name. Exception: {ex}\nName -> None')
                    logger.error(f'Got exception while getting name. Exception: {ex}\nName -> None')
                    name = None
                
                data = json.dumps({'symbol': symbol, 'decimals': decimals, 'name': name})
                self.REDIS.hset('tokens_data', key=token, value=data)

                
            result[token] = {'decimals' : decimals, 'symbol': symbol, 'name': name}
        return result

    async def _sync_reserves(self):
        all_pairs_addresses = self.REDIS.zrange('pairs', 0, -1)

        for address in all_pairs_addresses:
            self._add_pair(pair_address=address)

    def _get_new_filter(self):
        event_filter = self.w3.eth.filter({
                "address": self.w3.toChecksumAddress(self.factory.address),
                "topics": [
                    "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9" # PairCreated event
                ],
            })
        return event_filter


if __name__ == "__main__":
    EventMonitor()


