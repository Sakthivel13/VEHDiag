"""Reorderable ECU flashing sequence.

A production flash is a fixed list of steps, but the *order* and the *set* of
steps differ per OEM and per ECU generation: some bootloaders want the erase
routine before ``RequestDownload``, some expect security access twice, some
skip the hardware-version read entirely. This module models the sequence as
data so the UI can drag, drop, enable and disable steps, and so the whole run
can be replayed head-lessly in a test.

The default sequence is the one required by the project specification:

===  ==========================================================
#    Step
===  ==========================================================
1    CAN initialisation
2    CAN configuration
3    ECU communication check
4    Read VIN
5    Read ECU hardware information
6    Read ECU software version
7    Security access
8    Erase memory
9    File upload (parse and stage the flash file)
10   Request download
11   Transfer data
12   Request transfer exit
13   ECU reset
===  ==========================================================

Example:
    >>> sequence = FlashSequence.default()
    >>> len(sequence)
    13
    >>> sequence.steps[0].kind is FlashStepKind.CAN_INIT
    True
    >>> sequence.move(0, 2) and sequence.steps[2].kind is FlashStepKind.CAN_INIT
    True
    >>> problems = sequence.validate()
    >>> any("must run before" in p for p in problems)
    True
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable

__all__ = [
    "CATEGORY_ORDER",
    "DEFAULT_ORDER",
    "FlashSequence",
    "FlashStep",
    "FlashStepKind",
    "StepOutcome",
    "StepStatus",
    "palette_steps",
]


class FlashStepKind(str, Enum):
    """The steps a flash sequence can be built from."""

    CAN_INIT = "CAN_INIT"
    CAN_CONFIG = "CAN_CONFIG"
    ECU_COMM = "ECU_COMM"
    READ_VIN = "READ_VIN"
    READ_HARDWARE = "READ_HARDWARE"
    READ_SOFTWARE = "READ_SOFTWARE"
    SECURITY_ACCESS = "SECURITY_ACCESS"
    ERASE_MEMORY = "ERASE_MEMORY"
    FILE_UPLOAD = "FILE_UPLOAD"
    REQUEST_DOWNLOAD = "REQUEST_DOWNLOAD"
    TRANSFER_DATA = "TRANSFER_DATA"
    TRANSFER_EXIT = "TRANSFER_EXIT"
    ECU_RESET = "ECU_RESET"
    # -- optional steps, draggable in from the palette ---------------------
    ENTER_EXTENDED = "ENTER_EXTENDED"
    ENTER_PROGRAMMING = "ENTER_PROGRAMMING"
    ENTER_DEFAULT = "ENTER_DEFAULT"
    TESTER_PRESENT = "TESTER_PRESENT"
    DISABLE_DTC = "DISABLE_DTC"
    ENABLE_DTC = "ENABLE_DTC"
    DISABLE_COMMUNICATION = "DISABLE_COMMUNICATION"
    ENABLE_COMMUNICATION = "ENABLE_COMMUNICATION"
    CLEAR_DTC = "CLEAR_DTC"
    READ_DTC = "READ_DTC"
    CHECK_PROGRAMMING_DEPENDENCIES = "CHECK_PROGRAMMING_DEPENDENCIES"
    CHECK_MEMORY = "CHECK_MEMORY"
    VERIFY_CHECKSUM = "VERIFY_CHECKSUM"
    READ_BATTERY_VOLTAGE = "READ_BATTERY_VOLTAGE"
    READ_DID = "READ_DID"
    WRITE_DID = "WRITE_DID"
    ROUTINE_CONTROL = "ROUTINE_CONTROL"
    RAW_REQUEST = "RAW_REQUEST"
    DELAY = "DELAY"

    @property
    def label(self) -> str:
        """Return the name shown in the sequence editor.

        Example:
            >>> FlashStepKind.READ_VIN.label
            'Read VIN'
            >>> FlashStepKind.TRANSFER_DATA.label
            'Transfer data'
        """
        return {
            FlashStepKind.CAN_INIT: "CAN initialisation",
            FlashStepKind.CAN_CONFIG: "CAN configuration",
            FlashStepKind.ECU_COMM: "ECU communication",
            FlashStepKind.READ_VIN: "Read VIN",
            FlashStepKind.READ_HARDWARE: "Read ECU hardware information",
            FlashStepKind.READ_SOFTWARE: "Read ECU software version",
            FlashStepKind.SECURITY_ACCESS: "Security access",
            FlashStepKind.ERASE_MEMORY: "Erase memory",
            FlashStepKind.FILE_UPLOAD: "File upload",
            FlashStepKind.REQUEST_DOWNLOAD: "Request download",
            FlashStepKind.TRANSFER_DATA: "Transfer data",
            FlashStepKind.TRANSFER_EXIT: "Request transfer exit",
            FlashStepKind.ECU_RESET: "ECU reset",
            FlashStepKind.ENTER_EXTENDED: "Enter extended session",
            FlashStepKind.ENTER_PROGRAMMING: "Enter programming session",
            FlashStepKind.ENTER_DEFAULT: "Return to default session",
            FlashStepKind.TESTER_PRESENT: "Tester present",
            FlashStepKind.DISABLE_DTC: "Disable DTC setting",
            FlashStepKind.ENABLE_DTC: "Enable DTC setting",
            FlashStepKind.DISABLE_COMMUNICATION: "Disable normal communication",
            FlashStepKind.ENABLE_COMMUNICATION: "Enable normal communication",
            FlashStepKind.CLEAR_DTC: "Clear fault memory",
            FlashStepKind.READ_DTC: "Read fault memory",
            FlashStepKind.CHECK_PROGRAMMING_DEPENDENCIES: "Check programming dependencies",
            FlashStepKind.CHECK_MEMORY: "Check memory",
            FlashStepKind.VERIFY_CHECKSUM: "Verify checksum",
            FlashStepKind.READ_BATTERY_VOLTAGE: "Read battery voltage",
            FlashStepKind.READ_DID: "Read data identifier",
            FlashStepKind.WRITE_DID: "Write data identifier",
            FlashStepKind.ROUTINE_CONTROL: "Routine control",
            FlashStepKind.RAW_REQUEST: "Raw request",
            FlashStepKind.DELAY: "Delay",
        }[self]

    @property
    def detail(self) -> str:
        """Return the one line explanation shown under the step name."""
        return {
            FlashStepKind.CAN_INIT: "Open the VCI channel and start the driver.",
            FlashStepKind.CAN_CONFIG: "Apply the bitrate, identifiers and ISO-TP timing.",
            FlashStepKind.ECU_COMM: "Confirm the ECU answers a tester present.",
            FlashStepKind.READ_VIN: "Read DID 0xF190.",
            FlashStepKind.READ_HARDWARE: "Read DID 0xF191 and 0xF192.",
            FlashStepKind.READ_SOFTWARE: "Read DID 0xF194 and 0xF195.",
            FlashStepKind.SECURITY_ACCESS: "Request the seed and send the computed key.",
            FlashStepKind.ERASE_MEMORY: "Run the erase routine (0x31 / 0xFF00).",
            FlashStepKind.FILE_UPLOAD: "Parse the flash file into memory segments.",
            FlashStepKind.REQUEST_DOWNLOAD: "Negotiate the block size (0x34).",
            FlashStepKind.TRANSFER_DATA: "Send the blocks (0x36) with flow control.",
            FlashStepKind.TRANSFER_EXIT: "Close the transfer (0x37) and verify.",
            FlashStepKind.ECU_RESET: "Reset the ECU (0x11) into the new software.",
            FlashStepKind.ENTER_EXTENDED: "Switch to session 0x03.",
            FlashStepKind.ENTER_PROGRAMMING: "Switch to session 0x02 (bootloader).",
            FlashStepKind.ENTER_DEFAULT: "Switch back to session 0x01.",
            FlashStepKind.TESTER_PRESENT: "Send 0x3E to keep the session alive.",
            FlashStepKind.DISABLE_DTC: "Stop DTC storage during the flash (0x85 0x02).",
            FlashStepKind.ENABLE_DTC: "Resume DTC storage (0x85 0x01).",
            FlashStepKind.DISABLE_COMMUNICATION: "Silence the bus (0x28 0x03).",
            FlashStepKind.ENABLE_COMMUNICATION: "Restore normal traffic (0x28 0x00).",
            FlashStepKind.CLEAR_DTC: "Clear the fault memory (0x14).",
            FlashStepKind.READ_DTC: "Read the fault memory (0x19 0x02).",
            FlashStepKind.CHECK_PROGRAMMING_DEPENDENCIES: "Run routine 0xFF01.",
            FlashStepKind.CHECK_MEMORY: "Run the memory check routine 0x0202.",
            FlashStepKind.VERIFY_CHECKSUM: "Compare the ECU checksum with the file CRC.",
            FlashStepKind.READ_BATTERY_VOLTAGE: "Read the supply voltage before flashing.",
            FlashStepKind.READ_DID: "Read any data identifier.",
            FlashStepKind.WRITE_DID: "Write any data identifier.",
            FlashStepKind.ROUTINE_CONTROL: "Start, stop or poll any routine (0x31).",
            FlashStepKind.RAW_REQUEST: "Send arbitrary request bytes.",
            FlashStepKind.DELAY: "Wait a fixed time before the next step.",
        }[self]

    @property
    def requires_file(self) -> bool:
        """Return ``True`` when the step cannot run without a flash file.

        Example:
            >>> FlashStepKind.TRANSFER_DATA.requires_file
            True
            >>> FlashStepKind.READ_VIN.requires_file
            False
        """
        return self in (
            FlashStepKind.FILE_UPLOAD,
            FlashStepKind.REQUEST_DOWNLOAD,
            FlashStepKind.TRANSFER_DATA,
            FlashStepKind.TRANSFER_EXIT,
            FlashStepKind.VERIFY_CHECKSUM,
        )

    @property
    def category(self) -> str:
        """Return the palette group the step belongs to.

        The sequence editor lists the draggable steps under these headings.

        Example:
            >>> FlashStepKind.CAN_INIT.category
            'Connection'
            >>> FlashStepKind.TRANSFER_DATA.category
            'Transfer'
            >>> FlashStepKind.DELAY.category
            'Custom'
        """
        return _CATEGORIES.get(self, "Custom")

    @property
    def repeatable(self) -> bool:
        """Return ``True`` when the step may appear more than once.

        Reading a DID or waiting is naturally repeatable; opening the CAN
        channel twice is a mistake worth flagging.

        Example:
            >>> FlashStepKind.READ_DID.repeatable
            True
            >>> FlashStepKind.CAN_INIT.repeatable
            False
        """
        return self in _REPEATABLE


#: Palette group of every step, in the order the editor shows the groups.
_CATEGORIES: dict[FlashStepKind, str] = {
    FlashStepKind.CAN_INIT: "Connection",
    FlashStepKind.CAN_CONFIG: "Connection",
    FlashStepKind.ECU_COMM: "Connection",
    FlashStepKind.READ_BATTERY_VOLTAGE: "Connection",
    FlashStepKind.ENTER_EXTENDED: "Session",
    FlashStepKind.ENTER_PROGRAMMING: "Session",
    FlashStepKind.ENTER_DEFAULT: "Session",
    FlashStepKind.TESTER_PRESENT: "Session",
    FlashStepKind.SECURITY_ACCESS: "Session",
    FlashStepKind.READ_VIN: "Identification",
    FlashStepKind.READ_HARDWARE: "Identification",
    FlashStepKind.READ_SOFTWARE: "Identification",
    FlashStepKind.READ_DID: "Identification",
    FlashStepKind.WRITE_DID: "Identification",
    FlashStepKind.DISABLE_DTC: "Preconditions",
    FlashStepKind.ENABLE_DTC: "Preconditions",
    FlashStepKind.DISABLE_COMMUNICATION: "Preconditions",
    FlashStepKind.ENABLE_COMMUNICATION: "Preconditions",
    FlashStepKind.CLEAR_DTC: "Preconditions",
    FlashStepKind.READ_DTC: "Preconditions",
    FlashStepKind.CHECK_PROGRAMMING_DEPENDENCIES: "Preconditions",
    FlashStepKind.ERASE_MEMORY: "Transfer",
    FlashStepKind.FILE_UPLOAD: "Transfer",
    FlashStepKind.REQUEST_DOWNLOAD: "Transfer",
    FlashStepKind.TRANSFER_DATA: "Transfer",
    FlashStepKind.TRANSFER_EXIT: "Transfer",
    FlashStepKind.CHECK_MEMORY: "Verification",
    FlashStepKind.VERIFY_CHECKSUM: "Verification",
    FlashStepKind.ECU_RESET: "Finalisation",
    FlashStepKind.ROUTINE_CONTROL: "Custom",
    FlashStepKind.RAW_REQUEST: "Custom",
    FlashStepKind.DELAY: "Custom",
}

#: Order the palette groups are listed in.
CATEGORY_ORDER: tuple[str, ...] = (
    "Connection",
    "Session",
    "Identification",
    "Preconditions",
    "Transfer",
    "Verification",
    "Finalisation",
    "Custom",
)

#: Steps that may legitimately appear several times in one sequence.
_REPEATABLE: frozenset[FlashStepKind] = frozenset(
    {
        FlashStepKind.TESTER_PRESENT,
        FlashStepKind.READ_DID,
        FlashStepKind.WRITE_DID,
        FlashStepKind.READ_DTC,
        FlashStepKind.ROUTINE_CONTROL,
        FlashStepKind.RAW_REQUEST,
        FlashStepKind.DELAY,
        FlashStepKind.ENTER_EXTENDED,
        FlashStepKind.ENTER_PROGRAMMING,
        FlashStepKind.ENTER_DEFAULT,
        FlashStepKind.SECURITY_ACCESS,
        FlashStepKind.FILE_UPLOAD,
        FlashStepKind.REQUEST_DOWNLOAD,
        FlashStepKind.TRANSFER_DATA,
        FlashStepKind.TRANSFER_EXIT,
        FlashStepKind.ERASE_MEMORY,
    }
)


def palette_steps() -> dict[str, list[FlashStepKind]]:
    """Return every draggable step grouped by category.

    The sequence editor renders this as the palette the operator drags from,
    so a sequence is never limited to the 13 default steps.

    Example:
        >>> groups = palette_steps()
        >>> groups["Connection"][0] is FlashStepKind.CAN_INIT
        True
        >>> sum(len(v) for v in groups.values()) == len(list(FlashStepKind))
        True
    """
    grouped: dict[str, list[FlashStepKind]] = {name: [] for name in CATEGORY_ORDER}
    for kind in FlashStepKind:
        grouped.setdefault(kind.category, []).append(kind)
    return {name: kinds for name, kinds in grouped.items() if kinds}


#: The specification order, used by :meth:`FlashSequence.default`.
DEFAULT_ORDER: tuple[FlashStepKind, ...] = (
    FlashStepKind.CAN_INIT,
    FlashStepKind.CAN_CONFIG,
    FlashStepKind.ECU_COMM,
    FlashStepKind.READ_VIN,
    FlashStepKind.READ_HARDWARE,
    FlashStepKind.READ_SOFTWARE,
    FlashStepKind.SECURITY_ACCESS,
    FlashStepKind.ERASE_MEMORY,
    FlashStepKind.FILE_UPLOAD,
    FlashStepKind.REQUEST_DOWNLOAD,
    FlashStepKind.TRANSFER_DATA,
    FlashStepKind.TRANSFER_EXIT,
    FlashStepKind.ECU_RESET,
)

#: Steps that must precede another step, as ``{step: (must run before it, ...)}``.
_ORDER_RULES: dict[FlashStepKind, tuple[FlashStepKind, ...]] = {
    FlashStepKind.CAN_CONFIG: (FlashStepKind.CAN_INIT,),
    FlashStepKind.ECU_COMM: (FlashStepKind.CAN_INIT,),
    FlashStepKind.REQUEST_DOWNLOAD: (FlashStepKind.FILE_UPLOAD,),
    FlashStepKind.TRANSFER_DATA: (FlashStepKind.REQUEST_DOWNLOAD,),
    FlashStepKind.TRANSFER_EXIT: (FlashStepKind.TRANSFER_DATA,),
}


class StepStatus(str, Enum):
    """Live state of one step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

    @property
    def is_finished(self) -> bool:
        """Return ``True`` once the step will not change again.

        Example:
            >>> StepStatus.PASSED.is_finished, StepStatus.RUNNING.is_finished
            (True, False)
        """
        return self in (StepStatus.PASSED, StepStatus.FAILED, StepStatus.SKIPPED)


