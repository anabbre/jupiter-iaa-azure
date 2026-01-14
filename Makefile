# ==========================================
# 🧠 GESTIÓN DE CONOCIMIENTO (RAG & QDRANT)
# ==========================================

# Espera a que Qdrant esté saludable antes de lanzar nada
wait-qdrant:
	@echo "⏳ Esperando a Qdrant en http://localhost:6333/healthz ..."
	@for i in $$(seq 1 40); do \
		if curl -fsS http://localhost:6333/healthz >/dev/null 2>&1; then \
			echo "✅ Qdrant OK"; exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "❌ Qdrant no respondió a tiempo" && exit 1

# Indexación INCREMENTAL (Solo añade lo nuevo, no borra nada)
# Uso: make rag-index
rag-index: wait-qdrant
	@echo "📥 Iniciando indexación incremental..."
	docker compose run --rm api python src/services/rag_indexer.py

# Re-indexación COMPLETA (Borra la base de datos y empieza de cero)
# Uso: make rag-reindex
# Ideal cuando cambias la estructura de los chunks o metadata
rag-reindex:
	@echo "🚀 Levantando Qdrant..."
	docker compose up -d qdrant
	$(MAKE) wait-qdrant
	@echo "🧹🧹 Borrando colecciones y re-indexando TODO..."
# Montamos las credenciales locales en el contenedor
	docker compose run --rm \
		-v $(HOME)/.aws:/root/.aws \
		-e AWS_PROFILE=jupiter-iaa \
		api python src/services/rag_indexer.py --recreate

# Arranque en frío (Levanta infra + Reindexa todo + Levanta app)
# Uso: make cold-start
cold-start:
	@echo "🚀 Iniciando secuencia de arranque en frío..."
	docker compose up -d qdrant
	$(MAKE) wait-qdrant
	docker compose run --rm api python src/services/rag_indexer.py --recreate
	docker compose up -d api ui
	@echo "✅ Sistema listo en: http://localhost:7860"

	# ==========================================
# 🚀 COMANDO MAESTRO (Hacerlo todo)
# ==========================================

# Levanta TODO desde cero: BBDD -> Espera -> Carga Datos S3 -> Indexa -> Levanta App
# Uso: make start
start: rag-reindex
	@echo "🔥 Levantando los servicios de la aplicación (API + UI)..."
	docker compose up -d api ui
	@echo "✅ ¡SISTEMA OPERATIVO!"
	@echo "   📘 API Docs: http://localhost:8008/docs"
	@echo "   🤖 Chat UI:  http://localhost:7860"
	@echo "   🧠 Qdrant:   http://localhost:6333/dashboard"
