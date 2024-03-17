import logging
import os
from datetime import date

class Logger(object):

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Logger, cls).__new__(cls)
            cls.__init_logger_params__(cls)
        return cls.instance
    
    def __init_logger_params__(cls):

        cls.instance.date = date.today()
        dir_name = f'logs/'
        os.makedirs(dir_name, exist_ok=True)

        cls.instance.main = cls.setup_logger(cls, 'main', 'main.log', '%(asctime)s - %(filename)s - %(levelname)s - %(message)s')

    def setup_logger(cls, name, file_name, format, level=logging.INFO):
        file_name = f'logs/{cls.instance.date}.{file_name}'


        handler = logging.FileHandler(file_name)        
        handler.setFormatter(logging.Formatter(format))

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)
        
        return logger
    
logger = Logger().instance.main
