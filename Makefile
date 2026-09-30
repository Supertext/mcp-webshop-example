.PHONY: install run seed reset stage budget check translate quote

install:
	uv sync --extra dev || pip install -r requirements.txt

run:
	uvicorn app.main:app --reload --port 8000

seed:
	python scripts/seed_analytics.py
	python scripts/gen_placeholders.py

reset:
	python scripts/reset_demo.py

stage:
	python scripts/make_stage.py $(if $(STAGE_DIR),--dest $(STAGE_DIR),)

translate:
	python scripts/translate.py $(if $(LOCALE),--locale $(LOCALE),)

quote:
	python scripts/translate.py --quote $(if $(LOCALE),--locale $(LOCALE),)

budget:
	python -m app.ledger

check:
	ruff check .
	python -m pytest -q
