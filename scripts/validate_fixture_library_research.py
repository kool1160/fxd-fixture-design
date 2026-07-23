"""Validate the non-runtime fixture-library research package.

This standard-library-only checker implements the bounded JSON Schema
Draft 2020-12 vocabulary used by the research contracts and the cross-record
engineering invariants JSON Schema cannot express.  Production code does not
import this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from urllib.parse import urlsplit


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
    "revision": "library_revision_v1.schema.json",
    "revision_history": "library_revision_history_v1.schema.json",
    "frame": "owned_coordinate_frame_v1.schema.json",
}

PARTICIPATION_VALUES = {
    "required",
    "permitted",
    "provisional only",
    "excluded",
    "blocks when missing",
    "human confirmation required",
}

SCOPE_PRECEDENCE = {
    "fxd_default": 1,
    "organization": 2,
    "shop": 3,
    "machine_process": 4,
    "project": 5,
    "engineer_decision": 6,
}

FIXTURE_OUTPUT_FIELDS = {
    "fixture_component_step",
    "fixture_assembly_step",
    "fixture_dxf",
    "manufacturing_release",
}

FORBIDDEN_CONTENT_PATTERNS = (
    ("Windows local path", re.compile(r"(?i)(?:^|[\s\"'])(?:[a-z]:[\\/])")),
    ("UNC/network path", re.compile(r"\\\\[^\s\\]+\\[^\s]+")),
    ("file URL", re.compile(r"(?i)file://")),
    (
        "Unix home/private path",
        re.compile(r"(?i)(?:^|[\s\"'])(?:/(?:home|users|private)/|~/)"),
    ),
    (
        "CAD or image filename",
        re.compile(
            r"(?i)(?:^|[^a-z0-9])[^\\/\s]+\."
            r"(?:step|stp|iges|igs|sldprt|sldasm|ipt|iam|f3d|x_t|"
            r"stl|obj|3dm|dwg|dxf|zip|7z|rar|tar|gz|"
            r"png|jpe?g|gif|bmp|tiff?)(?:$|[?#\s\"'])"
        ),
    ),
    (
        "customer/employer asset path",
        re.compile(r"(?i)(?:customer|employer)[-_ ]?(?:asset|cad|fixture|file|path)[/\\]"),
    ),
    (
        "private network or storage indicator",
        re.compile(
            r"(?i)(?:https?://)?(?:localhost|127(?:\.[0-9]{1,3}){3}|"
            r"10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|"
            r"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2}|"
            r"[^/\s]+\.local)(?:[:/]|$)|"
            r"(?:^|[/\\])(?:private|confidential|intranet|network-share|nas)(?:[/\\]|$)"
        ),
    ),
)

RELEASE_CAPABLE_RIGHTS_BASES = {
    "original_synthetic_work",
    "owner_authorization",
    "contractual_permission",
    "employment_or_assignment_rights",
}

CONTACT_INTERFACE_TYPES = {
    "clamp_contact",
    "locator_contact",
    "support_contact",
    "stop_contact",
    "probe_point",
}

INTERFACE_FEATURE_COMPATIBILITY = {
    "face_mount": {"planar_face"},
    "hole_pattern": {"hole"},
    "slot_pattern": {"slot"},
    "pin_and_bushing": {"pin", "bushing"},
    "rail_mount": {"rail"},
    "weld_mount": {"weld_mount"},
    "table_grid_mount": {"table_grid_mount"},
    "custom_datum_frame": {"custom_datum_frame"},
}

FEATURE_DIMENSIONS = {
    "hole": {"diameter"},
    "slot": {"width", "length"},
    "pin": {"diameter", "length"},
    "bushing": {"diameter", "length"},
    "rail": {"width", "height"},
    "planar_face": set(),
    "weld_mount": set(),
    "table_grid_mount": {"pitch"},
    "custom_datum_frame": set(),
}

ALL_FEATURE_DIMENSIONS = {"diameter", "length", "width", "height", "pitch"}


@dataclass(frozen=True)
class AuthorityRule:
    """One authoritative semantic contract for a fixture-library authority."""

    categories: frozenset[str]
    source_policy: str
    geometry_policy: str
    bom_values: frozenset[str]
    preview_kinds: frozenset[str]
    preview_authorities: frozenset[str]
    exact_validation: bool
    manufacturing_output: bool
    separate_equipment_source: bool


AUTHORITY_RULES = {
    "fxd_parametric_component": AuthorityRule(
        frozenset({"fxd_standard_parametric_primitive"}),
        "no_source_file",
        "parametric_exact",
        frozenset({"required", "permitted", "human confirmation required"}),
        frozenset({"parametric_preview"}),
        frozenset({"exact"}),
        True,
        True,
        False,
    ),
    "exact_private_imported_cad": AuthorityRule(
        frozenset({"private_purchased_tooling", "user_created_reusable_component"}),
        "private_exact",
        "imported_exact",
        frozenset({"required", "permitted", "excluded", "human confirmation required"}),
        frozenset({"exact_tessellation"}),
        frozenset({"exact"}),
        True,
        True,
        True,
    ),
    "supplier_authorized_exact_cad": AuthorityRule(
        frozenset({"private_purchased_tooling"}),
        "supplier_exact",
        "imported_exact",
        frozenset({"required", "permitted", "human confirmation required"}),
        frozenset({"exact_tessellation"}),
        frozenset({"exact"}),
        True,
        True,
        True,
    ),
    "metadata_only_commercial_component": AuthorityRule(
        frozenset({"private_purchased_tooling"}),
        "no_source_file",
        "none",
        frozenset({"excluded"}),
        frozenset({"metadata_card"}),
        frozenset({"informational"}),
        False,
        False,
        False,
    ),
    "provisional_review_envelope": AuthorityRule(
        frozenset(
            {
                "private_purchased_tooling",
                "user_created_reusable_component",
                "process_context_asset",
            }
        ),
        "no_source_file",
        "provisional_only",
        frozenset({"excluded"}),
        frozenset({"provisional_envelope"}),
        frozenset({"provisional"}),
        False,
        False,
        False,
    ),
    "user_authored_reusable_component": AuthorityRule(
        frozenset({"user_created_reusable_component"}),
        "user_authored",
        "user_authored",
        frozenset({"required", "permitted", "human confirmation required"}),
        frozenset({"parametric_preview", "exact_tessellation"}),
        frozenset({"exact"}),
        True,
        True,
        False,
    ),
    "fixture_family_template": AuthorityRule(
        frozenset({"fixture_family_template"}),
        "no_source_file",
        "none",
        frozenset({"excluded"}),
        frozenset({"template_diagram"}),
        frozenset({"informational"}),
        False,
        False,
        False,
    ),
    "shop_standard": AuthorityRule(
        frozenset({"shop_standard_pack"}),
        "no_source_file",
        "none",
        frozenset({"excluded"}),
        frozenset({"none", "metadata_card"}),
        frozenset({"none", "informational"}),
        False,
        False,
        False,
    ),
    "process_context_asset": AuthorityRule(
        frozenset({"process_context_asset"}),
        "no_source_file",
        "none",
        frozenset({"excluded"}),
        frozenset({"none", "metadata_card"}),
        frozenset({"none", "informational"}),
        False,
        False,
        False,
    ),
    "private_benchmark_reference": AuthorityRule(
        frozenset({"private_benchmark_reference"}),
        "no_source_file",
        "none",
        frozenset({"excluded"}),
        frozenset({"none", "metadata_card"}),
        frozenset({"none", "informational"}),
        False,
        False,
        False,
    ),
    "public_engineering_knowledge": AuthorityRule(
        frozenset({"public_engineering_knowledge"}),
        "no_source_file",
        "none",
        frozenset({"excluded"}),
        frozenset({"none"}),
        frozenset({"none"}),
        False,
        False,
        False,
    ),
}


class ResearchValidationError(ValueError):
    """Raised when research data or its bounded schemas fail validation."""


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchValidationError(f"{_display_path(path)}: {exc}") from exc


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
    raise ResearchValidationError(f"unsupported JSON Schema type {expected!r}")


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
        schema = self.schemas[schema_name]
        self._validate(schema, instance, path, schema)

    def _resolve_ref(
        self, ref: str, root_schema: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        if ref.startswith("#/"):
            target: Any = root_schema
            for token in ref[2:].split("/"):
                target = target[token.replace("~1", "/").replace("~0", "~")]
            return target, root_schema
        filename, separator, fragment = ref.partition("#")
        if filename not in self.by_filename:
            raise ResearchValidationError(f"unsupported external schema reference {ref!r}")
        external_root = self.by_filename[filename]
        if not separator or not fragment:
            return external_root, external_root
        target: Any = external_root
        for token in fragment.removeprefix("/").split("/"):
            target = target[token.replace("~1", "/").replace("~0", "~")]
        return target, external_root

    def _matches(
        self, schema: Any, instance: Any, path: str, root_schema: dict[str, Any]
    ) -> bool:
        try:
            self._validate(schema, instance, path, root_schema)
        except ResearchValidationError:
            return False
        return True

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
            siblings = {key: value for key, value in schema.items() if key != "$ref"}
            if siblings:
                self._validate(siblings, instance, path, root_schema)
            return

        for index, subschema in enumerate(schema.get("allOf", [])):
            self._validate(subschema, instance, f"{path}.allOf[{index}]", root_schema)
        if "anyOf" in schema:
            if not any(
                self._matches(subschema, instance, path, root_schema)
                for subschema in schema["anyOf"]
            ):
                raise ResearchValidationError(f"{path}: no anyOf branch matched")
        if "oneOf" in schema:
            matches = sum(
                self._matches(subschema, instance, path, root_schema)
                for subschema in schema["oneOf"]
            )
            if matches != 1:
                raise ResearchValidationError(
                    f"{path}: expected exactly one oneOf match, found {matches}"
                )
        if "not" in schema and self._matches(schema["not"], instance, path, root_schema):
            raise ResearchValidationError(f"{path}: value matches forbidden schema")
        if "if" in schema:
            branch = "then" if self._matches(schema["if"], instance, path, root_schema) else "else"
            if branch in schema:
                self._validate(schema[branch], instance, f"{path}.{branch}", root_schema)

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
            if not math.isfinite(float(instance)):
                raise ResearchValidationError(f"{path}: numeric value must be finite")
            if "minimum" in schema and instance < schema["minimum"]:
                raise ResearchValidationError(f"{path}: value is below minimum")
            if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
                raise ResearchValidationError(
                    f"{path}: value is not above exclusiveMinimum"
                )
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
            if len(instance) < schema.get("minProperties", 0):
                raise ResearchValidationError(f"{path}: object has too few properties")
            for key in schema.get("required", []):
                if key not in instance:
                    raise ResearchValidationError(f"{path}: missing required property {key!r}")
            properties = schema.get("properties", {})
            for key, value in instance.items():
                if key in properties:
                    self._validate(properties[key], value, f"{path}.{key}", root_schema)
                    continue
                additional = schema.get("additionalProperties", True)
                if additional is False:
                    raise ResearchValidationError(f"{path}: unexpected property {key!r}")
                if isinstance(additional, dict):
                    self._validate(additional, value, f"{path}.{key}", root_schema)


def _identity(record: dict[str, Any]) -> str:
    for field in (
        "item_id",
        "source_id",
        "template_id",
        "asset_id",
        "case_id",
        "pack_id",
        "pin_id",
        "history_id",
    ):
        if field in record:
            return str(record[field])
    raise ResearchValidationError("record has no stable identity field")


def _walk_strings(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_strings(item, f"{path}.{key}")


def _validate_no_private_payloads(documents: dict[str, Any]) -> None:
    for filename, document in documents.items():
        for path, value in _walk_strings(document):
            if (
                filename == "fixture_library_reference_v1.json"
                and re.fullmatch(r"\$\.sources\[[0-9]+\]\.canonical_url", path)
                and value.startswith("https://")
            ):
                parsed = urlsplit(value)
                if (
                    not parsed.hostname
                    or parsed.username is not None
                    or parsed.password is not None
                ):
                    raise ResearchValidationError(
                        f"{filename}:{path}: canonical public source URL is malformed"
                    )
                for label, pattern in FORBIDDEN_CONTENT_PATTERNS:
                    if pattern.search(value):
                        raise ResearchValidationError(
                            f"{filename}:{path}: canonical public source URL contains "
                            f"private or asset content ({label})"
                        )
                continue
            for label, pattern in FORBIDDEN_CONTENT_PATTERNS:
                if pattern.search(value):
                    raise ResearchValidationError(
                        f"{filename}:{path}: likely private payload reference ({label})"
                    )
            if value.startswith(("https://", "http://")):
                parsed = urlsplit(value)
                if parsed.scheme != "https":
                    raise ResearchValidationError(
                        f"{filename}:{path}: non-canonical public URL outside source register"
                    )


def _canonical_content(record: dict[str, Any]) -> bytes:
    payload = {key: value for key, value in record.items() if key != "revision"}
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def compute_content_digest(record: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_content(record)).hexdigest()


def compute_concurrency_token(revision: dict[str, Any], content_digest: str) -> str:
    parent = revision.get("parent_revision_id") or "null"
    material = f"{revision.get('revision_id')}|{parent}|{content_digest}".encode()
    return hashlib.sha256(material).hexdigest()


def refresh_revision_evidence(record: dict[str, Any]) -> None:
    """Refresh digest/token after an intentional test mutation."""

    revision = record["revision"]
    digest = compute_content_digest(record)
    revision["content_sha256"] = digest
    revision["optimistic_concurrency_token"] = compute_concurrency_token(
        revision, digest
    )


def _validate_timestamp(value: str, path: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ResearchValidationError(f"{path}: invalid UTC calendar timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ResearchValidationError(f"{path}: timestamp is not canonical")
    return parsed


def _validate_revision(record: dict[str, Any], path: str) -> None:
    revision = record["revision"]
    _validate_timestamp(revision["created_at"], f"{path}.revision.created_at")
    revision_number = int(revision["revision_id"][1:])
    parent = revision["parent_revision_id"]
    restored = revision["restores_content_from_revision_id"]
    if revision_number == 1:
        if parent is not None or restored is not None:
            raise ResearchValidationError(
                f"{path}.revision: root r1 cannot have parent or rollback target"
            )
    elif parent is None:
        raise ResearchValidationError(
            f"{path}.revision: non-initial revision requires a parent"
        )
    for field in ("parent_revision_id", "restores_content_from_revision_id"):
        if revision[field] == revision["revision_id"]:
            raise ResearchValidationError(
                f"{path}.revision: invalid ancestry; {field} is the current revision"
            )
    if restored is not None and int(restored[1:]) >= revision_number:
        raise ResearchValidationError(
            f"{path}.revision: rollback target must be an earlier revision"
        )
    expected_digest = compute_content_digest(record)
    if revision["content_sha256"] != expected_digest:
        raise ResearchValidationError(f"{path}.revision: content digest mismatch")
    expected_token = compute_concurrency_token(revision, expected_digest)
    if revision["optimistic_concurrency_token"] != expected_token:
        raise ResearchValidationError(f"{path}.revision: concurrency token mismatch")


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(float(value) ** 2 for value in vector))


def _dot(first: list[float], second: list[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def _cross(first: list[float], second: list[float]) -> tuple[float, float, float]:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _validate_direction(vector: list[float], path: str, tolerance: float = 1e-6) -> None:
    if any(not math.isfinite(float(value)) for value in vector):
        raise ResearchValidationError(f"{path}: direction contains non-finite value")
    magnitude = _norm(vector)
    if magnitude <= tolerance:
        raise ResearchValidationError(f"{path}: zero-length direction")
    if abs(magnitude - 1.0) > tolerance:
        raise ResearchValidationError(f"{path}: direction is not normalized")


def _validate_frame(
    frame: dict[str, Any], owner_id: str, owner_units: str, path: str
) -> None:
    if frame["owner_id"] != owner_id:
        raise ResearchValidationError(f"{path}: frame owner does not match owning record")
    if frame["units"] != owner_units:
        raise ResearchValidationError(f"{path}: frame units differ from owning record")
    for value in frame["origin"]:
        if not math.isfinite(float(value)):
            raise ResearchValidationError(f"{path}: origin contains non-finite value")
    axes = frame["axes"]
    for name in ("x", "y", "z"):
        _validate_direction(axes[name], f"{path}.axes.{name}")
    for first, second in (("x", "y"), ("x", "z"), ("y", "z")):
        if abs(_dot(axes[first], axes[second])) > 1e-6:
            raise ResearchValidationError(f"{path}: axes are not orthogonal")
    orientation = _dot(list(_cross(axes["x"], axes["y"])), axes["z"])
    expected_positive = frame["handedness"] == "right_handed"
    if (orientation > 0) != expected_positive or abs(abs(orientation) - 1.0) > 1e-6:
        raise ResearchValidationError(f"{path}: handedness does not match axes")


def _validate_geometry(geometry: dict[str, Any], path: str) -> None:
    kind = geometry["kind"]
    allowed_non_null = {
        "point": {"point"},
        "tool_center_point": {"point"},
        "line": {"point", "axis"},
        "axis": {"point", "axis"},
        "plane": {"point", "normal"},
        "bounded_region": {"bounds_min", "bounds_max"},
        "contact_patch": {"point", "normal", "bounds_min", "bounds_max"},
        "envelope": {"bounds_min", "bounds_max"},
        "sensor_field": {"bounds_min", "bounds_max"},
    }[kind]
    geometry_fields = {
        "point",
        "axis",
        "normal",
        "bounds_min",
        "bounds_max",
        "radius",
    }
    for field in allowed_non_null:
        if geometry[field] is None:
            raise ResearchValidationError(
                f"{path}: {kind} geometry requires {field}"
            )
    for field in geometry_fields - allowed_non_null:
        if geometry[field] is not None:
            raise ResearchValidationError(
                f"{path}: {kind} geometry forbids incompatible field {field}"
            )
    for field in ("axis", "normal"):
        if geometry[field] is not None:
            _validate_direction(geometry[field], f"{path}.{field}")
    if geometry["bounds_min"] is not None and geometry["bounds_max"] is not None:
        if any(
            low > high
            for low, high in zip(geometry["bounds_min"], geometry["bounds_max"])
        ):
            raise ResearchValidationError(f"{path}: invalid bounded geometry range")


def _validate_mounting_interface(
    interface: dict[str, Any], item_id: str, units: str, path: str
) -> None:
    _validate_frame(interface["frame"], interface["interface_id"], units, f"{path}.frame")
    feature_ids: list[str] = []
    compatible_features = INTERFACE_FEATURE_COMPATIBILITY[interface["interface_type"]]
    feature_types: list[str] = []
    for index, feature in enumerate(interface["features"]):
        feature_path = f"{path}.features[{index}]"
        feature_ids.append(feature["feature_id"])
        feature_type = feature["feature_type"]
        feature_types.append(feature_type)
        if feature["owning_interface_id"] != interface["interface_id"]:
            raise ResearchValidationError(
                f"{feature_path}: owning interface reference does not resolve"
            )
        if feature_type not in compatible_features:
            raise ResearchValidationError(
                f"{feature_path}: {feature_type} is incompatible with "
                f"{interface['interface_type']}"
            )
        _validate_direction(feature["axis"], f"{feature_path}.axis")
        if feature["dimensions"]["units"] != units:
            raise ResearchValidationError(f"{feature_path}: dimensions units mismatch")
        tolerance = feature["tolerance_clearance_intent"]
        if tolerance["units"] != units:
            raise ResearchValidationError(f"{feature_path}: tolerance units mismatch")
        adjustment = feature["adjustment_range"]
        if adjustment is not None and adjustment["minimum"] > adjustment["maximum"]:
            raise ResearchValidationError(f"{feature_path}: invalid adjustment range")
        applicable_dimensions = FEATURE_DIMENSIONS[feature_type]
        for dimension in ALL_FEATURE_DIMENSIONS:
            value = feature["dimensions"][dimension]
            if dimension in applicable_dimensions and (
                value is None or not math.isfinite(float(value)) or value <= 0
            ):
                raise ResearchValidationError(
                    f"{feature_path}: {feature_type} requires positive finite {dimension}"
                )
            if dimension not in applicable_dimensions and value is not None:
                raise ResearchValidationError(
                    f"{feature_path}: {feature_type} forbids dimension {dimension}"
                )
        if feature_type in {"slot", "rail"} and adjustment is None:
            raise ResearchValidationError(
                f"{feature_path}: adjustable feature lacks adjustment range"
            )
        if feature_type not in {"slot", "rail"} and adjustment is not None:
            raise ResearchValidationError(
                f"{feature_path}: non-adjustable feature carries adjustment range"
            )
        if (
            feature["allowed_replacement_class"]
            not in interface["allowed_replacement_classes"]
        ):
            raise ResearchValidationError(
                f"{feature_path}: replacement class is not declared by interface"
            )
    if len(feature_ids) != len(set(feature_ids)):
        raise ResearchValidationError(f"{path}: duplicate mounting feature identity")
    if interface["interface_type"] == "pin_and_bushing" and not {
        "pin",
        "bushing",
    }.issubset(set(feature_types)):
        raise ResearchValidationError(
            f"{path}: pin-and-bushing interface requires both pin and bushing features"
        )


def _validate_interfaces(item: dict[str, Any], path: str) -> None:
    item_id = item["item_id"]
    units = item["units"]
    frame_ids: set[str] = set()
    local = item["local_coordinate_system"]
    if local is not None:
        _validate_frame(local, item_id, units, f"{path}.local_coordinate_system")
        frame_ids.add(local["frame_id"])
    mounting_ids: list[str] = []
    for index, interface in enumerate(item["mounting_interfaces"]):
        mounting_ids.append(interface["interface_id"])
        _validate_mounting_interface(
            interface, item_id, units, f"{path}.mounting_interfaces[{index}]"
        )
        frame_id = interface["frame"]["frame_id"]
        if frame_id in frame_ids:
            raise ResearchValidationError(
                f"{path}: duplicate coordinate-frame identity {frame_id!r}"
            )
        frame_ids.add(frame_id)
    if len(mounting_ids) != len(set(mounting_ids)):
        raise ResearchValidationError(f"{path}: duplicate mounting interface identity")

    states = [state["state_id"] for state in item["movement_states"]]
    if len(states) != len(set(states)):
        raise ResearchValidationError(f"{path}: duplicate movement-state identity")
    functional_ids: list[str] = []
    for index, interface in enumerate(item["functional_interfaces"]):
        interface_path = f"{path}.functional_interfaces[{index}]"
        functional_ids.append(interface["interface_id"])
        if interface["frame_id"] not in frame_ids:
            raise ResearchValidationError(
                f"{interface_path}: coordinate-frame reference does not resolve"
            )
        if interface["movement_state"] not in states:
            raise ResearchValidationError(
                f"{interface_path}: movement-state reference does not resolve"
            )
        _validate_direction(interface["direction"], f"{interface_path}.direction")
        if interface["geometry"]["units"] != units:
            raise ResearchValidationError(
                f"{interface_path}: functional geometry units differ from owning item"
            )
        _validate_geometry(interface["geometry"], f"{interface_path}.geometry")
    if len(functional_ids) != len(set(functional_ids)):
        raise ResearchValidationError(f"{path}: duplicate functional-interface identity")
    missing_contacts = set(item["contact_points"]) - set(functional_ids)
    if missing_contacts:
        raise ResearchValidationError(
            f"{path}: contact references do not resolve {sorted(missing_contacts)}"
        )
    functional_by_id = {
        interface["interface_id"]: interface for interface in item["functional_interfaces"]
    }
    invalid_contacts = [
        contact_id
        for contact_id in item["contact_points"]
        if functional_by_id[contact_id]["interface_type"] not in CONTACT_INTERFACE_TYPES
    ]
    if invalid_contacts:
        raise ResearchValidationError(
            f"{path}: contact references target incompatible interface roles "
            f"{sorted(invalid_contacts)}"
        )
    closure = item["open_closed_states"]
    if closure["claimed"]:
        if not closure["open_state_id"] or not closure["closed_state_id"]:
            raise ResearchValidationError(f"{path}: claimed open/closed states incomplete")
        if {closure["open_state_id"], closure["closed_state_id"]} - set(states):
            raise ResearchValidationError(f"{path}: open/closed state reference missing")
        if closure["open_state_id"] == closure["closed_state_id"]:
            raise ResearchValidationError(
                f"{path}: open and closed states must be distinct"
            )
        state_kinds = {
            state["state_id"]: state["state_kind"] for state in item["movement_states"]
        }
        if state_kinds[closure["open_state_id"]] != "open":
            raise ResearchValidationError(
                f"{path}: open-state reference does not have open state kind"
            )
        if state_kinds[closure["closed_state_id"]] != "closed":
            raise ResearchValidationError(
                f"{path}: closed-state reference does not have closed state kind"
            )
    elif closure["open_state_id"] is not None or closure["closed_state_id"] is not None:
        raise ResearchValidationError(f"{path}: unclaimed open/closed states must be null")
    replacement = item["replacement_compatibility"]
    declared_replacement_classes = {
        replacement_class
        for interface in item["mounting_interfaces"]
        for replacement_class in interface["allowed_replacement_classes"]
    }
    if (
        replacement["replacement_class"] is not None
        and replacement["replacement_class"] not in declared_replacement_classes
    ):
        raise ResearchValidationError(
            f"{path}: item replacement class is not declared by a mounting interface"
        )
    if replacement["functionally_equivalent"] and (
        not replacement["placement_compatible"]
        or not replacement["requires_interface_match"]
        or not replacement["requires_revalidation"]
    ):
        raise ResearchValidationError(
            f"{path}: functional equivalence cannot bypass placement/interface revalidation"
        )


def _validate_item_authority(item: dict[str, Any], path: str) -> None:
    authority = item["authority_level"]
    if authority not in AUTHORITY_RULES:
        raise ResearchValidationError(f"{path}: unknown authority level")
    rule = AUTHORITY_RULES[authority]
    if item["category"] not in rule.categories:
        raise ResearchValidationError(
            f"{path}: authority {authority} is incompatible with category "
            f"{item['category']}"
        )
    output = item["export_participation"]
    validation = item["validation_participation"]
    if any(value not in PARTICIPATION_VALUES for value in output.values()):
        raise ResearchValidationError(f"{path}: illegal output participation")
    if any(value not in PARTICIPATION_VALUES for value in validation.values()):
        raise ResearchValidationError(f"{path}: illegal validation participation")
    if item["bom_participation"] not in rule.bom_values:
        raise ResearchValidationError(
            f"{path}: authority {authority} forbids BOM participation "
            f"{item['bom_participation']!r}"
        )
    advisory_bom_hint = item.get("advisory_bom_hint")
    if advisory_bom_hint is not None:
        if authority not in {
            "metadata_only_commercial_component",
            "provisional_review_envelope",
        }:
            raise ResearchValidationError(
                f"{path}: authority {authority} forbids advisory BOM hints"
            )
        if advisory_bom_hint["deliverable_eligible"]:
            raise ResearchValidationError(
                f"{path}: advisory BOM hint cannot enter a deliverable BOM"
            )
    preview = item["preview_representation"]
    if (
        preview["kind"] not in rule.preview_kinds
        or preview["authority"] not in rule.preview_authorities
    ):
        raise ResearchValidationError(
            f"{path}: authority {authority} contradicts preview representation"
        )
    if not rule.manufacturing_output and any(
        output[field] != "excluded" for field in FIXTURE_OUTPUT_FIELDS
    ):
        raise ResearchValidationError(
            f"{path}: authority {authority} contradicts manufacturing output participation"
        )
    if not rule.exact_validation and (
        validation["exact_collision"] != "excluded"
        or validation["exact_clearance"] != "excluded"
        or validation["manufacturing_release"] != "excluded"
    ):
        raise ResearchValidationError(
            f"{path}: authority {authority} contradicts exact validation participation"
        )
    source_file = item["source_file"]
    if rule.source_policy == "no_source_file" and source_file is not None:
        raise ResearchValidationError(
            f"{path}: authority {authority} forbids exact source-file geometry"
        )
    if rule.source_policy == "private_exact" and (
        source_file is None
        or source_file["source_classification"] != "private_owner_authorized"
    ):
        raise ResearchValidationError(
            f"{path}: exact private authority requires private authorized source evidence"
        )
    if rule.source_policy == "supplier_exact" and (
        source_file is None
        or source_file["source_classification"] != "supplier_authorized_exact"
    ):
        raise ResearchValidationError(
            f"{path}: supplier exact authority requires supplier source evidence"
        )

    no_geometry_values = {
        "local_coordinate_system": None,
        "feature_definition": None,
        "mounting_interfaces": [],
        "functional_interfaces": [],
        "contact_points": [],
        "movement_states": [],
        "keep_out_envelopes": [],
        "maintenance_envelopes": [],
        "material_manufacturing_intent": None,
    }
    if rule.geometry_policy == "none":
        for field, expected in no_geometry_values.items():
            if item[field] != expected:
                raise ResearchValidationError(
                    f"{path}: authority {authority} forbids geometry-bearing field {field}"
                )
        closure = item["open_closed_states"]
        if closure != {
            "claimed": False,
            "open_state_id": None,
            "closed_state_id": None,
        }:
            raise ResearchValidationError(
                f"{path}: authority {authority} forbids movement-state closure"
            )
    elif rule.geometry_policy == "provisional_only":
        for field in (
            "feature_definition",
            "mounting_interfaces",
            "functional_interfaces",
            "contact_points",
            "material_manufacturing_intent",
        ):
            expected = None if field in {
                "feature_definition",
                "material_manufacturing_intent",
            } else []
            if item[field] != expected:
                raise ResearchValidationError(
                    f"{path}: provisional authority forbids exact field {field}"
                )
    elif rule.geometry_policy == "parametric_exact":
        for field in (
            "local_coordinate_system",
            "feature_definition",
            "material_manufacturing_intent",
        ):
            if item[field] is None:
                raise ResearchValidationError(
                    f"{path}: parametric authority requires {field}"
                )
    elif rule.geometry_policy == "imported_exact":
        if item["local_coordinate_system"] is None:
            raise ResearchValidationError(
                f"{path}: imported exact authority requires a local coordinate frame"
            )
        if item["feature_definition"] is not None:
            raise ResearchValidationError(
                f"{path}: imported exact authority cannot also claim parametric features"
            )
    elif rule.geometry_policy == "user_authored":
        has_parametric = item["feature_definition"] is not None and source_file is None
        has_exact = (
            item["feature_definition"] is None
            and source_file is not None
            and source_file["source_classification"] == "user_authored_exact"
        )
        if has_parametric == has_exact:
            raise ResearchValidationError(
                f"{path}: user-authored authority requires exactly one authored geometry form"
            )


ENGINEERING_SUBSTANCE_FIELDS = {
    "engineering_principle": (
        "record_type",
        "summary",
        "applicability",
        "limitations",
        "engineering_details",
    ),
    "fixture_pattern": (
        "record_type",
        "summary",
        "applicability",
        "limitations",
        "engineering_details",
    ),
    "component_application": (
        "record_type",
        "summary",
        "applicability",
        "limitations",
        "engineering_details",
    ),
    "failure_mode": (
        "record_type",
        "summary",
        "applicability",
        "limitations",
        "engineering_details",
    ),
    "library_component": (
        "record_type",
        "category",
        "authority_level",
        "feature_definition",
        "mounting_interfaces",
        "functional_interfaces",
        "material_manufacturing_intent",
        "configurable_variants",
        "replacement_compatibility",
        "summary",
        "applicability",
        "limitations",
        "engineering_details",
    ),
}


def _normalize_engineering_substance(value: Any) -> Any:
    if isinstance(value, str):
        tokens = re.findall(r"[a-z0-9]+", value.casefold())
        return " ".join(sorted(tokens))
    if isinstance(value, list):
        normalized = [_normalize_engineering_substance(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, dict):
        return {
            key: _normalize_engineering_substance(item)
            for key, item in sorted(value.items())
        }
    return value


def _semantic_fingerprint(record: dict[str, Any]) -> str:
    record_type = record["record_type"]
    fields = ENGINEERING_SUBSTANCE_FIELDS[record_type]
    projection = {field: record[field] for field in fields}
    normalized = _normalize_engineering_substance(projection)
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _validate_unique_and_ordered(
    records: list[dict[str, Any]], label: str
) -> None:
    identities = [_identity(record) for record in records]
    if len(identities) != len(set(identities)):
        raise ResearchValidationError(f"{label}: duplicate identity")
    if identities != sorted(identities):
        raise ResearchValidationError(f"{label}: records are not deterministically ordered")


def _validate_public_rights(case: dict[str, Any], path: str) -> None:
    rights = case["rights_and_release"]
    approval = _validate_timestamp(
        rights["approval_timestamp"], f"{path}.rights.approval_timestamp"
    )
    release_decision = _validate_timestamp(
        rights["release_decision_timestamp"],
        f"{path}.rights.release_decision_timestamp",
    )
    expiry = (
        _validate_timestamp(
            rights["expiry_timestamp"], f"{path}.rights.expiry_timestamp"
        )
        if rights["expiry_timestamp"] is not None
        else None
    )
    revocation = (
        _validate_timestamp(
            rights["revocation_timestamp"], f"{path}.rights.revocation_timestamp"
        )
        if rights["revocation_timestamp"] is not None
        else None
    )
    if release_decision < approval:
        raise ResearchValidationError(
            f"{path}: release decision precedes rights approval"
        )
    if expiry is not None:
        if expiry <= approval:
            raise ResearchValidationError(
                f"{path}: rights expiry must follow approval"
            )
        if release_decision >= expiry:
            raise ResearchValidationError(
                f"{path}: release decision is not before rights expiry"
            )
    if rights["release_decision_state"] != "approved" and (
        rights["public_release_permission"] or rights["export_permission"]
    ):
        raise ResearchValidationError(
            f"{path}: non-approved release decision still permits release or export"
        )
    if rights["revocation_state"] == "revoked":
        if rights["revocation_timestamp"] is None or not rights["revocation_reason"]:
            raise ResearchValidationError(f"{path}: revoked rights lack timestamp/reason")
        if revocation is not None and revocation < approval:
            raise ResearchValidationError(
                f"{path}: revocation precedes rights approval"
            )
        if rights["public_release_permission"] or rights["export_permission"]:
            raise ResearchValidationError(f"{path}: revoked rights still permit release")
    elif rights["revocation_timestamp"] is not None or rights["revocation_reason"] is not None:
        raise ResearchValidationError(f"{path}: non-revoked rights carry revocation data")
    if rights["revocation_state"] == "pending_review" and (
        rights["public_release_permission"] or rights["export_permission"]
    ):
        raise ResearchValidationError(
            f"{path}: pending rights review still permits release or export"
        )
    if (
        revocation is not None
        and rights["release_decision_state"] == "approved"
        and release_decision >= revocation
    ):
        raise ResearchValidationError(
            f"{path}: release decision occurred after rights revocation"
        )

    if case["privacy_classification"] == "synthetic_public":
        if (
            rights["rights_basis"] != "original_synthetic_work"
            or rights["release_decision_state"] != "approved"
            or not rights["public_release_permission"]
            or not rights["export_permission"]
            or rights["revocation_state"] != "not_revoked"
            or case["linked_private_asset_identities"]
        ):
            raise ResearchValidationError(
                f"{path}: public synthetic case violates fail-closed release boundary"
            )
    if case["privacy_classification"] == "selected_public_release":
        if (
            rights["rights_basis"] not in RELEASE_CAPABLE_RIGHTS_BASES
            or rights["release_decision_state"] != "approved"
            or rights["revocation_state"] != "not_revoked"
            or not rights["public_release_permission"]
            or not rights["export_permission"]
        ):
            raise ResearchValidationError(
                f"{path}: selected public release lacks active release-capable rights"
            )
        released_fields = {
            key
            for key in case
            if key not in {"revision", "rights_and_release", "linked_private_asset_identities"}
        }
        if not released_fields.issubset(set(rights["permitted_metadata_fields"])):
            raise ResearchValidationError(
                f"{path}: selected public fields exceed explicit permission"
            )
        if not set(case["linked_private_asset_identities"]).issubset(
            set(rights["permitted_asset_scope"])
        ):
            raise ResearchValidationError(
                f"{path}: selected public assets exceed explicit permission"
            )


def _validate_process_asset(asset: dict[str, Any], path: str) -> None:
    _validate_frame(asset["frame"], asset["asset_id"], asset["units"], f"{path}.frame")
    geometry_authority = asset["geometry_authority"]
    authority_fields = {
        "collision_authority": asset["collision_authority"],
        "envelope_authority": asset["envelope_authority"],
        "access_authority": asset["access_authority"],
    }
    permitted_context_authorities = {
        "exact_private_imported_cad": {"exact", "provisional_only", "excluded"},
        "supplier_authorized_exact_cad": {"exact", "provisional_only", "excluded"},
        "provisional_review_envelope": {"provisional_only", "excluded"},
        "metadata_only_commercial_component": {"metadata_only", "excluded"},
    }[geometry_authority]
    for field, value in authority_fields.items():
        if value not in permitted_context_authorities:
            raise ResearchValidationError(
                f"{path}: {field}={value!r} exceeds geometry authority "
                f"{geometry_authority}"
            )
    if (
        "exact" in authority_fields.values()
        and asset["geometry_source_item_id"] is None
    ):
        raise ResearchValidationError(
            f"{path}: exact context authority lacks exact governed source evidence"
        )
    states = [state["state_id"] for state in asset["movement_states"]]
    if len(states) != len(set(states)):
        raise ResearchValidationError(f"{path}: duplicate movement-state identity")
    for state in asset["movement_states"]:
        if (
            geometry_authority == "provisional_review_envelope"
            and state["authoritative_for_collision"]
        ):
            raise ResearchValidationError(
                f"{path}: provisional context marked collision-authoritative"
            )
    envelope_ids: list[str] = []
    for group in ("keep_out_envelopes", "maintenance_envelopes"):
        for index, envelope in enumerate(asset[group]):
            envelope_ids.append(envelope["envelope_id"])
            if envelope["state_id"] not in states:
                raise ResearchValidationError(
                    f"{path}.{group}[{index}]: movement-state reference does not resolve"
                )
            if (
                geometry_authority == "provisional_review_envelope"
                and not envelope["provisional"]
            ):
                raise ResearchValidationError(
                    f"{path}.{group}[{index}]: provisional geometry has "
                    "non-provisional envelope"
                )
            _validate_geometry(envelope["geometry"], f"{path}.{group}[{index}].geometry")
            if envelope["geometry"]["units"] != asset["units"]:
                raise ResearchValidationError(
                    f"{path}.{group}[{index}]: envelope units differ from owning asset"
                )
    if len(envelope_ids) != len(set(envelope_ids)):
        raise ResearchValidationError(f"{path}: duplicate envelope identity")
    interface_ids: list[str] = []
    for index, interface in enumerate(asset["functional_interfaces"]):
        interface_ids.append(interface["interface_id"])
        if interface["frame_id"] != asset["frame"]["frame_id"]:
            raise ResearchValidationError(
                f"{path}.functional_interfaces[{index}]: frame reference does not resolve"
            )
        if interface["movement_state"] not in states:
            raise ResearchValidationError(
                f"{path}.functional_interfaces[{index}]: state reference does not resolve"
            )
        _validate_direction(
            interface["direction"], f"{path}.functional_interfaces[{index}].direction"
        )
        if interface["geometry"]["units"] != asset["units"]:
            raise ResearchValidationError(
                f"{path}.functional_interfaces[{index}]: geometry units differ "
                "from owning asset"
            )
        _validate_geometry(
            interface["geometry"], f"{path}.functional_interfaces[{index}].geometry"
        )
    if len(interface_ids) != len(set(interface_ids)):
        raise ResearchValidationError(f"{path}: duplicate functional-interface identity")

    output = asset["output_participation"]
    fixture_fields = (
        "fixture_bom",
        "fixture_component_step",
        "fixture_assembly_step",
        "fixture_dxf",
        "fixture_manufacturing_release",
    )
    if asset["deliverable_scope"] in {
        "reference_context_only",
        "excluded_from_deliverables",
    } and any(output[field] != "excluded" for field in fixture_fields):
        raise ResearchValidationError(
            f"{path}: reference process context entered fixture deliverables"
        )
    if asset["deliverable_scope"] == "separate_equipment_deliverable":
        if asset["geometry_authority"] not in {
            "exact_private_imported_cad",
            "supplier_authorized_exact_cad",
        }:
            raise ResearchValidationError(
                f"{path}: separate equipment lacks exact geometry authority"
            )
        if asset["delivery_authorization"] is None:
            raise ResearchValidationError(
                f"{path}: separate equipment lacks explicit delivery authorization"
            )


def _validate_revision_history_state(
    state: dict[str, Any], validator: BoundedSchemaValidator
) -> None:
    validator.validate_named("revision_history", state, "revision_state")
    histories = state["histories"]
    pins = state["project_pins"]
    _validate_unique_and_ordered(histories, "revision_state.histories")
    _validate_unique_and_ordered(pins, "revision_state.project_pins")
    history_by_id: dict[str, dict[str, Any]] = {}

    for history_index, history in enumerate(histories):
        path = f"revision_state.histories[{history_index}]"
        history_by_id[history["history_id"]] = history
        entries = history["revisions"]
        revision_ids = [entry["revision"]["revision_id"] for entry in entries]
        if len(revision_ids) != len(set(revision_ids)):
            raise ResearchValidationError(f"{path}: duplicate revision identity")
        if revision_ids != sorted(revision_ids, key=lambda value: int(value[1:])):
            raise ResearchValidationError(
                f"{path}: revisions are not deterministically ordered"
            )
        revisions = {entry["revision"]["revision_id"]: entry for entry in entries}
        if "r1" not in revisions:
            raise ResearchValidationError(f"{path}: history lacks exactly defined r1 root")
        roots = [
            entry
            for entry in entries
            if entry["revision"]["parent_revision_id"] is None
        ]
        if len(roots) != 1 or roots[0]["revision"]["revision_id"] != "r1":
            raise ResearchValidationError(
                f"{path}: history must have exactly one parentless r1 root"
            )
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(revision_id: str) -> None:
            if revision_id in visiting:
                raise ResearchValidationError(
                    f"{path}: revision ancestry contains a cycle"
                )
            if revision_id in visited:
                return
            visiting.add(revision_id)
            parent_id = revisions[revision_id]["revision"]["parent_revision_id"]
            if parent_id in revisions:
                visit(parent_id)
            visiting.remove(revision_id)
            visited.add(revision_id)

        for revision_id in revisions:
            visit(revision_id)

        children_by_parent: dict[str, list[dict[str, Any]]] = {}
        created_at: dict[str, datetime] = {}
        for entry_index, entry in enumerate(entries):
            entry_path = f"{path}.revisions[{entry_index}]"
            revision = entry["revision"]
            revision_id = revision["revision_id"]
            created_at[revision_id] = _validate_timestamp(
                revision["created_at"], f"{entry_path}.revision.created_at"
            )
            expected_token = compute_concurrency_token(
                revision, revision["content_sha256"]
            )
            if revision["optimistic_concurrency_token"] != expected_token:
                raise ResearchValidationError(
                    f"{entry_path}: revision concurrency token mismatch"
                )
            parent_id = revision["parent_revision_id"]
            restored_id = revision["restores_content_from_revision_id"]
            if revision_id == "r1":
                if (
                    parent_id is not None
                    or restored_id is not None
                    or entry["change_kind"] != "root"
                ):
                    raise ResearchValidationError(
                        f"{entry_path}: r1 must be an immutable root revision"
                    )
            else:
                if parent_id is None:
                    raise ResearchValidationError(
                        f"{entry_path}: non-initial revision requires a parent"
                    )
                if parent_id not in revisions:
                    raise ResearchValidationError(
                        f"{entry_path}: parent revision does not resolve"
                    )
                children_by_parent.setdefault(parent_id, []).append(entry)
                if int(parent_id[1:]) >= int(revision_id[1:]):
                    raise ResearchValidationError(
                        f"{entry_path}: parent must be an earlier revision"
                    )
            if restored_id is None:
                if entry["change_kind"] == "rollback":
                    raise ResearchValidationError(
                        f"{entry_path}: rollback lacks restored revision"
                    )
            else:
                if restored_id not in revisions:
                    raise ResearchValidationError(
                        f"{entry_path}: restored revision does not resolve"
                    )
                if entry["change_kind"] != "rollback":
                    raise ResearchValidationError(
                        f"{entry_path}: restored revision requires rollback change kind"
                    )
                if parent_id is None:
                    raise ResearchValidationError(
                        f"{entry_path}: rollback must create a new child revision"
                    )
                ancestors: set[str] = set()
                cursor = parent_id
                while cursor is not None:
                    if cursor in ancestors:
                        raise ResearchValidationError(
                            f"{entry_path}: revision ancestry contains a cycle"
                        )
                    ancestors.add(cursor)
                    cursor = revisions[cursor]["revision"]["parent_revision_id"]
                if restored_id not in ancestors:
                    raise ResearchValidationError(
                        f"{entry_path}: rollback target is not an ancestor"
                    )
                if (
                    revision["content_sha256"]
                    != revisions[restored_id]["revision"]["content_sha256"]
                ):
                    raise ResearchValidationError(
                        f"{entry_path}: rollback content digest does not match "
                        "the restored ancestor"
                    )
                if not entry["evidence_invalidated"]:
                    raise ResearchValidationError(
                        f"{entry_path}: rollback must invalidate dependent evidence"
                    )
            if entry["evidence_invalidated"] != (
                entry["invalidation_reason"] is not None
            ):
                raise ResearchValidationError(
                    f"{entry_path}: evidence invalidation requires matching reason"
                )

        for revision_id, entry in revisions.items():
            parent_id = entry["revision"]["parent_revision_id"]
            if parent_id is not None and created_at[revision_id] < created_at[parent_id]:
                raise ResearchValidationError(
                    f"{path}: child revision predates its parent"
                )

        for parent_id, children in children_by_parent.items():
            published = [
                entry
                for entry in children
                if entry["revision"]["publication_state"] == "published_research"
            ]
            current = [
                entry for entry in published if entry["current_published_successor"]
            ]
            if len(published) > 1 or len(current) > 1:
                raise ResearchValidationError(
                    f"{path}: parent {parent_id} has duplicate published successors"
                )

        current_id = history["current_revision_id"]
        if current_id not in revisions:
            raise ResearchValidationError(
                f"{path}: current revision does not resolve"
            )
        marked_current = [
            entry["revision"]["revision_id"]
            for entry in entries
            if entry["current_published_successor"]
        ]
        if marked_current != [current_id]:
            raise ResearchValidationError(
                f"{path}: exactly the current revision must be marked current"
            )
        if revisions[current_id]["revision"]["publication_state"] != "published_research":
            raise ResearchValidationError(
                f"{path}: current revision is not published research"
            )

        attempt_ids: set[str] = set()
        for attempt_index, attempt in enumerate(history["publication_attempts"]):
            attempt_path = f"{path}.publication_attempts[{attempt_index}]"
            if attempt["attempt_id"] in attempt_ids:
                raise ResearchValidationError(
                    f"{attempt_path}: duplicate publication-attempt identity"
                )
            attempt_ids.add(attempt["attempt_id"])
            proposed_id = attempt["proposed_revision_id"]
            parent_id = attempt["expected_parent_revision_id"]
            if proposed_id not in revisions or parent_id not in revisions:
                raise ResearchValidationError(
                    f"{attempt_path}: publication revision reference does not resolve"
                )
            proposed = revisions[proposed_id]["revision"]
            parent = revisions[parent_id]["revision"]
            if proposed["parent_revision_id"] != parent_id:
                raise ResearchValidationError(
                    f"{attempt_path}: publication expected parent is not proposal parent"
                )
            if (
                attempt["expected_parent_concurrency_token"]
                != parent["optimistic_concurrency_token"]
            ):
                raise ResearchValidationError(
                    f"{attempt_path}: stale parent concurrency token"
                )
            decision_time = _validate_timestamp(
                attempt["decision_timestamp"],
                f"{attempt_path}.decision_timestamp",
            )
            if decision_time < created_at[proposed_id]:
                raise ResearchValidationError(
                    f"{attempt_path}: publication decision predates proposal"
                )
            if (
                attempt["disposition"] == "accepted"
                and proposed["publication_state"] != "published_research"
            ):
                raise ResearchValidationError(
                    f"{attempt_path}: accepted publication is not published"
                )

    for pin_index, pin in enumerate(pins):
        path = f"revision_state.project_pins[{pin_index}]"
        history = history_by_id.get(pin["history_id"])
        if history is None or history["subject_id"] != pin["subject_id"]:
            raise ResearchValidationError(
                f"{path}: project pin history or subject does not resolve"
            )
        revision_ids = {
            entry["revision"]["revision_id"] for entry in history["revisions"]
        }
        if pin["pinned_revision_id"] not in revision_ids:
            raise ResearchValidationError(
                f"{path}: pinned revision does not resolve"
            )
        if pin["automatic_adoption"]:
            raise ResearchValidationError(
                f"{path}: project cannot silently adopt a newer revision"
            )
        migration = pin["migration"]
        if migration is not None:
            if {
                migration["from_revision_id"],
                migration["to_revision_id"],
            } - revision_ids:
                raise ResearchValidationError(
                    f"{path}: migration revision does not resolve"
                )
            if (
                migration["from_revision_id"] == migration["to_revision_id"]
                or migration["to_revision_id"] != pin["pinned_revision_id"]
            ):
                raise ResearchValidationError(
                    f"{path}: migration does not explicitly change to pinned revision"
                )
            if migration["silent_adoption"]:
                raise ResearchValidationError(
                    f"{path}: silent project migration is prohibited"
                )
            if not migration["evidence_invalidated"]:
                raise ResearchValidationError(
                    f"{path}: project migration must invalidate dependent evidence"
                )
            _validate_timestamp(
                migration["decision_timestamp"],
                f"{path}.migration.decision_timestamp",
            )


def validate_corpus() -> dict[str, int]:
    validator = BoundedSchemaValidator()
    documents = {
        "fixture_library_reference_v1.json": load_json(
            DATA_DIR / "fixture_library_reference_v1.json"
        ),
        "fixture_family_templates_v1.json": load_json(
            DATA_DIR / "fixture_family_templates_v1.json"
        ),
        "component_patterns_v1.json": load_json(DATA_DIR / "component_patterns_v1.json"),
        "failure_modes_v1.json": load_json(DATA_DIR / "failure_modes_v1.json"),
        "synthetic_examples_v1.json": load_json(DATA_DIR / "synthetic_examples_v1.json"),
        "revision_history_examples_v1.json": load_json(
            DATA_DIR / "revision_history_examples_v1.json"
        ),
    }
    reference = documents["fixture_library_reference_v1.json"]
    families = documents["fixture_family_templates_v1.json"]
    components = documents["component_patterns_v1.json"]
    failures = documents["failure_modes_v1.json"]
    synthetic = documents["synthetic_examples_v1.json"]
    revision_state = documents["revision_history_examples_v1.json"]

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
        _validate_unique_and_ordered(records, label)
        for index, record in enumerate(records):
            path = f"{label}[{index}]"
            validator.validate_named(schema_name, record, path)
            if schema_name in {"item", "family", "shop", "process", "benchmark"}:
                _validate_revision(record, path)

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
        "revision_histories": len(revision_state["histories"]),
        "project_pins": len(revision_state["project_pins"]),
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

    source_ids = [item["source_id"] for item in reference["sources"]]
    canonical_urls = [item["canonical_url"] for item in reference["sources"]]
    if len(canonical_urls) != len(set(canonical_urls)):
        raise ResearchValidationError("reference.sources: duplicate canonical source")
    for index, source in enumerate(reference["sources"]):
        try:
            parsed = date.fromisoformat(source["date_accessed"])
        except ValueError as exc:
            raise ResearchValidationError(
                f"reference.sources[{index}]: invalid calendar date"
            ) from exc
        if parsed.isoformat() != source["date_accessed"]:
            raise ResearchValidationError(
                f"reference.sources[{index}]: date is not canonical"
            )

    all_items = (
        reference["engineering_principles"]
        + reference["fixture_patterns"]
        + reference["complete_item_examples"]
        + components["records"]
        + failures["records"]
    )
    all_item_ids = [_identity(item) for item in all_items]
    if len(all_item_ids) != len(set(all_item_ids)):
        raise ResearchValidationError("fixture-library item identities are not unique")
    sources = set(source_ids)
    fingerprints: dict[str, str] = {}
    for index, item in enumerate(all_items):
        path = f"all_items[{index}]"
        if item["provenance"]["record_identity"] != item["item_id"]:
            raise ResearchValidationError(
                f"{item['item_id']}: provenance record identity does not match item"
            )
        missing = set(item["source_ids"]) - sources
        if missing:
            raise ResearchValidationError(
                f"{item['item_id']}: unresolved source identities {sorted(missing)}"
            )
        _validate_item_authority(item, path)
        _validate_interfaces(item, path)
        fingerprint = _semantic_fingerprint(item)
        if fingerprint in fingerprints:
            raise ResearchValidationError(
                f"semantic duplicate records: {fingerprints[fingerprint]} and {item['item_id']}"
            )
        fingerprints[fingerprint] = item["item_id"]

    context_ids = {asset["asset_id"] for asset in reference["process_context_patterns"]}
    context_frame_ids: set[str] = set()
    for index, asset in enumerate(reference["process_context_patterns"]):
        missing = set(asset["source_ids"]) - sources
        if missing:
            raise ResearchValidationError(
                f"{asset['asset_id']}: unresolved source identities {sorted(missing)}"
            )
        _validate_process_asset(asset, f"reference.process_context_patterns[{index}]")
        frame_id = asset["frame"]["frame_id"]
        if frame_id in context_frame_ids:
            raise ResearchValidationError(
                f"{asset['asset_id']}: duplicate process-context frame identity"
            )
        context_frame_ids.add(frame_id)
        geometry_source = asset["geometry_source_item_id"]
        if geometry_source is not None:
            if geometry_source not in all_item_ids:
                raise ResearchValidationError(
                    f"{asset['asset_id']}: geometry-source item does not resolve"
                )
            source_item = next(
                item for item in all_items if item["item_id"] == geometry_source
            )
            if source_item["authority_level"] != asset["geometry_authority"]:
                raise ResearchValidationError(
                    f"{asset['asset_id']}: context geometry authority exceeds source item"
                )

    shop = reference["shop_standard_examples"][0]
    if SCOPE_PRECEDENCE[shop["scope"]] != shop["precedence_level"]:
        raise ResearchValidationError("shop standard scope/precedence mismatch")

    for index, template in enumerate(families["templates"]):
        volume = template["production_volume_range"]
        if volume["maximum"] is not None and volume["minimum"] > volume["maximum"]:
            raise ResearchValidationError(
                f"families.templates[{index}]: production minimum exceeds maximum"
            )
        stations = template.get("station_count_range")
        if stations is not None and stations["minimum"] > stations["maximum"]:
            raise ResearchValidationError(
                f"families.templates[{index}]: station minimum exceeds maximum"
            )

    for index, case in enumerate(synthetic["cases"]):
        missing_context = set(case["process_context_asset_ids"]) - context_ids
        if missing_context:
            raise ResearchValidationError(
                f"{case['case_id']}: unresolved process-context identities "
                f"{sorted(missing_context)}"
            )
        _validate_public_rights(case, f"synthetic.cases[{index}]")

    _validate_revision_history_state(revision_state, validator)

    for item in all_items:
        if (
            item["record_type"] in {"fixture_pattern", "component_application"}
            and "json-schema-2020-12" in item["source_ids"]
        ):
            raise ResearchValidationError(
                f"{item['item_id']}: JSON Schema is not engineering provenance"
            )
    destaco = next(
        source
        for source in reference["sources"]
        if source["source_id"] == "destaco-welding-applications"
    )
    if destaco["canonical_url"] != "https://www.destaco.com/applications/welding":
        raise ResearchValidationError("DESTACO source does not use resolved canonical URL")

    _validate_no_private_payloads(documents)

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
                    f"forbidden research asset committed: {_display_path(path)}"
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
        if key
        not in {
            "sources",
            "complete_item_examples",
            "shop_standard_examples",
            "revision_histories",
            "project_pins",
        }
    )
    print("fixture-library research validation passed")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    print(f"  total_required_reference_records: {total_reference_records}")
    print(f"  schemas: {len(SCHEMA_FILES)}")
    print(
        "  semantic_checks: identity/order, cross-references, revision histories, "
        "project pins, ranges, dates"
    )
    print(
        "  authority_checks: centralized eleven-level category/source/geometry/"
        "BOM/output/validation matrix"
    )
    print(
        "  interface_checks: owned frames, strict dimensions, typed features/"
        "geometry, replacements, movement/contact closure"
    )
    print(
        "  privacy_checks: deterministic release-decision chronology, rights "
        "scope, revocation/export, field/asset release, leakage patterns"
    )
    print(
        "  context_checks: geometry-bounded collision/envelope/access authority "
        "and deliverable separation"
    )
    print(
        "  duplication_checks: record-type engineering-substance projections "
        "independent of tags/provenance/dependency labels"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
