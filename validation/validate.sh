#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <xml-file>" >&2
  exit 1
fi
xmllint --noout --catalogs --valid --dtdvalid dtd/v1.1/docbookx.dtd "$1"
