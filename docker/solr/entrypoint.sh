#!/bin/bash

keepalive() {
  # Wait for Solr to fully initialize
  echo "Waiting for Solr to start..."
  until curl -s 'http://localhost:8983/solr/admin/cores' > /dev/null; do
    sleep 5
  done
  echo "Solr started."

  # Keep-alive loop
  while true; do
    curl -s 'http://localhost:8983/solr/logs/select?q=*:*&rows=1' > /dev/null
    echo "Keep-alive query sent at $(date)"
    sleep 5 
  done
}

# Precreate the "logs" core
keepalive & solr-precreate logs



