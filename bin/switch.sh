#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

COMPOSE_BASE="-f docker-compose.yml"
COMPOSE_DEV="-f docker-compose.yml -f docker-compose.dev.yml"
PROJECT="printer-search"
MODE_FILE="${PROJECT_DIR}/.mode"

usage() {
  cat <<EOF
PCM Printer Search Docker Mode Switcher

Usage: $(basename "$0") <command> [options]

Commands:
  dev              Switch to development mode (Flask dev server, debug on)
  prod             Switch to production mode (Gunicorn, optimized)
  rebuild [mode]   Rebuild and restart (dev or prod, defaults to current)
  status           Show current mode and container state
  logs             Tail logs from the web service

Examples:
  $(basename "$0") dev          # Switch to dev mode
  $(basename "$0") rebuild prod # Force rebuild of prod mode
  $(basename "$0") status       # Check current mode

EOF
  exit 1
}

detect_mode() {
  if [ -f "$MODE_FILE" ]; then
    cat "$MODE_FILE"
  elif docker ps --filter "name=${PROJECT}" --format '{{.Names}}' 2>/dev/null | grep -q .; then
    local label
    label=$(docker inspect "${PROJECT}-web" --format '{{index .Labels "app.mode"}}' 2>/dev/null || echo "unknown")
    case "$label" in
      dev|prod) echo "$label" ;;
      *) echo "unknown" ;;
    esac
  else
    echo "stopped"
  fi
}

save_mode() {
  echo "$1" > "$MODE_FILE"
}

get_local_ip() {
  ip -4 route get 1.1.1.1 2>/dev/null | grep -oP 'src \K[\d.]+' || \
  hostname -I 2>/dev/null | awk '{print $1}' || \
  echo "localhost"
}

cmd_status() {
  local mode
  mode=$(detect_mode)
  local lan_ip
  lan_ip=$(get_local_ip)

  case "$mode" in
    dev)
      echo "Mode: dev (Flask dev server with auto-reload)"
      echo "URL:  http://localhost:5000"
      echo "LAN:  http://${lan_ip}:5000"
      ;;
    prod)
      echo "Mode: prod (Gunicorn, production-optimized)"
      echo "URL:  http://localhost:5000"
      echo "LAN:  http://${lan_ip}:5000"
      ;;
    stopped)
      echo "Mode: stopped"
      echo "URL:  (not running)"
      echo "LAN:  (not running)"
      ;;
    *)
      echo "Mode: unknown (container may be orphaned)"
      ;;
  esac

  echo ""
  docker ps --filter "name=${PROJECT}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

cmd_dev() {
  local current
  current=$(detect_mode)

  if [ "$current" = "dev" ]; then
    echo "Already in dev mode"
    return
  fi

  echo "→ Stopping any running containers..."
  docker compose $COMPOSE_BASE down 2>/dev/null || true
  docker compose $COMPOSE_DEV down 2>/dev/null || true

  echo "→ Starting development mode..."
  docker compose $COMPOSE_DEV up -d
  save_mode "dev"
  echo ""
  echo "✓ Dev mode ready at http://localhost:5000"
  echo "  • Flask dev server with auto-reload enabled"
  echo "  • Source files mounted for live editing"
}

cmd_prod() {
  local current
  current=$(detect_mode)

  if [ "$current" = "prod" ]; then
    echo "Already in prod mode"
    return
  fi

  echo "→ Stopping any running containers..."
  docker compose $COMPOSE_BASE down 2>/dev/null || true
  docker compose $COMPOSE_DEV down 2>/dev/null || true

  echo "→ Starting production mode..."
  docker compose $COMPOSE_BASE up -d
  save_mode "prod"
  echo ""
  echo "✓ Prod mode ready at http://localhost:5000"
  echo "  • Gunicorn with 4 workers"
  echo "  • Optimized for production"
}

cmd_rebuild() {
  local mode="${1:-$(detect_mode)}"

  case "$mode" in
    dev)
      echo "→ Rebuilding dev image..."
      docker compose $COMPOSE_DEV up -d --build
      save_mode "dev"
      echo "✓ Dev rebuild complete at http://localhost:5000"
      ;;
    prod)
      echo "→ Rebuilding prod image..."
      docker compose $COMPOSE_BASE up -d --build
      save_mode "prod"
      echo "✓ Prod rebuild complete at http://localhost:5000"
      ;;
    stopped)
      echo "No containers running. Specify dev or prod:"
      echo "  $(basename "$0") rebuild dev"
      echo "  $(basename "$0") rebuild prod"
      exit 1
      ;;
    *)
      echo "Unknown mode: $mode (use dev or prod)"
      exit 1
      ;;
  esac
}

cmd_logs() {
  local mode
  mode=$(detect_mode)

  case "$mode" in
    dev)
      docker compose $COMPOSE_DEV logs -f
      ;;
    prod)
      docker compose $COMPOSE_BASE logs -f
      ;;
    stopped)
      echo "No containers running. Start a mode first:"
      echo "  $(basename "$0") dev"
      exit 1
      ;;
    *)
      docker compose logs -f
      ;;
  esac
}

cmd_stop() {
  echo "→ Stopping all containers..."
  docker compose $COMPOSE_BASE down 2>/dev/null || true
  docker compose $COMPOSE_DEV down 2>/dev/null || true
  rm -f "$MODE_FILE"
  echo "✓ Stopped"
}

# --- main ---
case "${1:-}" in
  dev)     cmd_dev ;;
  prod)    cmd_prod ;;
  rebuild) cmd_rebuild "${2:-}" ;;
  status)  cmd_status ;;
  logs)    cmd_logs ;;
  stop)    cmd_stop ;;
  *)       usage ;;
esac