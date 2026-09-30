"""Read and validate BFSI / healthcare entity input workbooks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import openpyxl

ENTITY_NAME_HEADERS = ("entity name", "account name")
ENTITY_TYPE_HEADER = "entity type"

OUTPUT_HEADERS = [
    "Entity Name",
    "Entity Type",
    "Company Website",
    "Company Linkedin",
    "Company Address",
    "Employee Size",
    "Contacts Available on Website",
    "Source",
    "validation_status",
]

EXCEL_COLUMN_WIDTHS = "ABCDEFGHI"
EXCEL_WIDTHS = (40, 14, 38, 45, 55, 45, 55, 22, 36)


@dataclass
class InputEntity:
    row_index: int
    entity_name: str
    entity_type: str | None


def _normalize_header(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def find_header_row(ws) -> tuple[int, dict[str, int]]:
    """Locate header row and column indexes for entity name / type."""
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row or 1, 50)):
        labels = {_normalize_header(c.value): c.column for c in row if c.value is not None}
        name_col = None
        for key in ENTITY_NAME_HEADERS:
            if key in labels:
                name_col = labels[key]
                break
        if name_col is not None:
            type_col = labels.get(ENTITY_TYPE_HEADER)
            return row[0].row, {"entity_name": name_col, "entity_type": type_col}
    raise ValueError(
        'Could not find an "Entity Name" (or legacy "Account Name") header row in the input sheet'
    )


def read_entities(input_path: str | Path) -> tuple[openpyxl.Workbook, int, dict[str, int], list[InputEntity]]:
    """Load workbook and yield entities from the first sheet."""
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    header_row, cols = find_header_row(ws)
    entities: list[InputEntity] = []
    r = header_row + 1
    while True:
        name_cell = ws.cell(row=r, column=cols["entity_name"])
        if name_cell.value is None or str(name_cell.value).strip() == "":
            break
        entity_type = None
        if cols.get("entity_type"):
            tv = ws.cell(row=r, column=cols["entity_type"]).value
            if tv is not None and str(tv).strip():
                entity_type = str(tv).strip()
        entities.append(
            InputEntity(
                row_index=r,
                entity_name=str(name_cell.value).strip(),
                entity_type=entity_type,
            )
        )
        r += 1
    if not entities:
        raise ValueError("No entity rows found below the header row")
    return wb, header_row, cols, entities


def prepare_output_sheet(ws, header_row: int) -> None:
    for i, h in enumerate(OUTPUT_HEADERS, 1):
        ws.cell(row=header_row, column=i, value=h)
    for col, w in zip(EXCEL_COLUMN_WIDTHS, EXCEL_WIDTHS):
        ws.column_dimensions[col].width = w


def write_entity_row(ws, row_index: int, values: dict) -> None:
    ordered = [
        values.get("entity_name"),
        values.get("entity_type") or "",
        values.get("company_website"),
        values.get("company_linkedin"),
        values.get("company_address"),
        values.get("employee_size"),
        values.get("contacts"),
        values.get("source"),
        values.get("validation_status"),
    ]
    for col, val in enumerate(ordered, start=1):
        ws.cell(row=row_index, column=col, value=val)

