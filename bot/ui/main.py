#!/usr/bin/env python3
import os
import logging
import time
import asyncio
import random
import urllib.request
import json
from dotenv import load_dotenv
from telegram import Update
from gateway.api.braintree import check_braintree
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

load_dotenv()

from bot.ui.handlers import (
    start_command, menu_callback, show_wallet_menu
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8716607201:AAHkAUn_ujOn3HESsc8IMC_X5tFrCqSglJU")

pending_transfers = {}

# ============ COOLDOWN & SESSION TRACKING ============
_cooldowns: dict = {}
_shtxt_sessions: dict = {}
_shtxt_cooldown: dict = {}

COOLDOWN_SECONDS = {
    "sh": 3,
    "msh": 5,
    "shtxt": 10,
}

def check_cooldown(user_id: int, cmd: str) -> float:
    last = _cooldowns.get(user_id, {}).get(cmd, 0)
    limit = COOLDOWN_SECONDS.get(cmd, 0)
    sisa = limit - (time.time() - last)
    return max(0.0, sisa)

def set_cooldown(user_id: int, cmd: str):
    if user_id not in _cooldowns:
        _cooldowns[user_id] = {}
    _cooldowns[user_id][cmd] = time.time()

# ============ DATABASE CONNECTION ============
from database.connection import execute, fetch_one, fetch_all

# Buat tabel proxy (1 user 1 proxy)
execute("""
CREATE TABLE IF NOT EXISTS user_proxy (
    user_id INTEGER PRIMARY KEY,
    proxy TEXT,
    updated_at INTEGER
)
""")

# ============ TRANSFER SYSTEM ============
async def transfer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("❌ Usage: /transfer <target> <amount>\nTarget: ID atau wallet address")
        return
    target = args[0]
    try:
        amount = float(args[1])
        if amount <= 0:
            await update.message.reply_text("❌ Amount harus lebih dari 0!")
            return
    except ValueError:
        await update.message.reply_text("❌ Masukkan angka yang valid!")
        return
    receiver_id = None
    from economy.wallets.lookup import get_telegram_id_by_wallet, get_wallet_by_telegram_id
    if target.isdigit():
        receiver_id = int(target)
    elif target.startswith("reich_"):
        receiver_id = get_telegram_id_by_wallet(target)
    if not receiver_id:
        await update.message.reply_text("❌ Target tidak ditemukan!")
        return
    if receiver_id == user_id:
        await update.message.reply_text("❌ Tidak bisa transfer ke diri sendiri!")
        return
    receiver_wallet = get_wallet_by_telegram_id(receiver_id)
    if not receiver_wallet:
        await update.message.reply_text("❌ Target tidak memiliki wallet!")
        return
    from economy.balances.manager import get_balance
    from economy.constitution.constitution import can_transfer
    sender_balance = get_balance(user_id)
    ok, reason = can_transfer(sender_balance, amount)
    if not ok:
        await update.message.reply_text(f"❌ {reason}")
        return
    pending_transfers[user_id] = {
        "step": "ask_note",
        "data": {"receiver_id": receiver_id, "amount": amount, "receiver_wallet": receiver_wallet}
    }
    await update.message.reply_text(
        f"📝 Do you want to add a note?\n\n💰 Amount: {amount:.6f} RSM\nReply YES or NO"
    )

async def show_transfer_confirmation(update: Update, user_id: int):
    from economy.wallets.lookup import get_wallet_by_telegram_id
    state = pending_transfers[user_id]
    data = state["data"]
    msg = f"📋 TRANSFER DETAIL\n\n👤 FROM: {user_id}\n👤 TO: {data['receiver_id']}\n💰 AMOUNT: {data['amount']:.6f} RSM"
    if data.get("note"):
        msg += f"\n📝 NOTE: {data['note']}"
    msg += "\n\n⚠️ Reply YES to confirm, NO to cancel."
    await update.message.reply_text(msg)

async def transfer_response_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from economy.balances.manager import get_balance
    user_id = update.effective_user.id
    text = update.message.text.strip().lower()
    if user_id not in pending_transfers:
        return
    state = pending_transfers[user_id]
    step = state.get("step")
    if step == "ask_note":
        if text == "yes":
            state["step"] = "waiting_note"
            await update.message.reply_text("✏️ Enter your note (max 500 chars):\nOr /skip")
        elif text == "no":
            state["step"] = "ask_confirm"
            state["data"]["note"] = None
            await show_transfer_confirmation(update, user_id)
        else:
            await update.message.reply_text("❌ Reply YES or NO.")
    elif step == "waiting_note":
        note = None if text == "/skip" else text[:500]
        state["step"] = "ask_confirm"
        state["data"]["note"] = note
        await show_transfer_confirmation(update, user_id)
    elif step == "ask_confirm":
        if text == "yes":
            data = pending_transfers.pop(user_id)["data"]
            from economy.wallets.transfer import transfer
            result = transfer(user_id, data["receiver_id"], data["amount"])
            if result["status"] == "success":
                msg = f"✅ TRANSFER SUCCESS!\n\n💰 {data['amount']:.6f} RSM\n🔗 TXID: {result['tx']['out'][:16]}..."
                if data.get("note"):
                    msg += f"\n📝 NOTE: {data['note']}"
                await update.message.reply_text(msg)
                receiver_balance = get_balance(data["receiver_id"])
                notif = f"📥 TRANSFER RECEIVED\n\n👤 From: {user_id}\n💰 {data['amount']:.6f} RSM\n💳 Balance: {receiver_balance:.6f} RSM"
                if data.get("note"):
                    notif += f"\n📝 NOTE: {data['note']}"
                try:
                    await context.bot.send_message(data["receiver_id"], notif)
                except:
                    pass
            else:
                await update.message.reply_text(f"❌ Transfer failed: {result['reason']}")
        elif text == "no":
            pending_transfers.pop(user_id, None)
            await update.message.reply_text("❌ Transfer cancelled.")
        else:
            await update.message.reply_text("❌ Reply YES or NO.")

# ============ PROXY MANAGEMENT (1 USER = 1 PROXY) ============
async def set_proxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set proxy untuk user (1 user 1 proxy)"""
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text(
            "📋 *Format Proxy:*\n\n"
            "`/setproxy http://user:pass@host:port`\n"
            "`/setproxy host:port`\n\n"
            "Contoh: `/setproxy http://user:pass@1.2.3.4:8080`"
        )
        return
    
    proxy = args[0]
    execute("INSERT OR REPLACE INTO user_proxy (user_id, proxy, updated_at) VALUES (?, ?, ?)",
            [user_id, proxy, int(time.time())])
    await update.message.reply_text(f"✅ Proxy saved:\n`{proxy}`", parse_mode="Markdown")

async def check_proxy_alive(proxy_url):
    def _check():
        try:
            proxy_handler = urllib.request.ProxyHandler({
                'http': proxy_url,
                'https': proxy_url
            })
            opener = urllib.request.build_opener(proxy_handler)
            opener.addheaders = [
                ('User-Agent', 'curl/8.19.0'),  # Plain UA, less likely diblok
                ('Accept', '*/*'),
                ('Connection', 'close'),         # Hindari keep-alive issues
            ]

            with opener.open("http://icanhazip.com/", timeout=15) as response:
                if response.status == 200:
                    ip = response.read().decode().strip()
                    # Validasi bahwa output beneran IP, bukan HTML error
                    if ip and len(ip) < 50 and '.' in ip:
                        return True, ip
            return False, None

        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.reason}")
            return False, None
        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason}")
            return False, None
        except Exception as e:
            print(f"Proxy check error: {e}")
            return False, None

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _check)

async def proxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lihat dan cek proxy yang digunakan"""
    user_id = update.effective_user.id
    row = fetch_one("SELECT proxy FROM user_proxy WHERE user_id = ?", [user_id])
    if not row:
        await update.message.reply_text("❌ No proxy set. Use /setproxy")
        return
        
    proxy = row[0]
    msg = await update.message.reply_text(f"🔧 Proxy saved:\n`{proxy}`\n\n⏳ Checking if proxy is alive...", parse_mode="Markdown")
    
    is_alive, ip = await check_proxy_alive(proxy)
        
    if is_alive:
        await msg.edit_text(f"✅ *PROXY ALIVE*\n\n🔧 *Proxy:* `{proxy}`\n🌐 *IP:* `{ip}`", parse_mode="Markdown")
    else:
        await msg.edit_text(f"❌ *PROXY DEAD / TIMEOUT*\n\n🔧 *Proxy:* `{proxy}`\n\nPlease use /setproxy to change it.", parse_mode="Markdown")

async def remove_proxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hapus proxy user"""
    user_id = update.effective_user.id
    execute("DELETE FROM user_proxy WHERE user_id = ?", [user_id])
    await update.message.reply_text("✅ Proxy removed.")

    sisa = check_cooldown(user_id, "sh")
    if sisa > 0:
        await update.message.reply_text(f"⏳ Cooldown /sh — tunggu {sisa:.1f} detik lagi.")
        return
    set_cooldown(user_id, "sh")
    
async def get_user_proxy(user_id: int) -> str:
    """Ambil proxy user"""
    row = fetch_one("SELECT proxy FROM user_proxy WHERE user_id = ?", [user_id])
    return row[0] if row else None

# ============ SHOPIFY GATEWAY ============
from gateway.api.shopify import check_shopify, get_bin_info
from economy.balances.manager import get_balance, add_balance
from economy.ledger.create import create_ledger_entry
from economy.reserve.reserve import add_reserve

COST = {
    "CHARGED": 0.1,
    "LIVE": 0.01,
    "DEAD": 0.001,
    "ERROR": 0.0,
    "CAPTCHA_REQUIRED": 0.0
}

COST_BRAINTREE = {
    "APPROVED": 0.1,
    "DEAD": 0.001,
    "RISK": 0.0,
    "ERROR": 0.0,
    "SKIP": 0.0
}

async def br_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    user_id = update.effective_user.id
    
    # Cooldown
    sisa = check_cooldown(user_id, "sh")  # pake cooldown yang sama
    if sisa > 0:
        await update.message.reply_text(f"⏳ Cooldown — tunggu {sisa:.1f} detik lagi.")
        return
    set_cooldown(user_id, "sh")
    
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /br <cc|mm|yy|cvv>\nContoh: /br 4539730059665764|08|2026|123")
        return
    
    card_str = args[0]
    parts = card_str.split("|")
    if len(parts) < 4:
        await update.message.reply_text("❌ Format salah. Gunakan: cc|mm|yy|cvv")
        return
    
    msg = await update.message.reply_text("⏳ Processing...")
    
    result = await check_braintree(card_str)
    status = result.get("status", "ERROR")
    response_text = result.get("response", "N/A")
    gate = result.get("gate", "Braintree Auth")
    time_taken = result.get("time", "N/A")
    
    cost = COST_BRAINTREE.get(status, 0.0)
    new_bal = None
    
    if cost > 0:
        current = get_balance(user_id)
        if current < cost:
            await msg.edit_text(f"❌ Insufficient balance. Need {cost} RSM")
            return
        new_bal = add_balance(user_id, -cost)
        add_reserve(cost, f"braintree_fee_{user_id}_{int(time.time())}")
        create_ledger_entry(user_id, "GATEWAY_FEE", -cost, current, new_bal,
                            f"Braintree check - {status} - {card_str[:12]}...")
    
    # Format output
    if status == "APPROVED":
        emoji, statustxt = "🔥", "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 🔥"
    elif status == "DEAD":
        emoji, statustxt = "💀", "𝐃𝐞𝐚𝐝 💀"
    elif status == "RISK":
        emoji, statustxt = "🏴‍☠️", "𝐑𝐢𝐬𝐤 🏴‍☠️"
    else:
        emoji, statustxt = "⚠️", "𝐄𝐫𝐫𝐨𝐫 ⚠️"
    
    elapsed = time.time() - start_time
    
    output = f"""{emoji} 𝗕𝗥𝗔𝗜𝗡𝗧𝗥𝗘𝗘 𝗔𝗨𝗧𝗛 {emoji}
-------------------------------------------------------
💳 Card: {card_str}
💬 Status: {statustxt}
🔔 Response: {response_text}
⚙️ Gateway: {gate}
⏱️ Time: {time_taken if time_taken != 'N/A' else f'{elapsed:.2f}s'}
-------------------------------------------------------
💲 Cost: {cost} RSM"""
    
    await msg.edit_text(output.strip())
    if cost > 0 and new_bal is not None:
        await update.message.reply_text(f"💰 Debited {cost} RSM (Balance: {new_bal:.6f} RSM)")
        
async def mbr_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_total = time.time()
    user_id = update.effective_user.id
    
    sisa = check_cooldown(user_id, "msh")
    if sisa > 0:
        await update.message.reply_text(f"⏳ Cooldown — tunggu {sisa:.1f} detik lagi.")
        return
    set_cooldown(user_id, "msh")
    
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /mbr <card1> <card2> ... (max 20 cards)")
        return
    
    cards = args[:20]
    total_cards = len(cards)
    if total_cards == 0:
        return
    
    msg = await update.message.reply_text(f"⏳ Processing {total_cards} cards...")
    
    tasks = [check_braintree(card) for card in cards]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_cost = 0.0
    current_balance = get_balance(user_id)
    initial_balance = current_balance
    output_lines = []
    
    stats = {"approved": 0, "dead": 0, "risk": 0, "skip": 0, "error": 0}
    
    for idx, (card, result) in enumerate(zip(cards, results), 1):
        if isinstance(result, Exception):
            stats["error"] += 1
            output_lines.append(f"{idx}. ❌ Error: {str(result)[:30]}")
            continue
        
        status = result.get("status", "ERROR")
        cost = COST_BRAINTREE.get(status, 0.0)
        
        if cost > 0:
            if current_balance < cost:
                stats["skip"] += 1
                output_lines.append(f"{idx}. ⚠️ Insufficient balance, skipped.")
                continue
            old_bal = current_balance
            current_balance = add_balance(user_id, -cost)
            create_ledger_entry(user_id, "GATEWAY_FEE", -cost, old_bal, current_balance,
                                f"Mass Braintree - {status} - {card[:12]}...")
            add_reserve(cost, f"braintree_mass_{user_id}_{int(time.time())}_{idx}")
            total_cost += cost
        
        response_text = result.get("response", "N/A")
        
        if status == "APPROVED":
            stats["approved"] += 1
            emoji = "🔥"
            statustxt = "Approved"
        elif status == "DEAD":
            stats["dead"] += 1
            emoji = "💀"
            statustxt = "Dead"
        elif status == "RISK":
            stats["risk"] += 1
            emoji = "🏴‍☠️"
            statustxt = "Risk"
        else:
            stats["error"] += 1
            emoji = "⚠️"
            statustxt = "Error"
        
        output_lines.append(f"{idx}. {emoji} {statustxt} | {card[:20]}... | {response_text[:30]}")
    
    final_balance = get_balance(user_id)
    total_debited = initial_balance - final_balance
    elapsed = time.time() - start_total
    
    final_text = f"""✅ MASS CHECK COMPLETED
Total cards: {total_cards} | Total debited: {total_debited:.4f} RSM
New Balance: {final_balance:.6f} RSM
⏱️ Total time: {elapsed:.2f} seconds

🔥 Approved: {stats['approved']}
💀 Dead: {stats['dead']}
🏴‍☠️ Risk: {stats['risk']}
⚠️ Skip: {stats['skip']}
❌ Error: {stats['error']}

{chr(10).join(output_lines[:20])}"""
    
    if len(final_text) > 4000:
        await msg.edit_text(final_text[:2000])
        await update.message.reply_text(final_text[2000:4000])
    else:
        await msg.edit_text(final_text)
    
    if total_cost > 0:
        await update.message.reply_text(f"💰 Total fee deducted: {total_cost:.4f} RSM")
        
async def brtxt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text("❌ Reply ke file .txt yang berisi kartu\nContoh: /brtxt (reply ke file txt)")
        return

    document = update.message.reply_to_message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Harus file .txt")
        return

    status_msg = await update.message.reply_text("📥 Downloading file...")
    file = await document.get_file()
    file_content = await file.download_as_bytearray()
    text_content = file_content.decode('utf-8', errors='ignore')

    lines = text_content.split('\n')
    cards = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        card = line.replace('/', '|')
        parts = card.split('|')
        if len(parts) >= 4:
            cards.append(f"{parts[0]}|{parts[1]}|{parts[2]}|{parts[3]}")

    total_cards = len(cards)
    if total_cards == 0:
        await status_msg.edit_text("❌ Tidak ada kartu valid dalam file")
        return

    if total_cards > 20000:
        cards = cards[:20000]
        total_cards = 20000

    await status_msg.edit_text(f"⏳ Processing {total_cards} cards...")

    stats = {"approved": 0, "dead": 0, "risk": 0, "skip": 0, "error": 0}
    total_cost = 0.0
    current_balance = get_balance(user_id)
    initial_balance = current_balance
    processed = 0

    for idx, card in enumerate(cards, 1):
        result = await check_braintree(card)
        processed += 1
        status = result.get("status", "ERROR")
        cost = COST_BRAINTREE.get(status, 0.0)

        card_display = card[:20] + "..." if len(card) > 20 else card
        response_display = result.get('response', 'N/A')[:40]

        if cost > 0:
            if current_balance < cost:
                stats["skip"] += 1
                continue
            old_bal = current_balance
            current_balance = add_balance(user_id, -cost)
            create_ledger_entry(user_id, "GATEWAY_FEE", -cost, old_bal, current_balance,
                                f"TXT Braintree - {status} - {card[:12]}...")
            add_reserve(cost, f"brtxt_{user_id}_{int(time.time())}_{idx}")
            total_cost += cost

        if status == "APPROVED":
            stats["approved"] += 1
        elif status == "DEAD":
            stats["dead"] += 1
        elif status == "RISK":
            stats["risk"] += 1
        else:
            stats["error"] += 1

        # UPDATE TIAP 5 KARTU (Biar gak kena rate limit)
        if processed % 5 == 0 or processed == total_cards:
            progress_text = f"""⏳ PROGRESS: {processed}/{total_cards}
💳 Card: {card_display}
🫆 Response: {response_display}

🔥 Approved: {stats['approved']}
💀 Dead: {stats['dead']}
🏴‍☠️ Risk: {stats['risk']}
⚠️ Skip: {stats['skip']}
❌ Error: {stats['error']}"""
            try:
                await status_msg.edit_text(progress_text)
            except:
                pass

    final_balance = get_balance(user_id)
    total_debited = initial_balance - final_balance

    final_text = f"""✅ TXT CHECK COMPLETED

📁 Total cards: {total_cards}

🔥 Approved: {stats['approved']}
💀 Dead: {stats['dead']}
🏴‍☠️ Risk: {stats['risk']}
⚠️ Skip: {stats['skip']}
❌ Error: {stats['error']}

💰 Total debited: {total_debited:.4f} RSM
💎 New Balance: {final_balance:.6f} RSM"""

    await status_msg.edit_text(final_text)

async def sh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    user_id = update.effective_user.id
    sisa = check_cooldown(user_id, "sh")
    if sisa > 0:
        await update.message.reply_text(f"⏳ Cooldown /sh — tunggu {sisa:.1f} detik lagi.")
        return
    set_cooldown(user_id, "sh")
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /sh <cc|mm|yy|cvv>\nContoh: /sh 5258551761432947|12|28|456")
        return
    card_str = args[0]
    parts = card_str.split("|")
    if len(parts) < 4:
        await update.message.reply_text("❌ Format salah. Gunakan: cc|mm|yy|cvv")
        return
    
    proxy = await get_user_proxy(user_id)
    if not proxy:
        await update.message.reply_text("❌ Anda harus set proxy terlebih dahulu. Gunakan /setproxy")
        return
    
    msg = await update.message.reply_text("⏳ Processing...")
    try:
        result = await check_shopify(card_str, proxy)
        status = result.get("status", "ERROR")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")
        return
    
    cost = COST.get(status, 0.0)
    new_bal = None
    if cost > 0:
        current = get_balance(user_id)
        if current < cost:
            await msg.edit_text(f"❌ Insufficient balance. Need {cost} RSM")
            return
        new_bal = add_balance(user_id, -cost)
        add_reserve(cost, f"shopify_fee_{user_id}_{int(time.time())}")
        create_ledger_entry(user_id, "GATEWAY_FEE", -cost, current, new_bal,
                            f"Shopify check - {status} - {card_str[:12]}...")
    
    bin6 = parts[0][:6]
    bin_info = await get_bin_info(bin6)
    elapsed = time.time() - start_time
    
    if status == "CHARGED":
        emoji, statustxt = "🔥", "𝐂𝐡𝐚𝐫𝐠𝐞𝐝 🔥"
    elif status == "LIVE":
        emoji, statustxt = "💳", "𝐋𝐢𝐯𝐞 💳"
    elif status == "DEAD":
        emoji, statustxt = "💀", "𝐃𝐞𝐚𝐝 💀"
    elif status == "CAPTCHA_REQUIRED":
        emoji, statustxt = "🤖", "𝐂𝐚𝐩𝐭𝐜𝐡𝐚 🤖"
    else:
        emoji, statustxt = "⚠️", "𝐄𝐫𝐫𝐨𝐫 ⚠️"
    
    if status == "ERROR":
        amount_display = "-"
    else:
        amount_display = f"{result.get('amount', '0')} {result.get('currency', 'USD')}"
    
    raw = result.get('raw', {})
    response_text = raw.get('response', 'N/A') if isinstance(raw, dict) else str(raw)[:50]
    
    output = f"""{emoji} 𝗦𝗛𝗢𝗣𝗜𝗙𝗬 𝗖𝗛𝗞 {emoji}
-------------------------------------------------------
💳 Card: {card_str}
💬 Status: {statustxt}
🔔 Response: {response_text}
⚙️ Gateway: Shopify Payments
⏱️ Time: {elapsed:.2f} seconds
-------------------------------------------------------
ℹ️ Info ↬ {bin_info.get('brand', 'Unknown')} | {bin_info.get('card_type', 'Unknown')}
🏦 Bank ↬ {bin_info.get('bank', 'Unknown')}
🌍 Country ↬ {bin_info.get('country', 'Unknown')} {bin_info.get('country_flag', '')}
💲 Amount: {amount_display}"""
    await msg.edit_text(output.strip())
    if cost > 0 and new_bal is not None:
        await update.message.reply_text(f"💰 Debited {cost} RSM (Balance: {new_bal:.6f} RSM)")

async def msh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_total = time.time()
    user_id = update.effective_user.id
    sisa = check_cooldown(user_id, "msh")
    if sisa > 0:
        await update.message.reply_text(f"⏳ Cooldown /msh — tunggu {sisa:.1f} detik lagi.")
        return
    set_cooldown(user_id, "msh")
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /msh <card1> <card2> ... (max 20 cards)")
        return

    cards = args[:20]
    total_cards = len(cards)
    if total_cards == 0:
        return

    proxy = await get_user_proxy(user_id)
    if not proxy:
        await update.message.reply_text("❌ Anda harus set proxy terlebih dahulu. Gunakan /setproxy")
        return

    msg = await update.message.reply_text(f"⏳ Processing {total_cards} cards...\nPlease wait, proses berjalan di background.")

    tasks = [check_shopify(card, proxy) for card in cards]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    total_cost = 0.0
    all_output_lines = []
    current_balance = get_balance(user_id)
    initial_balance = current_balance

    for idx, (card, result) in enumerate(zip(cards, results), 1):
        if isinstance(result, Exception):
            all_output_lines.append(f"{idx}. ❌ Error: {str(result)[:30]}")
            continue

        status = result.get("status", "ERROR")
        cost = COST.get(status, 0.0)

        if cost > 0:
            if current_balance < cost:
                all_output_lines.append(f"{idx}. ⚠️ Insufficient balance, skipped.")
                continue
            old_bal = current_balance
            current_balance = add_balance(user_id, -cost)
            create_ledger_entry(user_id, "GATEWAY_FEE", -cost, old_bal, current_balance,
                                f"Mass Shopify - {status} - {card[:12]}...")
            add_reserve(cost, f"shopify_mass_{user_id}_{int(time.time())}_{idx}")
            total_cost += cost

        bin6 = card.split("|")[0][:6]
        bin_info = await get_bin_info(bin6)

        if status == "ERROR":
            amount_display = "-"
        else:
            amount_display = f"{result.get('amount', '0')} {result.get('currency', 'USD')}"

        if status == "CHARGED":
            emoji, statustxt = "🔥", "𝐂𝐡𝐚𝐫𝐠𝐞𝐝 🔥"
        elif status == "LIVE":
            emoji, statustxt = "💳", "𝐋𝐢𝐯𝐞 💳"
        elif status == "DEAD":
            emoji, statustxt = "💀", "𝐃𝐞𝐚𝐝 💀"
        elif status == "CAPTCHA_REQUIRED":
            emoji, statustxt = "🤖", "𝐂𝐚𝐩𝐭𝐜𝐡𝐚 🤖"
        else:
            emoji, statustxt = "⚠️", "𝐄𝐫𝐫𝐨𝐫 ⚠️"

        raw = result.get('raw', {})
        response_text = raw.get('response', 'N/A') if isinstance(raw, dict) else str(raw)[:50]

        part = f"""{emoji} 𝗦𝗛𝗢𝗣𝗜𝗙𝗬 𝗖𝗛𝗞 {emoji}
-------------------------------------------------------
💳 Card: {card}
💬 Status: {statustxt}
🔔 Response: {response_text}
⚙️ Gateway: Shopify Payments
-------------------------------------------------------
ℹ️ Info ↬ {bin_info.get('brand', 'Unknown')} | {bin_info.get('card_type', 'Unknown')}
🏦 Bank ↬ {bin_info.get('bank', 'Unknown')}
🌍 Country ↬ {bin_info.get('country', 'Unknown')} {bin_info.get('country_flag', '')}
💲 Amount: {amount_display}"""
        all_output_lines.append(part)

    final_balance = get_balance(user_id)
    total_debited = initial_balance - final_balance
    elapsed = time.time() - start_total

    final_text = f"✅ MASS CHECK COMPLETED\nTotal cards: {total_cards} | Total debited: {total_debited:.4f} RSM\nNew Balance: {final_balance:.6f} RSM\n⏱️ Total time: {elapsed:.2f} seconds\n\n"
    full_output = final_text + "\n\n".join(all_output_lines)

    if len(full_output) > 4000:
        await msg.edit_text(final_text)
        for i in range(0, len(all_output_lines), 3):
            chunk = "\n\n".join(all_output_lines[i:i+3])
            try:
                await update.message.reply_text(chunk)
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error sending chunk: {e}")
    else:
        await msg.edit_text(full_output)

    if total_cost > 0:
        await update.message.reply_text(f"💰 Total fee deducted: {total_cost:.4f} RSM")

async def shtxt_stop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    data = query.data
    parts = data.split(":")
    if len(parts) != 2:
        await query.answer()
        return

    requester_id = query.from_user.id
    owner_id = int(parts[1])

    if requester_id != owner_id:
        await query.answer("❌ Ini bukan session kamu.", show_alert=True)
        return

    await query.answer()  # answer SETELAH validasi ownership passed

    if owner_id in _shtxt_sessions:
        _shtxt_sessions[owner_id].set()
        await query.edit_message_text("🛑 Stop signal dikirim, menunggu batch selesai...")
    else:
        await query.edit_message_text("ℹ️ Session sudah tidak aktif.")

async def send_card_detail(update: Update, card: str, status: str, result: dict, bin_info: dict, username: str):
    amount_display = f"{result.get('amount', '0')} {result.get('currency', 'USD')}"
    if status == "CHARGED":
        emoji = "🔥"
        status_text = "𝐂𝐡𝐚𝐫𝐠𝐞𝐝 🔥"
    else:
        emoji = "⚡"
        status_text = "𝐋𝐢𝐯𝐞 ⚡"

    level = bin_info.get('level', bin_info.get('card_type', 'Unknown'))

    raw = result.get('raw', {})
    response_text = raw.get('response', 'N/A') if isinstance(raw, dict) else str(raw)[:60]

    msg = f"""{emoji} {status_text}
💳 𝗖𝗖: {card}
🔔 𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲: {response_text}
⚙️ 𝗚𝗮𝘁𝗲: 𝗦𝗵𝗼𝗽𝗶𝗳𝘆 𝗣𝗮𝘆𝗺𝗲𝗻𝘁𝘀
💲 𝗣𝗿𝗶𝗰𝗲: {amount_display}
━━━━━━━━━━━━━━━━━━━━━━
ℹ️ 𝗜𝗻𝗳𝗼: {bin_info.get('brand', 'Unknown')} | {bin_info.get('card_type', 'Unknown')} | {level}
🏦 𝗕𝗮𝗻𝗸: {bin_info.get('bank', 'Unknown')}
🌍 𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_info.get('country_flag', '')} {bin_info.get('country', 'Unknown')}
👤 𝗖𝗵𝗲𝗰𝗸𝗲𝗱 𝗯𝘆: @{username}"""

    await update.message.reply_text(msg)

async def shtxt_stop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk tombol STOP di /shtxt."""
    query = update.callback_query
    await query.answer()

    data = query.data  # format: "shtxt_stop:<user_id>"
    parts = data.split(":")
    if len(parts) != 2:
        return

    requester_id = query.from_user.id
    owner_id = int(parts[1])

    if requester_id != owner_id:
        await query.answer("❌ Ini bukan session kamu.", show_alert=True)
        return

    if owner_id in _shtxt_sessions:
        _shtxt_sessions[owner_id].set()  # trigger stop signal
        await query.edit_message_text("🛑 Stop signal dikirim, menunggu batch selesai...")
    else:
        await query.edit_message_text("ℹ️ Session sudah tidak aktif.")

