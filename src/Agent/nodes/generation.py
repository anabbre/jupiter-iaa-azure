"""
Nodo de generación de respuestas
"""
from src.Agent.state import AgentState
from src.services.llms import llm
from config.logger_config import logger, get_request_id, set_request_id

def generate_answer(state: AgentState) -> AgentState:
    """
    Genera una respuesta usando el LLM.
    Usado para preguntas de explicación.
    """
    logger.info("🤖 Generando respuesta con LLM", source="generation")
    
    question = state.get("question", "")
    documents = state.get("documents", [])
    context = "\n\n---\n\n".join(documents) if documents else "No hay contexto disponible."
    
    try:
        prompt = f"""Eres un experto en Terraform y Azure. Responde la pregunta basándote en el contexto.

Contexto:
{context}

Pregunta: {question}

Respuesta:"""

        response = llm.invoke(prompt)
        state["answer"] = response.content
        state["messages"].append("✅ Respuesta generada con LLM")
        
        logger.info("✅ Respuesta generada", source="generation", 
                   answer_length=len(response.content))
        return state
        
    except Exception as e:
        logger.error("❌ Error en generación", source="generation", error=str(e))
        state["answer"] = f"Error al generar respuesta: {str(e)}"
        state["messages"].append(f"❌ Error: {str(e)}")
        raise


# MODO 2: Devolver template sin modificar
def format_template(state: AgentState) -> AgentState:
    """
    Devuelve el código template sin modificar.
    Usado cuando encontramos un buen match de código .tf
    """
    logger.info("📄 Formateando template", source="generation")
    
    template_code = state.get("template_code", "")
    raw_documents = state.get("raw_documents", [])
    
    if not template_code and raw_documents:
        template_code = raw_documents[0].content
    
    if not template_code:
        state["answer"] = "No se encontró un template relevante para tu consulta."
        state["messages"].append("⚠️ No hay template disponible")
        return state
    
    # Obtener metadata
    source = raw_documents[0].source if raw_documents else "unknown"
    score = raw_documents[0].relevance_score if raw_documents else 0.0
    
    # Formatear respuesta
    state["answer"] = f"""## 🔧 Código Terraform

```hcl
{template_code}
```

---
> 💡 Este código está listo para usar. Revisa las variables y ajusta según tu entorno.
"""
    
    state["messages"].append("📄 Template formateado")
    logger.info("✅ Template formateado", source="generation", source_file=source)
    return state


# MODO 3: Respuesta híbrida (código + explicación)
def format_hybrid(state: AgentState) -> AgentState:
    """
    Genera respuesta híbrida: explicación + código.
    Usado para queries multi-intent.
    """
    logger.info("🔀 Generando respuesta híbrida", source="generation")
    
    question = state.get("question", "")
    documents = state.get("documents", [])
    raw_documents = state.get("raw_documents", [])
    
    # Separar docs por tipo
    code_docs = []
    explanation_docs = []
    
    for doc in raw_documents:
        if _has_terraform_code(doc.content):
            code_docs.append(doc.content)
        else:
            explanation_docs.append(doc.content)
    
    # Si no hay separación clara, usar todos
    if not code_docs:
        code_docs = documents[:2] if documents else []
    if not explanation_docs:
        explanation_docs = documents[2:4] if len(documents) > 2 else []
    
    try:
        prompt = f"""Eres un experto en Terraform y Azure. El usuario quiere código Y explicación.

DOCUMENTACIÓN:
{chr(10).join(explanation_docs[:2]) if explanation_docs else "No disponible"}

CÓDIGO DISPONIBLE:
{chr(10).join(code_docs[:2]) if code_docs else "No disponible"}

PREGUNTA: {question}

INSTRUCCIONES:
1. Primero explica brevemente el concepto (2-3 párrafos)
2. Luego muestra el código Terraform relevante
3. Añade comentarios si es necesario

RESPUESTA:"""

        response = llm.invoke(prompt)
        state["answer"] = response.content
        state["messages"].append("🔀 Respuesta híbrida generada")
        
        logger.info("✅ Respuesta híbrida generada", source="generation",
                   code_docs=len(code_docs), explanation_docs=len(explanation_docs))
        return state
        
    except Exception as e:
        logger.error("❌ Error en híbrido", source="generation", error=str(e))
        
        # Fallback: mostrar lo que tengamos
        fallback = []
        if explanation_docs:
            fallback.append(f"## Explicación\n{explanation_docs[0][:500]}...")
        if code_docs:
            fallback.append(f"## Código\n```hcl\n{code_docs[0]}\n```")
        
        state["answer"] = "\n\n".join(fallback) if fallback else f"Error: {str(e)}"
        state["messages"].append(f"⚠️ Fallback: {str(e)}")
        return state


def _has_terraform_code(content: str) -> bool:
    """Verifica si el contenido tiene código Terraform."""
    tf_indicators = ["resource ", "variable ", "output ", "module ", "provider ", "terraform {"]
    return any(indicator in content for indicator in tf_indicators)


# TEST
if __name__ == "__main__":
    from src.Agent.state import DocumentScore
    
    print("\n" + "="*60)
    print("🧪 TEST GENERATION (sin LLM, solo format_template)")
    print("="*60)
    
    # Test format_template
    doc = DocumentScore(
        content='resource "azurerm_storage_account" "main" {\n  name = "test"\n}',
        metadata={},
        relevance_score=0.85,
        source="main.tf"
    )
    
    state = {
        "question": "Dame código para storage",
        "template_code": doc.content,
        "raw_documents": [doc],
        "documents": [],
        "messages": []
    }
    
    result = format_template(state)
    
    print(f"\n📄 Resultado format_template:")
    print("-"*60)
    print(result["answer"][:500])
    print("-"*60)
    print(f"\n✅ Test format_template completado")
    print("="*60)
