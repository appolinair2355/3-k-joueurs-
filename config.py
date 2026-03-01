"""
Configuration centralisée du bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API Configuration
API_ID = int(os.getenv('API_ID', '29177661'))
API_HASH = os.getenv('API_HASH', 'a8639172fa8d35dbfd8ea46286d349ab')
BOT_TOKEN = os.getenv('BOT_TOKEN', '7830176220:AAGPSbyhxLazb1G6IVCzen5oUbGPDwx7wY0')
ADMIN_ID = int(os.getenv('ADMIN_ID', '1190237801'))

# Channel Configuration
PREDICTION_CHANNEL_ID = int(os.getenv('PREDICTION_CHANNEL_ID', '-1003711328345'))
SOURCE_CHANNEL_ID = int(os.getenv('SOURCE_CHANNEL_ID', '-1002682552255'))

# Suit configuration
SUIT_SYMBOLS = ['♣️', '♦️', '❤️', '♠️']
SUIT_NAMES = {
    '♣️': 'Trèfle',
    '♦️': 'Carreau',
    '❤️': 'Cœur',
    '♠️': 'Pique'
}

