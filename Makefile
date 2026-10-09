# ComotVid — dev shortcuts
# make dev            -> start server dengan watch mode + auto-reload + buka browser
# make dev PORT=3000  -> gunakan port kustom
# make start          -> start server langsung (tanpa watch/reload)
# make check          -> syntax check app.js + server.py
# make open           -> buka URL di browser
# make clean          -> hapus artefak cache

PORT   ?= 3000
PYTHON ?= python3

.PHONY: help dev watch start check open clean

help:
	@echo "make dev [PORT=3000]   start server dengan watch mode + auto reload"
	@echo "make watch             alias untuk make dev"
	@echo "make start             start server langsung"
	@echo "make check             syntax check app.js & server.py"
	@echo "make open              buka browser"
	@echo "make clean             hapus artefak cache"

dev:
	@PORT="$(PORT)" PYTHON="$(PYTHON)" ./dev.sh

watch: dev

start:
	@echo "ComotVid -> http://localhost:$(PORT)  (Ctrl+C stop)"
	@"$(PYTHON)" server.py "$(PORT)"

check:
	@node --check app.js
	@"$(PYTHON)" -c "import ast; ast.parse(open('server.py').read())"
	@echo "✓ syntax OK"

open:
	@open "http://localhost:$(PORT)" 2>/dev/null || xdg-open "http://localhost:$(PORT)" 2>/dev/null || echo "buka manual: http://localhost:$(PORT)"

clean:
	@rm -rf __pycache__ .DS_Store .ruff_cache
	@echo "✓ bersih"
