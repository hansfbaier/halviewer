
all: format check

format:
	ruff format halviewer.py

check:
	ruff check halviewer.py

check_fix:
	ruff check --fix halviewer.py

install:
	sudo install halviewer.py /usr/local/bin/halviewer
