"""Inline $ref/$defs so strict json_schema works on runtimes without ref support."""

from __future__ import annotations

from typing import Any


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].rsplit("/", 1)[-1]
                resolved = walk(defs[name])
                # Pydantic puts field-specific instructions beside enum refs. Dropping
                # those siblings silently discards polarity/modality guidance.
                siblings = {k: walk(v) for k, v in node.items() if k != "$ref"}
                annotations = {
                    "title",
                    "description",
                    "default",
                    "examples",
                    "deprecated",
                    "readOnly",
                    "writeOnly",
                }
                if any(
                    k in resolved and k not in annotations and resolved[k] != v
                    for k, v in siblings.items()
                ):
                    return {"allOf": [resolved, siblings]}
                return {**resolved, **siblings}
            return {k: walk(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    out = walk(schema)
    assert isinstance(out, dict)
    return out


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Require every property on the wire, including fields with Pydantic defaults.

    An optional array such as sentences otherwise lets a constrained model omit the entire
    answer. Nullable properties remain nullable; parsing/semantic validation is still required.
    """

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(value) for value in node]
        if not isinstance(node, dict):
            return node
        out = {key: walk(value) for key, value in node.items() if key != "default"}
        if "properties" in out:
            out["required"] = list(out["properties"])
            out["additionalProperties"] = False
        return out

    result = walk(inline_refs(schema))
    assert isinstance(result, dict)
    return result
