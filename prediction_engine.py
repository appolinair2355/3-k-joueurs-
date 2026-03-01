"""
Moteur de prédiction - Détecte les patterns de 3 costumes différents
"""
import re
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

SUIT_NAMES = {
    '♣️': 'Trèfle', '♣': 'Trèfle',
    '♦️': 'Carreau', '♦': 'Carreau',
    '❤️': 'Cœur', '❤': 'Cœur',
    '♠️': 'Pique', '♠': 'Pique'
}

@dataclass
class PredictionResult:
    detected: bool
    suits: List[str]
    game_number: Optional[int] = None
    target_number: Optional[int] = None
    is_final: bool = False
    raw_message: str = ""
    
    @property
    def has_three_different_suits(self) -> bool:
        normalized = []
        for suit in self.suits:
            if suit in ['♣', '♣️']: normalized.append('♣️')
            elif suit in ['♦', '♦️']: normalized.append('♦️')
            elif suit in ['❤', '❤️']: normalized.append('❤️')
            elif suit in ['♠', '♠️']: normalized.append('♠️')
        unique = set(normalized)
        return len(unique) >= 3 and len(self.suits) >= 3
    
    @property
    def has_three_suits(self) -> bool:
        return len(self.suits) >= 3


class PredictionEngine:
    def __init__(self):
        self.suit_pattern = re.compile(r'(?:♣️|♦️|❤️|♠️|♣|♦|♠)')
        self.parentheses_pattern = re.compile(r'\(([^()]+)\)')
        self.final_pattern = re.compile(r'finalis[ée]', re.IGNORECASE)
        self.game_pattern = re.compile(r'jeu\s*n[°:]?\s*(\d+)', re.IGNORECASE)
        self.number_pattern = re.compile(r'\b(\d+)\b')
        
        self.current_game_number = 1182
        self.pending_prediction: Optional[Dict] = None
        self.last_prediction_message_id: Optional[int] = None
        
    def extract_suits(self, text: str) -> List[str]:
        return self.suit_pattern.findall(text)
    
    def extract_first_parentheses(self, text: str) -> str:
        match = self.parentheses_pattern.search(text)
        return match.group(1) if match else ""
    
    def is_final(self, text: str) -> bool:
        return bool(self.final_pattern.search(text))
    
    def extract_game_number(self, text: str) -> Optional[int]:
        match = self.game_pattern.search(text)
        return int(match.group(1)) if match else None
    
    def extract_number(self, text: str) -> Optional[int]:
        match = self.number_pattern.search(text)
        return int(match.group(1)) if match else None
    
    def normalize_suits(self, suits: List[str]) -> List[str]:
        mapping = {'♣': '♣️', '♣️': '♣️', '♦': '♦️', '♦️': '♦️',
                   '❤': '❤️', '❤️': '❤️', '♠': '♠️', '♠️': '♠️'}
        return [mapping.get(s, s) for s in suits]
    
    def analyze(self, text: str) -> PredictionResult:
        text = text.strip()
        is_final_msg = self.is_final(text)
        game_num = self.extract_game_number(text)
        if game_num:
            self.current_game_number = game_num
            
        first_group = self.extract_first_parentheses(text)
        suits = self.extract_suits(first_group) if first_group else self.extract_suits(text)
        
        return PredictionResult(
            detected=len(suits) > 0,
            suits=suits,
            game_number=self.current_game_number,
            is_final=is_final_msg,
            raw_message=text
        )
    
    def should_predict(self, result: PredictionResult) -> bool:
        return result.is_final and result.has_three_different_suits
    
    def generate_prediction(self, result: PredictionResult) -> Optional[Dict]:
        if not self.should_predict(result):
            return None
            
        current_num = self.extract_number(result.raw_message) or result.game_number or self.current_game_number
        target_num = current_num + 1
        
        normalized = self.normalize_suits(result.suits[:3])
        
        prediction = {
            'game_number': result.game_number,
            'detected_number': current_num,
            'target_number': target_num,
            'suits': normalized,
            'suits_str': ''.join(normalized),
            'suits_names': [SUIT_NAMES.get(s, s) for s in normalized],
            'timestamp': datetime.now(),
            'verified': False,
            'success': False
        }
        
        self.pending_prediction = prediction
        logger.info(f"🎯 Prédiction: Jeu {prediction['game_number']} → Numéro {target_num}")
        return prediction
    
    def format_prediction(self, p: Dict) -> str:
        return f"""🎯 **PRÉDICTION EN COURS**

🎮 **Jeu n°{p['game_number']}**
🎲 **Numéro cible: {p['target_number']}**
👤 **3K Joueur**

📊 **Analyse:**
• Costumes: {p['suits_str']} ({', '.join(p['suits_names'])})
• Pattern: 3 costumes différents ✅

⏳ **Statut:** En attente...

💡 *Basé sur le numéro {p['detected_number']}*"""
    
    def format_success(self, p: Dict) -> str:
        return f"""✅ **PRÉDICTION RÉUSSIE!**

🎮 **Jeu n°{p['game_number']}**
🎯 **Numéro {p['target_number']}**
📊 **3 costumes reçus**

💰 **SUCCÈS**"""
    
    def format_failure(self, p: Dict) -> str:
        return f"""❌ **PRÉDICTION ÉCHOUÉE**

🎮 **Jeu n°{p['game_number']}**
🎯 **Numéro {p['target_number']}**
📊 **Pas 3 costumes**

💸 **ÉCHEC**"""
    
    def check_verification(self, message_text: str) -> Optional[str]:
        """
        Vérifie si la prédiction en attente est confirmée ou non.
        Retourne 'success', 'failure', ou None si pas de vérification.
        """
        if not self.pending_prediction:
            return None
            
        result = self.analyze(message_text)
        current_num = self.extract_number(message_text)
        
        # Vérifie si c'est le numéro qu'on avait prédit
        if current_num != self.pending_prediction['target_number']:
            return None
        
        # Vérifie si ce numéro a reçu 3 costumes
        if result.has_three_suits:
            self.pending_prediction['verified'] = True
            self.pending_prediction['success'] = True
            logger.info(f"✅ VÉRIFICATION: Succès pour {current_num}")
            return 'success'
        else:
            self.pending_prediction['verified'] = True
            self.pending_prediction['success'] = False
            logger.info(f"❌ VÉRIFICATION: Échec pour {current_num}")
            return 'failure'


engine = PredictionEngine()
