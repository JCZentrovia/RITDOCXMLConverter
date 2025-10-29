.PHONY: pdf epub validate batch tests lint

pdf:
python cli.py pdf --input $${INPUT} --out $${OUT} --publisher $${PUBLISHER} $${ARGS}

epub:
python cli.py epub --input $${INPUT} --out $${OUT} --publisher $${PUBLISHER} $${ARGS}

validate:
python cli.py validate --input $${FILE}

batch:
python cli.py batch --manifest $${MANIFEST} --parallel $${PARALLEL}

tests:
pytest

lint:
flake8 pipeline cli.py
