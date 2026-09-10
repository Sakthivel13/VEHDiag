"""Generate runnable test scripts from the developer mode inputs.

The generator turns a declarative :class:`GeneratorSpec` - the values the
operator types into the Code Generator panel - into a complete ``TestScript``
module that follows the template required by the project specification::

    from src.test_execution.scripts.script_api import DiagnosticAPI

    class TestScript:
        def __init__(self, api: DiagnosticAPI): ...
        def setup(self): ...
        def execute(self): ...
        def teardown(self): ...

Everything here is pure Python: no Qt, no ECU. That keeps the generator fully
unit testable and lets the UI preview the result as the operator types.

Example:
    >>> spec = GeneratorSpec(
    ...     name="Read the VIN",
    ...     steps=[GeneratedStep(kind="read_did", did=0xF190)],
    ... )
    >>> code = generate_script(spec)
    >>> "class TestScript" in code
    True
    >>> "read_did(0xF190)" in code
    True
    >>> import ast; ast.parse(code) is not None
    True
"""
from __future__ import annotations

import keyword
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from ..core.enums.session_enums import SessionType
from ..core.enums.sid_enums import SID_DESCRIPTIONS, ServiceID

__all__ = [
    "GeneratedStep",
    "GeneratorSpec",
    "STEP_KINDS",
    "generate_script",
    "generate_yaml_sequence",
    "slugify",
    "validate_spec",
]

#: The step kinds the generator understands, as ``(kind, label)`` pairs.
STEP_KINDS: tuple[tuple[str, str], ...] = (
    ("session", "Change the diagnostic session"),
    ("security", "Unlock a security level"),
    ("read_did", "Read a data identifier"),
    ("write_did", "Write a data identifier"),
    ("read_dtc", "Read the fault memory"),
    ("clear_dtc", "Clear the fault memory"),
    ("routine", "Start a routine"),
    ("io_control", "Input/output control"),
    ("ecu_reset", "Reset the ECU"),
    ("tester_present", "Send tester present"),
    ("raw", "Send a raw request"),
    ("wait", "Wait"),
    ("assert_nrc", "Expect a negative response"),
)

_IDENTIFIER_RE = re.compile(r"[^0-9a-zA-Z]+")


def slugify(text: str, fallback: str = "generated") -> str:
    """Return *text* as a valid lowercase Python identifier.

    Args:
        text: Free-form text typed by the operator.
        fallback: Value used when *text* has no usable characters.

    Returns:
        A identifier-safe slug.

    Example:
        >>> slugify("Read the VIN!")
        'read_the_vin'
        >>> slugify("2 fast")
        's_2_fast'
        >>> slugify("---")
        'generated'
        >>> slugify("class")
        's_class'
    """
    slug = _IDENTIFIER_RE.sub("_", text).strip("_").lower()
    if not slug:
        return fallback
    if slug[0].isdigit() or keyword.iskeyword(slug):
        slug = f"s_{slug}"
    return slug


