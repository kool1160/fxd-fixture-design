"""Validate the non-runtime fixture-library research package.

This checker intentionally uses only the Python standard library.  It supports
the bounded JSON Schema Draft 2020-12 keywords used by the research schemas and
adds corpus invariants that JSON Schema alone does not express across files.
It is not imported by FXD production code and is not a general JSON Schema
implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "docs" / "research" / "schemas"
DATA_DIR = ROOT / "data" / "research" / "fixture_library_reference_v1"

AUTHORITY_LEVELS = {
    "fxd_parametric_component",
    "exact_private_imported_cad",
    "supplier_authorized_exact_cad",
    "metadata_only_commercial_component",
    "provisional_review_envelope",
    "user_authored_reusable_component",
    "fixture_family_template",
    "shop_standard",
    "process_context_asset",
    "private_benchmark_reference",
    "public_engineering_knowledge",
}

SCHEMA_FILES = {
    "item": "fixture_library_item_v1.schema.json",
    "family": "fixture_family_template_v1.schema.json",
    "shop": "shop_standard_pack_v1.schema.json",
    "benchmark": "private_benchmark_case_v1.schema.json",
    "process": "process_context_asset_v1.schema.json",
    "mounting": "mounting_interface_v1.schema.json",
    "functional": "functional_interface_v1.schema.json",
    "source": "fixture_library_source_v1.schema.json",
}


class ResearchValidationError(ValueError):
    """Raised when research data or its bounded schemas fail validation."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchValidationError(f"{path.relative_to(ROOT)}: {exc}") from exc


def type_matches(instance: Any, expected: str) -> bool:
    if expected == "null":
        return instance is None
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "object":
        return isinstance(instance, dict)
    raise ResearchValidationError(f"validator does not support JSON Schema type {expected!r}")


