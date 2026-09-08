"""NVIDIA GPU backend.

The vendor SDK is imported only when this backend is instantiated so importing
the core package remains vendor independent.
"""

from .backend import NvidiaBackend, NvidiaBackendUnavailable

__all__ = ["NvidiaBackend", "NvidiaBackendUnavailable"]