@dataclass(slots=True)
class GeneratedStep:
    """One action the generated script performs.

    Attributes:
        kind: A key of :data:`STEP_KINDS`.
        session: Sub-function for a ``session`` step.
        level: Security level for a ``security`` step.
        algorithm: Seed-key algorithm name for a ``security`` step.
        did: Data identifier for ``read_did`` / ``write_did`` / ``io_control``.
        data: Payload bytes for ``write_did``, ``routine``, ``io_control``, ``raw``.
        routine_id: Routine identifier for a ``routine`` step.
        sub_function: Sub-function byte for ``routine`` and ``io_control``.
        reset_type: Reset type for an ``ecu_reset`` step.
        status_mask: Status mask for a ``read_dtc`` step.
        group: DTC group for a ``clear_dtc`` step.
        milliseconds: Delay for a ``wait`` step.
        nrc: Expected NRC for an ``assert_nrc`` step.
        expect: Expected payload for a ``read_did`` assertion, if any.
        comment: Extra comment emitted above the step.
    """

    kind: str = "read_did"
    session: int = int(SessionType.EXTENDED_DIAGNOSTIC)
    level: int = 0x01
    algorithm: str = "xor_complement"
    did: int = 0xF190
    data: bytes = b""
    routine_id: int = 0x0203
    sub_function: int = 0x01
    reset_type: int = 0x01
    status_mask: int = 0xFF
    group: int = 0xFFFFFF
    milliseconds: int = 100
    nrc: int = 0x31
    expect: bytes = b""
    comment: str = ""

    def label(self) -> str:
        """Return the human readable description of the step.

        Example:
            >>> GeneratedStep(kind="read_did", did=0xF190).label()
            'Read DID 0xF190'
            >>> GeneratedStep(kind="wait", milliseconds=250).label()
            'Wait 250 ms'
        """
        return {
            "session": f"Change to session 0x{self.session:02X}",
            "security": f"Unlock security level 0x{self.level:02X}",
            "read_did": f"Read DID 0x{self.did:04X}",
            "write_did": f"Write DID 0x{self.did:04X}",
            "read_dtc": f"Read DTCs (mask 0x{self.status_mask:02X})",
            "clear_dtc": f"Clear DTC group 0x{self.group:06X}",
            "routine": f"Routine 0x{self.routine_id:04X} sub 0x{self.sub_function:02X}",
            "io_control": f"I/O control DID 0x{self.did:04X}",
            "ecu_reset": f"ECU reset type 0x{self.reset_type:02X}",
            "tester_present": "Tester present",
            "raw": f"Raw request {self.data.hex().upper() or '(empty)'}",
            "wait": f"Wait {self.milliseconds} ms",
            "assert_nrc": f"Expect NRC 0x{self.nrc:02X}",
        }.get(self.kind, self.kind)

    def service_id(self) -> int:
        """Return the UDS service the step exercises, or ``0`` for local steps.

        Example:
            >>> hex(GeneratedStep(kind="read_did").service_id())
            '0x22'
            >>> GeneratedStep(kind="wait").service_id()
            0
        """
        return {
            "session": int(ServiceID.DIAGNOSTIC_SESSION_CONTROL),
            "security": int(ServiceID.SECURITY_ACCESS),
            "read_did": int(ServiceID.READ_DATA_BY_IDENTIFIER),
            "write_did": int(ServiceID.WRITE_DATA_BY_IDENTIFIER),
            "read_dtc": int(ServiceID.READ_DTC_INFORMATION),
            "clear_dtc": int(ServiceID.CLEAR_DIAGNOSTIC_INFORMATION),
            "routine": int(ServiceID.ROUTINE_CONTROL),
            "io_control": int(ServiceID.INPUT_OUTPUT_CONTROL_BY_IDENTIFIER),
            "ecu_reset": int(ServiceID.ECU_RESET),
            "tester_present": int(ServiceID.TESTER_PRESENT),
            "raw": self.data[0] if self.data else 0,
        }.get(self.kind, 0)

    def to_lines(self) -> list[str]:
        """Return the body lines implementing this step, without indentation.

        Example:
            >>> GeneratedStep(kind="wait", milliseconds=50).to_lines()
            ['self.api.wait(50)']
            >>> GeneratedStep(kind="ecu_reset", reset_type=3).to_lines()
            ['self.api.ecu_reset(0x03)']
        """
        lines: list[str] = []
        if self.comment:
            lines.append(f"# {self.comment}")
        kind = self.kind
        if kind == "session":
            lines.append(f"self.api.change_session(0x{self.session:02X})")
        elif kind == "security":
            lines.append(
                f"self.api.security_unlock(0x{self.level:02X}, "
                f"algorithm={self.algorithm!r})"
            )
        elif kind == "read_did":
            lines.append(f"value = self.api.read_did(0x{self.did:04X})")
            lines.append(f'self.api.log(f"DID 0x{self.did:04X} = {{value.hex().upper()}}")')
            if self.expect:
                lines.append(f"self.api.assert_data({self.expect!r})")
        elif kind == "write_did":
            lines.append(f"self.api.write_did(0x{self.did:04X}, {self.data!r})")
        elif kind == "read_dtc":
            lines.append(f"dtcs = self.api.read_dtcs(0x{self.status_mask:02X})")
            lines.append('self.api.log(f"{len(dtcs)} DTC(s) reported")')
        elif kind == "clear_dtc":
            lines.append(f"self.api.clear_dtcs(0x{self.group:06X})")
        elif kind == "routine":
            payload = f", {self.data!r}" if self.data else ""
            lines.append(
                f"self.api.routine(0x{self.routine_id:04X}, "
                f"0x{self.sub_function:02X}{payload})"
            )
        elif kind == "io_control":
            payload = f", {self.data!r}" if self.data else ""
            lines.append(
                f"self.api.send_request(bytes([0x2F, 0x{self.did >> 8:02X}, "
                f"0x{self.did & 0xFF:02X}, 0x{self.sub_function:02X}])"
                f"{' + ' + repr(self.data) if self.data else ''})"
            )
            lines.append("self.api.assert_positive_response()")
        elif kind == "ecu_reset":
            lines.append(f"self.api.ecu_reset(0x{self.reset_type:02X})")
        elif kind == "tester_present":
            lines.append("self.api.tester_present()")
        elif kind == "raw":
            lines.append(f"self.api.send_request({self.data!r})")
            lines.append("self.api.assert_positive_response()")
        elif kind == "wait":
            lines.append(f"self.api.wait({self.milliseconds})")
        elif kind == "assert_nrc":
            lines.append(f"self.api.assert_nrc(0x{self.nrc:02X})")
        else:  # pragma: no cover - guarded by validate_spec
            lines.append(f"# unsupported step kind {kind!r}")
        return lines


