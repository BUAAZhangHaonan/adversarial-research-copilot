"""Registered file templates and reproducible invocation snapshots."""
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jinja2 import DictLoader, Environment, FileSystemLoader, PackageLoader, StrictUndefined, meta


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate_manifest_key:{key}")
        result[key] = value
    return result


def schema_example(schema: dict[str, Any], root: dict[str, Any] | None = None,
                   seen: frozenset[str] = frozenset()) -> Any:
    """Mechanical shape: never synthesize research facts or identifiers."""
    root = root or schema
    ref = schema.get("$ref")
    if ref:
        if ref in seen or not ref.startswith("#/"):
            return None
        target: Any = root
        for segment in ref[2:].split("/"):
            target = target[segment.replace("~1", "/").replace("~0", "~")]
        return schema_example(target, root, seen | {ref})
    if "const" in schema:
        return schema["const"]
    if "anyOf" in schema or "oneOf" in schema:
        choices = schema.get("anyOf", schema.get("oneOf", []))
        if any(s.get("type") == "null" for s in choices):
            return None
        return schema_example(choices[0], root, seen) if choices else None
    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        return {key: schema_example(value, root, seen)
                for key, value in schema.get("properties", {}).items()}
    if kind == "array":
        return []
    return None


@dataclass(frozen=True)
class RenderedPrompt:
    prompt_id: str
    messages: list[dict[str, str]]
    source_hashes: dict[str, str]
    dependencies: tuple[str, ...]
    prompt_hash: str
    tool_descriptions: dict[str, str]
    sources: dict[str, str]

    def save_snapshot(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_json(asdict(self)) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load_snapshot(cls, path: str | Path) -> "RenderedPrompt":
        payload = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        return cls.from_snapshot(payload)

    @classmethod
    def from_snapshot(cls, payload: dict[str, Any]) -> "RenderedPrompt":
        payload = dict(payload)
        payload["dependencies"] = tuple(payload["dependencies"])
        obj = cls(**payload)
        if set(obj.source_hashes) != set(obj.sources) or set(obj.dependencies) != set(obj.sources):
            raise ValueError("snapshot_dependency_mismatch")
        if any(_hash(text) != obj.source_hashes[name] for name, text in obj.sources.items()):
            raise ValueError("snapshot_source_hash_mismatch")
        if obj.prompt_hash != _hash(_json({"messages": obj.messages, "tools": obj.tool_descriptions,
                                          "sources": obj.source_hashes, "prompt_id": obj.prompt_id})):
            raise ValueError("snapshot_render_hash_mismatch")
        return obj


class PromptLoader:
    def __init__(self, resource_root: str | Path | None = None) -> None:
        loader = FileSystemLoader(str(Path(resource_root).resolve())) if resource_root is not None else PackageLoader("arc_prompt_assets", "")
        self.env = Environment(loader=loader, undefined=StrictUndefined, autoescape=False,
                               keep_trailing_newline=True)
        self.manifest_text = self._source("manifest.json")
        self.manifest = json.loads(self.manifest_text, object_pairs_hook=_unique_object)
        self.registered_files = {"manifest.json"}
        for entry in self.manifest["prompts"].values():
            self.registered_files.update(entry["system"])
            self.registered_files.update([entry["task_template"], entry["repair_template"]])
        self.registered_files.update(self.manifest["tools"].values())
        self.registered_files.update(self.manifest["reports"].values())
        for name in sorted(self.registered_files):
            if name != "manifest.json":
                self._dependencies(name)

    @property
    def bundle_hash(self) -> str:
        return _hash(_json({name: _hash(self._source(name)) for name in sorted(self.registered_files)}))

    def _source(self, name: str) -> str:
        if name.startswith(("/", "\\")) or ".." in Path(name).parts:
            raise ValueError("invalid_template_path")
        return self.env.loader.get_source(self.env, name)[0]

    def _dependencies(self, name: str, active: frozenset[str] = frozenset()) -> dict[str, str]:
        if name not in self.registered_files:
            raise ValueError(f"unregistered_template:{name}")
        if name in active:
            raise ValueError("cyclic_template_dependency")
        source = self._source(name)
        result = {name: source}
        for dependency in meta.find_referenced_templates(self.env.parse(source)):
            if dependency is None:
                raise ValueError("dynamic_template_dependency")
            result.update(self._dependencies(dependency, active | {name}))
        return result

    def tool_description(self, name: str) -> str:
        if name not in self.manifest["tools"]:
            raise ValueError(f"unregistered_tool:{name}")
        return self.env.get_template(self.manifest["tools"][name]).render()

    def render(self, prompt_id: str, data: dict[str, Any], *, schema: dict[str, Any],
               tool_profile: list[str] | None = None, repair: dict[str, Any] | None = None) -> RenderedPrompt:
        if prompt_id not in self.manifest["prompts"]:
            raise ValueError(f"unregistered_prompt:{prompt_id}")
        entry = self.manifest["prompts"][prompt_id]
        names = sorted(set(tool_profile or []))
        if set(names) - set(entry["tools"]):
            raise ValueError("tool_profile_not_allowed")
        variables = {"task_type": prompt_id, "task_id": data["task_id"],
                     "output_language": "zh", "payload_json": _json({"subject": data["subject"], "payload": data["payload"]}),
                     "output_schema_json": _json(schema),
                     "output_example_json": _json(data.get("output_example", schema_example(schema)))}
        task_template = entry["task_template"]
        if repair is not None:
            task_template = entry["repair_template"]
            variables.update(subject_json=_json(data["subject"]),
                             previous_response_json=_json(repair["previous_response"]),
                             validation_errors_json=_json(repair["validation_errors"]))
        sources = {"manifest.json": self.manifest_text}
        for name in entry["system"] + [entry["task_template"], entry["repair_template"]] + [self.manifest["tools"][n] for n in names]:
            sources.update(self._dependencies(name))
        messages = [{"role": "system", "content": "\n\n".join(self.env.get_template(name).render(**variables).rstrip() for name in entry["system"])},
                    {"role": "user", "content": self.env.get_template(task_template).render(**variables)}]
        descriptions = {name: self.tool_description(name) for name in names}
        hashes = {name: _hash(value) for name, value in sorted(sources.items())}
        digest = _hash(_json({"messages": messages, "tools": descriptions, "sources": hashes, "prompt_id": prompt_id}))
        return RenderedPrompt(prompt_id, messages, hashes, tuple(sorted(sources)), digest, descriptions, sources)

    def render_report(self, name: str, data: dict[str, Any]) -> str:
        if name not in self.manifest["reports"]:
            raise ValueError(f"unregistered_report:{name}")
        template = self.manifest["reports"][name]
        self._dependencies(template)
        return self.env.get_template(template).render(**data)

    @staticmethod
    def render_repair(snapshot: RenderedPrompt, data: dict[str, Any], *, schema: dict[str, Any],
                      previous_response: Any, validation_errors: Any) -> RenderedPrompt:
        return render_repair(snapshot, data, schema=schema, previous_response=previous_response,
                             validation_errors=validation_errors)


def render_repair(snapshot: RenderedPrompt, data: dict[str, Any], *, schema: dict[str, Any],
                  previous_response: Any, validation_errors: Any) -> RenderedPrompt:
    """Render only persisted Markdown sources; no live resource lookup."""
    if any(_hash(text) != snapshot.source_hashes.get(name) for name, text in snapshot.sources.items()):
        raise ValueError("snapshot_source_hash_mismatch")
    manifest = json.loads(snapshot.sources["manifest.json"], object_pairs_hook=_unique_object)
    template_name = manifest["prompts"][snapshot.prompt_id]["repair_template"]
    env = Environment(loader=DictLoader(snapshot.sources), undefined=StrictUndefined,
                      autoescape=False, keep_trailing_newline=True)
    variables = {"task_id": data["task_id"], "subject_json": _json(data["subject"]),
                 "payload_json": _json({"subject": data["subject"], "payload": data["payload"]}),
                 "previous_response_json": _json(previous_response),
                 "validation_errors_json": _json(validation_errors), "output_schema_json": _json(schema)}
    messages = [dict(snapshot.messages[0]),
                {"role": "user", "content": env.get_template(template_name).render(**variables)}]
    digest = _hash(_json({"messages": messages, "tools": snapshot.tool_descriptions,
                         "sources": snapshot.source_hashes, "prompt_id": snapshot.prompt_id}))
    return RenderedPrompt(snapshot.prompt_id, messages, dict(snapshot.source_hashes), snapshot.dependencies,
                          digest, dict(snapshot.tool_descriptions), dict(snapshot.sources))


def lint_production_prompts(source_root: str | Path, adapter: str = "runtime.py") -> list[str]:
    """AST boundary check over ARC production code only, never references."""
    failures: list[str] = []
    for path in sorted(Path(source_root).rglob("*.py")):
        if "references" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        is_adapter = path.name == adapter
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                fields = {key.value: value for key, value in zip(node.keys, node.values)
                          if isinstance(key, ast.Constant) and isinstance(key.value, str)}
                description = fields.get("description")
                if isinstance(description, (ast.Constant, ast.JoinedStr)):
                    failures.append(f"{path.name}:{node.lineno}:inline_tool_description")
                role, content = fields.get("role"), fields.get("content")
                if (path.name != "prompting.py" and isinstance(role, ast.Constant)
                        and role.value in {"system", "user"}
                        and isinstance(content, (ast.Constant, ast.JoinedStr))):
                    failures.append(f"{path.name}:{node.lineno}:inline_message")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                if not is_adapter and any(m == "openai" or m.startswith("openai.") for m in modules):
                    failures.append(f"{path.name}:{node.lineno}:sdk_outside_adapter")
            if not isinstance(node, ast.Call):
                continue
            call = ast.unparse(node.func)
            if call.endswith(".from_string"):
                failures.append(f"{path.name}:{node.lineno}:inline_template")
            if not is_adapter and (".completions.create" in call or ".responses.create" in call or call.endswith(".chat")):
                failures.append(f"{path.name}:{node.lineno}:direct_model_call")
            for keyword in node.keywords:
                if keyword.arg in {"system_prompt", "user_prompt"}:
                    failures.append(f"{path.name}:{node.lineno}:unregistered_prompt_argument")
                if keyword.arg == "description" and isinstance(keyword.value, (ast.Constant, ast.JoinedStr)):
                    failures.append(f"{path.name}:{node.lineno}:inline_description")
            if call.endswith(".invoke"):
                for keyword in node.keywords:
                    if keyword.arg in {"messages", "system", "prompt"}:
                        failures.append(f"{path.name}:{node.lineno}:unregistered_invocation")
    return failures
