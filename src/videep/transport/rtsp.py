"""외부 미디어 프로그램 없이 동작하는 경량 RTSP/RTP 전송.

픽셀 프레임이 아닌 H.264 압축 access unit만 취급하므로 GPU 상주 픽셀 경로와 분리된다.
"""

from __future__ import annotations

import base64
import socket
import struct
from collections import deque
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit, urlunsplit
from time import monotonic


class RtspError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RtspResponse:
    status: int
    reason: str
    headers: dict[str, str]
    body: bytes


def _split_annex_b(data: bytes) -> list[bytes]:
    starts: list[tuple[int, int]] = []
    index = 0
    while index < len(data) - 2:
        if data[index : index + 3] == b"\x00\x00\x01":
            starts.append((index, 3))
            index += 3
        elif data[index : index + 4] == b"\x00\x00\x00\x01":
            starts.append((index, 4))
            index += 4
        else:
            index += 1
    if not starts:
        # NVENC/컨테이너 어댑터가 반환하는 length-prefixed(AVCC) 형식도
        # RTP packetizer의 입력인 NAL 목록으로 정규화한다.
        nals: list[bytes] = []
        offset = 0
        while offset + 4 <= len(data):
            size = struct.unpack_from("!I", data, offset)[0]
            offset += 4
            if size == 0 or offset + size > len(data):
                nals = []
                break
            nals.append(data[offset : offset + size])
            offset += size
        if nals and offset == len(data):
            return nals
        return [data] if data else []
    units = []
    for position, (start, prefix) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(data)
        if end > start + prefix:
            units.append(data[start + prefix : end])
    return units


class H264Depacketizer:
    def __init__(self) -> None:
        self._access_unit: list[bytes] = []
        self._fragment: bytearray | None = None

    def push(self, payload: bytes, marker: bool) -> bytes | None:
        if not payload:
            return None
        nal_type = payload[0] & 0x1F
        if 1 <= nal_type <= 23:
            self._access_unit.append(payload)
        elif nal_type == 24:
            offset = 1
            while offset + 2 <= len(payload):
                size = struct.unpack_from("!H", payload, offset)[0]
                offset += 2
                if size == 0 or offset + size > len(payload):
                    raise RtspError("잘못된 H.264 STAP-A 패킷입니다")
                self._access_unit.append(payload[offset : offset + size])
                offset += size
        elif nal_type == 28:
            if len(payload) < 2:
                raise RtspError("잘못된 H.264 FU-A 패킷입니다")
            start, end = bool(payload[1] & 0x80), bool(payload[1] & 0x40)
            header = bytes(((payload[0] & 0xE0) | (payload[1] & 0x1F),))
            if start:
                self._fragment = bytearray(header + payload[2:])
            elif self._fragment is None:
                raise RtspError("시작 조각 없는 H.264 FU-A 패킷입니다")
            else:
                self._fragment.extend(payload[2:])
            if end and self._fragment is not None:
                self._access_unit.append(bytes(self._fragment))
                self._fragment = None
        else:
            raise RtspError(f"지원하지 않는 H.264 RTP NAL 유형: {nal_type}")
        if not marker:
            return None
        if self._fragment is not None:
            raise RtspError("완료되지 않은 H.264 FU-A access unit입니다")
        result = b"".join(b"\x00\x00\x00\x01" + nal for nal in self._access_unit)
        self._access_unit.clear()
        return result or None


class H264Packetizer:
    def __init__(self, mtu: int = 1200) -> None:
        if mtu < 64:
            raise ValueError("RTP MTU는 64 이상이어야 합니다")
        self.mtu = mtu

    def packetize(self, access_unit: bytes) -> list[tuple[bytes, bool]]:
        output: list[tuple[bytes, bool]] = []
        nals = _split_annex_b(access_unit)
        for nal_index, nal in enumerate(nals):
            last_nal = nal_index == len(nals) - 1
            if len(nal) <= self.mtu:
                output.append((nal, last_nal))
                continue
            indicator = (nal[0] & 0xE0) | 28
            nal_type = nal[0] & 0x1F
            chunks = [nal[i : i + self.mtu - 2] for i in range(1, len(nal), self.mtu - 2)]
            for index, chunk in enumerate(chunks):
                fu_header = nal_type
                if index == 0:
                    fu_header |= 0x80
                if index == len(chunks) - 1:
                    fu_header |= 0x40
                output.append(
                    (bytes((indicator, fu_header)) + chunk, last_nal and index == len(chunks) - 1)
                )
        return output


