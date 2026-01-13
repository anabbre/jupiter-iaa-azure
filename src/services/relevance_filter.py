import re
import unicodedata
from typing import List, Dict, Any, Tuple
from config.classifier_loader import (
    get_domain_keywords,
    get_out_of_scope_patterns,
    get_rejection_message,
    get_validation_messages
)
def normalize_query(query: str) -> str:
    """
    Normaliza la query: minúsculas, sin tildes, sin puntuación.
    
    Args:
        query: Consulta del usuario
        
    Returns:
        Query normalizada
    """
    # 1. Minúsculas
    text = query.lower()
    
    # 2. Quitar tildes: é→e, ñ→n, etc.
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    
    # 3. Quitar signos de puntuación (mantener espacios y alfanuméricos)
    text = re.sub(r'[^\w\s]', '', text)
    
    return text

def is_query_in_scope(query: str, min_keywords: int = 0) -> Tuple[bool, str]:
    """
    Verifica si una consulta está dentro del scope del RAG
    
    Args:
        query: Consulta del usuario
        min_keywords: Mínimo de keywords del dominio requeridas (0 = solo validar out-of-scope)
    
    Returns:
        (is_valid, reason) donde:
        - is_valid: True si la consulta es válida
        - reason: Mensaje explicativo
    """
    # Normalizar para keywords (sin puntuación)
    query_normalized = normalize_query(query)
    # Original en minúsculas para patrones
    query_lower = query.lower()
    # Cargar patrones y keywords desde el config/classifier_loader
    out_of_scope_patterns = get_out_of_scope_patterns()
    domain_keywords = get_domain_keywords()
    
    # 1. Verificar si es una consulta fuera de scope (saludos, etc.)
    for pattern in out_of_scope_patterns:
        if re.match(pattern, query_lower, re.IGNORECASE):
            return False, get_validation_messages("not_technical")
    
    # 2. Verificar si es demasiado corta
    words = query_normalized.split()
    if len(words) < 2:
        return False, get_validation_messages("too_short")
    
    # 3. Contar keywords del dominio
    query_words = set(words)
    domain_count = len(query_words & domain_keywords)
    
    if min_keywords > 0 and domain_count < min_keywords:
        return False, get_validation_messages("insufficient_keywords", found=domain_count, required=min_keywords)
    
    
    # 4. Si tiene al menos 1 keyword del dominio, es válida
    if domain_count > 0:
        return True, get_validation_messages("valid_with_keywords", count=domain_count)
    
    # 5. Si no tiene keywords pero tiene > 3 palabras, dar oportunidad
    if len(words) >= 3:
        return True, get_validation_messages("valid_with_context")
    
    return False, get_validation_messages("too_generic")

def filter_results_by_relevance(
    query: str,
    results: List[Dict[str, Any]],
    min_score: float = 0.75,
    min_domain_overlap: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Filtra resultados por relevancia real
    
    Args:
        query: Consulta original
        results: Lista de resultados de búsqueda
        min_score: Score mínimo absoluto
        min_domain_overlap: Proporción mínima de palabras del dominio en la consulta
    
    Returns:
        Lista filtrada de resultados
    """
    if not results:
        return []
    
    # Usar query normalizada para comparar con keywords
    query_normalized = normalize_query(query)
    query_words = set(query_normalized.split())
    # Cargar patrones y keywords desde el config/classifier_loader
    domain_keywords = get_domain_keywords()
    # Calcular overlap con domain keywords
    domain_overlap = len(query_words & domain_keywords) / max(len(query_words), 1)
    
    filtered = []
    for result in results:
        score = result.get("score", 0.0)
        
        # Si la consulta tiene buen overlap con el dominio, ser menos estricto
        if domain_overlap >= min_domain_overlap:
            threshold = min_score
        else:
            # Para consultas genéricas, requerir score MÁS alto
            threshold = 0.85
        
        if score >= threshold:
            filtered.append(result)
    
    return filtered


def get_rejection_message_for_query(query: str) -> str:
    """ Obtiene mensaje de rechazo basado en la consulta """
    query_lower = query.lower()
    if re.search(r"\b(hola|hi|hello|hey)\b", query_lower):
        return get_rejection_message("greeting")  
    return get_rejection_message("generic")  
