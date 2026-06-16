import json
import time
import os
import requests
from datetime import datetime

CACHE_FILE = "cache/gold_price.json"
CACHE_TTL = 43200  # 12 jam

# ============ KONFIGURASI AWAL ============
# Harga emas awal (per gram) sesuai hari ini
GOLD_INITIAL_IDR = 2407026  # Rp2.407.026 per gram

# 1 RSM awal = 10.000 IDR
RSM_INITIAL_IDR = 10000

# Hitung berapa gram emas yang bisa dibeli dengan 10.000 IDR di awal
GRAM_PER_RSM = RSM_INITIAL_IDR / GOLD_INITIAL_IDR  # ~ 0.00415 gram
# ===========================================


def get_usd_to_idr():
    """Dapatkan kurs USD/IDR realtime"""
    try:
        url = "https://api.frankfurter.app/latest?from=USD&to=IDR"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        return data["rates"]["IDR"]
    except Exception as e:
        print(f"⚠️ Gagal ambil kurs: {e}, pake default 16000")
        return 16000.0


def get_gold_price_usd_per_gram():
    """Harga emas per gram dalam USD dari API"""
    try:
        # Pake API gratis untuk harga emas real-time
        # Fallback: 1 oz = 31.1035 gram, harga emas ~ 2650 USD/oz (2026)
        # Tapi lebih baik ambil dari API
        url = "https://api.gold-api.com/price/XAU"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            price_per_ounce = data.get("price", 2650)
        else:
            price_per_ounce = 2650.0
        return price_per_ounce / 31.1035
    except Exception:
        # Fallback harga emas per gram ~ 85 USD
        return 85.0


def get_current_gold_price():
    """Dapatkan harga emas terkini dalam IDR per gram"""
    usd_rate = get_usd_to_idr()
    gold_usd = get_gold_price_usd_per_gram()
    gold_idr = gold_usd * usd_rate
    return gold_idr, usd_rate


def get_rsm_rate():
    """
    Hitung 1 RSM berdasarkan harga emas terkini:
    1 RSM = 10.000 × (harga_emas_sekarang / harga_emas_awal)
    """
    current_gold_idr, usd_rate = get_current_gold_price()
    
    # Rasio kenaikan/penurunan emas
    gold_ratio = current_gold_idr / GOLD_INITIAL_IDR
    
    # 1 RSM = 10.000 × rasio
    rsm_rate = round(RSM_INITIAL_IDR * gold_ratio, 2)
    
    return rsm_rate, current_gold_idr, usd_rate
