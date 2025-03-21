#!/bin/bash
# Define ANSI color for blue and reset
BLUE='\033[34m'
YELLOW='\033[33m'
COLOR=$YELLOW
RESET='\033[0m'

# Spinner styles (each element will be printed in blue)
spinner_ascii=( '|' '/' '-' '\' )
spinner_unicode=( '◐' '◓' '◑' '◒' )
spinner_dots=( '⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏' )
spinner_arrows=( '←' '↑' '→' '↓' )
spinner_bounce=( '⠁' '⠂' '⠄' '⠂' )

# Function to simulate spinner for a given duration (in seconds)
simulate_spinner() {
  local spinner=("${!1}")
  local duration=$2
  local i=0
  local end=$((SECONDS+duration))
  while [ $SECONDS -lt $end ]; do
    printf "\rWaiting... ${COLOR}%s${RESET} " "${spinner[$((i % ${#spinner[@]}))]}"
    i=$((i+1))
    sleep 0.1
  done
  printf "\rWaiting... Done           \n"
}

# Test each spinner style for 3 seconds
echo "ASCII Spinner:"
simulate_spinner spinner_ascii[@] 3

echo "Unicode Circle Spinner:"
simulate_spinner spinner_unicode[@] 3

echo "Dots Spinner:"
simulate_spinner spinner_dots[@] 3

echo "Arrows Spinner:"
simulate_spinner spinner_arrows[@] 3

echo "Bounce Spinner:"
simulate_spinner spinner_bounce[@] 3
