.PHONY: up down rag-index rag-reindex rag-search cold-start wait-qdrant


wait-qdrant: 
	@echo "⏳ Esperando a Qdrant en http://localhost:6333/healthz ..."
	@for i in $$(seq 1 40); do \
		if curl -fsS http://localhost:6333/healthz >/dev/null 2>&1; then \
			echo "✅ Qdrant OK"; exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "❌ Qdrant no respondió a tiempo" && exit 1

down:
	docker compose down -v

rag-index:
	docker compose up -d qdrant
	$(MAKE) wait-qdrant
	docker compose run --rm \
		-e EXAMPLES_MANIFEST=data/docs/examples/manifest.yaml \
		api python Scripts/RAG/index_examples.py

rag-reindex:
	docker compose up -d qdrant
	$(MAKE) wait-qdrant
	docker compose run --rm \
		-e EXAMPLES_MANIFEST=data/docs/examples/manifest.yaml \
		api python Scripts/RAG/index_examples.py

cold-start:
	docker compose up -d qdrant
	$(MAKE) wait-qdrant
	docker compose run --rm \
		-e EXAMPLES_MANIFEST=data/docs/examples/manifest.yaml \
		api python Scripts/RAG/index_examples.py
	docker compose up -d api ui