class BoundedSchemaValidator:
    """Validate the exact schema vocabulary used by this research package."""

    def __init__(self) -> None:
        self.schemas = {
            name: load_json(SCHEMA_DIR / filename)
            for name, filename in SCHEMA_FILES.items()
        }
        self.by_filename = {
            filename: self.schemas[name] for name, filename in SCHEMA_FILES.items()
        }

    def validate_named(self, schema_name: str, instance: Any, path: str) -> None:
        self._validate(self.schemas[schema_name], instance, path, self.schemas[schema_name])

    def _resolve_ref(self, ref: str, root_schema: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        if ref.startswith("#/"):
            target: Any = root_schema
            for token in ref[2:].split("/"):
                token = token.replace("~1", "/").replace("~0", "~")
                target = target[token]
            return target, root_schema
        filename, separator, fragment = ref.partition("#")
        if filename not in self.by_filename:
            raise ResearchValidationError(f"unsupported external schema reference {ref!r}")
        external_root = self.by_filename[filename]
        if not separator or not fragment:
            return external_root, external_root
        target = external_root
        for token in fragment.removeprefix("/").split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            target = target[token]
        return target, external_root

    def _validate(
        self,
        schema: Any,
        instance: Any,
        path: str,
        root_schema: dict[str, Any],
    ) -> None:
        if schema is True or schema == {}:
            return
        if schema is False:
            raise ResearchValidationError(f"{path}: schema rejects value")
        if not isinstance(schema, dict):
            raise ResearchValidationError(f"{path}: malformed schema node")

        if "$ref" in schema:
            target, target_root = self._resolve_ref(schema["$ref"], root_schema)
            self._validate(target, instance, path, target_root)
            return

        if "const" in schema and instance != schema["const"]:
            raise ResearchValidationError(
                f"{path}: expected constant {schema['const']!r}, got {instance!r}"
            )
        if "enum" in schema and instance not in schema["enum"]:
            raise ResearchValidationError(
                f"{path}: value {instance!r} is not in {schema['enum']!r}"
            )

        expected = schema.get("type")
        if expected is not None:
            expected_types = [expected] if isinstance(expected, str) else expected
            if not any(type_matches(instance, item) for item in expected_types):
                raise ResearchValidationError(
                    f"{path}: expected type {expected_types!r}, got {type(instance).__name__}"
                )

        if isinstance(instance, str):
            if len(instance) < schema.get("minLength", 0):
                raise ResearchValidationError(f"{path}: string is shorter than minLength")
            pattern = schema.get("pattern")
            if pattern and re.search(pattern, instance) is None:
                raise ResearchValidationError(
                    f"{path}: value {instance!r} does not match {pattern!r}"
                )

        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if "minimum" in schema and instance < schema["minimum"]:
                raise ResearchValidationError(f"{path}: value is below minimum")
            if "maximum" in schema and instance > schema["maximum"]:
                raise ResearchValidationError(f"{path}: value is above maximum")

        if isinstance(instance, list):
            if len(instance) < schema.get("minItems", 0):
                raise ResearchValidationError(f"{path}: array has too few items")
            if "maxItems" in schema and len(instance) > schema["maxItems"]:
                raise ResearchValidationError(f"{path}: array has too many items")
            if schema.get("uniqueItems"):
                normalized = [json.dumps(item, sort_keys=True) for item in instance]
                if len(normalized) != len(set(normalized)):
                    raise ResearchValidationError(f"{path}: array items are not unique")
            prefix_items = schema.get("prefixItems", [])
            for index, subschema in enumerate(prefix_items):
                if index < len(instance):
                    self._validate(
                        subschema, instance[index], f"{path}[{index}]", root_schema
                    )
            items_schema = schema.get("items")
            if items_schema is False and len(instance) > len(prefix_items):
                raise ResearchValidationError(f"{path}: additional array items are forbidden")
            if isinstance(items_schema, dict):
                start = len(prefix_items) if prefix_items else 0
                for index in range(start, len(instance)):
                    self._validate(
                        items_schema, instance[index], f"{path}[{index}]", root_schema
                    )

        if isinstance(instance, dict):
            required = schema.get("required", [])
            for key in required:
                if key not in instance:
                    raise ResearchValidationError(f"{path}: missing required property {key!r}")
            properties = schema.get("properties", {})
            for key, value in instance.items():
                if key in properties:
                    self._validate(
                        properties[key], value, f"{path}.{key}", root_schema
                    )
                    continue
                additional = schema.get("additionalProperties", True)
                if additional is False:
                    raise ResearchValidationError(
                        f"{path}: unexpected property {key!r}"
                    )
                if isinstance(additional, dict):
                    self._validate(
                        additional, value, f"{path}.{key}", root_schema
                    )


def validate_corpus() -> dict[str, int]:
    validator = BoundedSchemaValidator()
    reference = load_json(DATA_DIR / "fixture_library_reference_v1.json")
    families = load_json(DATA_DIR / "fixture_family_templates_v1.json")
    components = load_json(DATA_DIR / "component_patterns_v1.json")
    failures = load_json(DATA_DIR / "failure_modes_v1.json")
    synthetic = load_json(DATA_DIR / "synthetic_examples_v1.json")

    collections = (
        ("source", reference["sources"], "reference.sources"),
        ("item", reference["engineering_principles"], "reference.engineering_principles"),
        ("item", reference["fixture_patterns"], "reference.fixture_patterns"),
        ("process", reference["process_context_patterns"], "reference.process_context_patterns"),
        ("item", reference["complete_item_examples"], "reference.complete_item_examples"),
        ("shop", reference["shop_standard_examples"], "reference.shop_standard_examples"),
        ("family", families["templates"], "families.templates"),
        ("item", components["records"], "components.records"),
        ("item", failures["records"], "failures.records"),
        ("benchmark", synthetic["cases"], "synthetic.cases"),
    )
    for schema_name, records, label in collections:
        for index, record in enumerate(records):
            validator.validate_named(schema_name, record, f"{label}[{index}]")

    counts = {
        "sources": len(reference["sources"]),
        "engineering_principles": len(reference["engineering_principles"]),
        "fixture_patterns": len(reference["fixture_patterns"]),
        "process_context_patterns": len(reference["process_context_patterns"]),
        "complete_item_examples": len(reference["complete_item_examples"]),
        "shop_standard_examples": len(reference["shop_standard_examples"]),
        "fixture_family_templates": len(families["templates"]),
        "component_application_patterns": len(components["records"]),
        "failure_modes": len(failures["records"]),
        "synthetic_benchmarks": len(synthetic["cases"]),
    }
    minimums = {
        "engineering_principles": 15,
        "fixture_patterns": 15,
        "process_context_patterns": 8,
        "fixture_family_templates": 8,
        "component_application_patterns": 20,
        "failure_modes": 10,
        "synthetic_benchmarks": 4,
    }
    for key, minimum in minimums.items():
        if counts[key] < minimum:
            raise ResearchValidationError(
                f"{key}: expected at least {minimum}, found {counts[key]}"
            )

    sources = {item["source_id"] for item in reference["sources"]}
    all_items = (
        reference["engineering_principles"]
        + reference["fixture_patterns"]
        + reference["complete_item_examples"]
        + components["records"]
        + failures["records"]
    )
    all_ids = [item["item_id"] for item in all_items]
    if len(all_ids) != len(set(all_ids)):
        raise ResearchValidationError("fixture-library item identities are not unique")

    for item in all_items:
        missing = set(item["source_ids"]) - sources
        if missing:
            raise ResearchValidationError(
                f"{item['item_id']}: unresolved source identities {sorted(missing)}"
            )
        if item["authority_level"] not in AUTHORITY_LEVELS:
            raise ResearchValidationError(
                f"{item['item_id']}: unknown authority level"
            )
    for asset in reference["process_context_patterns"]:
        missing = set(asset["source_ids"]) - sources
        if missing:
            raise ResearchValidationError(
                f"{asset['asset_id']}: unresolved source identities {sorted(missing)}"
            )

    for case in synthetic["cases"]:
        if (
            case["privacy_classification"] != "synthetic_public"
            or not case["selected_public_release_permission"]
            or case["linked_private_asset_identities"]
        ):
            raise ResearchValidationError(
                f"{case['case_id']}: public synthetic case violates privacy boundary"
            )

    forbidden_suffixes = {
        ".step",
        ".stp",
        ".iges",
        ".igs",
        ".stl",
        ".obj",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".tif",
        ".tiff",
        ".pdf",
        ".docx",
        ".xlsx",
    }
    for root in (ROOT / "docs" / "research", DATA_DIR):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in forbidden_suffixes:
                raise ResearchValidationError(
                    f"forbidden research asset committed: {path.relative_to(ROOT)}"
                )

    return counts


def main() -> int:
    try:
        counts = validate_corpus()
    except ResearchValidationError as exc:
        print(f"fixture-library research validation failed: {exc}", file=sys.stderr)
        return 1
    total_reference_records = sum(
        value
        for key, value in counts.items()
        if key not in {"sources", "complete_item_examples", "shop_standard_examples"}
    )
    print("fixture-library research validation passed")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    print(f"  total_required_reference_records: {total_reference_records}")
    print(f"  schemas: {len(SCHEMA_FILES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
