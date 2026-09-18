BEND ?= bun ../bend/bend2/main.ts
BUILD_DIR := .build

.PHONY: setup build smoke rewrite-demo test clean

setup:
	./scripts/setup-toolchain.sh

build: $(BUILD_DIR)/smoke

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/smoke: src/Smoke.bend | $(BUILD_DIR)
	$(BEND) $< -o $@

smoke: build
	./$(BUILD_DIR)/smoke --threads 4

rewrite-demo:
	./scripts/try-add-overflow-rewrite.sh cpu

test:
	python3 -m unittest discover -s tests -v

clean:
	rm -rf $(BUILD_DIR)
