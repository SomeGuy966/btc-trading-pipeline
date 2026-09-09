.PHONY: install build test test-cpp test-py clean lint format run record replay analyze benchmark benchmark-replay

RELEASE_TYPE = Release
PY_SRC = src/pysrc
CPP_SRC = src/cppsrc
TICKS   = ticks.jsonl

install:
	conan install . --build=missing
	poetry install

build: install
	@mkdir -p build
	cd build && cmake .. -DCMAKE_TOOLCHAIN_FILE=$(RELEASE_TYPE)/generators/conan_toolchain.cmake -DCMAKE_BUILD_TYPE=$(RELEASE_TYPE) -G Ninja
	cd build && cmake --build .

test: test-cpp test-py

test-cpp: build
	@ctest --test-dir build --output-on-failure

test-py: build
	@PYTHONPATH="$(PWD)/src:$$PYTHONPATH" poetry run pytest -q $(PY_SRC)/test

clean:
	@rm -rf build
	@rm -f $(PY_SRC)/*.so

lint:
	poetry run mypy -p pysrc
	poetry run ruff check $(PY_SRC)
	poetry run ruff format --check $(PY_SRC)

format:
	find $(CPP_SRC) -name '*.cpp' -o -name '*.hpp' | xargs clang-format -i
	poetry run ruff format $(PY_SRC)
	poetry run ruff check --fix $(PY_SRC)

# Live run, bounded so it terminates.
run:
	poetry run python -m pysrc.main --max-ticks 20

# Capture a live session to $(TICKS) for offline replay.
record:
	poetry run python -m pysrc.main --record $(TICKS) --max-ticks 60

# Replay a recorded session: fast, offline, reproducible.
replay:
	poetry run python -m pysrc.main --replay $(TICKS) --quiet

analyze:
	poetry run python -m pysrc.evaluate_predictions

# Synthetic ticks by default so this works without a recording.
benchmark:
	poetry run python -m pysrc.benchmark

benchmark-replay:
	poetry run python -m pysrc.benchmark --replay $(TICKS)
