#!/usr/bin/env python3
"""Deterministic catalog-level checks for discovery metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]+")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
CONTRACT_HEADING_RE = re.compile(r"^## (?:Output contract|Report)\s*$", re.MULTILINE)
REQUIRED_ROUTE_KINDS = {
    "lexical": "modality",
    "structural": "modality",
    "code-intelligence": "modality",
    "structured-data": "modality",
    "history": "modality",
    "data-files": "modality",
    "metrics": "modality",
    "docs": "modality",
    "semantic-rag": "modality",
    "graph": "modality",
    "durable-memory": "modality",
    "handoff": "non-retrieval",
    "verify-before-trust": "non-retrieval",
    "runtime-evidence": "non-retrieval",
}
REQUIRED_COMPOSITIONS = {
    "hybrid-rerank",
    "scope-then-search",
    "find-then-pin",
    "resolve-then-pin",
    "recall-then-pin",
    "recall-then-verify",
    "retrieve-then-expand",
    "verify-then-observe",
    "verify-then-hand-off",
}
RETRIEVAL_EVALUATION_BOUNDARY = (
    "Deterministic intended-routing contracts only; passing does not measure "
    "live-model routing accuracy."
)
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "use",
    "via",
    "when",
    "with",
}


@dataclass(frozen=True)
class Component:
    path: str
    kind: str
    name: str
    description: str
    body: str


@dataclass
class ValidationResult:
    errors: list[str]
    component_count: int = 0
    description_chars: int = 0
    description_budget: int = 0
    max_similarity: float = 0.0
    max_similarity_pair: tuple[str, str] | None = None
    similarity_threshold: float = 0.0
    fixture_count: int = 0
    fixture_example_count: int = 0
    contract_count: int = 0
    retrieval_route_count: int = 0
    retrieval_composition_count: int = 0
    retrieval_scenario_count: int = 0
    retrieval_near_miss_count: int = 0


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_frontmatter(path: Path) -> tuple[dict[str, str] | None, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "\n".join(lines)

    fields: dict[str, str] = {}
    active: str | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return fields, "\n".join(lines[index + 1 :])
        if not line:
            continue
        if line[0] in {" ", "\t"}:
            if active is not None:
                fields[active] = f"{fields[active]} {line.strip()}".strip()
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        active = key.strip()
        value = value.strip()
        fields[active] = "" if value[:1] in {"|", ">"} else value
    return None, "\n".join(lines)


def discover_components(repo_root: Path) -> tuple[list[Component], list[str]]:
    plugins_dir = repo_root / "plugins"
    paths = sorted(plugins_dir.glob("*/skills/*/SKILL.md"))
    paths.extend(sorted(plugins_dir.glob("*/agents/*.md")))

    components: list[Component] = []
    errors: list[str] = []
    for path in sorted(paths):
        fields, body = parse_frontmatter(path)
        label = path.relative_to(repo_root).as_posix()
        if fields is None:
            errors.append(f"{label}: missing or unterminated YAML frontmatter")
            continue
        kind = "skill" if path.name == "SKILL.md" else "agent"
        expected = path.parent.name if kind == "skill" else path.stem
        name = _unquote(fields.get("name", ""))
        description = _unquote(fields.get("description", ""))
        if not name or not NAME_RE.fullmatch(name) or name != expected:
            errors.append(f"{label}: invalid or mismatched component name")
        if not description:
            errors.append(f"{label}: missing discovery description")
        components.append(Component(label, kind, name, description, body))
    return components, errors


def content_tokens(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS]


def description_similarity(left: str, right: str) -> float:
    """Return weighted Jaccard overlap of content tokens and adjacent bigrams."""
    left_tokens = content_tokens(left)
    right_tokens = content_tokens(right)
    left_words = set(left_tokens)
    right_words = set(right_tokens)
    left_bigrams = set(zip(left_tokens, left_tokens[1:]))
    right_bigrams = set(zip(right_tokens, right_tokens[1:]))

    def jaccard(first: set[Any], second: set[Any]) -> float:
        union = first | second
        return len(first & second) / len(union) if union else 0.0

    word_score = jaccard(left_words, right_words)
    if not (left_bigrams | right_bigrams):
        return word_score
    return 0.7 * word_score + 0.3 * jaccard(left_bigrams, right_bigrams)


def load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: cannot load JSON: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{label}: top level must be an object")
        return {}
    return data


def _number(
    mapping: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    minimum: float,
    maximum: float | None = None,
) -> float:
    value = mapping.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        errors.append(f"policy: `{key}` must be a number")
        return minimum
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f"{minimum}..{maximum}" if maximum is not None else f">= {minimum}"
        errors.append(f"policy: `{key}` must be {bounds}")
    return float(value)


def _integer(
    mapping: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    minimum: int,
) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"policy: `{key}` must be an integer")
        return minimum
    if value < minimum:
        errors.append(f"policy: `{key}` must be >= {minimum}")
    return value


def _allowlisted_pairs(
    policy: dict[str, Any], component_paths: set[str], errors: list[str]
) -> set[tuple[str, str]]:
    entries = policy.get("similarity_allowlist", [])
    if not isinstance(entries, list):
        errors.append("policy: `similarity_allowlist` must be an array")
        return set()
    allowed: set[tuple[str, str]] = set()
    for index, entry in enumerate(entries):
        label = f"policy: similarity_allowlist[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        paths = entry.get("components")
        reason = entry.get("reason")
        if (
            not isinstance(paths, list)
            or len(paths) != 2
            or not all(isinstance(path, str) for path in paths)
        ):
            errors.append(f"{label}.components must contain exactly two paths")
            continue
        pair = tuple(sorted(paths))
        if pair[0] == pair[1]:
            errors.append(f"{label}.components must name two different components")
        if not set(pair) <= component_paths:
            errors.append(f"{label}.components references an unknown component")
        if not isinstance(reason, str) or len(reason.strip()) < 12:
            errors.append(f"{label}.reason must explain the exception")
        if pair in allowed:
            errors.append(f"{label} duplicates an earlier allowlist pair")
        allowed.add(pair)
    return allowed


def _validate_fixtures(
    fixtures: dict[str, Any],
    components: list[Component],
    minimum_positive: int,
    minimum_negative: int,
    errors: list[str],
) -> tuple[int, int]:
    fixture_map = fixtures.get("components")
    if not isinstance(fixture_map, dict):
        errors.append("fixtures: `components` must be an object")
        return 0, 0

    expected = {component.path for component in components}
    actual = set(fixture_map)
    for path in sorted(expected - actual):
        errors.append(f"fixtures: missing component `{path}`")
    for path in sorted(actual - expected):
        errors.append(f"fixtures: unknown component `{path}`")

    seen_examples: dict[str, str] = {}
    example_count = 0
    components_by_path = {component.path: component for component in components}
    for path in sorted(expected & actual):
        entry = fixture_map[path]
        if not isinstance(entry, dict):
            errors.append(f"fixtures: `{path}` must map to an object")
            continue
        description_terms = set(content_tokens(components_by_path[path].description))
        polarity_terms: dict[str, list[set[str]]] = {}
        for polarity, minimum in (
            ("positive", minimum_positive),
            ("negative", minimum_negative),
        ):
            examples = entry.get(polarity)
            if not isinstance(examples, list) or not all(
                isinstance(example, str) for example in examples
            ):
                errors.append(
                    f"fixtures: `{path}`.{polarity} must be an array of strings"
                )
                continue
            if len(examples) < minimum:
                errors.append(
                    f"fixtures: `{path}`.{polarity} needs at least {minimum} examples"
                )
            term_sets: list[set[str]] = []
            for index, example in enumerate(examples):
                example_count += 1
                fixture_label = f"fixtures: `{path}`.{polarity}[{index}]"
                terms = set(content_tokens(example))
                term_sets.append(terms)
                if len(example.strip()) < 12 or len(terms) < 3:
                    errors.append(f"{fixture_label} is too weak to be a useful query")
                normalized = " ".join(TOKEN_RE.findall(example.lower()))
                previous = seen_examples.get(normalized)
                if previous is not None:
                    errors.append(f"{fixture_label} duplicates {previous}")
                else:
                    seen_examples[normalized] = fixture_label
                if polarity == "positive" and not (terms & description_terms):
                    errors.append(
                        f"{fixture_label} shares no content term with its description"
                    )
            polarity_terms[polarity] = term_sets
        negatives = polarity_terms.get("negative", [])
        if negatives and not any(terms & description_terms for terms in negatives):
            errors.append(
                f"fixtures: `{path}` needs a near-miss negative sharing a description term"
            )
    return len(expected & actual), example_count


def _validate_contracts(
    policy: dict[str, Any], components: list[Component], errors: list[str]
) -> int:
    configured = policy.get("agent_output_contracts")
    if not isinstance(configured, dict):
        errors.append("policy: `agent_output_contracts` must be an object")
        return 0

    agents = {
        component.path: component
        for component in components
        if component.kind == "agent"
    }
    detected = {
        path
        for path, component in agents.items()
        if CONTRACT_HEADING_RE.search(component.body)
    }
    configured_paths = set(configured)
    for path in sorted(detected - configured_paths):
        errors.append(f"policy: output contract marker for `{path}` is not configured")
    for path in sorted(configured_paths - detected):
        errors.append(
            f"policy: configured output contract for `{path}` was not detected"
        )

    valid = 0
    for path in sorted(configured_paths & set(agents)):
        entry = configured[path]
        if not isinstance(entry, dict):
            errors.append(f"policy: agent output contract `{path}` must be an object")
            continue
        marker = entry.get("marker")
        required_terms = entry.get("required_terms")
        if not isinstance(marker, str) or not marker.startswith("## "):
            errors.append(f"policy: agent output contract `{path}` needs a `##` marker")
            continue
        if not isinstance(required_terms, list) or not all(
            isinstance(term, str) and term for term in required_terms
        ):
            errors.append(
                f"policy: agent output contract `{path}` needs required_terms strings"
            )
            continue
        body = agents[path].body
        marker_pattern = re.compile(rf"^{re.escape(marker)}\s*$", re.MULTILINE)
        match = marker_pattern.search(body)
        if match is None:
            errors.append(f"{path}: missing output contract marker `{marker}`")
            continue
        next_heading = re.search(r"^## ", body[match.end() :], re.MULTILINE)
        end = match.end() + next_heading.start() if next_heading else len(body)
        section = body[match.end() : end].strip()
        if not section:
            errors.append(f"{path}: output contract section is empty")
            continue
        for term in required_terms:
            if term.casefold() not in section.casefold():
                errors.append(
                    f"{path}: output contract `{marker}` is missing required term `{term}`"
                )
        valid += 1
    return valid


def _string_list(
    value: Any,
    label: str,
    errors: list[str],
    *,
    minimum: int = 1,
    unique: bool = True,
) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        errors.append(f"{label} must be an array of non-empty strings")
        return []
    if len(value) < minimum:
        errors.append(f"{label} needs at least {minimum} item(s)")
    if unique and len(value) != len(set(value)):
        errors.append(f"{label} must not contain duplicates")
    return value


def _check_fields(
    value: dict[str, Any],
    label: str,
    errors: list[str],
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    for field in sorted(required - set(value)):
        errors.append(f"{label} is missing `{field}`")
    for field in sorted(set(value) - required - optional):
        errors.append(f"{label} has unknown field `{field}`")


def _scenario_text(
    value: Any,
    label: str,
    errors: list[str],
    seen_queries: dict[str, str],
) -> None:
    if not isinstance(value, str) or len(value.strip()) < 12:
        errors.append(f"{label} must be a substantive string")
        return
    terms = content_tokens(value)
    if len(terms) < 3:
        errors.append(f"{label} is too weak to be a useful query")
    normalized = " ".join(TOKEN_RE.findall(value.lower()))
    previous = seen_queries.get(normalized)
    if previous is not None:
        errors.append(f"{label} duplicates {previous}")
    else:
        seen_queries[normalized] = label


def _ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _shipped_plugin_names(repo_root: Path, errors: list[str]) -> set[str]:
    marketplace = load_json(
        repo_root / ".claude-plugin/marketplace.json",
        "marketplace",
        errors,
    )
    entries = marketplace.get("plugins")
    if not isinstance(entries, list):
        errors.append("marketplace: `plugins` must be an array")
        return set()

    shipped: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"marketplace: plugins[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        name = entry.get("name")
        source = entry.get("source")
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            errors.append(f"{label}.name must be a kebab-case plugin name")
            continue
        if name in shipped:
            errors.append(f"{label}.name duplicates shipped plugin `{name}`")
            continue
        if not isinstance(source, str) or not source.strip():
            errors.append(f"{label}.source must be a non-empty path")
            continue

        manifest = load_json(
            repo_root / source / ".claude-plugin/plugin.json",
            f"{label} manifest",
            errors,
        )
        if manifest.get("name") != name:
            errors.append(
                f"{label} manifest name `{manifest.get('name')}` does not match `{name}`"
            )
            continue
        shipped.add(name)
    return shipped


def _validate_retrieval_scenarios(
    data: dict[str, Any],
    repo_root: Path,
    errors: list[str],
) -> tuple[int, int, int, int]:
    if data.get("schema_version") != 1:
        errors.append("retrieval scenarios: `schema_version` must be 1")
    if data.get("evaluation_boundary") != RETRIEVAL_EVALUATION_BOUNDARY:
        errors.append(
            "retrieval scenarios: `evaluation_boundary` must equal the canonical "
            "static-evaluation disclaimer"
        )

    routes = data.get("routes")
    if not isinstance(routes, dict):
        errors.append("retrieval scenarios: `routes` must be an object")
        routes = {}
    actual_route_ids = set(routes)
    required_route_ids = set(REQUIRED_ROUTE_KINDS)
    for route_id in sorted(required_route_ids - actual_route_ids):
        errors.append(f"retrieval scenarios: missing documented route `{route_id}`")
    for route_id in sorted(actual_route_ids - required_route_ids):
        errors.append(f"retrieval scenarios: unknown route `{route_id}`")

    known_plugins = _shipped_plugin_names(repo_root, errors)
    route_plugins: dict[str, str] = {}
    route_tools: dict[str, set[str]] = {}
    for route_id in sorted(actual_route_ids):
        label = f"retrieval scenarios: route `{route_id}`"
        entry = routes[route_id]
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        _check_fields(
            entry,
            label,
            errors,
            required={"kind", "plugin", "tools"},
        )
        kind = entry.get("kind")
        expected_kind = REQUIRED_ROUTE_KINDS.get(route_id)
        if kind not in {"modality", "non-retrieval"}:
            errors.append(f"{label}.kind must be `modality` or `non-retrieval`")
        elif expected_kind is not None and kind != expected_kind:
            errors.append(f"{label}.kind must be `{expected_kind}`")
        plugin = entry.get("plugin")
        if not isinstance(plugin, str) or not NAME_RE.fullmatch(plugin):
            errors.append(f"{label}.plugin must be a kebab-case plugin name")
        else:
            route_plugins[route_id] = plugin
            if plugin not in known_plugins:
                errors.append(f"{label}.plugin references unknown plugin `{plugin}`")
        tools = _string_list(entry.get("tools"), f"{label}.tools", errors)
        route_tools[route_id] = set(tools)

    compositions = data.get("compositions")
    if not isinstance(compositions, dict):
        errors.append("retrieval scenarios: `compositions` must be an object")
        compositions = {}
    actual_composition_ids = set(compositions)
    for name in sorted(REQUIRED_COMPOSITIONS - actual_composition_ids):
        errors.append(f"retrieval scenarios: missing documented composition `{name}`")
    for name in sorted(actual_composition_ids - REQUIRED_COMPOSITIONS):
        errors.append(f"retrieval scenarios: unknown composition `{name}`")

    composition_variants: dict[str, list[list[str]]] = {}
    for name in sorted(actual_composition_ids):
        label = f"retrieval scenarios: composition `{name}`"
        entry = compositions[name]
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        _check_fields(entry, label, errors, required={"step_variants"})
        variants = entry.get("step_variants")
        if not isinstance(variants, list) or not variants:
            errors.append(f"{label}.step_variants must be a non-empty array")
            continue
        valid_variants: list[list[str]] = []
        seen_variants: set[tuple[str, ...]] = set()
        for index, variant in enumerate(variants):
            variant_label = f"{label}.step_variants[{index}]"
            steps = _string_list(
                variant, variant_label, errors, minimum=2, unique=False
            )
            if any(step not in actual_route_ids for step in steps):
                errors.append(f"{variant_label} references an unknown route")
            key = tuple(steps)
            if key in seen_variants:
                errors.append(f"{variant_label} duplicates an earlier step variant")
            seen_variants.add(key)
            if steps:
                valid_variants.append(steps)
        composition_variants[name] = valid_variants

    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list):
        errors.append("retrieval scenarios: `scenarios` must be an array")
        return (
            len(actual_route_ids & required_route_ids),
            len(actual_composition_ids & REQUIRED_COMPOSITIONS),
            0,
            0,
        )

    seen_ids: set[str] = set()
    seen_queries: dict[str, str] = {}
    covered_routes: set[str] = set()
    covered_compositions: set[str] = set()
    covered_composition_variants: set[tuple[str, tuple[str, ...]]] = set()
    near_miss_count = 0
    for index, scenario in enumerate(scenarios):
        label = f"retrieval scenarios: scenarios[{index}]"
        if not isinstance(scenario, dict):
            errors.append(f"{label} must be an object")
            continue
        _check_fields(
            scenario,
            label,
            errors,
            required={
                "id",
                "query",
                "corpus_cues",
                "expected",
                "rationale",
                "near_misses",
            },
        )
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not NAME_RE.fullmatch(scenario_id):
            errors.append(f"{label}.id must be a kebab-case identifier")
        elif scenario_id in seen_ids:
            errors.append(f"{label}.id duplicates `{scenario_id}`")
        else:
            seen_ids.add(scenario_id)
        _scenario_text(scenario.get("query"), f"{label}.query", errors, seen_queries)
        cues = _string_list(scenario.get("corpus_cues"), f"{label}.corpus_cues", errors)
        for cue_index, cue in enumerate(cues):
            if len(cue.strip()) < 4:
                errors.append(
                    f"{label}.corpus_cues[{cue_index}] must be a substantive cue"
                )
        rationale = scenario.get("rationale")
        if not isinstance(rationale, str) or len(rationale.strip()) < 12:
            errors.append(f"{label}.rationale must be a substantive string")

        expected = scenario.get("expected")
        route_id: str | None = None
        composition_name: str | None = None
        participating_routes: list[str] = []
        if not isinstance(expected, dict):
            errors.append(f"{label}.expected must be an object")
        else:
            _check_fields(
                expected,
                f"{label}.expected",
                errors,
                required={"route", "plugins", "tools"},
                optional={"composition"},
            )
            route = expected.get("route")
            if not isinstance(route, str) or route not in actual_route_ids:
                errors.append(f"{label}.expected.route references an unknown route")
            else:
                route_id = route
                covered_routes.add(route)
                participating_routes = [route]

            composition = expected.get("composition")
            if composition is not None:
                if not isinstance(composition, dict):
                    errors.append(f"{label}.expected.composition must be an object")
                else:
                    _check_fields(
                        composition,
                        f"{label}.expected.composition",
                        errors,
                        required={"name", "steps"},
                    )
                    name = composition.get("name")
                    steps = _string_list(
                        composition.get("steps"),
                        f"{label}.expected.composition.steps",
                        errors,
                        minimum=2,
                        unique=False,
                    )
                    if not isinstance(name, str) or name not in actual_composition_ids:
                        errors.append(
                            f"{label}.expected.composition.name references an "
                            "unknown composition"
                        )
                    else:
                        composition_name = name
                        covered_compositions.add(name)
                        if steps not in composition_variants.get(name, []):
                            errors.append(
                                f"{label}.expected.composition.steps do not match "
                                f"contract `{name}`"
                            )
                        else:
                            covered_composition_variants.add((name, tuple(steps)))
                    if route_id is not None and steps and steps[0] != route_id:
                        errors.append(
                            f"{label}.expected.route must equal the first "
                            "composition step"
                        )
                    if steps:
                        participating_routes = steps

            plugins = _string_list(
                expected.get("plugins"), f"{label}.expected.plugins", errors
            )
            expected_plugins = _ordered_unique(
                [
                    route_plugins[step]
                    for step in participating_routes
                    if step in route_plugins
                ]
            )
            if plugins != expected_plugins:
                errors.append(
                    f"{label}.expected.plugins must match participating route "
                    f"plugins {expected_plugins}"
                )

            tools = _string_list(
                expected.get("tools"), f"{label}.expected.tools", errors
            )
            allowed_tools = set().union(
                *(route_tools.get(step, set()) for step in participating_routes)
            )
            for tool in tools:
                if tool not in allowed_tools:
                    errors.append(
                        f"{label}.expected.tools references unknown tool `{tool}`"
                    )
            for step in _ordered_unique(participating_routes):
                if step in route_tools and not (set(tools) & route_tools[step]):
                    errors.append(
                        f"{label}.expected.tools does not represent route `{step}`"
                    )

        near_misses = scenario.get("near_misses")
        if not isinstance(near_misses, list) or not near_misses:
            errors.append(f"{label}.near_misses must be a non-empty array")
            continue
        for near_index, near_miss in enumerate(near_misses):
            near_label = f"{label}.near_misses[{near_index}]"
            near_miss_count += 1
            if not isinstance(near_miss, dict):
                errors.append(f"{near_label} must be an object")
                continue
            _check_fields(
                near_miss,
                near_label,
                errors,
                required={"query", "expected_route", "reason"},
            )
            _scenario_text(
                near_miss.get("query"),
                f"{near_label}.query",
                errors,
                seen_queries,
            )
            near_route = near_miss.get("expected_route")
            if not isinstance(near_route, str) or near_route not in actual_route_ids:
                errors.append(
                    f"{near_label}.expected_route references an unknown route"
                )
            elif near_route == route_id and composition_name is None:
                errors.append(
                    f"{near_label}.expected_route must differ from the primary route"
                )
            reason = near_miss.get("reason")
            if not isinstance(reason, str) or len(reason.strip()) < 12:
                errors.append(f"{near_label}.reason must explain the routing boundary")

    for route_id in sorted(required_route_ids - covered_routes):
        errors.append(f"retrieval scenarios: route `{route_id}` has no scenario")
    for name in sorted(REQUIRED_COMPOSITIONS - covered_compositions):
        errors.append(f"retrieval scenarios: composition `{name}` has no scenario")
    for name, variants in sorted(composition_variants.items()):
        for steps in variants:
            if (name, tuple(steps)) not in covered_composition_variants:
                errors.append(
                    f"retrieval scenarios: composition `{name}` step variant "
                    f"{steps} has no scenario"
                )
    return (
        len(actual_route_ids & required_route_ids),
        len(actual_composition_ids & REQUIRED_COMPOSITIONS),
        len(scenarios),
        near_miss_count,
    )


def validate_repository(
    repo_root: Path,
    *,
    policy_path: Path | None = None,
    fixtures_path: Path | None = None,
    retrieval_scenarios_path: Path | None = None,
) -> ValidationResult:
    repo_root = repo_root.resolve()
    policy_path = policy_path or (
        repo_root / "plugins/plugin-forge/quality/discovery-policy.json"
    )
    fixtures_path = fixtures_path or (
        repo_root / "plugins/plugin-forge/quality/discovery-fixtures.json"
    )
    retrieval_scenarios_path = retrieval_scenarios_path or (
        repo_root / "plugins/plugin-forge/quality/retrieval-scenarios.json"
    )
    errors: list[str] = []
    components, discovery_errors = discover_components(repo_root)
    errors.extend(discovery_errors)
    policy = load_json(policy_path, "policy", errors)
    fixtures = load_json(fixtures_path, "fixtures", errors)
    retrieval_scenarios = load_json(
        retrieval_scenarios_path, "retrieval scenarios", errors
    )

    budget = _integer(
        policy,
        "aggregate_description_max_chars",
        errors,
        minimum=1,
    )
    threshold = _number(
        policy,
        "similarity_threshold",
        errors,
        minimum=0,
        maximum=1,
    )
    minimum_positive = _integer(
        policy,
        "minimum_positive_fixtures",
        errors,
        minimum=1,
    )
    minimum_negative = _integer(
        policy,
        "minimum_negative_fixtures",
        errors,
        minimum=1,
    )

    description_chars = sum(len(component.description) for component in components)
    if description_chars > budget:
        errors.append(
            f"discovery descriptions use {description_chars} chars, exceeding budget {budget}"
        )

    component_paths = {component.path for component in components}
    allowed_pairs = _allowlisted_pairs(policy, component_paths, errors)
    max_similarity = 0.0
    max_pair: tuple[str, str] | None = None
    for index, left in enumerate(components):
        for right in components[index + 1 :]:
            score = description_similarity(left.description, right.description)
            pair = tuple(sorted((left.path, right.path)))
            if score > max_similarity:
                max_similarity = score
                max_pair = pair
            if score >= threshold and pair not in allowed_pairs:
                errors.append(
                    f"descriptions too similar ({score:.3f} >= {threshold:.3f}): "
                    f"`{pair[0]}` and `{pair[1]}`"
                )

    fixture_count, fixture_example_count = _validate_fixtures(
        fixtures,
        components,
        minimum_positive,
        minimum_negative,
        errors,
    )
    contract_count = _validate_contracts(policy, components, errors)
    (
        retrieval_route_count,
        retrieval_composition_count,
        retrieval_scenario_count,
        retrieval_near_miss_count,
    ) = _validate_retrieval_scenarios(retrieval_scenarios, repo_root, errors)

    return ValidationResult(
        errors=errors,
        component_count=len(components),
        description_chars=description_chars,
        description_budget=budget,
        max_similarity=max_similarity,
        max_similarity_pair=max_pair,
        similarity_threshold=threshold,
        fixture_count=fixture_count,
        fixture_example_count=fixture_example_count,
        contract_count=contract_count,
        retrieval_route_count=retrieval_route_count,
        retrieval_composition_count=retrieval_composition_count,
        retrieval_scenario_count=retrieval_scenario_count,
        retrieval_near_miss_count=retrieval_near_miss_count,
    )


def _print_report(result: ValidationResult) -> None:
    print(
        "Discovery budget: "
        f"{result.description_chars}/{result.description_budget} chars "
        f"across {result.component_count} components"
    )
    pair = (
        f" (`{result.max_similarity_pair[0]}` vs `{result.max_similarity_pair[1]}`)"
        if result.max_similarity_pair
        else ""
    )
    print(
        f"Description similarity: max {result.max_similarity:.3f}{pair}; "
        f"threshold {result.similarity_threshold:.3f}"
    )
    print(
        f"Discovery fixtures: {result.fixture_count} components, "
        f"{result.fixture_example_count} positive/negative examples"
    )
    print(f"Agent output contracts: {result.contract_count} validated")
    print(
        "Retrieval contracts: "
        f"{result.retrieval_route_count} routes, "
        f"{result.retrieval_composition_count} compositions, "
        f"{result.retrieval_scenario_count} scenarios, "
        f"{result.retrieval_near_miss_count} near misses"
    )
    print("Evaluation boundary: deterministic contracts, not live-model accuracy")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[3],
    )
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--retrieval-scenarios", type=Path)
    args = parser.parse_args(argv)
    result = validate_repository(
        args.repo_root,
        policy_path=args.policy,
        fixtures_path=args.fixtures,
        retrieval_scenarios_path=args.retrieval_scenarios,
    )
    _print_report(result)
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if result.errors:
        print(
            f"FAIL: {len(result.errors)} catalog quality problem(s)",
            file=sys.stderr,
        )
        return 1
    print("OK: catalog discovery quality gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
