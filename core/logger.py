import logging

def setup_logging():
    logging.basicConfig(
        filename='logs/trades.log',
        format='%(asctime)s | %(levelname)s | %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
