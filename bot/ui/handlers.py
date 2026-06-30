from telegram import Update
from telegram.ext import ContextTypes
from bot.ui.keyboards import get_main_keyboard, get_wallet_keyboard, get_back_keyboard, get_reserve_keyboard
from economy.wallets.lookup import get_wallet_by_telegram_id
from economy.balances.manager import get_balance
from services.gold_price import get_rsm_rate
from database.connection import fetch_all
import time

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    
    from economy.wallets.create import create_wallet
    create_wallet(user_id)
    
    text = f"👋 Hello @{username}!\n\nWelcome To 𝐒𝐜𝐡𝐮𝐭𝐳 𝐂𝐇𝐊\nVersion : 1.0.0\nUser ID : `{user_id}`"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu_command":
        await show_command_menu(update, context)
    elif query.data == "menu_wallet":
        await show_wallet_menu(update, context)
    elif query.data == "menu_reserve":
        await show_reserve_menu(update, context)
    elif query.data == "menu_back":
        await back_to_main(update, context)

async def show_command_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text = """📋 COMMAND LIST
━━━━━━━━━━━━━━━━━━━━━━
🔥 SHOPIFY GATEWAY (0-10$)
━━━━━━━━━━━━━━━━━━━━━━
`/sh <cc|mm|yy|cvv>` - Single card check
`/msh <card1> <card2> ...` - Mass check (max 20 cards)
`/shtxt` - Check from .txt file

━━━━━━━━━━━━━━━━━━━━━━
☘️ BRAINTREE AUTH
━━━━━━━━━━━━━━━━━━━━━━
`/br <cc|mm|yy|cvv>` - Single card check
`/mbr <card1> <card2> ...` - Mass check (max 20 cards)
`/brtxt` - Check from .txt file

━━━━━━━━━━━━━━━━━━━━━━
💳 CREDIT USAGE
━━━━━━━━━━━━━━━━━━━━━━
• Dead card: `0.001` RSM
• Live card: `0.01` RSM
• Charged: `0.1` RSM

━━━━━━━━━━━━━━━━━━━━━━
🔧 PROXY MANAGEMENT
━━━━━━━━━━━━━━━━━━━━━━
`/setproxy <proxy>` - Set new proxy
`/proxy` - Check & list active proxy
`/removeproxy` - Remove current proxy
"""
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_back_keyboard())

async def show_wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    wallet = get_wallet_by_telegram_id(user_id)
    balance = get_balance(user_id)
    rsm_rate, gold_idr, usd_rate = get_rsm_rate()
    
    rows = fetch_all("""
        SELECT ref_id, amount, claimed_at 
        FROM claimed_deposits 
        WHERE user_id = ? 
        ORDER BY claimed_at DESC 
        LIMIT 10
    """, [user_id])
    
    history_lines = []
    if rows:
        for ref_id, amount, ts in rows:
            date = time.strftime("%d/%m %H:%M", time.localtime(ts))
            history_lines.append(f"• {amount:.2f} RSM - {ref_id[:16]}... - {date}")
    else:
        history_lines.append("• No deposits yet")
    
    history_text = "\n".join(history_lines)
    
    text = (
        f"🏦 *WALLET INFO*\n\n"
        f"📦 *Address:* `{wallet['wallet_address'] if wallet else 'Not created'}`\n"
        f"💎 *Balance:* `{balance:.6f}` RSM\n"
        f"🆔 *User ID:* `{user_id}`\n\n"
        f"💵 *EXCHANGE RATE (LIVE)*\n"
        f"💸 1 RSM = `{rsm_rate:,.0f}` IDR\n"
        f"🥇 Gold/gram = `{gold_idr:,.0f}` IDR\n"
        f"💵 USD = `{usd_rate:,.0f}` IDR\n\n"
        f"📋 *DEPOSIT HISTORY (SUCCESS)*\n{history_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💸 *TRANSFER*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"`/transfer <target> <amount>` - Kirim RSM\n\n"
        f"Target bisa:\n"
        f"• Telegram ID: `/transfer 123456789 5`\n"
        f"• Wallet address: `/transfer reich_xxx 5`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 *DEPOSIT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"`/deposit <amount>` - Buat invoice\n"
        f"`/check <ref_id>` - Verifikasi setelah bayar\n"
        f"`/claimed` - Lihat history deposit\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔧 *PROXY*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"`/setproxy <proxy>` - Set proxy\n"
        f"`/proxy` - Lihat proxy\n"
        f"`/removeproxy` - Hapus proxy\n\n"
        f"⚡ *Min transfer: 0.1 RSM | Fee: 1%*"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_wallet_keyboard())

async def show_reserve_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    from economy.reserve.reserve import get_total_reserve
    from economy.reserve.statistics import get_reserve_statistics
    from economy.supply.circulating import get_circulating
    
    total_reserve = get_total_reserve()
    stats = get_reserve_statistics()
    supply = get_circulating()
    
    text = (
        f"🏦 *RESERVE / BANK INFO*\n\n"
        f"💰 *Total Reserve:* `{total_reserve:,.2f}` RSM\n"
        f"📊 *Total Fees Collected:* `{stats['total_fees_collected']:,.6f}` RSM\n"
        f"🔢 *Fee Transactions:* `{stats['fee_transactions']}`\n\n"
        f"💎 *System Total:* `{supply['system_total']:,.2f}` RSM\n"
        f"🔄 *Circulating Supply:* `{supply['circulating']:,.2f}` RSM\n"
        f"🏦 *Reserve:* `{supply['reserve']:,.2f}` RSM\n\n"
        f"📌 Reserve adalah dana cadangan dari fee transaksi (1%%).\n"
        f"Dana ini digunakan untuk stabilitas ekonomi."
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_reserve_keyboard())

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    text = f"👋 Hello @{user.username or user.first_name}!\n\nWelcome To 𝐒𝐜𝐡𝐮𝐭𝐳 𝐂𝐇𝐊\nVersion : 1.0.0\nUser ID : `{user.id}`"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# Stub untuk kompatibilitas
async def sh_stub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚧 Gunakan /sh <cc|mm|yy|cvv> untuk single check")

async def msh_stub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚧 Gunakan /msh <card1 card2 ...> untuk mass check")

async def shtxt_stub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚧 /shtxt - Reply to .txt file")

async def shop_stub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚧 /shop - Coming soon")
