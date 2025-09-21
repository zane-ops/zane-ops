from datetime import datetime
import json
from typing import cast


class ColorfulFormatter:
    """Custom formatter with colors for terminal output"""

    # Color codes for terminal output
    COLORS = {
        "reset": "\033[0m",
        "bright": "\033[1m",
        "dim": "\033[2m",
        # Text colors
        "black": "\033[30m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
        "gray": "\033[90m",
        # Background colors
        "bg_red": "\033[41m",
        "bg_green": "\033[42m",
        "bg_yellow": "\033[43m",
        "bg_blue": "\033[44m",
    }

    def get_status_color(self, status):
        """Get color based on status code"""
        if 200 <= status < 300:
            return self.COLORS["green"]
        elif 300 <= status < 400:
            return self.COLORS["cyan"]
        elif 400 <= status < 500:
            return self.COLORS["yellow"]
        elif status >= 500:
            return self.COLORS["red"]
        return self.COLORS["white"]

    def get_method_color(self, method):
        """Get color based on HTTP method"""
        method_colors = {
            "GET": self.COLORS["blue"],
            "POST": self.COLORS["green"],
            "PUT": self.COLORS["yellow"],
            "DELETE": self.COLORS["red"],
            "PATCH": self.COLORS["magenta"],
        }
        return method_colors.get(method, self.COLORS["white"])

    def get_duration_color(self, duration_ms):
        """Get duration color based on performance"""
        if duration_ms < 100:
            return self.COLORS["green"]
        elif duration_ms < 500:
            return self.COLORS["yellow"]
        elif duration_ms < 1000:
            return self.COLORS["magenta"]
        return self.COLORS["red"]

    def format(self, data: dict):
        # Get the log data from the record

        request_time = cast(datetime, data.get("request_time"))
        method = data.get("request_method", "UNKNOWN")
        path = data.get("request_path", "/")
        status = data.get("response_status", 0)
        duration_ms = data.get("run_time_ms", 0)
        request_body = data.get("request_body", {})
        remote_addr = data.get("remote_address", "unknown")

        # Get colors
        method_color = self.get_method_color(method)
        status_color = self.get_status_color(status)
        duration_color = self.get_duration_color(duration_ms)

        # Format the main log line
        log_line = (
            f"{method_color}{self.COLORS['white']}{request_time.isoformat()}{self.COLORS['reset']}  "
            f"{method_color}{self.COLORS['bright']}{method.ljust(7)}{self.COLORS['reset']} "
            f"{self.COLORS['cyan']}{path}{self.COLORS['reset']} - "
            f"{status_color}{self.COLORS['bright']}{status}{self.COLORS['reset']} - "
            f"{duration_color}{duration_ms:.2f}ms{self.COLORS['reset']} "
            f"{self.COLORS['gray']}from {remote_addr}{self.COLORS['reset']}"
        )

        # Add request body if it exists and is not empty
        if request_body:
            body_json = json.dumps(request_body)
            log_line += (
                f"\n{self.COLORS['dim']}{self.COLORS['yellow']}Request Body:{self.COLORS['reset']}\n"
                f"{self.COLORS['dim']}{str(body_json)}{self.COLORS['reset']}"
            )

        return log_line