@dataclass(slots=True)
class GeneratorSpec:
    """Everything the Code Generator needs to emit a script.

    Attributes:
        name: Human readable name of the test.
        description: One line summary written into the docstring.
        author: Optional author recorded in the header.
        steps: The ordered actions the script performs.
        setup_session: Session entered in :meth:`setup`, ``0`` to skip.
        setup_security: Security level unlocked in :meth:`setup`, ``0`` to skip.
        teardown_default_session: Return to the default session in teardown.
        tester_present: Keep the session alive while the test runs.
        stop_on_failure: Let assertions raise instead of being collected.
        include_logging: Emit ``self.api.log(...)`` progress calls.
        include_docstrings: Emit Google style docstrings on every method.
    """

    name: str = "Generated test"
    description: str = ""
    author: str = ""
    steps: list[GeneratedStep] = field(default_factory=list)
    setup_session: int = int(SessionType.EXTENDED_DIAGNOSTIC)
    setup_security: int = 0
    teardown_default_session: bool = True
    tester_present: bool = False
    stop_on_failure: bool = True
    include_logging: bool = True
    include_docstrings: bool = True

    def class_name(self) -> str:
        """Return the generated class name, always ``TestScript``.

        The runner discovers the class by name, so this is fixed by contract.

        Example:
            >>> GeneratorSpec().class_name()
            'TestScript'
        """
        return "TestScript"

    def module_name(self) -> str:
        """Return the suggested file name for the script.

        Example:
            >>> GeneratorSpec(name="Read the VIN").module_name()
            'test_read_the_vin.py'
        """
        return f"test_{slugify(self.name)}.py"

    def services(self) -> list[int]:
        """Return the distinct service identifiers the script touches.

        Example:
            >>> spec = GeneratorSpec(steps=[GeneratedStep(kind="read_did")])
            >>> [hex(s) for s in spec.services()]
            ['0x22']
        """
        seen: list[int] = []
        for step in self.steps:
            sid = step.service_id()
            if sid and sid not in seen:
                seen.append(sid)
        return seen


def validate_spec(spec: GeneratorSpec) -> tuple[bool, list[str]]:
    """Validate *spec* before generating code.

    Args:
        spec: The specification assembled by the UI.

    Returns:
        ``(is_valid, problems)``; *problems* is empty when the spec is usable.

    Example:
        >>> validate_spec(GeneratorSpec())[1]
        ['add at least one step']
        >>> ok, problems = validate_spec(
        ...     GeneratorSpec(steps=[GeneratedStep(kind="read_did")]))
        >>> ok, problems
        (True, [])
        >>> validate_spec(GeneratorSpec(steps=[GeneratedStep(kind="nope")]))[1]
        ["step 1: unknown kind 'nope'"]
    """
    problems: list[str] = []
    if not spec.name.strip():
        problems.append("the test needs a name")
    if not spec.steps:
        problems.append("add at least one step")
    known = {kind for kind, _ in STEP_KINDS}
    for index, step in enumerate(spec.steps, start=1):
        if step.kind not in known:
            problems.append(f"step {index}: unknown kind {step.kind!r}")
            continue
        if step.kind in ("read_did", "write_did", "io_control") and not 0 <= step.did <= 0xFFFF:
            problems.append(f"step {index}: the DID must be a 16-bit value")
        if step.kind == "write_did" and not step.data:
            problems.append(f"step {index}: writing a DID needs data")
        if step.kind == "raw" and not step.data:
            problems.append(f"step {index}: a raw request needs at least one byte")
        if step.kind == "security" and not step.level & 0x01:
            problems.append(f"step {index}: the security level must be an odd requestSeed value")
    return not problems, problems


def _indent(lines: Iterable[str], level: int = 2) -> list[str]:
    """Return *lines* indented by *level* steps of four spaces."""
    pad = "    " * level
    return [f"{pad}{line}" if line else "" for line in lines]


