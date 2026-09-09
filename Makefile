.PHONY: build install test clean lint format

RELEASE_TYPE = Release
PY_SRC = src/pysrc
CPP_SRC = src/cppsrc

build: install
	@mkdir -p build
	cd build && cmake .. -DCMAKE_TOOLCHAIN_FILE=$(RELEASE_TYPE)/generators/conan_toolchain.cmake -DCMAKE_BUILD_TYPE=$(RELEASE_TYPE) -G Ninja
	cd build && cmake --build .
	# The pybind module is already emitted to $(PY_SRC) by CMake; no copy needed.

install:
	conan install . --build=missing
	poetry install





.PHONY: test test-cpp test-py

TOOLCHAIN := build/build/Debug/generators/conan_toolchain.cmake
GENPFX   := build/build/Debug/generators

test: test-cpp test-py

test-cpp: build
# 	@[ -f $(TOOLCHAIN) ] || conan install . -of build/build -s build_type=Debug -g CMakeDeps -g CMakeToolchain
# 	@cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug \
# 		-DCMAKE_TOOLCHAIN_FILE=$(PWD)/$(TOOLCHAIN) \
# 		-DCMAKE_PREFIX_PATH=$(PWD)/$(GENPFX)
# 	@cmake --build build -j
	@ctest --test-dir build --output-on-failure

test-py: build
# 	@cmake --build build -j --target intern
	@PYTHONPATH="$(PWD)/src/pysrc:$(PWD)/src:$$PYTHONPATH" poetry run pytest -q


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

run-main:
	poetry run python src/pysrc/main.py

analyze:
	poetry run python src/pysrc/evaluate_predictions.py
