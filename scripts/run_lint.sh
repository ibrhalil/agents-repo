#!/usr/bin/env bash
# Run lint checks locally via pre-commit
set -e
if ! command -v pre-commit &> /dev/null; then
  echo "pre-commit not installed. Installing..."
  pip install pre-commit
fi
pre-commit run --all-files