@dataclass(slots=True)
class FlashStep:
    """One entry of the sequence.

    Attributes:
        kind: Which action the step performs.
        enabled: Disabled steps are skipped by the runner.
        status: Live execution state.
        message: Result detail shown in the UI.
        duration_ms: How long the step took.
        options: Step specific overrides, e.g. ``{"level": 0x11}``.
    """

    kind: FlashStepKind
    enabled: bool = True
    status: StepStatus = StepStatus.PENDING
    message: str = ""
    duration_ms: float = 0.0
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        """Return the display name of the step."""
        return self.kind.label

    def reset(self) -> None:
        """Return the step to its pending state."""
        self.status = StepStatus.PENDING
        self.message = ""
        self.duration_ms = 0.0

    def as_dict(self) -> dict[str, Any]:
        """Return the YAML serialisable representation of the step."""
        return {
            "step": self.kind.value,
            "enabled": self.enabled,
            "options": dict(self.options),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlashStep":
        """Build a step from its serialised representation.

        Example:
            >>> FlashStep.from_dict({"step": "READ_VIN"}).kind is FlashStepKind.READ_VIN
            True
        """
        return cls(
            kind=FlashStepKind(str(data.get("step", "ECU_COMM"))),
            enabled=bool(data.get("enabled", True)),
            options=dict(data.get("options", {})),
        )


@dataclass(slots=True)
class StepOutcome:
    """Result of executing one step."""

    step: FlashStep
    status: StepStatus
    message: str = ""
    duration_ms: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return ``True`` when the step did not fail."""
        return self.status is not StepStatus.FAILED


@dataclass(slots=True)
class FlashSequence:
    """An ordered, reorderable list of :class:`FlashStep`.

    Attributes:
        name: Display name of the sequence.
        steps: The steps in execution order.
        flash_file: Firmware file the transfer steps use.
        security_file: Optional seed-key script or library.
        security_level: Security level requested by the security step.
        security_algorithm: Built-in algorithm used when no file is given.
        base_address: Download address; taken from the file when ``None``.
        block_size: Requested transfer block size, ``0`` to let the ECU decide.
    """

    name: str = "Flash sequence"
    steps: list[FlashStep] = field(default_factory=list)
    flash_file: Path | None = None
    security_file: Path | None = None
    security_level: int = 0x11
    security_algorithm: str = "add_constant"
    base_address: int | None = None
    block_size: int = 0

    # -- construction --------------------------------------------------------
    @classmethod
    def default(cls, **kwargs: Any) -> "FlashSequence":
        """Return the 13 step sequence from the specification.

        Example:
            >>> [s.kind.value for s in FlashSequence.default().steps][:3]
            ['CAN_INIT', 'CAN_CONFIG', 'ECU_COMM']
        """
        return cls(steps=[FlashStep(kind=kind) for kind in DEFAULT_ORDER], **kwargs)

    # -- editing -------------------------------------------------------------
    def move(self, from_index: int, to_index: int) -> bool:
        """Move the step at *from_index* to *to_index*.

        Returns:
            ``True`` when the move was applied.

        Example:
            >>> s = FlashSequence.default()
            >>> s.move(0, 1) and s.steps[1].kind is FlashStepKind.CAN_INIT
            True
            >>> s.move(0, 99)
            False
        """
        if not (0 <= from_index < len(self.steps) and 0 <= to_index < len(self.steps)):
            return False
        self.steps.insert(to_index, self.steps.pop(from_index))
        return True

    def add(self, kind: FlashStepKind, index: int | None = None) -> FlashStep:
        """Insert a step of *kind*, at *index* when given."""
        step = FlashStep(kind=kind)
        if index is None:
            self.steps.append(step)
        else:
            self.steps.insert(max(0, min(index, len(self.steps))), step)
        return step

    def remove(self, index: int) -> bool:
        """Remove the step at *index*."""
        if not 0 <= index < len(self.steps):
            return False
        del self.steps[index]
        return True

    def reset(self) -> None:
        """Return every step to its pending state."""
        for step in self.steps:
            step.reset()

    @property
    def enabled_steps(self) -> list[FlashStep]:
        """Return the steps the runner will execute."""
        return [step for step in self.steps if step.enabled]

    # -- validation ----------------------------------------------------------
    def validate(self) -> list[str]:
        """Return the problems that would make the run fail.

        Two classes of problem are reported: a missing file that an enabled
        step needs, and an ordering that violates the UDS state machine (for
        example transferring data before ``RequestDownload``).

        Example:
            >>> "no flash file selected" in FlashSequence.default().validate()[0]
            True
            >>> bare = FlashSequence(steps=[FlashStep(kind=FlashStepKind.READ_VIN)])
            >>> bare.validate()
            []
        """
        problems: list[str] = []
        enabled = self.enabled_steps
        kinds = [step.kind for step in enabled]

        if any(kind.requires_file for kind in kinds) and self.flash_file is None:
            problems.append(
                "no flash file selected, which the transfer steps require"
            )
        elif self.flash_file is not None and not Path(self.flash_file).is_file():
            problems.append(f"the flash file {self.flash_file} does not exist")
        if self.security_file is not None and not Path(self.security_file).is_file():
            problems.append(f"the security file {self.security_file} does not exist")

        for kind in set(kinds):
            count = kinds.count(kind)
            if count > 1 and not kind.repeatable:
                problems.append(
                    f"{kind.label!r} appears {count} times but may only run once"
                )

        # First occurrence: a repeatable step such as TESTER_PRESENT may recur,
        # and the ordering rule only cares about the first time each one runs.
        position: dict[FlashStepKind, int] = {}
        for index, kind in enumerate(kinds):
            position.setdefault(kind, index)
        for kind, predecessors in _ORDER_RULES.items():
            if kind not in position:
                continue
            for predecessor in predecessors:
                if predecessor not in position:
                    continue
                if position[predecessor] > position[kind]:
                    problems.append(
                        f"step {position[predecessor] + 1} {predecessor.label!r} must run "
                        f"before step {position[kind] + 1} {kind.label!r}"
                    )
        return problems

    @property
    def is_valid(self) -> bool:
        """Return ``True`` when the sequence can be executed."""
        return not self.validate()

    # -- persistence ---------------------------------------------------------
    def as_dict(self) -> dict[str, Any]:
        """Return the YAML serialisable representation of the sequence."""
        return {
            "name": self.name,
            "flash_file": str(self.flash_file) if self.flash_file else "",
            "security_file": str(self.security_file) if self.security_file else "",
            "security_level": self.security_level,
            "security_algorithm": self.security_algorithm,
            "base_address": self.base_address,
            "block_size": self.block_size,
            "flash_sequence": [step.as_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlashSequence":
        """Build a sequence from its serialised representation.

        Example:
            >>> raw = FlashSequence.default(security_level=0x09).as_dict()
            >>> FlashSequence.from_dict(raw).security_level
            9
        """
        return cls(
            name=str(data.get("name", "Flash sequence")),
            steps=[FlashStep.from_dict(entry) for entry in data.get("flash_sequence", [])],
            flash_file=Path(data["flash_file"]) if data.get("flash_file") else None,
            security_file=Path(data["security_file"]) if data.get("security_file") else None,
            security_level=int(data.get("security_level", 0x11)),
            security_algorithm=str(data.get("security_algorithm", "add_constant")),
            base_address=data.get("base_address"),
            block_size=int(data.get("block_size", 0)),
        )

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.steps)

    def __iter__(self):  # noqa: D105 - trivial
        return iter(self.steps)
