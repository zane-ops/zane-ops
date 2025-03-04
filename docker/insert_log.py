import uuid
import datetime
import json
import time
import requests

LOKI_URL = "http://127.0.0.1:3100/loki/api/v1/push"
sources = ["SYSTEM", "PROXY", "SERVICE"]

for i in range(10):
    # Generate fields matching the SimpleLog model
    log_id = str(uuid.uuid4())
    now = (
        datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
        + "Z"
    )
    service_id = f"service-{i+1}"
    deployment_id = f"deployment-{i+1}"

    # Create the message with ANSI colors and its plain version (colors stripped)
    colored_message = f"\033[31mThis is log number {i+1}\033[0m"
    plain_message = f"This is log number {i+1}"

    # Alternate log level: even indices as ERROR, odd as INFO
    level = "ERROR" if i % 2 == 0 else "INFO"
    source = sources[i % len(sources)]

    # Build the log entry matching the Django SimpleLog model
    log_entry = {
        "id": log_id,
        "created_at": now,
        "service_id": service_id,
        "deployment_id": deployment_id,
        "time": now,
        "content": colored_message,  # text with ANSI colors
        "content_text": plain_message,  # text with colors stripped
        "level": level,
        "source": source,
    }

    # Use key fields as labels for filtering in Loki
    labels = {"service_id": service_id, "level": level, "source": source}

    # Generate an approximate nanosecond timestamp (macOS compatible)
    ts = str(int(time.time() * 1e9))

    # Build the payload as expected by Loki's push API
    payload = {"streams": [{"stream": labels, "values": [[ts, json.dumps(log_entry)]]}]}

    response = requests.post(LOKI_URL, json=payload)
    print(f"Inserted log {i+1} with status code {response.status_code}")
    # time.sleep(1)
