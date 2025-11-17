# src/agent/contextual_agent.py
"""
Agente contextual para validar si una consulta está dentro del alcance del servicio.
Ubicado en src/agent/ porque es independiente de API y UI.
"""

import json
import logging
from typing import Tuple

from src.api.services.llm_service import LLMService
from src.api.core.config import RAGConfig

logger = logging.getLogger(__name__)


class ContextualAgent:
    """
    Agente que valida si una consulta está dentro del alcance del servicio.
    Evita responder sobre temas fuera de su dominio (Azure, GCP, general programming, etc).
    """

    def __init__(self):
        """Inicializar agente con servicios necesarios"""
        self.llm_service = LLMService()
        self.config = RAGConfig()

    def can_handle(self, query: str) -> Tuple[bool, float, str]:
        """
        Determina si el agente puede manejar la consulta.

        Args:
            query: Pregunta del usuario

        Returns:
            Tupla con:
            - can_handle (bool): Si está dentro del alcance
            - confidence (float): Confianza de la decisión (0.0-1.0)
            - reasoning (str): Explicación de por qué sí o no
        """
        validation_prompt = f"""
DEFINICIÓN DEL SERVICIO:
{self.config.SERVICE_DESCRIPTION}

PREGUNTA DEL USUARIO: "{query}"

TAREA: Determina si esta pregunta está dentro del alcance del servicio.

Considera:
1. ¿Es sobre Terraform o infraestructura como código en AWS?
2. ¿Es una pregunta técnica sobre configuración o provisioning?
3. ¿Está fuera de temas como general programming, otros clouds, etc?

Responde ÚNICAMENTE con JSON, sin preambulen:
{{
    "can_handle": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "Explicación breve en 1-2 frases"
}}
        """

        try:
            response = self.llm_service.call_with_json(validation_prompt)

            can_handle = response.get("can_handle", False)
            confidence = response.get("confidence", 0.0)
            reasoning = response.get("reasoning", "")

            logger.info(
                f"[AGENT] Validación: can_handle={can_handle}, "
                f"confidence={confidence:.1%}, reasoning={reasoning}"
            )

            return can_handle, confidence, reasoning

        except Exception as e:
            logger.error(f"[AGENT] Error en validación: {e}")
            return False, 0.0, "Error validando la consulta"


# src/agent/validators.py
"""
Validadores adicionales para consultas.
"""

import re


def is_terraform_keyword(query: str) -> bool:
    """Verificar si la query contiene palabras clave de Terraform"""
    keywords = {
        "terraform", "aws", "resource", "module", "variable",
        "provider", "state", "backend", "vpc", "ec2", "rds",
        "security group", "iam", "s3", "lambda", "infra",
        "infraestructura", "código", "iac", "provisioning"
    }
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in keywords)


def off_topic(query: str) -> bool:
    """Verificar si la query está claramente fuera de tema"""
    off_topic_keywords = {
        "python", "java", "javascript", "golang",
        "azure", "gcp", "kubernetes",
        "machine learning", "data science",
        "receta", "cooking", "deporte", "película",
        "deportes", "música", "noticias"
    }
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in off_topic_keywords)


def logitud_query(query: str, min_length: int = 5, max_length: int = 500) -> Tuple[bool, str]:
    """Validar que la query tenga longitud razonable"""
    if len(query.strip()) < min_length:
        return False, "La pregunta es muy corta"
    if len(query) > max_length:
        return False, "La pregunta es muy larga"
    return True, "OK"


def limpiar_query(query: str) -> str:
    """Sanitizar la query: remover caracteres especiales, normalizar espacios"""
    # Remover caracteres especiales pero mantener los relevantes
    query = re.sub(r'[<>{}[\]]', '', query)
    # Normalizar espacios
    query = re.sub(r'\s+', ' ', query)
    return query.strip()