"""Unit tests for audio format handling (PCM16 / base64 round-trips)."""

import base64
import struct

from tests.helpers import make_pcm16_silence
from api.websocket import MAX_AUDIO_CHUNK_SIZE


class TestPcm16Format:
    def test_silence_has_correct_byte_count(self):
        """1 second at 16kHz mono = 16000 samples * 2 bytes = 32000 bytes."""
        audio = make_pcm16_silence(seconds=1.0, sample_rate=16000)
        assert len(audio) == 32000

    def test_bytes_are_even(self):
        """PCM16 samples are 2 bytes each, so total must be even."""
        for duration in (0.1, 0.5, 1.0, 2.0):
            audio = make_pcm16_silence(seconds=duration)
            assert len(audio) % 2 == 0


class TestBase64RoundTrip:
    def test_encode_decode_identity(self):
        """base64 encode → decode must return original bytes."""
        original = make_pcm16_silence(seconds=0.5)
        encoded = base64.b64encode(original).decode("utf-8")
        decoded = base64.b64decode(encoded)
        assert decoded == original

    def test_decoded_bytes_are_valid_pcm16(self):
        """Decoded base64 must have even length (valid PCM16)."""
        audio = make_pcm16_silence(seconds=0.25)
        encoded = base64.b64encode(audio).decode("utf-8")
        decoded = base64.b64decode(encoded)
        assert len(decoded) % 2 == 0


class TestMaxChunkSize:
    def test_max_chunk_is_256kb(self):
        assert MAX_AUDIO_CHUNK_SIZE == 256 * 1024

    def test_max_chunk_duration_at_16khz(self):
        """256KB of PCM16 @ 16kHz = 256*1024/2 samples / 16000 = ~8.19 seconds."""
        samples = MAX_AUDIO_CHUNK_SIZE // 2
        duration = samples / 16000
        assert 8.0 < duration < 8.5
