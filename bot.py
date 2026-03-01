#!/usr/bin/env python3
"""
Bot Telegram de Prédiction - Détection de 3 costumes différents
"""
import os
import sys
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, PREDICTION_CHANNEL_ID, SOURCE_CHANNEL_ID
from prediction_engine import engine

# Stockage des IDs de messages pour édition
prediction_messages = {}  # game_number -> (message_id, prediction_data)

async def start_bot():
    """Démarre le bot principal"""
    
    if not all([API_ID, API_HASH, BOT_TOKEN]):
        logger.error("❌ Configuration incomplète!")
        return
    
    session = os.getenv('TELEGRAM_SESSION', '')
    client = TelegramClient(StringSession(session), API_ID, API_HASH)
    
    try:
        await client.start(bot_token=BOT_TOKEN)
        me = await client.get_me()
        logger.info(f"✅ Bot connecté: @{me.username}")
        
        # Message de démarrage à l'admin
        try:
            await client.send_message(ADMIN_ID, "🤖 Bot de prédiction démarré!")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de contacter l'admin: {e}")
        
    except Exception as e:
        logger.error(f"❌ Erreur connexion: {e}")
        return
    
    # Handler messages du canal source
    @client.on(events.NewMessage(chats=SOURCE_CHANNEL_ID))
    async def handle_source(event):
        try:
            text = event.message.message
            logger.info(f"📩 Source: {text[:80]}...")
            
            # 1. Vérifier d'abord si c'est une vérification de prédiction précédente
            if engine.pending_prediction and not engine.pending_prediction.get('verified'):
                verification = engine.check_verification(text)
                
                if verification == 'success':
                    # Éditer le message de prédiction pour montrer le succès
                    game_num = engine.pending_prediction['game_number']
                    if game_num in prediction_messages:
                        msg_id, _ = prediction_messages[game_num]
                        new_text = engine.format_success(engine.pending_prediction)
                        try:
                            await client.edit_message(PREDICTION_CHANNEL_ID, msg_id, new_text)
                            logger.info(f"✅ Message édité: Succès jeu {game_num}")
                        except Exception as e:
                            logger.error(f"❌ Erreur édition: {e}")
                            # Envoyer nouveau message si édition échoue
                            await client.send_message(PREDICTION_CHANNEL_ID, new_text)
                    
                    engine.pending_prediction = None  # Reset pour prochaine prédiction
                    return
                    
                elif verification == 'failure':
                    # Éditer le message pour montrer l'échec
                    game_num = engine.pending_prediction['game_number']
                    if game_num in prediction_messages:
                        msg_id, _ = prediction_messages[game_num]
                        new_text = engine.format_failure(engine.pending_prediction)
                        try:
                            await client.edit_message(PREDICTION_CHANNEL_ID, msg_id, new_text)
                            logger.info(f"❌ Message édité: Échec jeu {game_num}")
                        except Exception as e:
                            await client.send_message(PREDICTION_CHANNEL_ID, new_text)
                    
                    engine.pending_prediction = None
                    return
            
            # 2. Analyser pour nouvelle prédiction
            result = engine.analyze(text)
            
            if engine.should_predict(result):
                prediction = engine.generate_prediction(result)
                if prediction:
                    msg_text = engine.format_prediction(prediction)
                    
                    # Envoyer la prédiction
                    sent_msg = await client.send_message(PREDICTION_CHANNEL_ID, msg_text)
                    
                    # Stocker l'ID pour édition ultérieure
                    prediction_messages[prediction['game_number']] = (sent_msg.id, prediction)
                    engine.last_prediction_message_id = sent_msg.id
                    
                    logger.info(f"🎯 Prédiction envoyée: Jeu {prediction['game_number']}, Numéro {prediction['target_number']}")
            else:
                logger.info(f"ℹ️ Pas de prédiction (final={result.is_final}, 3diff={result.has_three_different_suits})")
                
        except Exception as e:
            logger.error(f"❌ Erreur handle_source: {e}")
    
    # Handler commandes admin
    @client.on(events.NewMessage(from_users=ADMIN_ID, pattern='/'))
    async def handle_admin(event):
        try:
            cmd = event.message.message.lower().split()[0]
            
            if cmd == '/status':
                status = f"""📊 **Statut**
                
🎮 Jeu: n°{engine.current_game_number}
⏳ En attente: {'Oui' if engine.pending_prediction else 'Non'}
🎯 Dernier: {engine.pending_prediction['target_number'] if engine.pending_prediction else 'Aucun'}"""
                await event.respond(status)
            
            elif cmd == '/test':
                test_msg = "Test (♣️♦️❤️) finaliser 15"
                result = engine.analyze(test_msg)
                predict = engine.generate_prediction(result)
                await event.respond(f"""🧪 Test:
Message: {test_msg}
Costumes: {result.suits}
3 différents: {result.has_three_different_suits}
Prédiction: {predict['target_number'] if predict else 'Non'}""")
                # Reset après test
                engine.pending_prediction = None
            
            elif cmd == '/reset':
                engine.pending_prediction = None
                prediction_messages.clear()
                await event.respond("🔄 Reset effectué")
            
            elif cmd == '/game':
                parts = event.message.message.split()
                if len(parts) > 1 and parts[1].isdigit():
                    engine.current_game_number = int(parts[1])
                    await event.respond(f"🎮 Jeu: {engine.current_game_number}")
            
            elif cmd == '/help':
                await event.respond("""📖 Commandes:
/status - Statut
/test - Test détection
/reset - Reset
/game N - Changer jeu
/help - Aide""")
                
        except Exception as e:
            logger.error(f"❌ Erreur admin: {e}")
    
    # Garder le bot en vie
    logger.info("✅ Bot en écoute...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("👋 Arrêt")
    except Exception as e:
        logger.error(f"💥 Fatal: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