async def shtxt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    user_id = update.effective_user.id

    # Cek apakah user sudah punya session aktif
    if user_id in _shtxt_sessions:
        await update.message.reply_text(
            "⚠️ Kamu masih punya /shtxt yang sedang berjalan.\n"
            "Tunggu sampai selesai atau tekan tombol STOP di pesan sebelumnya."
        )
        return

    # Cek cooldown 10 detik setelah selesai/stop
    sisa_cd = _shtxt_cooldown.get(user_id, 0)
    sisa_detik = COOLDOWN_SECONDS["shtxt"] - (time.time() - sisa_cd)
    if sisa_cd > 0 and sisa_detik > 0:
        await update.message.reply_text(
            f"⏳ Cooldown /shtxt — tunggu {sisa_detik:.1f} detik lagi."
        )
        return

    start_total = time.time()

    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text("❌ Reply ke file .txt yang berisi kartu\nContoh: /shtxt (reply ke file txt)")
        return

    document = update.message.reply_to_message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("❌ Harus file .txt")
        return

    username = update.effective_user.username or update.effective_user.first_name

    proxy = await get_user_proxy(user_id)
    if not proxy:
        await update.message.reply_text("❌ Anda harus set proxy terlebih dahulu. Gunakan /setproxy")
        return

    status_msg = await update.message.reply_text("📥 Downloading file...")
    file = await document.get_file()
    file_content = await file.download_as_bytearray()
    text_content = file_content.decode('utf-8', errors='ignore')

    lines = text_content.split('\n')
    cards = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        card = line.replace('/', '|')
        parts_card = card.split('|')
        if len(parts_card) >= 4:
            cards.append(f"{parts_card[0]}|{parts_card[1]}|{parts_card[2]}|{parts_card[3]}")

    total_cards = len(cards)
    if total_cards == 0:
        await status_msg.edit_text("❌ Tidak ada kartu valid dalam file")
        return

    if total_cards > 20000:
        cards = cards[:20000]
        total_cards = 20000

    # Daftarkan session — stop_event digunakan sebagai sinyal berhenti
    stop_event = asyncio.Event()
    _shtxt_sessions[user_id] = stop_event

    stop_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛑 STOP", callback_data=f"shtxt_stop:{user_id}")]
    ])

    await status_msg.edit_text(
        f"⏳ Processing {total_cards} cards in batches of 5...\n"
        f"Tekan STOP untuk menghentikan.",
        reply_markup=stop_keyboard
    )

    stats = {"total": total_cards, "charged": 0, "live": 0, "dead": 0, "skip": 0, "error": 0}
    total_cost = 0.0
    current_balance = get_balance(user_id)
    initial_balance = current_balance
    processed = 0
    last_edit_time = 0
    batch_size = 5
    stopped_early = False

    try:
        for batch_start in range(0, total_cards, batch_size):
            # Cek stop signal sebelum tiap batch
            if stop_event.is_set():
                stopped_early = True
                break

            batch_cards = cards[batch_start:batch_start + batch_size]
            tasks = [check_shopify(card, proxy) for card in batch_cards]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for card, result in zip(batch_cards, batch_results):
                processed += 1

                if isinstance(result, Exception):
                    stats["error"] += 1
                    continue

                status = result.get("status", "ERROR")
                cost = COST.get(status, 0.0)

                if cost > 0:
                    if current_balance < cost:
                        stats["skip"] += 1
                        continue
                    old_bal = current_balance
                    current_balance = add_balance(user_id, -cost)
                    create_ledger_entry(user_id, "GATEWAY_FEE", -cost, old_bal, current_balance,
                                        f"TXT Shopify - {status} - {card[:12]}...")
                    add_reserve(cost, f"shopify_txt_{user_id}_{int(time.time())}_{processed}")
                    total_cost += cost

                bin6 = card.split("|")[0][:6]
                bin_info = await get_bin_info(bin6)

                if status == "CHARGED":
                    stats["charged"] += 1
                    await send_card_detail(update, card, status, result, bin_info, username)
                elif status == "LIVE":
                    stats["live"] += 1
                    await send_card_detail(update, card, status, result, bin_info, username)
                elif status == "DEAD":
                    stats["dead"] += 1
                elif status == "CAPTCHA_REQUIRED":
                    stats["skip"] += 1
                elif status == "ERROR":
                    stats["error"] += 1

                if processed % 10 == 0 or processed == total_cards:
                    if time.time() - last_edit_time >= 2.0 or processed == total_cards:
                        progress_text = (
                            f"📊 PROGRESS: {processed}/{total_cards}\n"
                            f"🔥 Charged: {stats['charged']}\n"
                            f"💳 Live: {stats['live']}\n"
                            f"💀 Dead: {stats['dead']}\n"
                            f"⚠️ Skip: {stats['skip']}\n"
                            f"❌ Error: {stats['error']}"
                        )
                        try:
                            await status_msg.edit_text(progress_text, reply_markup=stop_keyboard)
                            last_edit_time = time.time()
                        except Exception:
                            pass

            await asyncio.sleep(1.0)

    finally:
        # Selalu bersihkan session dan set cooldown, baik selesai normal maupun stop
        _shtxt_sessions.pop(user_id, None)
        _shtxt_cooldown[user_id] = time.time()

    final_balance = get_balance(user_id)
    total_debited = initial_balance - final_balance
    elapsed = time.time() - start_total

    if stopped_early:
        header = "🛑 TXT CHECK DIHENTIKAN"
        processed_info = f"📌 Diproses: {processed}/{total_cards} kartu\n"
    else:
        header = "✅ TXT CHECK COMPLETED"
        processed_info = f"📁 Total cards: {total_cards}\n"

    final_text = (
        f"{header}\n\n"
        f"{processed_info}"
        f"🔥 Charged: {stats['charged']}\n"
        f"💳 Live: {stats['live']}\n"
        f"💀 Dead: {stats['dead']}\n"
        f"⚠️ Skip: {stats['skip']}\n"
        f"❌ Error: {stats['error']}\n\n"
        f"💰 Total debited: {total_debited:.4f} RSM\n"
        f"💎 New Balance: {final_balance:.6f} RSM\n"
        f"⏱️ Total time: {elapsed:.2f} seconds"
    )

    await status_msg.edit_text(final_text)


