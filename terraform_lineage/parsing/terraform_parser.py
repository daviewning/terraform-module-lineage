from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import hcl2

MODULE_REF_RE = re.compile(r"\bmodule\.([A-Za-z0-9_-]+)\b", re.IGNORECASE)

@dataclass
class ModuleInfo:
    id: str
    name: str
    dir: str
    source: str | None
    file_path: str | None = None  # Path to the .tf file containing this module
    file_name: str | None = None  # Name of the .tf file
    inputs: Dict[str, Any] = field(default_factory=dict)
    explicit_deps: List[str] = field(default_factory=list)
    implicit_module_refs: List[str] = field(default_factory=list)

@dataclass
class ResourceInfo:
    id: str
    name: str
    type: str
    dir: str
    file_path: str | None = None  # Path to the .tf file containing this resource
    file_name: str | None = None  # Name of the .tf file
    config: Dict[str, Any] = field(default_factory=dict)
    explicit_deps: List[str] = field(default_factory=list)

@dataclass
class ParsedTerraform:
    root_dir: Path
    modules: Dict[str, ModuleInfo]
    resources: Dict[str, ResourceInfo]
    name_index: Dict[str, List[str]]

def parse_directory(root_dir: Path) -> ParsedTerraform:
    root_dir = Path(root_dir)
    parsed_paths: set[Path] = set()
    modules: Dict[str, ModuleInfo] = {}
    resources: Dict[str, ResourceInfo] = {}
    name_index: Dict[str, List[str]] = {}
    
    def _parse_path(current_path: Path, search_root: Path, is_source_module: bool = False):
        if current_path in parsed_paths:
            return
        parsed_paths.add(current_path)
        
        tf_files = [p for p in current_path.rglob("*.tf") if ".terraform" not in p.parts]
        
        # If this is a source module directory, create a single representative module
        if is_source_module:
            try:
                rel_dir = str(current_path.relative_to(search_root)).replace("\\", "/") or "."
            except ValueError:
                rel_dir = str(current_path)
            
            # Create a module representing the entire source module
            module_name = current_path.name
            node_id = f"source_module:{rel_dir}:{module_name}"
            mi = ModuleInfo(
                id=node_id,
                name=module_name,
                dir=rel_dir,
                source=None,  # This is a source module, not referencing another
                file_path=str(current_path),
                file_name="[source module]",
                inputs={},
                explicit_deps=[],
                implicit_module_refs=[],
            )
            modules[node_id] = mi
            name_index.setdefault(module_name, []).append(node_id)
            return
        
        for tf in tf_files:
            try:
                rel_dir = str(tf.parent.relative_to(search_root)).replace("\\", "/") or "."
            except ValueError:
                # File is outside search_root, use absolute-relative path
                rel_dir = str(tf.parent)
                
            try:
                with tf.open("r", encoding="utf-8") as f:
                    data = hcl2.load(f)
            except Exception:
                continue

            # Parse modules
            blocks = data.get("module", []) or []
            for b in blocks:
                if not isinstance(b, dict) or not b:
                    continue
                name = list(b.keys())[0]
                cfg = b[name] or {}
                source = cfg.get("source")
                explicit = _normalize_depends_on(cfg.get("depends_on", []))
                inputs = {k: v for k, v in cfg.items() if k not in ("source", "depends_on")}
                implicit = sorted(_find_module_refs(inputs))

                node_id = f"module:{rel_dir}:{name}"
                mi = ModuleInfo(
                    id=node_id,
                    name=name,
                    dir=rel_dir,
                    source=source,
                    file_path=str(tf),
                    file_name=tf.name,
                    inputs=inputs,
                    explicit_deps=explicit,
                    implicit_module_refs=implicit,
                )
                modules[node_id] = mi
                name_index.setdefault(name, []).append(node_id)
                
                # Follow local module sources and treat them as single entities
                if source and _is_local_source(source):
                    local_module_path = (tf.parent / source).resolve()
                    if local_module_path.exists() and local_module_path.is_dir():
                        _parse_path(local_module_path, search_root, is_source_module=True)
            
            # Parse resources
            resource_blocks = data.get("resource", []) or []
            for b in resource_blocks:
                if not isinstance(b, dict) or not b:
                    continue
                resource_type = list(b.keys())[0]
                resource_instances = b[resource_type] or {}
                
                for resource_name, resource_config in resource_instances.items():
                    if not isinstance(resource_config, dict):
                        continue
                    
                    explicit = _normalize_depends_on(resource_config.get("depends_on", []))
                    config = {k: v for k, v in resource_config.items() if k not in ("depends_on",)}
                    
                    resource_id = f"resource:{rel_dir}:{resource_type}.{resource_name}"
                    ri = ResourceInfo(
                        id=resource_id,
                        name=resource_name,
                        type=resource_type,
                        dir=rel_dir,
                        file_path=str(tf),
                        file_name=tf.name,
                        config=config,
                        explicit_deps=explicit,
                    )
                    resources[resource_id] = ri
                    name_index.setdefault(f"{resource_type}.{resource_name}", []).append(resource_id)
    
    _parse_path(root_dir, root_dir)
    return ParsedTerraform(root_dir=root_dir, modules=modules, resources=resources, name_index=name_index)

def _is_local_source(source: str) -> bool:
    """Check if a module source is a local path (not registry or git)."""
    if not source:
        return False
    # Local sources start with ./ or ../ or are relative paths without protocols
    return (source.startswith("./") or source.startswith("../") or 
            (not source.startswith("git::") and not source.startswith("http") and "::" not in source))

def _normalize_depends_on(dep) -> List[str]:
    if dep is None:
        return []
    if isinstance(dep, str):
        return [dep]
    if isinstance(dep, list):
        return [str(x) for x in dep]
    return []

def _find_module_refs(obj: Any) -> List[str]:
    refs: set[str] = set()
    def walk(val: Any):
        if isinstance(val, str):
            for m in MODULE_REF_RE.finditer(val):
                refs.add(m.group(1))
        elif isinstance(val, dict):
            for v in val.values():
                walk(v)
        elif isinstance(val, (list, tuple)):
            for v in val:
                walk(v)
    walk(obj)
    return list(refs)
