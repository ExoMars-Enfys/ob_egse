"""Hardware-free OB command/response replay using an existing run folder."""

from __future__ import annotations

import logging
import re
import threading
import time
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, NoReturn

from utility_modules.psu_log_utility import load_psu_channel_samples

logger = logging.getLogger("info_log")
_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[.,]\d{3,6}).*? - (.*)$")


class ReplayError(RuntimeError):
    """The recording cannot satisfy a requested transaction."""


@dataclass(frozen=True)
class Record:
    timestamp: datetime
    payload: bytes


@dataclass(frozen=True)
class Transaction:
    command: Record
    response: Record | None


def _records(path: Path) -> list[Record]:
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = _LINE.match(line)
        if match is None:
            raise ReplayError(f"Invalid OB log record: {path.name}:{number}")
        try:
            timestamp = datetime.strptime(match[1].replace(",", "."), "%Y-%m-%d %H:%M:%S.%f")
            payload = bytes.fromhex(match[2])
        except ValueError as exc:
            raise ReplayError(f"Invalid OB log record: {path.name}:{number}: {exc}") from exc
        if not payload:
            raise ReplayError(f"Empty packet: {path.name}:{number}")
        records.append(Record(timestamp, payload))
    if any(right.timestamp < left.timestamp for left, right in zip(records, records[1:])):
        raise ReplayError(f"Records are not chronological: {path}")
    return records