async def shop_stub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚧 /shop - Coming soon")

# ============ DEPOSIT & OTHER COMMANDS ============
async def list_claimed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = fetch_all("SELECT ref_id, claimed_at FROM claimed_deposits WHERE user_id = ? ORDER BY claimed_at DESC LIMIT 10", [user_id])
    if not rows:
        await update.message.reply_text("📭 No claimed deposits yet.")
        return
    lines = ["📋 Last claimed deposits:"]
    for ref_id, ts in rows:
        lines.append(f"• {ref_id} - {time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))}")
    await update.message.reply_text("\n".join(lines))

async def deposit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Usage: /deposit <amount>\nContoh: /deposit 10")
        return
    try:
        amount = float(args[0])
        if amount < 0.01:
            await update.message.reply_text("❌ Minimal deposit 0.01 RSM")
            return
    except ValueError:
        await update.message.reply_text("❌ Invalid amount")
        return
    
    from economy.deposits.create_invoice import create_invoice
    invoice = create_invoice(update.effective_user.id, amount)
    
    if invoice["status"] == "failed":
        await update.message.reply_text(f"❌ Failed: {invoice.get('reason')}")
        return
    
    # INI HARUS KELUAR DARI IF
    msg = f"""💳 INVOICE
💰 {amount:.2f} RSM
💵 Rate: {invoice['rsm_rate']:,.0f} IDR/RSM
💰 Total: {invoice['amount_idr']:,.0f} IDR
🆔 Ref ID: {invoice['ref_id']}
🔗 {invoice['pay_url']}
Expired: {invoice['expire']}

After payment: /check {invoice['ref_id']}"""
    
    await update.message.reply_text(msg)

