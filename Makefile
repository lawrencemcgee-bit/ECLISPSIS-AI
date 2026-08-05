run:
    python run.py

test:
    pytest -q

lint:
    ruff check .

typecheck:
    mypy src/

start-api:
    uvicorn api:app --reload
ui:
	python run.py
