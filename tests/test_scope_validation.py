import os
import yaml
import requests
import pytest
from dotenv import load_dotenv
load_dotenv()

BASE_URL = os.getenv("API_URL", "http://localhost:8008")
HEALTH_PATH = os.getenv("API_HEALTH_PATH", "/health")
QUERY_PATH = os.getenv("API_QUERY_PATH", "/query")
TIMEOUT = float(os.getenv("API_TIMEOUT", "50"))

# Texto/markers típicos para detectar rechazo por fuera de scope
REJECTION_MARKERS = [
    "terraform",
    "azure",
    "fuera de alcance",
    "fuera del alcance",
    "no puedo ayudarte con ese tema",
    "solo puedo ayudar con",
    "mi especialidad es",
    "estoy especializado en",
]

# --- Casos de prueba ---
# expected_in_scope:
#   True  -> debe responder de Terraform/Azure y sources == k_docs
#   False -> debe rechazar (y sources vacías)
CASES = [
    # In-scope ✅
    ("Crea un ejemplo de Terraform para desplegar un resource group en Azure con azurerm.", True),
    ("¿Cómo configuro el backend azurerm para remote state en un storage account?", True),
    ("Ejemplo de VNet con 2 subnets y NSG usando Terraform en Azure.", True),
    ("¿Cómo hago terraform import de una Key Vault existente en Azure?", True),
    ("¿Cómo creo una VNet desde el portal de Azure?", True),
    ("Dame un ejemplo de Terraform para AWS S3.", True),

    # Out-of-scope ❌ (conversacional/general)
    ("hola", False),
    ("gracias", False),
    ("¿Cuál es la capital de Francia?", False),
    ("Escríbeme un poema", False),]


def call_health() -> dict:
    r = requests.get(f"{BASE_URL}{HEALTH_PATH}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def call_query(question: str, k_docs: int = 3, threshold=None, temperature: float = 0.0, chat_history=None) -> dict:
    payload = {
        "question": question,
        "chat_history": chat_history or [],
        "k_docs": k_docs,
        "threshold": threshold,      # None => sin filtro por score
        "temperature": temperature,
    }
    r = requests.post(f"{BASE_URL}{QUERY_PATH}", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def is_rejection(answer: str) -> bool:
    a = (answer or "").lower()
    # OJO: en muchos bots el rechazo también menciona "terraform/azure".
    # Por eso miramos señales de "no puedo/solo/alcance" además.
    rejection_phrases = [
        "fuera de alcance",
        "fuera del alcance",
        "no puedo ayudarte",
        "solo puedo ayudar",
        "solo respondo",
        "estoy especializado",
        "mi especialidad",
    ]
    return any(p in a for p in rejection_phrases)


def minimal_domain_signal(answer: str) -> bool:
    a = (answer or "").lower()
    return any(x in a for x in ["terraform", "azurerm", "azure", "resource group", "vnet", "key vault", "state"])


def assert_queryresponse_shape(resp: dict):
    # Validación básica de shape según QueryResponse
    assert isinstance(resp, dict)
    for key in ("answer", "sources", "question", "context"):
        assert key in resp, f"Falta campo '{key}' en QueryResponse: {resp.keys()}"
    assert isinstance(resp["answer"], str)
    assert isinstance(resp["question"], str)
    assert isinstance(resp["sources"], list)
    assert isinstance(resp["context"], list)


def assert_health_shape(resp: dict):
    # Validación básica según HealthResponse
    assert isinstance(resp, dict)
    for key in ({"status"}):
        assert key in resp, f"Falta campo '{key}' en HealthResponse: {resp.keys()}"
    assert isinstance(resp["status"], str)



def assert_document_score_shape(doc: dict):
    # DocumentScore no lo has pegado; lo validamos de forma tolerante:
    # al menos debe ser dict y tener alguna señal útil (score / source / metadata).
    assert isinstance(doc, dict)
    # Si conoces campos exactos, endurece esto.
    # Por ejemplo: assert "score" in doc and "source" in doc
    assert len(doc.keys()) > 0


def test_health_ok():
    resp = call_health()
    assert_health_shape(resp)
    # Debe dar exactamente {"status":"ok"}
    assert resp["status"].lower() == "ok", f"Se esperaba status 'ok', pero se obtuvo: {resp['status']}"
    # Solo debe tener la clave "status" con valor "ok"
    assert resp == {"status": "ok"}, f"Se esperaba exactamente {{'status': 'ok'}}, pero se obtuvo: {resp}"


def load_rejection_messages():
    with open("config/classification_rules.yaml", encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    return [msg.strip() for msg in rules["rejection_messages"]["generic"]]

REJECTION_MESSAGES = load_rejection_messages()

def is_exact_rejection(answer: str) -> bool:
    a = (answer or "").strip()
    return any(a == msg for msg in REJECTION_MESSAGES)


@pytest.mark.parametrize("question,expected_in_scope", CASES)
def test_scope_and_sources_count(question, expected_in_scope):
    k_docs = 3
    threshold = 0.5  # Puedes ajustar el valor de threshold según tu caso
    resp = call_query(question=question, k_docs=k_docs, threshold=threshold, temperature=0.0)
    assert_queryresponse_shape(resp)

    assert resp["question"].strip() == question.strip()
    answer = resp["answer"]
    sources = resp["sources"]

    GREETING_REJECTION = (
        "¡Hola! Soy un asistente especializado en Terraform y Azure.\n"
        "Puedo ayudarte con:\n"
        "• Configuraciones de Terraform\n"
        "• Recursos de Azure\n"
        "• Infraestructura como código\n"
        "• Ejemplos y mejores prácticas\n\n"
        "¿En qué puedo ayudarte?"
    )

    if expected_in_scope:
        assert not is_exact_rejection(answer), f"Se esperaba in-scope pero parece rechazo:\n{answer}"
        assert minimal_domain_signal(answer), f"Respuesta in-scope pero sin señal clara de Terraform/Azure:\n{answer}"
        assert len(sources) <= k_docs, f"In-scope pero len(sources)={len(sources)} > k_docs={k_docs}. Sources={sources}"
        for s in sources:
            assert_document_score_shape(s)
            if threshold is not None and "score" in s:
                assert s["score"] >= threshold, f"Source con score < threshold: {s['score']} < {threshold}"
    else:
        if question.strip().lower() == "hola":
            def normalize(text):
                return "\n".join([line.strip() for line in text.strip().splitlines() if line.strip()])
            assert normalize(answer) == normalize(GREETING_REJECTION), (
                f"Para 'hola' se esperaba el mensaje de greeting exacto.\n"
                f"Esperado:\n{GREETING_REJECTION}\n\nObtenido:\n{answer}"
            )
        else:
            assert is_exact_rejection(answer), (
                "Se esperaba rechazo/out-of-scope exacto, pero la respuesta no coincide con los mensajes permitidos:\n"
                f"{answer}"
            )
        assert len(sources) <= k_docs