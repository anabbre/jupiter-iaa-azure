"""
Carga la configuracion de clasificadores desde YAML
"""
import yaml
from pathlib import Path
import random

_config =  None

def _load():
    global _config
    if _config is None:
        config_path = Path(__file__).parent / "classification_rules.yaml"
        with open(config_path, 'r', encoding='utf-8') as f:
            _config = yaml.safe_load(f)
    return _config

def get_intent_patterns():
    """ Obtiene los patrones de intención desde el archivo de configuración. """
    return _load()["intent_patterns"]

def get_multi_intent_connectors():
    """ Obtiene los conectores de multi-intención desde el archivo de configuración. """
    return _load()["multi_intent_connectors"]

def get_domain_keywords():
    """ Obtiene las palabras clave del dominio desde el archivo de configuración. """
    return set(_load()["domain_keywords"])

def get_out_of_scope_patterns():
    """ Obtiene las razones de fuera de scope desde el archivo de configuración. """
    return _load()["out_of_scope_patterns"]

def get_rejection_message(msg_type="generic"):
    """Obtiene un mensaje de rechazo aleatorio apropiado."""
    messages = _load()["rejection_messages"].get(msg_type, [])
    if not messages:
        return ""
    if isinstance(messages, str):
        return messages
    return random.choice(messages)

def get_validation_messages(msg_type, **kwargs):
    """ Obtiene los mensajes de validación. """
    msg = _load()["validation_messages"].get(msg_type, "")
    return msg.format(**kwargs) if kwargs else msg