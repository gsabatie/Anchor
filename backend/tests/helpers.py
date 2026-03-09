"""Shared test helpers and constants."""

import struct

TEST_TOKEN = "test-token-abc123"
FAKE_API_KEY = "fake-gemini-key"


def make_pcm16_silence(seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate PCM16 mono silence (all zeros).

    Args:
        seconds: Duration in seconds.
        sample_rate: Sample rate in Hz.

    Returns:
        Raw PCM16 bytes (little-endian int16).
    """
    num_samples = int(seconds * sample_rate)
    return struct.pack(f"<{num_samples}h", *([0] * num_samples))
