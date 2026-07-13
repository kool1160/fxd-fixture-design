"""Deterministic reader for FXD's small, synthetic STEP evidence contract.

The records are Part 21-shaped application records intended for legal,
dependency-free tests.  They are not a replacement for an ISO 10303 parser;
the future kernel adapter can translate full STEP into this same model.
"""

from dataclasses import dataclass
import re
from hashlib import sha256
from pathlib import Path

from .aabb import Aabb, Transform, Vec3
from .product_model import Body, Component, Edge, Face, ProductModel


class StepImportError(ValueError):
    """Raised when a file is malformed or outside the supported contract."""


_RECORD = re.compile(r"#(?P<id>\d+)\s*=\s*(?P<kind>[A-Z0-9_]+)\s*\((?P<body>.*)\)\s*;", re.I)


def _fields(body: str) -> list[str]:
    result, current, quoted = [], [], False
    for char in body:
        if char == "'":
            quoted = not quoted
        if char == "," and not quoted:
            result.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    result.append("".join(current).strip())
    return [field[1:-1] if len(field) >= 2 and field[0] == "'" and field[-1] == "'" else field for field in result]


def _float(value: str, context: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise StepImportError(f"invalid numeric value {value!r} in {context}") from exc


def import_step(source: str | Path, *, source_name: str | None = None) -> ProductModel:
    path = Path(source) if isinstance(source, Path) else None
    raw = path.read_bytes() if path else source.encode("utf-8")
    text = raw.decode("utf-8", errors="strict")
    records = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("/*") or line.upper() in {"ISO-10303-21;", "ENDSEC;", "END-ISO-10303-21;"}:
            continue
        match = _RECORD.fullmatch(line)
        if not match:
            if line.upper() in {"HEADER;", "DATA;"} or line.startswith("FILE_"):
                continue
            raise StepImportError(f"unsupported or malformed STEP record: {line}")
        records[match.group("id")] = (match.group("kind").upper(), _fields(match.group("body")))

    products, instances, product_bodies, body_by_id, units = {}, [], {}, {}, None
    for kind, fields in records.values():
        if kind == "PRODUCT":
            if len(fields) < 2:
                raise StepImportError("PRODUCT requires identity and name")
            products[fields[0]] = fields[1]
        elif kind == "FXD_INSTANCE":
            if len(fields) != 6:
                raise StepImportError("FXD_INSTANCE requires id, product, parent, x, y, z")
            instances.append(fields)
        elif kind == "FXD_BODY":
            if len(fields) != 8:
                raise StepImportError("FXD_BODY requires id, product, min xyz, max xyz")
            values = [_float(value, "FXD_BODY") for value in fields[2:]]
            body = Body(fields[0], Aabb(Vec3(*values[:3]), Vec3(*values[3:])))
            if fields[0] in body_by_id:
                raise StepImportError(f"duplicate body identity {fields[0]!r}")
            body_by_id[fields[0]] = body
            product_bodies.setdefault(fields[1], []).append(body)
        elif kind == "FXD_FACE":
            if len(fields) != 2:
                raise StepImportError("FXD_FACE requires body and identity")
            if fields[0] not in body_by_id:
                raise StepImportError(f"FACE references unknown body {fields[0]!r}")
            body = body_by_id[fields[0]]
            body_by_id[fields[0]] = Body(body.identity, body.bounds, body.faces + (Face(fields[1]),), body.edges)
        elif kind == "FXD_EDGE":
            if len(fields) != 2:
                raise StepImportError("FXD_EDGE requires body and identity")
            if fields[0] not in body_by_id:
                raise StepImportError(f"EDGE references unknown body {fields[0]!r}")
            body = body_by_id[fields[0]]
            body_by_id[fields[0]] = Body(body.identity, body.bounds, body.faces, body.edges + (Edge(fields[1]),))
        elif kind == "SI_UNIT":
            normalized = {field.strip(".").upper() for field in fields}
            if not normalized.intersection({"MILLI", "MILLIMETRE", "MILLIMETER"}) or "METRE" not in normalized and "METER" not in normalized:
                raise StepImportError("only explicit millimetre SI_UNIT is supported")
            units = "mm"
        elif kind not in {"FILE_DESCRIPTION", "FILE_NAME", "FILE_SCHEMA"}:
            raise StepImportError(f"unsupported STEP entity {kind}")

    if units is None:
        raise StepImportError("STEP input must declare SI_UNIT millimetres")
    if not products or not instances:
        raise StepImportError("STEP input must contain PRODUCT and FXD_INSTANCE records")
    known = {fields[0] for fields in instances}
    instance_by_id = {fields[0]: fields for fields in instances}
    world_transforms = {}

    def world_transform(identity: str, visiting: set[str] | None = None) -> Transform:
        if identity in world_transforms:
            return world_transforms[identity]
        visiting = set() if visiting is None else visiting
        if identity in visiting:
            raise StepImportError(f"cyclic instance parentage at {identity!r}")
        visiting.add(identity)
        fields = instance_by_id[identity]
        local = Transform(Vec3(_float(fields[3], "FXD_INSTANCE"), _float(fields[4], "FXD_INSTANCE"), _float(fields[5], "FXD_INSTANCE")))
        if fields[2]:
            local = Transform(world_transform(fields[2], visiting).translation + local.translation)
        world_transforms[identity] = local
        return local

    components = []
    for identity, product, parent, x, y, z in instances:
        if product not in products:
            raise StepImportError(f"instance {identity!r} references unknown product {product!r}")
        if parent and parent not in known:
            raise StepImportError(f"instance {identity!r} references unknown parent {parent!r}")
        component_bodies = tuple(body_by_id[body.identity] for body in product_bodies.get(product, ()))
        if not component_bodies and not parent:
            # Assembly products may be containers; their child instances carry geometry.
            pass
        elif not component_bodies:
            raise StepImportError(f"product {product!r} has no FXD_BODY")
        components.append(Component(identity, products[product], parent or None, world_transform(identity), component_bodies, product))
    return ProductModel(units, tuple(components), source_name or (path.name if path else "<memory>"), sha256(raw).hexdigest(), raw)
