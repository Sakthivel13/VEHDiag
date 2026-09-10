"""File transfer / flash programming enumerations."""
from __future__ import annotations

from enum import Enum, IntEnum


class TransferDirection(str, Enum):
    """Direction of a UDS data transfer."""

    DOWNLOAD = "DOWNLOAD"
    UPLOAD = "UPLOAD"


class TransferState(str, Enum):
    """State machine of the transfer manager."""

    IDLE = "IDLE"
    PREPARING = "PREPARING"
    REQUESTING = "REQUESTING"
    TRANSFERRING = "TRANSFERRING"
    PAUSED = "PAUSED"
    EXITING = "EXITING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` when no further progress is expected."""
        return self in (
            TransferState.COMPLETED,
            TransferState.FAILED,
            TransferState.CANCELLED,
        )


class FirmwareFileType(str, Enum):
    """Supported firmware container formats."""

    INTEL_HEX = "INTEL_HEX"
    SREC = "SREC"
    BINARY = "BINARY"
    ELF = "ELF"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_suffix(cls, suffix: str) -> "FirmwareFileType":
        """Infer the file type from a filename *suffix* such as ``.hex``."""
        mapping = {
            ".hex": cls.INTEL_HEX,
            ".ihex": cls.INTEL_HEX,
            ".ihx": cls.INTEL_HEX,
            ".mot": cls.SREC,
            ".srec": cls.SREC,
            ".s19": cls.SREC,
            ".s28": cls.SREC,
            ".s37": cls.SREC,
            ".bin": cls.BINARY,
            ".raw": cls.BINARY,
            ".elf": cls.ELF,
            ".axf": cls.ELF,
        }
        return mapping.get(suffix.lower(), cls.UNKNOWN)


class CompressionMethod(IntEnum):
    """High nibble of the UDS dataFormatIdentifier."""

    NONE = 0x0
    MANUFACTURER_1 = 0x1
    MANUFACTURER_2 = 0x2


class EncryptionMethod(IntEnum):
    """Low nibble of the UDS dataFormatIdentifier."""

    NONE = 0x0
    MANUFACTURER_1 = 0x1
    MANUFACTURER_2 = 0x2


def data_format_identifier(
    compression: CompressionMethod = CompressionMethod.NONE,
    encryption: EncryptionMethod = EncryptionMethod.NONE,
) -> int:
    """Combine *compression* and *encryption* into a dataFormatIdentifier byte."""
    return ((int(compression) & 0x0F) << 4) | (int(encryption) & 0x0F)


__all__ = [
    "TransferDirection",
    "TransferState",
    "FirmwareFileType",
    "CompressionMethod",
    "EncryptionMethod",
    "data_format_identifier",
]
