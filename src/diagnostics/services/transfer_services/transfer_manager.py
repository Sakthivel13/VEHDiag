"""End-to-end orchestration of UDS upload and download sequences."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from ....core.enums.transfer_enums import (
    CompressionMethod,
    EncryptionMethod,
    FirmwareFileType,
    TransferDirection,
    TransferState,
)
from ....core.event_bus import EventType
from ....core.exceptions import TransferError
from ....core.models.file_transfer_model import MemorySegment, TransferFile, TransferProgress
from ....utils.checksum_calculator import crc32
from .block_sequence_counter import BlockSequenceCounter
from .request_download import RequestDownload
from .request_transfer_exit import RequestTransferExit
from .request_upload import RequestUpload
from .transfer_data import TransferData

_logger = logging.getLogger(__name__)

#: Signature of the progress callback.
ProgressCallback = Callable[[TransferProgress], None]


@dataclass(slots=True)
class TransferOptions:
    """Options controlling one transfer run.

    Attributes:
        compression: Compression method announced in the dataFormatIdentifier.
        encryption: Encryption method announced in the dataFormatIdentifier.
        address_bytes: Width of the address field of RequestDownload.
        length_bytes: Width of the size field of RequestDownload.
        block_size: Override for the payload per TransferData request
            (``0`` uses the value reported by the ECU).
        retry_failed_blocks: How often a rejected block is retransmitted.
        verify_after_transfer: Compare the CRC-32 reported by the ECU.
        inter_block_delay_ms: Optional pause between two blocks.
    """

    compression: CompressionMethod = CompressionMethod.NONE
    encryption: EncryptionMethod = EncryptionMethod.NONE
    address_bytes: int = 4
    length_bytes: int = 4
    block_size: int = 0
    retry_failed_blocks: int = 3
    verify_after_transfer: bool = True
    inter_block_delay_ms: float = 0.0


@dataclass(slots=True)
class TransferReport:
    """Result of a completed (or aborted) transfer."""

    direction: TransferDirection
    state: TransferState
    bytes_transferred: int = 0
    blocks: int = 0
    duration_s: float = 0.0
    crc32: int | None = None
    ecu_checksum: int | None = None
    message: str = ""
    data: bytes = b""
    log: list[str] = field(default_factory=list)

    @property
    def successful(self) -> bool:
        """Return ``True`` when the transfer completed without error."""
        return self.state is TransferState.COMPLETED

    @property
    def speed_bps(self) -> float:
        """Return the average speed in bytes per second."""
        return self.bytes_transferred / self.duration_s if self.duration_s > 0 else 0.0

    def summary(self) -> str:
        """Return a one line summary for the log panel."""
        return (
            f"{self.direction.value.lower()} {self.state.value.lower()}: "
            f"{self.bytes_transferred} bytes in {self.blocks} blocks "
            f"({self.speed_bps / 1024:.1f} KB/s)"
        )


class TransferManager:
    """Drives RequestDownload / TransferData / RequestTransferExit sequences.

    Args:
        client: UDS client used for transmission.
        options: Transfer options.
        on_progress: Callback invoked after every block.

    Example:
        >>> # manager = TransferManager(client)
        >>> # report = manager.download(0x08000000, firmware_bytes)
        >>> None
    """

    def __init__(
        self,
        client,  # noqa: ANN001
        options: TransferOptions | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        """Create the manager in the idle state."""
        self.client = client
        self.options = options or TransferOptions()
        self.on_progress = on_progress
        self.counter = BlockSequenceCounter()
        self.progress = TransferProgress()
        self._cancel = threading.Event()
        self._pause = threading.Event()

    # -- control ------------------------------------------------------------
    def cancel(self) -> None:
        """Request a graceful abort of the running transfer."""
        self._cancel.set()

    def pause(self) -> None:
        """Pause the transfer after the current block."""
        self._pause.set()

    def resume(self) -> None:
        """Resume a paused transfer."""
        self._pause.clear()

    @property
    def cancelled(self) -> bool:
        """Return ``True`` when a cancel was requested."""
        return self._cancel.is_set()

    # -- download ---------------------------------------------------------------
    def download(
        self,
        address: int,
        data: bytes,
        options: TransferOptions | None = None,
    ) -> TransferReport:
        """Download *data* into ECU memory starting at *address*.

        Returns:
            The :class:`TransferReport` describing the run.
        """
        opts = options or self.options
        self._cancel.clear()
        self._pause.clear()
        report = TransferReport(direction=TransferDirection.DOWNLOAD, state=TransferState.PREPARING)
        started = time.perf_counter()
        self.progress = TransferProgress(
            state=TransferState.REQUESTING,
            direction=TransferDirection.DOWNLOAD,
            bytes_total=len(data),
            started_at=time.time(),
        )
        self.client.bus.publish(
            EventType.DIAG_TRANSFER_STARTED,
            {"address": address, "size": len(data)},
            "TransferManager",
        )

        try:
            permission = RequestDownload(self.client).execute(
                address,
                len(data),
                opts.address_bytes,
                opts.length_bytes,
                opts.compression,
                opts.encryption,
            )
            block_size = opts.block_size or permission.max_payload
            report.log.append(
                f"RequestDownload accepted, max block length {permission.max_block_length}"
            )
            self.progress.blocks_total = (len(data) + block_size - 1) // block_size
            self.progress.state = TransferState.TRANSFERRING

            transfer = TransferData(self.client, self.counter)
            self.counter.reset()
            for offset in range(0, len(data), block_size):
                if self._cancel.is_set():
                    report.state = TransferState.CANCELLED
                    report.message = "cancelled by the operator"
                    return self._finish(report, started)
                while self._pause.is_set() and not self._cancel.is_set():
                    time.sleep(0.05)
                chunk = data[offset : offset + block_size]
                self._send_with_retry(transfer, chunk, opts.retry_failed_blocks)
                report.blocks += 1
                report.bytes_transferred += len(chunk)
                self.progress.advance(len(chunk))
                self._report_progress()
                if opts.inter_block_delay_ms:
                    time.sleep(opts.inter_block_delay_ms / 1000.0)

            self.progress.state = TransferState.EXITING
            exit_result = RequestTransferExit(self.client).execute()
            report.ecu_checksum = exit_result.checksum
            report.crc32 = crc32(data)
            report.log.append(str(exit_result))
            if not exit_result.accepted:
                report.state = TransferState.FAILED
                report.message = "the ECU rejected RequestTransferExit"
                return self._finish(report, started)
            report.state = TransferState.COMPLETED
            report.message = "transfer completed"
        except TransferError as exc:
            report.state = TransferState.FAILED
            report.message = str(exc)
            report.log.append(str(exc))
        except Exception as exc:  # noqa: BLE001 - report any failure to the UI
            report.state = TransferState.FAILED
            report.message = f"unexpected error: {exc}"
            _logger.exception("transfer failed")
        return self._finish(report, started)

    def upload(
        self,
        address: int,
        size: int,
        options: TransferOptions | None = None,
    ) -> TransferReport:
        """Upload *size* bytes from ECU memory starting at *address*."""
        opts = options or self.options
        self._cancel.clear()
        report = TransferReport(direction=TransferDirection.UPLOAD, state=TransferState.PREPARING)
        started = time.perf_counter()
        self.progress = TransferProgress(
            state=TransferState.REQUESTING,
            direction=TransferDirection.UPLOAD,
            bytes_total=size,
            started_at=time.time(),
        )
        buffer = bytearray()
        try:
            permission = RequestUpload(self.client).execute(
                address, size, opts.address_bytes, opts.length_bytes
            )
            block_size = opts.block_size or permission.max_payload
            self.progress.blocks_total = (size + block_size - 1) // block_size
            self.progress.state = TransferState.TRANSFERRING
            transfer = TransferData(self.client, self.counter)
            self.counter.reset()
            while len(buffer) < size:
                if self._cancel.is_set():
                    report.state = TransferState.CANCELLED
                    report.message = "cancelled by the operator"
                    report.data = bytes(buffer)
                    return self._finish(report, started)
                chunk = transfer.receive_block()
                if not chunk:
                    break
                buffer.extend(chunk)
                report.blocks += 1
                self.progress.advance(len(chunk))
                self._report_progress()
            RequestTransferExit(self.client).execute()
            report.data = bytes(buffer[:size])
            report.bytes_transferred = len(report.data)
            report.crc32 = crc32(report.data)
            report.state = TransferState.COMPLETED
            report.message = "upload completed"
        except Exception as exc:  # noqa: BLE001
            report.state = TransferState.FAILED
            report.message = str(exc)
            report.data = bytes(buffer)
        return self._finish(report, started)

    # -- file oriented helpers ------------------------------------------------------
    def download_segments(
        self,
        segments: Iterable[MemorySegment],
        options: TransferOptions | None = None,
    ) -> list[TransferReport]:
        """Download every segment, stopping at the first failure."""
        reports: list[TransferReport] = []
        for segment in segments:
            report = self.download(segment.address, segment.data, options)
            reports.append(report)
            if not report.successful:
                break
        return reports

    def download_file(
        self,
        path: str | Path,
        base_address: int | None = None,
        options: TransferOptions | None = None,
    ) -> list[TransferReport]:
        """Parse a firmware file and download all of its segments.

        Raises:
            TransferError: The file format is not supported.
        """
        from ....data_processing.file_parsers import parse_firmware_file

        file_path = Path(path).expanduser()
        file_type = FirmwareFileType.from_suffix(file_path.suffix)
        if file_type is FirmwareFileType.UNKNOWN:
            raise TransferError(f"unsupported firmware file type: {file_path.suffix}")
        segments = parse_firmware_file(file_path, base_address=base_address)
        self.progress.current_file = file_path.name
        return self.download_segments(segments, options)

    def download_files(
        self,
        files: list[TransferFile],
        options: TransferOptions | None = None,
    ) -> list[TransferReport]:
        """Download every enabled file of *files* in order."""
        reports: list[TransferReport] = []
        for entry in files:
            if not entry.enabled:
                continue
            self.progress.current_file = entry.path.name
            reports.extend(self.download_segments(entry.segments, options))
            if reports and not reports[-1].successful:
                break
        return reports

    # -- internals -------------------------------------------------------------------
    def _send_with_retry(self, transfer: TransferData, chunk: bytes, retries: int) -> None:
        """Send one block, retrying up to *retries* times.

        Raises:
            TransferError: Every attempt failed.
        """
        last_error: Exception | None = None
        for attempt in range(max(1, retries)):
            try:
                transfer.send_block(chunk)
                return
            except TransferError as exc:
                last_error = exc
                _logger.warning("block retry %d/%d: %s", attempt + 1, retries, exc)
                time.sleep(0.1 * (attempt + 1))
        raise TransferError(
            "the ECU rejected a data block after every retry",
            {"cause": str(last_error) if last_error else ""},
        )

    def _report_progress(self) -> None:
        """Publish the progress to the callback and the event bus."""
        if self.on_progress is not None:
            self.on_progress(self.progress)
        self.client.bus.publish(
            EventType.DIAG_TRANSFER_PROGRESS,
            {
                "percent": self.progress.percent,
                "bytes_done": self.progress.bytes_done,
                "bytes_total": self.progress.bytes_total,
                "speed_bps": self.progress.speed_bps,
                "eta_s": self.progress.eta_s,
            },
            "TransferManager",
        )

    def _finish(self, report: TransferReport, started: float) -> TransferReport:
        """Finalise *report*, update the progress and publish the outcome."""
        report.duration_s = time.perf_counter() - started
        self.progress.state = report.state
        self.progress.message = report.message
        self._report_progress()
        event = (
            EventType.DIAG_TRANSFER_COMPLETE
            if report.successful
            else EventType.DIAG_TRANSFER_FAILED
        )
        self.client.bus.publish(
            event,
            {"summary": report.summary(), "message": report.message},
            "TransferManager",
        )
        _logger.info("%s", report.summary())
        return report


__all__ = ["TransferManager", "TransferOptions", "TransferReport", "ProgressCallback"]
