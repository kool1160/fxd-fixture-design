"""Validate the non-runtime fixture-library research package.

This standard-library-only checker implements the bounded JSON Schema
Draft 2020-12 vocabulary used by the research contracts and the cross-record
engineering invariants JSON Schema cannot express.  Production code does not
import this module.
"""

from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Iterable


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
            r"png|jpe?g|gif|bmp|tiff?)(?:$|[?#\s\"'])"
        ),
    ),
    (
        "customer/employer asset path",
        re.compile(r"(?i)(?:customer|employer)[-_ ]?(?:asset|cad|fixture|file|path)[/\\]"),
    ),
)

IDENTITY_FIELDS = {
    "item_id",
    "source_id",
    "template_id",
    "asset_id",
    "case_id",
    "name",
    "title",
    "revision",
    "source_ids",
    "record_identity",
    "audit_record_identity",
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
            if value.startswith(("https://", "http://")):
                continue
            for label, pattern in FORBIDDEN_CONTENT_PATTERNS:
                if pattern.search(value):
                    raise ResearchValidationError(
                        f"{filename}:{path}: likely private payload reference ({label})"
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


def _validate_timestamp(value: str, path: str) -> None:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ResearchValidationError(f"{path}: invalid UTC calendar timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ResearchValidationError(f"{path}: timestamp is not canonical")


def _validate_revision(record: dict[str, Any], path: str) -> None:
    revision = record["revision"]
    _validate_timestamp(revision["created_at"], f"{path}.revision.created_at")
    for field in ("parent_revision_id", "restores_content_from_revision_id"):
        if revision[field] == revision["revision_id"]:
            raise ResearchValidationError(
                f"{path}.revision: invalid ancestry; {field} is the current revision"
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
    required_non_null = {
        "point": {"point"},
        "tool_center_point": {"point"},
        "axis": {"point", "axis"},
        "plane": {"point", "normal"},
        "bounded_region": {"bounds_min", "bounds_max"},
        "contact_patch": {"point", "normal", "bounds_min", "bounds_max"},
        "envelope": {"bounds_min", "bounds_max"},
        "sensor_field": {"bounds_min", "bounds_max"},
    }[kind]
    for field in required_non_null:
        if geometry[field] is None:
            raise ResearchValidationError(
                f"{path}: {kind} geometry requires {field}"
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
    for index, feature in enumerate(interface["features"]):
        feature_path = f"{path}.features[{index}]"
        feature_ids.append(feature["feature_id"])
        if feature["owning_interface_id"] != interface["interface_id"]:
            raise ResearchValidationError(
                f"{feature_path}: owning interface reference does not resolve"
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
        applicable_dimensions = {
            "hole": ("diameter",),
            "pin": ("diameter", "length"),
            "bushing": ("diameter", "length"),
            "slot": ("width", "length"),
            "rail": ("width", "height"),
            "planar_face": (),
            "weld_mount": (),
            "table_grid_mount": ("pitch",),
            "custom_datum_frame": (),
        }[feature["feature_type"]]
        for dimension in applicable_dimensions:
            if feature["dimensions"][dimension] is None:
                raise ResearchValidationError(
                    f"{feature_path}: {feature['feature_type']} requires {dimension}"
                )
        if feature["feature_type"] in {"slot", "rail"} and adjustment is None:
            raise ResearchValidationError(
                f"{feature_path}: adjustable feature lacks adjustment range"
            )
    if len(feature_ids) != len(set(feature_ids)):
        raise ResearchValidationError(f"{path}: duplicate mounting feature identity")


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
        frame_ids.add(interface["frame"]["frame_id"])
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
        _validate_geometry(interface["geometry"], f"{interface_path}.geometry")
    if len(functional_ids) != len(set(functional_ids)):
        raise ResearchValidationError(f"{path}: duplicate functional-interface identity")
    missing_contacts = set(item["contact_points"]) - set(functional_ids)
    if missing_contacts:
        raise ResearchValidationError(
            f"{path}: contact references do not resolve {sorted(missing_contacts)}"
        )
    closure = item["open_closed_states"]
    if closure["claimed"]:
        if not closure["open_state_id"] or not closure["closed_state_id"]:
            raise ResearchValidationError(f"{path}: claimed open/closed states incomplete")
        if {closure["open_state_id"], closure["closed_state_id"]} - set(states):
            raise ResearchValidationError(f"{path}: open/closed state reference missing")
    elif closure["open_state_id"] is not None or closure["closed_state_id"] is not None:
        raise ResearchValidationError(f"{path}: unclaimed open/closed states must be null")
    replacement = item["replacement_compatibility"]
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
    if authority not in AUTHORITY_LEVELS:
        raise ResearchValidationError(f"{path}: unknown authority level")
    output = item["export_participation"]
    validation = item["validation_participation"]
    if any(value not in PARTICIPATION_VALUES for value in output.values()):
        raise ResearchValidationError(f"{path}: illegal output participation")
    if any(value not in PARTICIPATION_VALUES for value in validation.values()):
        raise ResearchValidationError(f"{path}: illegal validation participation")
    no_geometry_output = {
        "metadata_only_commercial_component",
        "provisional_review_envelope",
        "fixture_family_template",
        "shop_standard",
        "process_context_asset",
        "private_benchmark_reference",
        "public_engineering_knowledge",
    }
    if authority in no_geometry_output and any(
        output[field] != "excluded" for field in FIXTURE_OUTPUT_FIELDS
    ):
        raise ResearchValidationError(
            f"{path}: authority contradicts manufacturing output participation"
        )
    if authority in {
        "metadata_only_commercial_component",
        "provisional_review_envelope",
        "public_engineering_knowledge",
    } and (
        validation["exact_collision"] != "excluded"
        or validation["exact_clearance"] != "excluded"
        or validation["manufacturing_release"] != "excluded"
    ):
        raise ResearchValidationError(
            f"{path}: authority contradicts exact validation participation"
        )


def _normalize_semantic(value: Any, field_name: str | None = None) -> Any:
    if field_name in IDENTITY_FIELDS:
        return None
    if isinstance(value, str):
        tokens = re.findall(r"[a-z0-9]+", value.casefold())
        return " ".join(sorted(tokens))
    if isinstance(value, list):
        normalized = [_normalize_semantic(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, dict):
        return {
            key: _normalize_semantic(item, key)
            for key, item in sorted(value.items())
            if key not in IDENTITY_FIELDS
        }
    return value


def _semantic_fingerprint(record: dict[str, Any]) -> str:
    normalized = _normalize_semantic(record)
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
    _validate_timestamp(rights["approval_timestamp"], f"{path}.rights.approval_timestamp")
    for field in ("expiry_timestamp", "revocation_timestamp"):
        if rights[field] is not None:
            _validate_timestamp(rights[field], f"{path}.rights.{field}")
    if rights["revocation_state"] == "revoked":
        if rights["revocation_timestamp"] is None or not rights["revocation_reason"]:
            raise ResearchValidationError(f"{path}: revoked rights lack timestamp/reason")
        if rights["public_release_permission"] or rights["export_permission"]:
            raise ResearchValidationError(f"{path}: revoked rights still permit release")
    elif rights["revocation_timestamp"] is not None or rights["revocation_reason"] is not None:
        raise ResearchValidationError(f"{path}: non-revoked rights carry revocation data")

    if case["privacy_classification"] == "synthetic_public":
        if (
            rights["rights_basis"] != "original_synthetic_work"
            or not rights["public_release_permission"]
            or not rights["export_permission"]
            or rights["revocation_state"] != "not_revoked"
            or case["linked_private_asset_identities"]
        ):
            raise ResearchValidationError(
                f"{path}: public synthetic case violates fail-closed release boundary"
            )
    if case["privacy_classification"] == "selected_public_release":
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
    states = [state["state_id"] for state in asset["movement_states"]]
    if len(states) != len(set(states)):
        raise ResearchValidationError(f"{path}: duplicate movement-state identity")
    for state in asset["movement_states"]:
        if (
            asset["geometry_authority"] == "provisional_review_envelope"
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
            _validate_geometry(envelope["geometry"], f"{path}.{group}[{index}].geometry")
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
    }
    reference = documents["fixture_library_reference_v1.json"]
    families = documents["fixture_family_templates_v1.json"]
    components = documents["component_patterns_v1.json"]
    failures = documents["failure_modes_v1.json"]
    synthetic = documents["synthetic_examples_v1.json"]

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
    for index, asset in enumerate(reference["process_context_patterns"]):
        missing = set(asset["source_ids"]) - sources
        if missing:
            raise ResearchValidationError(
                f"{asset['asset_id']}: unresolved source identities {sorted(missing)}"
            )
        _validate_process_asset(asset, f"reference.process_context_patterns[{index}]")
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
        if key not in {"sources", "complete_item_examples", "shop_standard_examples"}
    )
    print("fixture-library research validation passed")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    print(f"  total_required_reference_records: {total_reference_records}")
    print(f"  schemas: {len(SCHEMA_FILES)}")
    print("  semantic_checks: identity/order, references, revisions, ranges, dates")
    print("  authority_checks: category, exact/provisional, output, validation")
    print("  interface_checks: frames, axes, typed features, movement closure")
    print("  privacy_checks: rights lifecycle, field/asset release, leakage patterns")
    print("  duplication_checks: deterministic substantive-field fingerprints")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
