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


used_orders = {}
err_count = 0
run = True
while run:
    try:
        for ty in ["BUY", "SELL"]:
            end = int(datetime.utcnow().timestamp() * 1000)
            start = end - 2000000  # almost 33 minutes
            logger.debug(f'Start timestamp: {start} and End timestamp: {end}')
            result = client.get_c2c_trade_history(tradeType=ty, startTimestamp=start, endTimestamp=end)
            logger.debug(f'Trade History Result: {result}')
            for i in result['data']:
                ex = used_orders.get(i['orderNumber'])
                if ex is None:
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
