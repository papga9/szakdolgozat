#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/tmp/safety-daemon.log"
GPIO_PIN=14
ACTIVE_LOW=true

log() {
  printf "%s %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

if ! command -v raspi-gpio >/dev/null 2>&1; then
  log "ERROR: raspi-gpio not found. Install raspi-gpio or run on Raspberry Pi OS."
  exit 1
fi

raspi-gpio set "$GPIO_PIN" ip pu
log "Configured GPIO$GPIO_PIN as input with pull-up."

# Debounce settings
DEBOUNCE_MS=500
CHECK_INTERVAL_MS=100

# Helper to read pin level (0 or 1)
read_level() {
  local info
  info=$(raspi-gpio get "$GPIO_PIN")
  if echo "$info" | grep -q "level=1"; then
    echo 1
  else
    echo 0
  fi
}

log "Safety daemon started (PID $$). Writing PID to $PID_FILE"
printf "%s" "$$" > "$PID_FILE"

# Main loop
while true; do
  level=$(read_level)
  pressed=0
  if [[ "$ACTIVE_LOW" == "true" ]]; then
    [[ "$level" == "0" ]] && pressed=1
  else
    [[ "$level" == "1" ]] && pressed=1
  fi

  if [[ "$pressed" == "1" ]]; then
    sleep "$(awk "BEGIN {print $DEBOUNCE_MS/1000}")"
    level2=$(read_level)
    pressed2=0
    if [[ "$ACTIVE_LOW" == "true" ]]; then
      [[ "$level2" == "0" ]] && pressed2=1
    else
      [[ "$level2" == "1" ]] && pressed2=1
    fi

    if [[ "$pressed2" == "1" ]]; then
      log "GPIO$GPIO_PIN button press detected. Initiating shutdown."
      wall "Safety daemon: shutdown triggered by GPIO$GPIO_PIN button"
      sudo /sbin/shutdown -h now
      exit 0
    fi
  fi

  sleep "$(awk "BEGIN {print $CHECK_INTERVAL_MS/1000}")"
done
