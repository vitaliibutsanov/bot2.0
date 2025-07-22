from config import binance
import logging

def get_binance_balance():
    try:
        balance = binance.fetch_balance()
        return {
            'USDT': round(balance.get('USDT', {}).get('free', 0), 2),
            'BTC': round(balance.get('BTC', {}).get('free', 0), 6),
            'ETH': round(balance.get('ETH', {}).get('free', 0), 6),
        }
    except Exception as e:
        logging.error(f"BALANCE_ERROR: {e}")
        return {'USDT': 0, 'BTC': 0, 'ETH': 0}