async def check_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /check <ref_id>")
        return
    from economy.deposits.status import check_status
    from economy.deposits.verify_payment import verify_payment
    status = check_status(args[0])
    if status["status"] == "success":
        result = verify_payment(args[0], update.effective_user.id, status["amount"])
        if result and result.get("status") == "already_claimed":
            await update.message.reply_text("Already claimed")
        else:
            await update.message.reply_text(f"✅ Verified! +{status['amount']:.2f} RSM")
    else:
        await update.message.reply_text(f"Status: {status['status']}")

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from economy.balances.manager import get_balance
    bal = get_balance(update.effective_user.id)
    await update.message.reply_text(f"💰 BALANCE: {bal:.6f} RSM")

async def wallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from economy.wallets.lookup import get_wallet_by_telegram_id
    from economy.balances.manager import get_balance
    from services.gold_price import get_rsm_rate
    user_id = update.effective_user.id
    wallet = get_wallet_by_telegram_id(user_id)
    balance = get_balance(user_id)
    rsm_rate, gold_idr, usd_rate = get_rsm_rate()
    rows = fetch_all("SELECT ref_id, amount, claimed_at FROM claimed_deposits WHERE user_id = ? ORDER BY claimed_at DESC LIMIT 10", [user_id])
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
    await update.message.reply_text(text, parse_mode="Markdown")

