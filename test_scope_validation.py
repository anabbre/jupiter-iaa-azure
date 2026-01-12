# test_scope_validation.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.services.relevance_filter import is_query_in_scope
from src.Agent.nodes.validate_scope import validate_scope, should_continue
from src.Agent.graph import Agent

# Test 1: Función de filtro directa
print("=" * 70)
print("TEST 1: Función is_query_in_scope()")
print("=" * 70)

test_queries = [
    ("hola", False),
    ("como estas", False),
    ("Qué es Terraform", True),
    ("Dame codigo storage", True),
]

for query, expected in test_queries:
    valid, reason = is_query_in_scope(query, min_keywords=1)
    status = "✅" if valid == expected else "❌"
    print(f"{status} '{query}' → {valid} (esperado {expected})")
    print(f"   Razón: {reason}\n")

# Test 2: Nodo validate_scope
print("\n" + "=" * 70)
print("TEST 2: Nodo validate_scope()")
print("=" * 70)

for query, expected_valid in test_queries:
    state = {
        "question": query,
        "messages": [],
        "is_valid_scope": True,
        "answer": "",
        "response_action": ""
    }
    
    result = validate_scope(state)
    status = "✅" if result["is_valid_scope"] == expected_valid else "❌"
    print(f"{status} '{query}' → {result['is_valid_scope']} (esperado {expected_valid})")
    print(f"   Mensajes: {result['messages']}\n")

# Test 3: El agente completo
print("\n" + "=" * 70)
print("TEST 3: Agente Completo")
print("=" * 70)

agent = Agent()

for query, expected_valid in test_queries:
    result = agent.invoke(query)
    is_valid = result["is_valid_scope"]
    action = result.get("response_action", "unknown")
    
    status = "✅" if is_valid == expected_valid else "❌"
    print(f"{status} '{query}'")
    print(f"   is_valid_scope: {is_valid} (esperado {expected_valid})")
    print(f"   response_action: {action}")
    print(f"   answer: {result.get('answer', '')[:80]}...\n")