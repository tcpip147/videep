from __future__ import annotations

import struct

from videep.transport.rtsp import (
    H264Depacketizer,
    H264Packetizer,
    RtspAnnounceSink,
    RtspPullSource,
    RtspResponse,
    _parse_rtp,
)


def rtp(payload: bytes, *, marker: bool, timestamp: int = 90_000) -> bytes:
    return struct.pack("!BBHII", 0x80, 96 | (0x80 if marker else 0), 1, timestamp, 7) + payload


def test_h264_single_nal_round_trip() -> None:
    access_unit = b"\x00\x00\x00\x01\x65" + b"payload"
    packetizer = H264Packetizer(1200)
    depacketizer = H264Depacketizer()
    result = None
    for payload, marker in packetizer.packetize(access_unit):
        result = depacketizer.push(payload, marker)
    assert result == access_unit


def test_h264_fu_a_round_trip() -> None:
    access_unit = b"\x00\x00\x00\x01\x65" + bytes(range(256)) * 8
    packets = H264Packetizer(128).packetize(access_unit)
    assert len(packets) > 1
    depacketizer = H264Depacketizer()
    result = None
    for payload, marker in packets:
        result = depacketizer.push(payload, marker)
    assert result == access_unit


def test_rtp_header_parser() -> None:
    marker, timestamp, payload = _parse_rtp(rtp(b"abc", marker=True))
    assert marker and timestamp == 90_000 and payload == b"abc"


class FakeConnection:
    def __init__(self, responses: list[tuple[int, bytes]] | None = None) -> None:
        self.url = "rtsp://localhost/live"
        self.requests: list[tuple[str, str | None, dict[str, str] | None, bytes]] = []
        self.frames: list[tuple[int, bytes]] = []
        self.responses = iter(responses or [])

    def request(
        self,
        method: str,
        url: str | None = None,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> RtspResponse:
        self.requests.append((method, url, headers, body))
        sdp = b"v=0\r\nm=video 0 RTP/AVP 96\r\na=rtpmap:96 H264/90000\r\na=control:trackID=0\r\n"
        return RtspResponse(200, "OK", {"session": "1"}, sdp if method == "DESCRIBE" else b"")

    def read_interleaved(self) -> tuple[int, bytes]:
        return next(self.responses)

    def write_interleaved(self, channel: int, payload: bytes) -> None:
        self.frames.append((channel, payload))

    def close(self) -> None:
        pass

    def keepalive_if_due(self) -> None:
        pass


def test_pull_source_uses_describe_setup_play_and_returns_annex_b() -> None:
    source = RtspPullSource("rtsp://localhost/live")
    fake = FakeConnection([(0, rtp(b"\x65abc", marker=True))])
    source._connection = fake  # type: ignore[assignment]
    assert next(source) == b"\x00\x00\x00\x01\x65abc"
    assert [item[0] for item in fake.requests] == ["DESCRIBE", "SETUP", "PLAY"]


def test_push_sink_uses_announce_setup_record_and_interleaved_rtp() -> None:
    sink = RtspAnnounceSink("rtsp://localhost/live", fps=30)
    fake = FakeConnection()
    sink._connection = fake  # type: ignore[assignment]
    sink.write(b"\x00\x00\x00\x01\x65abc")
    assert [item[0] for item in fake.requests] == ["ANNOUNCE", "SETUP", "RECORD"]
    assert fake.requests[0][3].startswith(b"v=0")
    assert len(fake.frames) == 1
    marker, timestamp, payload = _parse_rtp(fake.frames[0][1])
    assert marker and timestamp == 0 and payload == b"\x65abc"


def test_push_sink_uses_its_90khz_clock_instead_of_encoder_timestamps() -> None:
    sink = RtspAnnounceSink("rtsp://localhost/live", fps=30)
    fake = FakeConnection()
    sink._connection = fake  # type: ignore[assignment]

    sink.write(b"\x00\x00\x00\x01\x65abc", timestamp=100)
    sink.write(b"\x00\x00\x00\x01\x41def", timestamp=101)

    first_timestamp = _parse_rtp(fake.frames[0][1])[1]
    second_timestamp = _parse_rtp(fake.frames[1][1])[1]
    assert (first_timestamp, second_timestamp) == (0, 3_000)
    assert sink.timestamp_fallbacks == 2
