SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

TEST_FILTER ?= ""
TEST_MARKERS ?= ""
SRC_AND_TEST_FILES = pelican_jupyter tests

first: help


# ------------------------------------------------------------------------------
# Build

env:  ## Create Python env
	mamba env create


develop:  ## Install package for development
	python -m pip install --no-build-isolation -e .


build:  ## Build package
	python setup.py sdist


upload-pypi:  ## Upload package to PyPI
	twine upload dist/*.tar.gz


upload-test:  ## Upload package to test PyPI
	twine upload --repository test dist/*.tar.gz


# ------------------------------------------------------------------------------
# Testing

check:  ## Check linting
	flake8 ./pelican_jupyter
	isort ./pelican_jupyter --check-only --diff --project pelican_jupyter
	black ./pelican_jupyter --check --diff

format: ## Running code formatter: black and isort
	@echo "(isort) Ordering imports..."
	@isort $(SRC_AND_TEST_FILES)
	@echo "(black) Formatting codebase..."
	@black --config pyproject.toml $(SRC_AND_TEST_FILES)
	@echo "(ruff) Running fix only..."
	@ruff check $(SRC_AND_TEST_FILES) --fix-only

lint: ## Run the linter (ruff) to check the code style.
	@echo -e "$(COLOR_CYAN)Checking code style with ruff...$(COLOR_RESET)"
	ruff check $(SRC_AND_TEST_FILES)

fmt:  ## Format source
	isort ./pelican_jupyter --project pelican_jupyter
	black ./pelican_jupyter


test:  ## Run tests
	pytest -k $(TEST_FILTER) -m "$(TEST_MARKERS)"


test-all:  ## Run all tests
	pytest -k $(TEST_FILTER)


report:  ## Generate coverage reports
	coverage xml
	coverage html

# ------------------------------------------------------------------------------
# Other

clean:  ## Clean build files
	rm -rf build dist site htmlcov .pytest_cache .eggs
	rm -f .coverage coverage.xml pelican_jupyter/_generated_version.py
	find . -type f -name '*.py[co]' -delete
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .ipynb_checkpoints -exec rm -rf {} +


cleanall: clean   ## Clean everything
	rm -rf *.egg-info


help:  ## Show this help menu
	@grep -E '^[0-9a-zA-Z_-]+:.*?##.*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?##"; OFS="\t\t"}; {printf "\033[36m%-30s\033[0m %s\n", $$1, ($$2==""?"":$$2)}'
