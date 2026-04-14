#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "==> Tesserae local runner"
echo "Root: $ROOT_DIR"

PORT="${PORT:-5001}"
RUN_APP_INSTALL="${RUN_APP_INSTALL:-0}"
RUN_APP_BUILD="${RUN_APP_BUILD:-0}"
SSL_MODE="${SSL_MODE:-https}"
CERT_DIR="${CERT_DIR:-certs}"
CERT_CRT="${TESSERAE_SSL_CERT:-$CERT_DIR/dev.crt}"
CERT_KEY="${TESSERAE_SSL_KEY:-$CERT_DIR/dev.key}"

if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "Error: python3.12/python3 not found."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "==> Creating virtual environment with $PYTHON_BIN"
  "$PYTHON_BIN" -m venv .venv
fi

echo "==> Activating virtual environment"
source .venv/bin/activate

if [ "$RUN_APP_INSTALL" = "1" ] || [ ! -f ".venv/.deps_installed" ]; then
  echo "==> Ensuring pip tooling"
  python -m pip install -U pip setuptools wheel >/dev/null
  echo "==> Installing Python dependencies"
  python -m pip install -r requirements.txt
  touch .venv/.deps_installed
else
  echo "==> Reusing existing Python environment"
fi

if [ -f "package.json" ]; then
  if [ ! -d "node_modules" ]; then
    echo "==> Installing Node dependencies"
    npm install
  fi
  if [ "$RUN_APP_BUILD" = "1" ] || [ ! -f "dist/index.html" ]; then
    echo "==> Building frontend"
    npm run build
  else
    echo "==> Reusing existing frontend build"
  fi
fi

if [ -f ".env" ]; then
  echo "==> Loading environment from .env"
  set -a
  source .env
  set +a
fi

if [ "$SSL_MODE" = "https" ]; then
  mkdir -p "$CERT_DIR"
  if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: openssl is required to generate HTTPS certificates."
    exit 1
  fi

  LAN_IP="$(
    ifconfig | awk '/inet / {print $2}' | \
      grep -E '^(10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.)' | \
      head -n 1
  )"
  SAN_ENTRIES="IP:127.0.0.1,DNS:localhost"
  CERT_CN="localhost"
  if [ -n "${LAN_IP:-}" ]; then
    SAN_ENTRIES="IP:${LAN_IP},${SAN_ENTRIES}"
    CERT_CN="$LAN_IP"
  fi

  NEED_CERT_REGEN=0
  if [ ! -f "$CERT_CRT" ] || [ ! -f "$CERT_KEY" ]; then
    NEED_CERT_REGEN=1
  elif [ -n "${LAN_IP:-}" ]; then
    if ! openssl x509 -in "$CERT_CRT" -noout -ext subjectAltName 2>/dev/null | grep -q "IP Address:${LAN_IP}"; then
      echo "==> Existing HTTPS certificate does not match current LAN IP ${LAN_IP}; regenerating"
      NEED_CERT_REGEN=1
    fi
  fi

  if [ "$NEED_CERT_REGEN" = "1" ]; then
    echo "==> Generating self-signed HTTPS certificate"
    openssl req -x509 -nodes -newkey rsa:2048 \
      -keyout "$CERT_KEY" \
      -out "$CERT_CRT" \
      -days 365 \
      -subj "/CN=${CERT_CN}" \
      -addext "subjectAltName=${SAN_ENTRIES}"
  fi

  export TESSERAE_SSL_CERT="$CERT_CRT"
  export TESSERAE_SSL_KEY="$CERT_KEY"
  echo "==> Starting application on https://0.0.0.0:${PORT}"
else
  unset TESSERAE_SSL_CERT
  unset TESSERAE_SSL_KEY
  echo "==> Starting application on http://0.0.0.0:${PORT}"
fi

export PORT
python main.py