class OBLogReplay:
    """Share a recorded timeline between virtual OB and PSU ports.

    Non-HK commands must match exactly. Polling reads recorded snapshots, so a
    different GUI polling cadence does not consume script command responses.
    """

    def __init__(self, path: str | Path, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.RLock()
        self.ob_port = ReplayOBPort(self)
        self.psu_port = ReplayPSUPort(self)
        self.load(path)

    def load(self, path: str | Path) -> None:
        selected = Path(path)
        if selected.is_dir():
            candidates = list(selected.glob("*_CMD.LOG")) + list(selected.glob("*_CMD.log"))
            candidates = sorted(set(candidates))
            if len(candidates) != 1:
                raise ReplayError("Select a CMD log when the folder has zero or multiple CMD logs")
            selected = candidates[0]
        if not selected.name.upper().endswith("_CMD.LOG"):
            raise ReplayError("Select an OB run folder or its *_CMD.LOG file")
        prefix = selected.name[:-8]
        siblings = {item.name.lower(): item for item in selected.parent.iterdir() if item.is_file()}

        def sibling(suffix: str) -> Path:
            result = siblings.get(f"{prefix}{suffix}".lower())
            if result is None:
                raise ReplayError(f"Missing matching log: {prefix}{suffix}")
            return result

        commands = _records(selected)
        if not commands:
            raise ReplayError(f"No commands recorded in {selected}")
        if any(len(command.payload) != 8 for command in commands):
            raise ReplayError("Not an OB CMD log: commands must contain exactly 8 bytes")
        hk = _records(sibling("_HK.LOG"))
        responses = sorted(
            hk + _records(sibling("_ACK.LOG")) + _records(sibling("_SCI.LOG")),
            key=lambda record: record.timestamp,
        )
        if not hk:
            raise ReplayError("No HK packets recorded; the GUI requires housekeeping telemetry")
        response_times = [record.timestamp for record in responses]
        transactions = []
        for index, command in enumerate(commands):
            if command.payload[0] & 0x0F == 0:
                continue
            start = bisect_right(response_times, command.timestamp - timedelta(microseconds=1))
            end = commands[index + 1].timestamp if index + 1 < len(commands) else datetime.max
            response = responses[start] if start < len(responses) and responses[start].timestamp < end else None
            transactions.append(Transaction(command, response))

        psu_path = sibling("_PSU.log")
        psu_samples = load_psu_channel_samples(psu_path)
        # Setup lines contain programmed setpoints, not measured output values.
        setup_times = {
            datetime.strptime(match[1].replace(",", "."), "%Y-%m-%d %H:%M:%S.%f")
            for line in psu_path.read_text(encoding="utf-8").splitlines()
            if (match := _LINE.match(line)) is not None and "CH1_V" in match[2]
        }
        psu_samples = [sample for sample in psu_samples if sample["TIME"] not in setup_times]
        if not psu_samples:
            raise ReplayError("No PSU samples recorded; cannot replay current checks")
        with self._lock:
            self.source = selected
            self._transactions = transactions
            self._hk = hk
            self._hk_times = [record.timestamp for record in hk]
            self._psu_samples = psu_samples
            self._psu_times = [sample["TIME"] for sample in psu_samples]
            self._index = 0
            self._output_status = {f"CH{channel}": 0 for channel in range(1, 5)}
            self._anchor = max(commands[0].timestamp, hk[0].timestamp, self._psu_times[0])
            self._wall_anchor = self._clock()
            self.last_error: str | None = None
            self.ob_port.reset_input_buffer()
            self.psu_port.reset_input_buffer()
        logger.warning("OFFLINE OB REPLAY loaded: %s (%d non-HK commands)", selected, len(transactions))
        logger.warning("Replay PSU output switches are emulated; voltage/current values come only from the recording")

    @property
    def timestamp(self) -> datetime:
        with self._lock:
            current = self._anchor + timedelta(seconds=max(0.0, self._clock() - self._wall_anchor))
            boundary = (
                self._transactions[self._index].command.timestamp
                if self._index < len(self._transactions)
                else self._anchor
            )
            return max(self._anchor, min(current, boundary))

    @property
    def progress(self) -> str:
        with self._lock:
            return f"{self._index}/{len(self._transactions)} recorded non-HK commands; {self.timestamp}"

    @property
    def model_name(self) -> str:
        from core_modules import config

        model_id = self._hk[0].payload[0] >> 5
        return next(name for name in config.MODEL_OPTIONS if int(config.MODEL_BITMAPS[name], 2) == model_id)

    def _fail(self, message: str) -> NoReturn:
        self.last_error = message
        logger.error("OB replay: %s", message)
        raise ReplayError(message)

    def transact(self, payload: bytes) -> bytes:
        with self._lock:
            if not self.ob_port.is_open:
                self._fail("Virtual OB port is closed")
            if len(payload) != 8:
                self._fail("OB replay expects an 8-byte command")
            if payload[0] & 0x0F == 0:
                index = bisect_right(self._hk_times, self.timestamp) - 1
                if index < 0:
                    self._fail("No housekeeping recorded at the current replay time")
                return self._hk[index].payload
            if self._index == len(self._transactions):
                self._fail("Recording ended: no further command/response is available; this is not an FFT pass")
            transaction = self._transactions[self._index]
            if payload != transaction.command.payload:
                self._fail(
                    f"Command mismatch at {transaction.command.timestamp}: expected "
                    f"{transaction.command.payload.hex(' ')}, requested {payload.hex(' ')}. "
                    "The recording cannot predict responses to different commands."
                )
            if transaction.response is None:
                self._fail(f"No response recorded for command at {transaction.command.timestamp}")
            self._index += 1
            self._anchor = transaction.response.timestamp
            self._wall_anchor = self._clock()
            return transaction.response.payload

    def psu_value(self, channel: str, kind: str) -> str:
        with self._lock:
            index = bisect_right(self._psu_times, self.timestamp) - 1
            if index < 0:
                self._fail("No PSU measurement recorded at the current replay time")
            sample = self._psu_samples[index]
            if kind == "OP":
                value = self._output_status[channel]
            else:
                value = sample["CHANNELS"][channel][kind]
                if value is None:
                    self._fail(f"No {channel} {kind} measurement recorded at {sample['TIME']}")
            return f"{value}\n"

    def switch_outputs(self, channel: str, enabled: int) -> None:
        with self._lock:
            if channel == "ALL":
                self._output_status = {name: enabled for name in self._output_status}
            else:
                self._output_status[f"CH{channel}"] = enabled

    def publish_psu(self) -> None:
        """Publish recorded measurements through the normal PSU cache/GUI queue."""
        from core_modules import constants as const
        from utility_modules import eb_packet_utility

        with self._lock:
            index = bisect_right(self._psu_times, self.timestamp) - 1
            if index < 0:
                self._fail("No PSU measurement recorded at the current replay time")
            sample = self._psu_samples[index]
            packet: dict[str, Any] = {"TIME": datetime.now(), "STATUS": int(any(self._output_status.values()))}
            for channel, values in sample["CHANNELS"].items():
                packet[f"{channel}_STATUS"] = self._output_status[channel]
                packet[f"{channel}_V"] = values["V"]
                packet[f"{channel}_I"] = values["I"]
        eb_packet_utility.set_latest_psu(packet)
        if const.psu_queue is not None:
            const.psu_queue.put(packet)

    def monitor_psu(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self.publish_psu()
            stop_event.wait(0.1)


class ReplayOBPort:
    """Minimal serial endpoint used by existing OB TC/TM functions."""

    def __init__(self, replay: OBLogReplay) -> None:
        self.replay = replay
        self.is_open = True
        self.port = "OFFLINE-OB-REPLAY"
        self._buffer = b""

    def write(self, payload: bytes) -> int:
        if self._buffer:
            raise ReplayError("Previous recorded response has not been fully read")
        self._buffer = self.replay.transact(payload)
        return len(payload)

    def read(self, size: int = 1) -> bytes:
        result, self._buffer = self._buffer[:size], self._buffer[size:]
        return result

    def reset_input_buffer(self) -> None:
        self._buffer = b""

    def reset_output_buffer(self) -> None:
        pass

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.is_open = False


class ReplayPSUPort:
    """Read recorded PSU values; control writes never reach physical hardware."""

    def __init__(self, replay: OBLogReplay) -> None:
        self.replay = replay
        self.is_open = True
        self.port = "OFFLINE-PSU-REPLAY"
        self._buffer = b""

    def write(self, payload: bytes) -> int:
        command = payload.decode("ascii").strip()
        if not self.is_open:
            raise ReplayError("Virtual PSU port is closed")
        query = re.fullmatch(r"(OP|V|I)([1-4])O?\?", command)
        if query:
            self._buffer = self.replay.psu_value(f"CH{query[2]}", query[1]).encode("ascii")
        elif command == "*IDN?":
            self._buffer = b"OFFLINE OB LOG REPLAY\n"
        elif (switch := re.fullmatch(r"OP(ALL|[1-4]) ([01])", command)) is not None:
            self.replay.switch_outputs(switch[1], int(switch[2]))
        elif re.fullmatch(r"(?:OPALL|OP[1-4]|V[1-4]|I[1-4]|OVP[1-4]) [-+\d.]+(?: 1)?|LOCAL", command):
            logger.info("Offline PSU control: %s (recorded measurements are unchanged)", command)
        else:
            raise ReplayError(f"Unsupported offline PSU command: {command}")
        return len(payload)

    def readline(self) -> bytes:
        result, self._buffer = self._buffer, b""
        return result

    def reset_input_buffer(self) -> None:
        self._buffer = b""

    def reset_output_buffer(self) -> None:
        pass

    def flush(self) -> None:
        pass

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False
