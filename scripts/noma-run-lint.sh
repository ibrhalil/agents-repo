#!/usr/bin/env bash
# Lint girişi: sözleşme linter (ERR'de durur) + pre-commit (stil)
set -e
python3 "$(dirname "$0")/noma_lint.py"
if command -v pre-commit &> /dev/null; then
  pre-commit run --all-files
elif python3 -m pre_commit --version &> /dev/null 2>&1; then
  python3 -m pre_commit run --all-files
else
  echo "WARN: pre-commit kurulu değil — stil kontrolleri atlandı (kurulum: pip3 install --user pre-commit)"
fi
