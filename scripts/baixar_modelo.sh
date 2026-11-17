#!/usr/bin/env bash
set -euo pipefail

MODEL_URL="https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
MODEL_SHA256="3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"
MODEL_FILE="Qwen3-4B-Instruct-2507-Q4_K_M.gguf"

model_directory="${MODEL_DIRECTORY:-./models}"
mkdir -p -- "$model_directory"
model_path="$model_directory/$MODEL_FILE"

if [[ -e "$model_path" || -L "$model_path" ]]; then
  printf 'O arquivo do modelo já existe. Substituí-lo? [s/N] ' >&2
  if ! read -r answer || [[ "$answer" != "s" && "$answer" != "S" ]]; then
    printf 'Download cancelado; o arquivo existente não foi alterado.\n' >&2
    exit 1
  fi
fi

partial=$(mktemp "$model_directory/.modelo.XXXXXXXX")
trap 'rm -f -- "$partial"' EXIT

curl -L --fail --output "$partial" "$MODEL_URL"
if ! printf '%s  %s\n' "$MODEL_SHA256" "$partial" | sha256sum --check --status; then
  printf 'Erro: SHA-256 do modelo não confere; download descartado.\n' >&2
  exit 1
fi

mv -fT -- "$partial" "$model_path"
printf 'Modelo baixado e verificado em %s.\n' "$model_path"
