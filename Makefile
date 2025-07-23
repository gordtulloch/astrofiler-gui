# AstroFiler Makefile for PyInstaller packaging

VERSION = 1.0.0
APP_NAME = AstroFiler

# Default target
.PHONY: all
all: build

# Install dependencies including PyInstaller
.PHONY: install
install:
	pip install -r requirements.txt
	pip install pyinstaller

# Build executable for current platform
.PHONY: build
build:
	python build_packages.py

# Build executable only (no packaging)
.PHONY: executable
executable:
	python -m PyInstaller astrofiler.spec --clean

# Clean build artifacts
.PHONY: clean
clean:
	rm -rf build/
	rm -rf dist/
	rm -f *.tar.gz
	rm -f *.zip
	rm -f *.dmg
	rm -f BUILD_INFO.txt
	rm -f *.spec~ 

# Test the built executable
.PHONY: test
test:
	@if [ -f "dist/astrofiler/astrofiler" ]; then \
		echo "Testing Linux executable..."; \
		./dist/astrofiler/astrofiler --version || echo "Version check failed"; \
	elif [ -f "dist/astrofiler/astrofiler.exe" ]; then \
		echo "Testing Windows executable..."; \
		./dist/astrofiler/astrofiler.exe --version || echo "Version check failed"; \
	elif [ -d "dist/AstroFiler.app" ]; then \
		echo "Testing macOS app bundle..."; \
		open dist/AstroFiler.app --args --version || echo "Version check failed"; \
	else \
		echo "No executable found. Run 'make build' first."; \
	fi

# Run the executable
.PHONY: run
run:
	@if [ -f "dist/astrofiler/astrofiler" ]; then \
		./dist/astrofiler/astrofiler; \
	elif [ -f "dist/astrofiler/astrofiler.exe" ]; then \
		./dist/astrofiler/astrofiler.exe; \
	elif [ -d "dist/AstroFiler.app" ]; then \
		open dist/AstroFiler.app; \
	else \
		echo "No executable found. Run 'make build' first."; \
	fi

# Development setup
.PHONY: dev-setup
dev-setup:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install pyinstaller pytest

# Run tests
.PHONY: pytest
pytest:
	python -m pytest test/ -v

# Show information
.PHONY: info
info:
	@echo "AstroFiler v$(VERSION) - PyInstaller Packaging"
	@echo "=============================================="
	@echo "Available targets:"
	@echo "  all/build     - Build executable and create package"
	@echo "  executable    - Build executable only (no packaging)"
	@echo "  install       - Install dependencies including PyInstaller"
	@echo "  clean         - Remove build artifacts"
	@echo "  test          - Test the built executable"
	@echo "  run           - Run the built executable"
	@echo "  dev-setup     - Set up development environment"
	@echo "  pytest        - Run test suite"
	@echo "  info          - Show this information"
	@echo ""
	@echo "Platform-specific packages will be created:"
	@echo "  Linux:   $(APP_NAME)-$(VERSION)-linux-x64.tar.gz"
	@echo "  Windows: $(APP_NAME)-$(VERSION)-windows-x64.zip"
	@echo "  macOS:   $(APP_NAME)-$(VERSION)-macos-*.dmg"

# Help target
.PHONY: help
help: info
