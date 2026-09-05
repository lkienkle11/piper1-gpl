#!/usr/bin/env bash
VALID_COMMANDS=("speak" "download" "stanza-download" "server")

DATA_DIR='/data'
COMMAND="$1"
shift

case "${COMMAND}" in
  speak)
    exec python3 -m piper --data-dir "${DATA_DIR}" "$@"
    ;;
  download)
    exec python3 -m piper.download_voices "$@" --download-dir "${DATA_DIR}"
    ;;
  stanza-download)
    exec python3 -m piper.stanza_resources "$@" --model-dir "${DATA_DIR}/stanza"
    ;;
  server)
    exec python3 -m piper.http_server \
      --host 0.0.0.0 \
      "$@" \
      --data-dir "${DATA_DIR}" \
      --download-dir "${DATA_DIR}"
    ;;
  ""|help|-h|--help)
    echo "Usage: <command> [args...]"
    echo "Available commands:"
    echo "  speak        Synthesize audio from text"
    echo "  download     Download voices"
    echo "  stanza-download  Download Stanza resources"
    echo "  server       Run HTTP server"
    exit 0
    ;;
  *)
    echo "Error: Unknown command '$COMMAND'"
    echo "Run with --help for usage."
    exit 1
    ;;
esac
