"""
All files included in this directory contain code that is NOT part of the
MIT-licensed ZaneOps core. They are covered by the ZaneOps Enterprise Edition
(EE) license, found in ``backend/ee/LICENSE``, and may not be used, copied, or
distributed under the terms of the MIT license.

Dependency rule: code here may import from the MIT core (``zane_api`` and other
core apps), but the core must never import from ``ee/``. EE behavior is wired in
at startup through the registry seams exposed by the core (e.g.
``zane_api.licensing.gate.register_license_gate``), so the core keeps working —
with free-tier defaults, even when this entire directory is absent.
"""
