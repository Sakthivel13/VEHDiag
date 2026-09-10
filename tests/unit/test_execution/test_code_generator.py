"""Tests for the developer mode code generator.

The generator must always emit a module that (a) parses, (b) passes the script
validator and (c) exposes the ``TestScript`` contract the runner expects. A
regression here produces scripts that only fail once they are run on a bench,
so every step kind is covered.
"""
from __future__ import annotations

import ast

import pytest

from src.test_execution.code_generator import (
    STEP_KINDS,
    GeneratedStep,
    GeneratorSpec,
    generate_script,
    generate_yaml_sequence,
    slugify,
    validate_spec,
)
from src.test_execution.scripts.script_validator import ScriptValidator


class TestSlugify:
    """Identifier generation for file and module names."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Read the VIN", "read_the_vin"),
            ("Read  the   VIN!!", "read_the_vin"),
            ("2 fast", "s_2_fast"),
            ("class", "s_class"),
            ("", "generated"),
            ("---", "generated"),
        ],
    )
    def test_slugify(self, text: str, expected: str) -> None:
        """Every slug must be a valid, non-keyword identifier."""
        slug = slugify(text)
        assert slug == expected
        assert slug.isidentifier()


class TestValidation:
    """The spec is checked before any code is emitted."""

    def test_empty_spec_is_rejected(self) -> None:
        """A spec without steps produces nothing useful."""
        valid, problems = validate_spec(GeneratorSpec())
        assert not valid
        assert "add at least one step" in problems

    def test_unknown_kind_is_reported(self) -> None:
        """A typo in the step kind names the offending step."""
        valid, problems = validate_spec(
            GeneratorSpec(steps=[GeneratedStep(kind="teleport")])
        )
        assert not valid
        assert "step 1" in problems[0]

    def test_write_did_needs_data(self) -> None:
        """Writing a DID without a payload is a mistake worth catching."""
        valid, problems = validate_spec(
            GeneratorSpec(steps=[GeneratedStep(kind="write_did", did=0xF190)])
        )
        assert not valid
        assert any("needs data" in p for p in problems)

    def test_even_security_level_is_rejected(self) -> None:
        """A sendKey sub-function cannot start a seed request."""
        valid, problems = validate_spec(
            GeneratorSpec(steps=[GeneratedStep(kind="security", level=0x02)])
        )
        assert not valid
        assert any("requestSeed" in p for p in problems)

    def test_valid_spec_passes(self) -> None:
        """A well formed spec reports no problems."""
        assert validate_spec(
            GeneratorSpec(steps=[GeneratedStep(kind="read_did", did=0xF190)])
        ) == (True, [])


class TestGeneratedCode:
    """The emitted module must be real, runnable Python."""

    @pytest.mark.parametrize("kind", [kind for kind, _ in STEP_KINDS])
    def test_every_step_kind_emits_parsable_code(self, kind: str) -> None:
        """Each supported action produces a syntactically valid script."""
        step = GeneratedStep(kind=kind, data=b"\x01\x02", did=0xF190)
        source = generate_script(GeneratorSpec(name=f"Test {kind}", steps=[step]))
        assert ast.parse(source) is not None

    @pytest.mark.parametrize("kind", [kind for kind, _ in STEP_KINDS])
    def test_every_step_kind_passes_the_validator(self, kind: str) -> None:
        """The script validator accepts the generated module."""
        step = GeneratedStep(kind=kind, data=b"\x01\x02", did=0xF190)
        source = generate_script(GeneratorSpec(name=f"Test {kind}", steps=[step]))
        report = ScriptValidator(strict=False).validate_source(source)
        assert report.valid, report.summary()

    def test_contract_methods_are_present(self) -> None:
        """The runner looks for exactly this shape."""
        source = generate_script(
            GeneratorSpec(name="Shape", steps=[GeneratedStep(kind="tester_present")])
        )
        tree = ast.parse(source)
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        assert [c.name for c in classes] == ["TestScript"]
        methods = {n.name for n in classes[0].body if isinstance(n, ast.FunctionDef)}
        assert {"__init__", "setup", "execute", "teardown"} <= methods

    def test_steps_appear_in_order(self) -> None:
        """The emitted calls follow the order of the spec."""
        spec = GeneratorSpec(
            name="Ordered",
            steps=[
                GeneratedStep(kind="read_did", did=0xF190),
                GeneratedStep(kind="read_did", did=0xF18C),
            ],
        )
        source = generate_script(spec)
        assert source.index("0xF190") < source.index("0xF18C")

    def test_setup_and_teardown_honour_the_flags(self) -> None:
        """Optional setup and teardown actions can be switched off."""
        spec = GeneratorSpec(
            name="Bare",
            steps=[GeneratedStep(kind="tester_present")],
            setup_session=0,
            setup_security=0,
            teardown_default_session=False,
            include_logging=False,
        )
        source = generate_script(spec)
        assert "change_session" not in source
        assert "security_unlock" not in source
        assert "self.api.log" not in source
        assert ast.parse(source) is not None

    def test_docstrings_can_be_disabled(self) -> None:
        """Terse output is still valid Python."""
        spec = GeneratorSpec(
            name="Terse",
            steps=[GeneratedStep(kind="tester_present")],
            include_docstrings=False,
        )
        source = generate_script(spec)
        assert ast.parse(source) is not None

    def test_header_documents_the_steps(self) -> None:
        """The module docstring lists what the script does."""
        spec = GeneratorSpec(
            name="Documented",
            description="Check the fault memory.",
            author="QA",
            steps=[GeneratedStep(kind="read_dtc")],
        )
        source = generate_script(spec)
        assert "Check the fault memory." in source
        assert "Author: QA" in source
        assert "1. Read DTCs" in source

    def test_payload_bytes_survive_round_trip(self) -> None:
        """A raw request keeps its exact payload."""
        spec = GeneratorSpec(
            name="Raw", steps=[GeneratedStep(kind="raw", data=bytes.fromhex("22F190"))]
        )
        source = generate_script(spec)
        assert ast.parse(source) is not None
        assert r"\x22\xf1\x90" in source or "b'\"\\xf1\\x90'" in source


class TestSpecHelpers:
    """Derived metadata used by the UI."""

    def test_module_name(self) -> None:
        """The suggested file name follows the test name."""
        assert GeneratorSpec(name="Read the VIN").module_name() == "test_read_the_vin.py"

    def test_services_are_deduplicated(self) -> None:
        """Two reads of different DIDs still report one service."""
        spec = GeneratorSpec(
            steps=[
                GeneratedStep(kind="read_did", did=0xF190),
                GeneratedStep(kind="read_did", did=0xF18C),
                GeneratedStep(kind="read_dtc"),
            ]
        )
        assert spec.services() == [0x22, 0x19]

    def test_local_steps_have_no_service(self) -> None:
        """A wait touches no bus service."""
        assert GeneratedStep(kind="wait").service_id() == 0


class TestYamlSequence:
    """The alternative developer mode sequence output."""

    def test_yaml_shape_matches_the_specification(self) -> None:
        """The document uses the documented ``test_sequence`` keys."""
        spec = GeneratorSpec(
            name="Seq",
            steps=[GeneratedStep(kind="session"), GeneratedStep(kind="read_did")],
        )
        text = generate_yaml_sequence(spec)
        assert text.startswith("test_sequence:")
        for key in ("service:", "name:", "enabled:", "test_file:", "payload:", "order:"):
            assert key in text

    def test_yaml_parses(self) -> None:
        """The emitted document is valid YAML with one entry per step."""
        yaml = pytest.importorskip("yaml")
        spec = GeneratorSpec(
            steps=[GeneratedStep(kind="session"), GeneratedStep(kind="read_dtc")]
        )
        data = yaml.safe_load(generate_yaml_sequence(spec))
        assert len(data["test_sequence"]) == 2
        assert data["test_sequence"][0]["order"] == 1


class TestGeneratedScriptRunsAgainstTheSimulator:
    """End to end: generate, load and execute against the built-in ECU."""

    def test_generated_script_executes(self, tmp_path) -> None:
        """The generated module drives a real UDS session."""
        from src.communication.vci_drivers.virtual.virtual_bus import VirtualBus
        from src.test_execution.scripts.script_api import DiagnosticAPI
        from src.test_execution.test_script_loader import TestScriptLoader
        from tests.simulation.mock_ecu import make_simulator
        from tests.simulation.test_with_simulator import build_client, close

        spec = GeneratorSpec(
            name="Generated smoke",
            setup_session=0x03,
            steps=[
                GeneratedStep(kind="read_did", did=0xF190),
                GeneratedStep(kind="read_dtc"),
                GeneratedStep(kind="tester_present"),
            ],
        )
        path = tmp_path / spec.module_name()
        path.write_text(generate_script(spec), encoding="utf-8")

        loaded = TestScriptLoader().load(path)
        bus = VirtualBus("codegen-test")
        client, driver, transport = build_client(make_simulator(bus), bus, 2000.0)
        try:
            script = loaded.instantiate(DiagnosticAPI(client))
            script.setup()
            assert script.execute() is True
            script.teardown()
            assert client.statistics.timeouts == 0
            assert client.statistics.positive >= 3
        finally:
            close(driver, transport)