class _RtspConnection:
    def __init__(self, url: str, timeout: float = 10.0) -> None:
        parsed = urlsplit(url)
        if parsed.scheme.lower() != "rtsp" or not parsed.hostname:
            raise ValueError(f"유효하지 않은 RTSP URL: {url}")
        self.url = urlunsplit(
            (parsed.scheme, parsed.netloc.rsplit("@", 1)[-1], parsed.path, parsed.query, "")
        )
        self.host = parsed.hostname
        self.port = parsed.port or 554
        self.timeout = timeout
        self.authorization = None
        if parsed.username is not None:
            credential = f"{unquote(parsed.username)}:{unquote(parsed.password or '')}".encode()
            self.authorization = "Basic " + base64.b64encode(credential).decode("ascii")
        self.socket: socket.socket | None = None
        self.cseq = 0
        self.session: str | None = None
        self._buffer = bytearray()
        self._interleaved: deque[tuple[int, bytes]] = deque()
        self._last_control = monotonic()
        self._keepalive_interval = 20.0

    def connect(self) -> None:
        if self.socket is None:
            try:
                self.socket = socket.create_connection((self.host, self.port), self.timeout)
            except OSError as exc:
                raise RtspError(
                    f"RTSP 서버에 연결할 수 없습니다: {self.host}:{self.port} ({exc})"
                ) from exc
            self.socket.settimeout(self.timeout)

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def request(
        self,
        method: str,
        url: str | None = None,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> RtspResponse:
        self.connect()
        self.cseq += 1
        values = {"CSeq": str(self.cseq), "User-Agent": "videep/0.1"}
        if self.authorization:
            values["Authorization"] = self.authorization
        if self.session and method not in {"DESCRIBE", "ANNOUNCE", "SETUP"}:
            values["Session"] = self.session
        values.update(headers or {})
        if body:
            values["Content-Length"] = str(len(body))
        head = f"{method} {url or self.url} RTSP/1.0\r\n" + "".join(
            f"{key}: {value}\r\n" for key, value in values.items()
        )
        assert self.socket is not None
        self.socket.sendall(head.encode("ascii") + b"\r\n" + body)
        response = self._read_response()
        session = response.headers.get("session")
        if session:
            self.session = session.split(";", 1)[0]
            for parameter in session.split(";")[1:]:
                if parameter.strip().lower().startswith("timeout="):
                    with suppress(ValueError):
                        timeout = float(parameter.split("=", 1)[1])
                        self._keepalive_interval = max(5.0, min(20.0, timeout * 0.5))
        self._last_control = monotonic()
        if not 200 <= response.status < 300:
            if (
                response.status == 401
                and "digest" in response.headers.get("www-authenticate", "").lower()
            ):
                raise RtspError(
                    "Digest 인증은 지원하지 않습니다; Basic 인증 또는 무인증을 사용하세요"
                )
            raise RtspError(f"RTSP {method} 실패: {response.status} {response.reason}")
        return response

    def _recv_until(self, marker: bytes) -> bytes:
        assert self.socket is not None
        while marker not in self._buffer:
            block = self.socket.recv(65536)
            if not block:
                raise RtspError("RTSP 연결이 종료되었습니다")
            self._buffer.extend(block)
        end = self._buffer.index(marker) + len(marker)
        result = bytes(self._buffer[:end])
        del self._buffer[:end]
        return result

    def _read_response(self) -> RtspResponse:
        while True:
            while not self._buffer:
                assert self.socket is not None
                self._buffer.extend(self.socket.recv(65536))
            if self._buffer[0] != 0x24:
                break
            self._interleaved.append(self._pop_interleaved())
        raw = self._recv_until(b"\r\n\r\n")
        lines = raw[:-4].decode("utf-8", "replace").split("\r\n")
        protocol, status, reason = lines[0].split(" ", 2)
        if protocol != "RTSP/1.0":
            raise RtspError(f"지원하지 않는 RTSP 응답: {protocol}")
        headers = {
            key.strip().lower(): value.strip()
            for key, value in (line.split(":", 1) for line in lines[1:] if ":" in line)
        }
        length = int(headers.get("content-length", "0"))
        while len(self._buffer) < length:
            assert self.socket is not None
            self._buffer.extend(self.socket.recv(65536))
        body = bytes(self._buffer[:length])
        del self._buffer[:length]
        return RtspResponse(int(status), reason, headers, body)

    def read_interleaved(self) -> tuple[int, bytes]:
        assert self.socket is not None
        if self._interleaved:
            return self._interleaved.popleft()
        while True:
            while len(self._buffer) < 4:
                self._buffer.extend(self.socket.recv(65536))
            if self._buffer[0] == 0x24:
                return self._pop_interleaved()
            self._read_response()

    def _pop_interleaved(self) -> tuple[int, bytes]:
        assert self.socket is not None and self._buffer[0] == 0x24
        channel, length = self._buffer[1], struct.unpack_from("!H", self._buffer, 2)[0]
        while len(self._buffer) < 4 + length:
            self._buffer.extend(self.socket.recv(65536))
        payload = bytes(self._buffer[4 : 4 + length])
        del self._buffer[: 4 + length]
        return channel, payload

    def keepalive_if_due(self) -> None:
        if self.session is None or monotonic() - self._last_control < self._keepalive_interval:
            return
        try:
            self.request("GET_PARAMETER")
        except RtspError:
            self.request("OPTIONS")

    def write_interleaved(self, channel: int, payload: bytes) -> None:
        assert self.socket is not None
        self.socket.sendall(b"$" + bytes((channel,)) + struct.pack("!H", len(payload)) + payload)


def _parse_rtp(packet: bytes) -> tuple[bool, int, bytes]:
    if len(packet) < 12 or packet[0] >> 6 != 2:
        raise RtspError("잘못된 RTP 패킷입니다")
    csrc_count = packet[0] & 0x0F
    extension = bool(packet[0] & 0x10)
    offset = 12 + csrc_count * 4
    if extension:
        if len(packet) < offset + 4:
            raise RtspError("잘못된 RTP 확장 헤더입니다")
        words = struct.unpack_from("!H", packet, offset + 2)[0]
        offset += 4 + words * 4
    if offset > len(packet):
        raise RtspError("잘못된 RTP 헤더 길이입니다")
    return bool(packet[1] & 0x80), struct.unpack_from("!I", packet, 4)[0], packet[offset:]


class RtspPullSource(Iterator[bytes]):
    """DESCRIBE/SETUP/PLAY 후 H.264 Annex-B access unit을 제공한다."""

    def __init__(self, url: str, *, timeout: float = 10.0) -> None:
        self._connection = _RtspConnection(url, timeout)
        self._depacketizer = H264Depacketizer()
        self._started = False

    def start(self) -> None:
        response = self._connection.request("DESCRIBE", headers={"Accept": "application/sdp"})
        sdp = response.body.decode("utf-8", "replace")
        if "H264/90000" not in sdp.upper():
            raise RtspError("현재 RTSP 입력은 H.264/90000만 지원합니다")
        control = next(
            (
                line[10:]
                for line in sdp.splitlines()
                if line.startswith("a=control:") and line[10:] != "*"
            ),
            self._connection.url,
        )
        track_url = (
            control
            if control.startswith("rtsp://")
            else self._connection.url.rstrip("/") + "/" + control.lstrip("/")
        )
        self._connection.request(
            "SETUP", track_url, {"Transport": "RTP/AVP/TCP;unicast;interleaved=0-1"}
        )
        self._connection.request("PLAY")
        self._started = True

    def __iter__(self) -> RtspPullSource:
        return self

    def __next__(self) -> bytes:
        if not self._started:
            self.start()
        while True:
            self._connection.keepalive_if_due()
            channel, packet = self._connection.read_interleaved()
            if channel != 0:
                continue
            marker, _timestamp, payload = _parse_rtp(packet)
            access_unit = self._depacketizer.push(payload, marker)
            if access_unit is not None:
                return access_unit

    def close(self) -> None:
        if self._started:
            with suppress(OSError, RtspError):
                self._connection.request("TEARDOWN")
        self._connection.close()


class RtspAnnounceSink:
    """ANNOUNCE/SETUP/RECORD로 H.264 access unit을 push한다."""

    def __init__(
        self, url: str, *, fps: float = 30.0, mtu: int = 1200, timeout: float = 10.0
    ) -> None:
        if fps <= 0:
            raise ValueError("fps는 양수여야 합니다")
        self._connection = _RtspConnection(url, timeout)
        self._packetizer = H264Packetizer(mtu)
        self._step = round(90_000 / fps)
        self._sequence = 0
        self._timestamp = 0
        self._ssrc = 0x56494445
        self._started = False
        self.sent_packets = 0
        self.sent_bytes = 0
        self.nal_units = 0
        self.sps_units = 0
        self.pps_units = 0
        self.idr_units = 0
        self.timestamp_fallbacks = 0
        self.last_rtp_timestamp = 0

    def start(self) -> None:
        sdp = (
            "v=0\r\no=videep 0 0 IN IP4 127.0.0.1\r\ns=Videep\r\nt=0 0\r\n"
            "m=video 0 RTP/AVP 96\r\na=rtpmap:96 H264/90000\r\n"
            "a=fmtp:96 packetization-mode=1\r\na=control:trackID=0\r\n"
        ).encode("ascii")
        self._connection.request("ANNOUNCE", headers={"Content-Type": "application/sdp"}, body=sdp)
        self._connection.request(
            "SETUP",
            self._connection.url.rstrip("/") + "/trackID=0",
            {"Transport": "RTP/AVP/TCP;unicast;interleaved=0-1;mode=record"},
        )
        self._connection.request("RECORD")
        self._started = True

    def write(self, access_unit: bytes, *, timestamp: int | None = None) -> None:
        if not self._started:
            self.start()
        self._connection.keepalive_if_due()
        for nal in _split_annex_b(access_unit):
            if not nal:
                continue
            self.nal_units += 1
            nal_type = nal[0] & 0x1F
            if nal_type == 7:
                self.sps_units += 1
            elif nal_type == 8:
                self.pps_units += 1
            elif nal_type == 5:
                self.idr_units += 1
        # NVENC의 timestamp는 버전/입력 방식에 따라 90 kHz PTS가 아니라
        # 프레임 인덱스(0, 1, 2...)일 수 있다. RTP 영상 시계는 항상 90 kHz이므로
        # sink가 알고 있는 FPS를 기준으로 독립적인 단조 증가 시계를 사용한다.
        current_timestamp = self._timestamp
        if timestamp is not None and (timestamp & 0xFFFFFFFF) != current_timestamp:
            self.timestamp_fallbacks += 1
        for payload, marker in self._packetizer.packetize(access_unit):
            header = struct.pack(
                "!BBHII",
                0x80,
                96 | (0x80 if marker else 0),
                self._sequence,
                current_timestamp,
                self._ssrc,
            )
            self._connection.write_interleaved(0, header + payload)
            self._sequence = (self._sequence + 1) & 0xFFFF
            self.sent_packets += 1
            self.sent_bytes += len(payload)
        self.last_rtp_timestamp = current_timestamp
        self._timestamp = (current_timestamp + self._step) & 0xFFFFFFFF

    def close(self) -> None:
        if self._started:
            with suppress(OSError, RtspError):
                self._connection.request("TEARDOWN")
        self._connection.close()
