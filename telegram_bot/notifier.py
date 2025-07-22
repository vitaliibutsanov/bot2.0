from core.portfolio import virtual_portfolio
from config import CHAT_ID

async def daily_report(context):
    await context.bot.send_message(chat_id=CHAT_ID, text=virtual_portfolio.full_report())
