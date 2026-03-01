#!/usr/bin/env python3
"""
Bot Telegram de Prédiction - Détection de 3 costumes différents
Ouvre le port 10000 pour Render.com
"""
import os
import sys
import asyncio
import logging
from aiohttp import web

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
prediction_messages = {}

# Client bot global
bot_client = None

async def start_bot():
    """Démarre le bot Telegram"""
    global bot_client
    
    if not all([API_ID, API_HASH, BOT_TOKEN]):
        logger.error("❌ Configuration incomplète!")
        return None
    
    session = os.getenv('TELEGRAM_SESSION', '')
    client = TelegramClient(StringSession(session), API_ID, API_HASH)
    bot_client = client
    
    try:
        await client.start(bot_token=BOT_TOKEN)
        me = await client.get_me()
        logger.info(f"✅ Bot connecté: @{me.username}")
        
        try:
            await client.send_message(ADMIN_ID, "🤖 Bot de prédiction démarré!")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de contacter l'admin: {e}")
        
    except Exception as e:
        logger.error(f"❌ Erreur connexion: {e}")
        return None
    
    @client.on(events.NewMessage(chats=SOURCE_CHANNEL_ID))
    async def handle_source(event):
        try:
            text = event.message.message
            logger.info(f"📩 Source: {text[:80]}...")
            
            # Vérification prédiction précédente
            if engine.pending_prediction and not engine.pending_prediction.get('verified'):
                verification = engine.check_verification(text)
                
                if verification == 'success':
                    game_num = engine.pending_prediction['game_number']
                    if game_num in prediction_messages:
                        msg_id, _ = prediction_messages[game_num]
                        new_text = engine.format_success(engine.pending_prediction)
                        try:
                            await client.edit_message(PREDICTION_CHANNEL_ID, msg_id, new_text)
                            logger.info(f"✅ Succès édité jeu {game_num}")
                        except Exception as e:
                            await client.send_message(PREDICTION_CHANNEL_ID, new_text)
                    
                    engine.pending_prediction = None
                    return
                    
                elif verification == 'failure':
                    game_num = engine.pending_prediction['game_number']
                    if game_num in prediction_messages:
                        msg_id, _ = prediction_messages[game_num]
                        new_text = engine.format_failure(engine.pending_prediction)
                        try:
                            await client.edit_message(PREDICTION_CHANNEL_ID, msg_id, new_text)
                            logger.info(f"❌ Échec édité jeu {game_num}")
                        except Exception as e:
                            await client.send_message(PREDICTION_CHANNEL_ID, new_text)
                    
                    engine.pending_prediction = None
                    return
            
            # Nouvelle prédiction
            result = engine.analyze(text)
            
            if engine.should_predict(result):
                prediction = engine.generate_prediction(result)
                if prediction:
                    msg_text = engine.format_prediction(prediction)
                    sent_msg = await client.send_message(PREDICTION_CHANNEL_ID, msg_text)
                    prediction_messages[prediction['game_number']] = (sent_msg.id, prediction)
                    logger.info(f"🎯 Prédiction: Jeu {prediction['game_number']}, Numéro {prediction['target_number']}")
            else:
                logger.info(f"ℹ️ Pas de prédiction (final={result.is_final}, 3diff={result.has_three_different_suits})")
                
        except Exception as e:
            logger.error(f"❌ Erreur handle_source: {e}")
    
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
    
    logger.info("✅ Bot en écoute...")
    await client.run_until_disconnected()

async def start_web_server():
    """Démarre le serveur web sur le port 10000"""
    app = web.Application()
    
    async def health(request):
        return web.json_response({
            'status': 'healthy',
            'bot': 'running',
            'game': engine.current_game_number
        })
    
    async def home(request):
        return web.Response(text="🤖 Bot de Prédiction - En ligne", content_type='text/plain')
    
    app.router.add_get('/', home)
    app.router.add_get('/health', health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv('PORT', '10000'))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    logger.info(f"🌐 Serveur web démarré sur le port {port}")
    return runner

async def main():
    """Fonction principale"""
    logger.info("🚀 Démarrage...")
    
    web_runner = await start_web_server()
    asyncio.create_task(start_bot())
    
    logger.info("✅ Services démarrés")
    
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Arrêt")
    except Exception as e:
        logger.error(f"💥 Fatal: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
