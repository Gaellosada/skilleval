"""A test file's YAML read into plain values, and the small validators every section shares."""

from collections.abc import Collection
from pathlib import Path
from typing import Any

import yaml

from skilleval.testfile.paths import find_root
from skilleval.testfile.schema import LoadError, at

KINDS = frozenset({"static-check"})


def read_document(path: Path) -> dict[str, Any]:
    """The file as a mapping. The YAML is composed into a node tree and walked, so a repeated
    key is an error at its dotted key where PyYAML would silently keep the last value."""
    try:
        node = yaml.compose(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
        if not isinstance(node, yaml.MappingNode):
            raise LoadError(path, "", "the document must be a mapping holding root, tests or templates")
        document: dict[str, Any] = _build(node, path, "")
    except (OSError, yaml.YAMLError) as e:
        raise LoadError(path, "", f"cannot read the file: {e}") from e
    return document


def _build(node: yaml.Node, path: Path, key: str) -> Any:
    if isinstance(node, yaml.MappingNode):
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            k = _build(key_node, path, key)
            if k in mapping:
                raise LoadError(path, at(key, k), f"key {k!r} is repeated; a key appears once in a mapping")
            mapping[k] = _build(value_node, path, at(key, k))
        return mapping
    if isinstance(node, yaml.SequenceNode):
        return [_build(item, path, at(key, i)) for i, item in enumerate(node.value)]
    return yaml.constructor.SafeConstructor().construct_object(node)


def mapping(value: object, path: Path, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LoadError(path, key, f"must be a mapping, not {value!r}")
    return value


def known_keys(mapping: dict[str, Any], allowed: Collection[str], path: Path, key: str) -> None:
    for k in mapping:
        if k not in allowed:
            known = ", ".join(sorted(allowed))
            raise LoadError(path, at(key, k), f"unknown key {k!r}; the keys here are {known}")


def kind_of(body: dict[str, Any], path: Path, key: str) -> str:
    """The `kind` of a test or template body: required and one of `KINDS`."""
    kind = body.get("kind")
    if kind is None:
        raise LoadError(path, at(key, "kind"), "kind is missing")
    if kind not in KINDS:
        kinds = ", ".join(sorted(KINDS))
        raise LoadError(path, at(key, "kind"), f"kind must be one of {kinds}, not {kind!r}")
    return str(kind)


def root_of(document: dict[str, Any], path: Path) -> Path | None:
    """The project root named by `root`, None when the file declares none."""
    marker = document.get("root")
    if marker is None:
        return None
    if not isinstance(marker, str):
        raise LoadError(path, "root", f"root names a marker file or directory, not {marker!r}")
    try:
        return find_root(path, marker)
    except FileNotFoundError:
        raise LoadError(path, "root", f"no ancestor of the file holds the marker {marker!r}") from None
