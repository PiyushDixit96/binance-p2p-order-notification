import logging
import time
from datetime import datetime

import requests
from binance import Client

from config_env import BINANCE_KEY, BINANCE_SECRET, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

logging.basicConfig(format='%(asctime)s  %(name)s  %(levelname)s: %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

client = Client(BINANCE_KEY, BINANCE_SECRET)


def send_message(chat_id, text):
    data = dict(chat_id=chat_id, text=text, parse_mode="html")
    ok = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", params=data).json()
    logger.debug(f'SendMessage Result: {ok}')
    if ok['ok']:
        logger.info(f'[MessageID:{ok["result"]["message_id"]}] Message has been successfully delivered to {chat_id}')
    else:
        logger.debug(text)
        logger.warning(f'Message Delivery Failed to {chat_id}')
    return ok


def startup_update(database: dict):
    for trd in ["BUY", "SELL"]:
        res = client.get_c2c_trade_history(tradeType=trd)
        logger.debug(f'Startup Trade History Result: {res}')
        for k in res['data']:
            database[k['orderNumber']] = k['orderStatus']
    else:
        logger.info(f'Startup Trade Database Updated: {database}')


used_orders = {}
err_count = 0
run = True
logger.info(f'Bot Started P2P Order Tracking for Last 45 Minutes Only.')
startup_update(used_orders)
while run:
    try:
        for ty in ["BUY", "SELL"]:
            end = int(datetime.utcnow().timestamp() * 1000)
            start = end - 2700000  # almost 45 minutes
            logger.debug(f'Start timestamp: {start} and End timestamp: {end}')
            result = client.get_c2c_trade_history(tradeType=ty, startDate=start, endDate=end)
            logger.debug(f'Trade History Result: {result}')
            for i in result['data']:
                ex = used_orders.get(i['orderNumber'])
                if ex is None:
                    logger.info(f"New Update:- Order No.: {i['orderNumber']} | Status: {i['orderStatus']}")
                    txt = (
                        f"Status: {i['orderStatus']}\n"
                        f"Type: {i['tradeType']}\n"
                        f"Price: {i['unitPrice']}\n"
                        f"Fiat Amount: {float(i['totalPrice'])} {i['fiat']}\n"
                        f"Crypto Amount: {float(i['amount'])} {i['asset']}\n"
                        f"Order No.: {i['orderNumber']}"
                    )
                    used_orders[i['orderNumber']] = i['orderStatus']
                    send_message(TELEGRAM_CHAT_ID, txt)
                else:
                    if ex == i['orderStatus']:
                        pass
                    else:
                        logger.info(f"New Update:- Order No.: {i['orderNumber']} | Status: {i['orderStatus']}")
                        txt = (
                            f"Status: {i['orderStatus']}\n"
                            f"Type: {i['tradeType']}\n"
                            f"Price: {i['unitPrice']}\n"
                            f"Fiat Amount: {float(i['totalPrice'])} {i['fiat']}\n"
                            f"Crypto Amount: {float(i['amount'])} {i['asset']}\n"
                            f"Order No.: {i['orderNumber']}"
                        )
                        used_orders[i['orderNumber']] = i['orderStatus']
                        send_message(TELEGRAM_CHAT_ID, txt)
        time.sleep(1)
    except Exception as e:
        logger.error(f'{e}', exc_info=True)
        err_count = err_count + 1
        if err_count > 3:
            run = False
            logger.warning(f"Error Count is {err_count}. Bot Stopped.")
            send_message(TELEGRAM_CHAT_ID, f"Error Count is {err_count}. Bot Stopped.")
