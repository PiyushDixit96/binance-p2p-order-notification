import logging
import time
from datetime import datetime, timedelta, timezone

import requests
from binance import Client

# Import config from environment (ensure these are properly set)
from config_env import BINANCE_KEY, BINANCE_SECRET, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s: %(message)s',
    level=logging.DEBUG,
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize Binance Client
client = Client(BINANCE_KEY, BINANCE_SECRET)

# Constants
BINANCE_P2P_LINK = "https://p2p.binance.com/en/fiatOrderDetail?orderNo="
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
MAX_RETRIES = 3
CHECK_INTERVAL = 1  # seconds
TIME_WINDOW_MINUTES = 120

# Status & Trade Type Mapping
STATUS_MAP = {
    "COMPLETED": "✅ COMPLETED",
    "PENDING": "🕒 PENDING",
    "TRADING": "🔄 TRADING",
    "BUYER_PAYED": "🟡 Buyer Paid",
    "DISTRIBUTING": "🚚 DISTRIBUTING",
    "IN_APPEAL": "⚠️ IN APPEAL",
    "CANCELLED": "❌ CANCELLED",
    "CANCELLED_BY_SYSTEM": "🛠️ Cancelled by System"
}

SIDE_MAP = {
    "BUY": "🟢 BUY",
    "SELL": "🔴 SELL"
}

used_orders = {}
err_count = 0
bot_running = True


def send_telegram_message(chat_id: str, text: str) -> None:
    """Send styled message to Telegram with emoji and HTML formatting."""
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }

    try:
        response = requests.post(TELEGRAM_API_URL, data=payload)
        result = response.json()

        if result.get("ok"):
            msg_id = result["result"]["message_id"]
            logger.info(f"[MessageID:{msg_id}] Sent message to {chat_id}")
        else:
            logger.warning(f"Telegram delivery failed: {result}")
            logger.debug(text)
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


def startup_update(database: dict) -> None:
    """Load existing orders at startup."""
    for trade_type in ["BUY", "SELL"]:
        try:
            res = client.get_c2c_trade_history(tradeType=trade_type)
            for item in res.get('data', []):
                database[item['orderNumber']] = item['orderStatus']
        except Exception as e:
            logger.error(f"Startup update failed for {trade_type}: {e}")

    logger.info(f"✅ Startup order database initialized with {len(database)} orders.")


def get_time_range() -> tuple[int, int]:
    """Return start and end timestamps for the last X minutes."""
    end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_time = int((datetime.now(timezone.utc) - timedelta(minutes=TIME_WINDOW_MINUTES)).timestamp() * 1000)
    return start_time, end_time


def format_order_message(order_data) -> str:
    """Format the Telegram message with emojis and proper styling."""
    status = STATUS_MAP.get(order_data['orderStatus'], order_data['orderStatus'])
    trade_side = SIDE_MAP.get(order_data['tradeType'], order_data['tradeType'])

    return (
        f"<b>🔔 New Order Update</b>\n\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Type:</b> {trade_side}\n"
        f"<b>Price:</b> {order_data['fiatSymbol']}{order_data['unitPrice']}\n"
        f"<b>Fiat Amount:</b> {float(order_data['totalPrice']):,.2f} {order_data['fiat']}\n"
        f"<b>Crypto Amount:</b> {float(order_data['amount']):.8f} {order_data['asset']}\n"
        f"<b>Order No.:</b> <a href='{BINANCE_P2P_LINK}{order_data['orderNumber']}'>{order_data['orderNumber']}</a>"
    )


def fetch_and_process_trades() -> None:
    """Fetch trades from Binance and process updates."""
    start, end = get_time_range()
    logger.debug(f"🔍 Checking orders between {start} and {end}")

    for trade_type in ["BUY", "SELL"]:
        try:
            result = client.get_c2c_trade_history(tradeType=trade_type, startDate=start, endDate=end)
            for order in result.get('data', []):
                order_number = order['orderNumber']
                current_status = order['orderStatus']
                previous_status = used_orders.get(order_number)

                if previous_status is None:
                    logger.info(f"🆕 NEW ORDER | Order: {order_number} | Status: {current_status}")
                    message = format_order_message(order)
                    send_telegram_message(TELEGRAM_CHAT_ID, message)
                    used_orders[order_number] = current_status

                elif previous_status != current_status:
                    logger.info(f"🔄 STATUS CHANGED | Order: {order_number} | From: {previous_status} To: {current_status}")
                    message = format_order_message(order)
                    send_telegram_message(TELEGRAM_CHAT_ID, message)
                    used_orders[order_number] = current_status

        except Exception as e:
            logger.error(f"Error fetching {trade_type} trades: {e}", exc_info=True)


def main():
    global bot_running, err_count

    logger.info(f"🚀 Bot started. Tracking P2P orders from last {TIME_WINDOW_MINUTES} minutes.")
    send_telegram_message(TELEGRAM_CHAT_ID, "🟢 P2P Tracker Bot Started!")

    startup_update(used_orders)

    while bot_running:
        try:
            fetch_and_process_trades()
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("🛑 Bot manually stopped by user.")
            send_telegram_message(TELEGRAM_CHAT_ID, "🛑 P2P Tracker Bot Stopped Manually.")
            bot_running = False
        except Exception as e:
            logger.error(f"🚨 Unexpected error: {e}", exc_info=True)
            err_count += 1
            if err_count >= MAX_RETRIES:
                logger.critical(f"💥 Max retries reached ({MAX_RETRIES}). Stopping bot.")
                send_telegram_message(TELEGRAM_CHAT_ID, f"💥 Too many errors. Bot stopping after {MAX_RETRIES} failures.")
                bot_running = False


if __name__ == "__main__":
    main()