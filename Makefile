.PHONY: install-dev test-core test coverage build check-package clean

install-dev:
	python -m pip install --upgrade pip
	python -m pip install -r requirements-dev.txt

test-core:
	python test_runner_simple.py

test:
	python -m django test tests --settings=tests.test_settings --verbosity=1

coverage:
	coverage run --source=drf_api_logger -m django test tests --settings=tests.test_settings --verbosity=1
	coverage report

build:
	python -m build --sdist --wheel

check-package:
	python -m twine check dist/*

clean:
	python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in map(pathlib.Path, ['build', 'dist', 'htmlcov', '.tox'])]; [p.unlink(missing_ok=True) for p in pathlib.Path('.').glob('*.prof')]; pathlib.Path('.coverage').unlink(missing_ok=True)"
