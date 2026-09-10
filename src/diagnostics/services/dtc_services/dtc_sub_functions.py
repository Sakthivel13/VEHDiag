"""Catalogue of the ReadDTCInformation (0x19) sub-functions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class DTCSubFunction(IntEnum):
    """Every standardised sub-function of SID 0x19."""

    REPORT_NUMBER_OF_DTC_BY_STATUS_MASK = 0x01
    REPORT_DTC_BY_STATUS_MASK = 0x02
    REPORT_DTC_SNAPSHOT_IDENTIFICATION = 0x03
    REPORT_DTC_SNAPSHOT_RECORD_BY_DTC_NUMBER = 0x04
    REPORT_DTC_STORED_DATA_BY_RECORD_NUMBER = 0x05
    REPORT_DTC_EXT_DATA_RECORD_BY_DTC_NUMBER = 0x06
    REPORT_NUMBER_OF_DTC_BY_SEVERITY_MASK_RECORD = 0x07
    REPORT_DTC_BY_SEVERITY_MASK_RECORD = 0x08
    REPORT_SEVERITY_INFORMATION_OF_DTC = 0x09
    REPORT_SUPPORTED_DTC = 0x0A
    REPORT_FIRST_TEST_FAILED_DTC = 0x0B
    REPORT_FIRST_CONFIRMED_DTC = 0x0C
    REPORT_MOST_RECENT_TEST_FAILED_DTC = 0x0D
    REPORT_MOST_RECENT_CONFIRMED_DTC = 0x0E
    REPORT_DTC_FAULT_DETECTION_COUNTER = 0x14
    REPORT_DTC_WITH_PERMANENT_STATUS = 0x15
    REPORT_USER_DEF_MEMORY_DTC_BY_STATUS_MASK = 0x17
    REPORT_USER_DEF_MEMORY_DTC_EXT_DATA_RECORD_BY_DTC_NUMBER = 0x19

    @property
    def pretty_name(self) -> str:
        """Return the ISO style lowerCamelCase name."""
        words = self.name.split("_")
        return words[0].lower() + "".join(w.capitalize() for w in words[1:])


@dataclass(slots=True)
class SubFunctionSpec:
    """Describes the parameters and the response shape of a sub-function.

    Attributes:
        value: The sub-function byte.
        label: Text shown in the sub-function drop-down.
        needs_status_mask: A status mask byte must follow the sub-function.
        needs_dtc: A three byte DTC must follow the sub-function.
        needs_record_number: A record number byte must follow.
        needs_severity_mask: A severity mask byte must follow.
        needs_memory_selection: A memory selection byte precedes the parameters.
        returns_count: The response carries a DTC count instead of a list.
        returns_list: The response carries a list of DTC + status entries.
    """

    value: int
    label: str
    needs_status_mask: bool = False
    needs_dtc: bool = False
    needs_record_number: bool = False
    needs_severity_mask: bool = False
    needs_memory_selection: bool = False
    returns_count: bool = False
    returns_list: bool = False

    @property
    def hex_value(self) -> str:
        """Return the sub-function as ``"0x02"``."""
        return f"0x{self.value:02X}"


#: Specification table used by the UI and the parser.
SUB_FUNCTION_SPECS: dict[int, SubFunctionSpec] = {
    0x01: SubFunctionSpec(0x01, "Report number of DTC by status mask", needs_status_mask=True, returns_count=True),
    0x02: SubFunctionSpec(0x02, "Report DTC by status mask", needs_status_mask=True, returns_list=True),
    0x03: SubFunctionSpec(0x03, "Report DTC snapshot identification", returns_list=True),
    0x04: SubFunctionSpec(0x04, "Report DTC snapshot record by DTC number", needs_dtc=True, needs_record_number=True),
    0x05: SubFunctionSpec(0x05, "Report DTC stored data by record number", needs_record_number=True),
    0x06: SubFunctionSpec(0x06, "Report DTC extended data record by DTC number", needs_dtc=True, needs_record_number=True),
    0x07: SubFunctionSpec(0x07, "Report number of DTC by severity mask", needs_severity_mask=True, needs_status_mask=True, returns_count=True),
    0x08: SubFunctionSpec(0x08, "Report DTC by severity mask record", needs_severity_mask=True, needs_status_mask=True, returns_list=True),
    0x09: SubFunctionSpec(0x09, "Report severity information of DTC", needs_dtc=True),
    0x0A: SubFunctionSpec(0x0A, "Report supported DTC", returns_list=True),
    0x0B: SubFunctionSpec(0x0B, "Report first test failed DTC", returns_list=True),
    0x0C: SubFunctionSpec(0x0C, "Report first confirmed DTC", returns_list=True),
    0x0D: SubFunctionSpec(0x0D, "Report most recent test failed DTC", returns_list=True),
    0x0E: SubFunctionSpec(0x0E, "Report most recent confirmed DTC", returns_list=True),
    0x14: SubFunctionSpec(0x14, "Report DTC fault detection counter", returns_list=True),
    0x15: SubFunctionSpec(0x15, "Report DTC with permanent status", returns_list=True),
    0x17: SubFunctionSpec(0x17, "Report user defined memory DTC by status mask", needs_status_mask=True, needs_memory_selection=True, returns_list=True),
    0x19: SubFunctionSpec(0x19, "Report user defined memory DTC extended data", needs_dtc=True, needs_record_number=True, needs_memory_selection=True),
}


def describe_sub_function(value: int) -> SubFunctionSpec:
    """Return the specification of *value*, or a generic placeholder."""
    return SUB_FUNCTION_SPECS.get(
        value, SubFunctionSpec(value, f"Manufacturer specific (0x{value:02X})")
    )


def selectable_sub_functions() -> list[SubFunctionSpec]:
    """Return the specs ordered by sub-function value for the UI drop-down."""
    return [SUB_FUNCTION_SPECS[key] for key in sorted(SUB_FUNCTION_SPECS)]


__all__ = [
    "DTCSubFunction",
    "SubFunctionSpec",
    "SUB_FUNCTION_SPECS",
    "describe_sub_function",
    "selectable_sub_functions",
]
