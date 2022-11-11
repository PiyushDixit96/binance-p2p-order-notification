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
    data = dict(chat_id=chat_id, text=text, parse_mode="html", disable_web_page_preview=True)
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


status = {
    "COMPLETED": "COMPLETED",
    "PENDING": "PENDING",
    "TRADING": "TRADING",
    "BUYER_PAYED": "BUYER PAYED",
    "DISTRIBUTING": "DISTRIBUTING",
    "IN_APPEAL": "IN APPEAL",
    "CANCELLED": "CANCELLED",
    "CANCELLED_BY_SYSTEM": "CANCELLED BY SYSTEM"
}
side = {"BUY": "BUY", "SELL": "SELL"}
used_orders = {}
err_count = 0
run = True
link = "https://p2p.binance.com/en/fiatOrderDetail?orderNo="
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
                # Important values
                orderStatus = i['orderStatus']
                orderNumber = i['orderNumber']
                ex = used_orders.get(orderNumber)
                if ex is None:
                    logger.info(f"New Update:- Order No.: {orderNumber} | Status: {orderStatus}")
                    txt = (
                        f"Status: {status.get(orderStatus)}\n"
                        f"Type: {side.get(i['tradeType'])}\n"
                        f"Price: {i['fiatSymbol']}{i['unitPrice']}\n"
                        f"Fiat Amount: {float(i['totalPrice'])} {i['fiat']}\n"
                        f"Crypto Amount: {float(i['amount'])} {i['asset']}\n"
                        f"Order No.: <a href='{link}{orderNumber}'>{orderNumber}</a>"
                    )
                    used_orders[orderStatus] = orderStatus
                    send_message(TELEGRAM_CHAT_ID, txt)
                else:
                    if ex == orderStatus:
                        pass
                    else:
                        logger.info(f"New Update:- Order No.: {orderNumber} | Status: {orderStatus}")
                        txt = (
                            f"Status: {status.get(orderStatus)}\n"
                            f"Type: {side.get(i['tradeType'])}\n"
                            f"Price: {i['fiatSymbol']}{i['unitPrice']}\n"
                            f"Fiat Amount: {float(i['totalPrice'])} {i['fiat']}\n"
                            f"Crypto Amount: {float(i['amount'])} {i['asset']}\n"
                            f"Order No.: <a href='{link}{orderNumber}'>{orderNumber}</a>"
                        )
                        used_orders[orderStatus] = orderStatus
                        send_message(TELEGRAM_CHAT_ID, txt)
        time.sleep(1)
    except Exception as e:
        logger.error(f'{e}', exc_info=True)
        err_count = err_count + 1
        if err_count > 3:
            run = False
            logger.warning(f"Error Count is {err_count}. Bot Stopped.")
            send_message(TELEGRAM_CHAT_ID, f"Error Count is {err_count}. Bot Stopped.")
