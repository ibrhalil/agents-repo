#!/usr/bin/env bash
# Lint girişi: sözleşme linter (ERR'de durur) + pre-commit (stil)
set -e
python3 "$(dirname "$0")/lint_repo.py"
if ! command -v pre-commit &> /dev/null; then
  echo "pre-commit not installed. Installing..."
  pip install pre-commit
fi
pre-commit run --all-files