def generate_script(spec: GeneratorSpec) -> str:
    """Render *spec* as a complete, runnable test script.

    Args:
        spec: The specification assembled by the UI.

    Returns:
        The Python source of the script.

    Example:
        >>> spec = GeneratorSpec(name="Smoke", steps=[GeneratedStep(kind="tester_present")])
        >>> src = generate_script(spec)
        >>> import ast; bool(ast.parse(src))
        True
        >>> "def teardown" in src
        True
    """
    description = spec.description or f"Generated test: {spec.name}."
    header: list[str] = ['"""' + description, ""]
    if spec.steps:
        header.append("Steps:")
        for index, step in enumerate(spec.steps, start=1):
            header.append(f"    {index}. {step.label()}")
        header.append("")
    services = spec.services()
    if services:
        names = ", ".join(
            f"0x{sid:02X} {SID_DESCRIPTIONS.get(sid, '').split(' - ')[0]}".strip()
            for sid in services
        )
        header.append(f"Services exercised: {names}")
        header.append("")
    if spec.author:
        header.append(f"Author: {spec.author}")
        header.append("")
    header.append("Generated by the Vehicle Diagnostics Platform code generator.")
    header.append('"""')

    body: list[str] = [
        "from __future__ import annotations",
        "",
        "from src.test_execution.scripts.script_api import DiagnosticAPI",
        "",
        "",
        f"class {spec.class_name()}:",
    ]
    if spec.include_docstrings:
        body += [f'    """{spec.name}."""', ""]

    # -- __init__ -----------------------------------------------------------
    body.append("    def __init__(self, api: DiagnosticAPI) -> None:")
    if spec.include_docstrings:
        body.append('        """Store the diagnostic API handed in by the runner."""')
    body.append("        self.api = api")
    body.append("")

    # -- setup ---------------------------------------------------------------
    body.append("    def setup(self) -> None:")
    if spec.include_docstrings:
        body.append('        """Bring the ECU into the state the test expects."""')
    setup: list[str] = []
    if spec.include_logging:
        setup.append(f"self.api.log({('Setting up: ' + spec.name)!r})")
    if spec.setup_session:
        setup.append(f"self.api.change_session(0x{spec.setup_session:02X})")
    if spec.setup_security:
        setup.append(f"self.api.security_unlock(0x{spec.setup_security:02X})")
    if spec.tester_present:
        setup.append("self.api.tester_present()")
    body += _indent(setup or ["pass"], 2)
    body.append("")

    # -- execute --------------------------------------------------------------
    body.append("    def execute(self) -> bool:")
    if spec.include_docstrings:
        body += [
            '        """Run the test steps.',
            "",
            "        Returns:",
            "            ``True`` when every step passed.",
            '        """',
        ]
    execute: list[str] = []
    if spec.include_logging:
        execute.append(f"self.api.log({('Running: ' + spec.name)!r})")
    for index, step in enumerate(spec.steps, start=1):
        execute.append("")
        execute.append(f"# Step {index}: {step.label()}")
        if spec.include_logging:
            execute.append(f"self.api.log({f'Step {index}: {step.label()}'!r})")
        execute += step.to_lines()
    execute.append("")
    execute.append("return True")
    body += _indent(execute, 2)
    body.append("")

    # -- teardown -------------------------------------------------------------
    body.append("    def teardown(self) -> None:")
    if spec.include_docstrings:
        body.append('        """Return the ECU to a safe state."""')
    teardown: list[str] = []
    if spec.include_logging:
        teardown.append(f"self.api.log({('Tearing down: ' + spec.name)!r})")
    if spec.teardown_default_session:
        teardown.append(f"self.api.change_session(0x{int(SessionType.DEFAULT):02X})")
    body += _indent(teardown or ["pass"], 2)

    return "\n".join(header + [""] + body) + "\n"


def generate_yaml_sequence(spec: GeneratorSpec) -> str:
    """Render *spec* as a developer mode ``test_sequence`` YAML document.

    The format is the one defined by the project specification, so the result
    can be dropped straight into the sequence editor.

    Example:
        >>> spec = GeneratorSpec(name="S", steps=[GeneratedStep(kind="session")])
        >>> print(generate_yaml_sequence(spec).splitlines()[0])
        test_sequence:
        >>> "service: \\"0x10\\"" in generate_yaml_sequence(spec)
        True
    """
    lines = ["test_sequence:"]
    for index, step in enumerate(spec.steps, start=1):
        sid = step.service_id()
        payload = step.data.hex().upper() if step.kind == "raw" else ""
        payload = " ".join(payload[i : i + 2] for i in range(0, len(payload), 2))
        lines += [
            f'  - service: "0x{sid:02X}"',
            f'    name: "{step.label()}"',
            "    enabled: true",
            f'    test_file: ""',
            f'    payload: "{payload}"',
            f"    order: {index}",
        ]
    return "\n".join(lines) + "\n"
