# ADR 0001 Scope and initial contracts

Status: Accepted for Phase 0; API remains experimental.

TacStack owns tactile-specific observations, semantic events, calibration provenance and model
contracts. It does not own generic cloud storage, a new recording format or a replacement viewer.
Reuse MCAP / Rerun / ROS2 / LeRobot at integration boundaries. Start with Python dataclasses,
NumPy and a local CLI; defer cloud services and training / inference dependencies.

Preserve raw payloads. Debug JSON is an inspection view, not lossless storage.
Validate obvious invalid timestamps, probabilities, latency and capability mismatches early.
Freeze API only after real data integration; schema evolution after v0.1 requires an ADR.

Consequences: Phase 0 can be installed and tested without hardware. Namespaced placeholder modules
make the planned structure visible, but do not claim implemented adapters or models.
