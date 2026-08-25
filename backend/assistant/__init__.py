"""Tesserae assistant: guidance and results analysis from a locally served open model.

Design: compute the analysis in Python, let the model narrate it. See
research/motif_feature/CHATBOT_FEASIBILITY_2026-08-24.md for the benchmarks and
the evidence behind this architecture.
"""
from backend.assistant.model import is_available  # noqa: F401
