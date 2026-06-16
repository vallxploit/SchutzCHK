from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📋 Command", callback_data="menu_command"),
            InlineKeyboardButton("🏦 Wallet", callback_data="menu_wallet")
        ],
        [
            InlineKeyboardButton("🏦 Reserve / Bank", callback_data="menu_reserve")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_wallet_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu_back")]]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu_back")]]
    return InlineKeyboardMarkup(keyboard)

def get_reserve_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu_back")]]
    return InlineKeyboardMarkup(keyboard)