async def cancel_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")

# ============ MAIN ============
def main():
    app = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("wallet", wallet_cmd))
    app.add_handler(CommandHandler("deposit", deposit_cmd))
    app.add_handler(CommandHandler("check", check_cmd))
    app.add_handler(CommandHandler("cancel", cancel_deposit))
    app.add_handler(CommandHandler("claimed", list_claimed))
    app.add_handler(CommandHandler("transfer", transfer_cmd))
    app.add_handler(CommandHandler("setproxy", set_proxy_cmd))
    app.add_handler(CommandHandler("proxy", proxy_cmd))
    app.add_handler(CommandHandler("removeproxy", remove_proxy_cmd))
    app.add_handler(CommandHandler("sh", sh_cmd))
    app.add_handler(CommandHandler("msh", msh_cmd))
    app.add_handler(CommandHandler("shtxt", shtxt_cmd))
    app.add_handler(CommandHandler("shop", shop_stub))
    app.add_handler(CommandHandler("br", br_cmd))
    app.add_handler(CommandHandler("mbr", mbr_cmd))
    app.add_handler(CommandHandler("brtxt", brtxt_cmd))
    app.add_handler(CallbackQueryHandler(shtxt_stop_callback, pattern=r"^shtxt_stop:"))
    app.add_handler(CallbackQueryHandler(menu_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_response_handler))
    print("🤖 Schutz CHK Bot running...")
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()