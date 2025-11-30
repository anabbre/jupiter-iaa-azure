import re
from typing import List, Dict, Any, Tuple


# Keywords relacionadas con tu dominio (Terraform/Azure/Infrastructure)
DOMAIN_KEYWORDS = {
    # Terraform
    "terraform", "tf", "hcl", "provider", "module", "resource", "variable",
    "output", "state", "backend", "workspace", "plan", "apply", "init",
    "destroy", "import", "taint", "untaint",
    
    # Azure
    "azure", "azurerm", "microsoft", "subscription", "tenant", "ad",
    
    # Azure Resources
    "storage", "account", "blob", "container", "vm", "virtual", "machine",
    "network", "vnet", "subnet", "nsg", "security", "group", "route",
    "frontdoor", "cdn", "appservice", "function", "aks", "kubernetes",
    "cosmosdb", "sql", "database", "redis", "cache",
    
    # Infrastructure as Code
    "iac", "infrastructure", "deployment", "provision", "provisioning",
    "configuration", "config", "setup", "automation",
    
    # Cloud concepts
    "cloud", "vpc", "firewall", "loadbalancer", "gateway", "endpoint",
    "region", "zone", "availability", "scalability", "redundancy",
    
    # DevOps
    "devops", "cicd", "pipeline", "ci", "cd", "automation", "deploy",
    "release", "build", "artifact",
    
    # Common tech terms
    "code", "script", "template", "create", "configure", "manage", 
    "update", "delete", "modify", "example", "tutorial", "guide",
    "documentation", "docs", "how", "what", "why", "when"
}

# Palabras que indican consultas fuera de scope
OUT_OF_SCOPE_PATTERNS = [
    r"^(hola|hi|hello|hey|buenos días|good morning|buenas tardes|good afternoon)$",
    r"^(qué tal|cómo estás|how are you|what's up)$",
    r"^(gracias|thanks|thank you|thx)$",
    r"^(adiós|bye|goodbye|chao|hasta luego)$",
    r"^(ok|okay|vale|bien|good)$",
]

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
    query_lower = query.lower()
    
    # 1. Verificar si es una consulta fuera de scope (saludos, etc.)
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.match(pattern, query_lower, re.IGNORECASE):
            return False, "La consulta parece ser conversacional y no técnica"
    
    # 2. Verificar si es demasiado corta
    words = query_lower.split()
    if len(words) < 2:
        return False, "La consulta es demasiado corta (mínimo 2 palabras para contexto técnico)"
    
    # 3. Contar keywords del dominio
    query_words = set(words)
    domain_count = len(query_words & DOMAIN_KEYWORDS)
    
    if min_keywords > 0 and domain_count < min_keywords:
        return False, (
            f"La consulta no contiene suficientes términos técnicos "
            f"(encontrados: {domain_count}, requeridos: {min_keywords})"
        )
    
    # 4. Si tiene al menos 1 keyword del dominio, es válida
    if domain_count > 0:
        return True, f"Consulta válida con {domain_count} términos técnicos"
    
    # 5. Si no tiene keywords pero tiene > 3 palabras, dar oportunidad
    if len(words) >= 3:
        return True, "Consulta sin keywords específicas pero con contexto suficiente"
    
    return False, "Consulta demasiado genérica sin términos técnicos"

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
    
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    # Calcular overlap con domain keywords
    domain_overlap = len(query_words & DOMAIN_KEYWORDS) / max(len(query_words), 1)
    
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


def get_rejection_message(query: str) -> str:
    """
    Genera mensaje de rechazo apropiado para consultas fuera de scope
    
    Args:
        query: Consulta del usuario
    
    Returns:
        Mensaje de rechazo amigable
    """
    query_lower = query.lower()
    # Saludos
    if re.search(r"\b(hola|hi|hello|hey)\b", query_lower):
        return (
            "¡Hola! Soy un asistente especializado en Terraform y Azure. "
            "Puedo ayudarte con:\n"
            "• Configuraciones de Terraform\n"
            "• Recursos de Azure\n"
            "• Infraestructura como código\n"
            "• Ejemplos y mejores prácticas\n\n"
            "¿En qué puedo ayudarte?"
        )
    
    # Consulta demasiado genérica
    return (
        "No encontré información relevante para tu consulta. "
        "Recuerda que estoy especializado en Terraform y Azure.\n\n"
        "Ejemplos de consultas que puedo responder:\n"
        "• 'Cómo crear un storage account en Azure con Terraform?'\n"
        "• 'Ejemplo de configuración de Azure Front Door'\n"
        "• 'Cómo definir variables en Terraform?'\n\n"
        "Por favor, reformula tu pregunta con más detalles técnicos."
    )
