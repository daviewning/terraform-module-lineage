from __future__ import annotations

import networkx as nx
from pathlib import Path
from typing import Iterable, List
from urllib.parse import parse_qs, urlparse
from terraform_lineage.parsing.terraform_parser import ParsedTerraform

def build_graph(parsed: ParsedTerraform, include_resources: bool = False) -> nx.DiGraph:
    G = nx.DiGraph()
    
    # First, collect all terraform files and create file entities
    terraform_files = {}
    folders = {}
    
    for mid, m in parsed.modules.items():
        # EXCLUDE source modules from file processing - they represent directories, not files
        if m.file_path and m.file_name and not mid.startswith("source_module:"):
            file_id = f"file:{m.file_path}"
            if file_id not in terraform_files:
                # Extract folder information from file path
                file_path_obj = parsed.root_dir / m.file_path if not Path(m.file_path).is_absolute() else Path(m.file_path)
                folder_path = file_path_obj.parent
                folder_name = folder_path.name
                
                terraform_files[file_id] = {
                    'file_path': m.file_path,
                    'file_name': m.file_name,
                    'folder_path': str(folder_path),
                    'folder_name': folder_name,
                    'modules': []
                }
                
                # Collect all folders in the hierarchy (including intermediate folders) - but don't assign files yet
                current_path = folder_path
                while current_path != parsed.root_dir.parent and current_path != current_path.parent:
                    folder_id = f"folder:{current_path}"
                    if folder_id not in folders:
                        try:
                            # Try to get relative path from root
                            rel_folder_path = current_path.relative_to(parsed.root_dir)
                            display_path = str(rel_folder_path).replace("\\", "/")
                            if display_path == ".":
                                display_path = current_path.name
                        except ValueError:
                            # Use absolute path if relative doesn't work
                            display_path = str(current_path)
                        
                        folders[folder_id] = {
                            'folder_path': str(current_path),
                            'folder_name': current_path.name,
                            'display_path': display_path,
                            'files': [],
                            'parent_path': str(current_path.parent) if current_path.parent != current_path else None
                        }
                    
                    # Move up the hierarchy
                    current_path = current_path.parent
                
                # Now assign the file ONLY to its immediate parent folder
                immediate_parent_folder_id = f"folder:{folder_path}"
                if immediate_parent_folder_id in folders:
                    folders[immediate_parent_folder_id]['files'].append(file_id)
                
            terraform_files[file_id]['modules'].append(mid)
    
    # (Folder entities are now added after resource processing)
    
    # (Terraform file entities are now added after resource processing)
    
    # Add edges from folders to their contained files (only for actual leaf folders)
    for folder_id, folder_info in folders.items():
        # Check if this folder has any child folders
        has_child_folders = any(
            other_info.get('parent_path') == folder_info['folder_path'] 
            for other_info in folders.values()
        )
        
        # Only leaf folders should connect to files
        if not has_child_folders:
            for file_id in folder_info['files']:
                if G.has_node(file_id):
                    G.add_edge(folder_id, file_id, edge_type="contains", style="dashed")
    
    # Add edges between parent and child folders
    for folder_id, folder_info in folders.items():
        parent_path = folder_info.get('parent_path')
        if parent_path:
            parent_folder_id = f"folder:{parent_path}"
            if parent_folder_id in folders and G.has_node(parent_folder_id):
                G.add_edge(parent_folder_id, folder_id, edge_type="contains", style="dashed")
    
    # Add module entities
    for mid, m in parsed.modules.items():
        # Create better labels with file information and module type
        if mid.startswith("source_module:"):
            label = f"{m.name}\n[source module]"
            module_type = "source_module"
            level = 2  # Third layer - modules
        elif m.source and _is_registry_module(m.source):
            label = f"{m.name}\n[registry]"
            module_type = "registry_module"
            level = 2  # Third layer - modules (registry modules are still modules)
        elif m.source and _is_git_source(m.source):
            label = f"{m.name}\n[git module]"
            module_type = "git_module"
            level = 2  # Third layer - modules (git modules are still modules)
        else:
            label = f"{m.name}\n[module]"
            module_type = "local_module" 
            level = 2  # Third layer - modules
        
        G.add_node(
            mid,
            id=mid,
            kind="module",
            module_type=module_type,
            label=label,
            name=m.name,
            dir=m.dir,
            source=m.source or "",
            file_path=m.file_path or "",
            file_name=m.file_name or "",
            level=level,
        )
    
    # Add resource entities (if enabled)
    if include_resources:
        # First, collect resources and add them to terraform_files
        for rid, r in parsed.resources.items():
            if r.file_path and r.file_name:
                file_id = f"file:{r.file_path}"
                # If the file doesn't exist in terraform_files, create it (for resource-only files)
                if file_id not in terraform_files:
                    file_path_obj = parsed.root_dir / r.file_path if not Path(r.file_path).is_absolute() else Path(r.file_path)
                    folder_path = file_path_obj.parent
                    folder_name = folder_path.name
                    
                    terraform_files[file_id] = {
                        'file_path': r.file_path,
                        'file_name': r.file_name,
                        'folder_path': str(folder_path),
                        'folder_name': folder_name,
                        'modules': []
                    }
                    
                    # Also add the folder to the hierarchy if it doesn't exist
                    current_path = folder_path
                    while current_path != parsed.root_dir.parent and current_path != current_path.parent:
                        folder_id = f"folder:{current_path}"
                        if folder_id not in folders:
                            try:
                                rel_folder_path = current_path.relative_to(parsed.root_dir)
                                display_path = str(rel_folder_path).replace("\\", "/")
                                if display_path == ".":
                                    display_path = current_path.name
                            except ValueError:
                                display_path = str(current_path)
                            
                            folders[folder_id] = {
                                'folder_path': str(current_path),
                                'folder_name': current_path.name,
                                'display_path': display_path,
                                'files': [],
                                'parent_path': str(current_path.parent) if current_path.parent != current_path else None
                            }
                        
                        # Add file to its immediate parent folder
                        if current_path == folder_path:
                            folders[folder_id]['files'].append(file_id)
                        
                        current_path = current_path.parent
                
                # Add resource to the file
                if 'resources' not in terraform_files[file_id]:
                    terraform_files[file_id]['resources'] = []
                terraform_files[file_id]['resources'].append(rid)
        
        # Add resource nodes to the graph
        for rid, r in parsed.resources.items():
            resource_label = f"{r.type}.{r.name}\n[terraform resource]"
            G.add_node(
                rid,
                id=rid,
                kind="resource",
                module_type="terraform_resource",
                label=resource_label,
                name=r.name,
                type=r.type,
                dir=r.dir,
                file_path=r.file_path or "",
                file_name=r.file_name or "",
                level=3,  # Put resources at level 3 to separate from modules
            )

    # NOW Add terraform file entities to the graph (Level 1) - after resource processing
    for file_id, file_info in terraform_files.items():
        # Always label as terraform file, regardless of what modules it contains
        file_label = f"{file_info['file_name']}\n[terraform file]"
        G.add_node(
            file_id,
            id=file_id,
            kind="terraform_file",
            module_type="terraform_file",
            label=file_label,
            name=file_info['file_name'],
            file_path=file_info['file_path'],
            file_name=file_info['file_name'],
            folder_path=file_info['folder_path'],
            folder_name=file_info['folder_name'],
            level=1,  # Second layer
        )

    # NOW Add folder entities to the graph (Level 0) - after resource processing
    for folder_id, folder_info in folders.items():
        folder_label = f"{folder_info['folder_name']}\n[folder]"
        G.add_node(
            folder_id,
            id=folder_id,
            kind="folder",
            module_type="folder",
            label=folder_label,
            name=folder_info['folder_name'],
            folder_path=folder_info['folder_path'],
            display_path=folder_info['display_path'],
            level=0,  # Leftmost layer
        )

    # Add edges from folders to their contained files
    for folder_id, folder_info in folders.items():
        for file_id in folder_info['files']:
            if G.has_node(file_id):
                G.add_edge(folder_id, file_id, edge_type="contains", style="dashed")

    # Add edges between parent and child folders
    for folder_id, folder_info in folders.items():
        parent_path = folder_info.get('parent_path')
        if parent_path:
            parent_folder_id = f"folder:{parent_path}"
            if parent_folder_id in folders and G.has_node(parent_folder_id):
                G.add_edge(parent_folder_id, folder_id, edge_type="contains", style="dashed")

    # Add edges from terraform files to their contained modules
    for file_id, file_info in terraform_files.items():
        for module_id in file_info['modules']:
            if G.has_node(module_id):
                G.add_edge(file_id, module_id, edge_type="contains", style="dashed")
        
        # Add edges from terraform files to their contained resources (if enabled)
        if include_resources and 'resources' in file_info:
            for resource_id in file_info['resources']:
                if G.has_node(resource_id):
                    G.add_edge(file_id, resource_id, edge_type="contains", style="dashed")

    # Add edges for explicit depends_on (but not from registry or git modules)
    for mid, m in parsed.modules.items():
        # Skip creating edges FROM registry or git modules - they are external dependencies
        if m.source and (_is_registry_module(m.source) or _is_git_source(m.source)):
            continue
            
        targets = _resolve_module_like_refs(parsed, m.explicit_deps)
        for tgt in targets:
            if G.has_node(tgt):
                G.add_edge(mid, tgt)

    # Add edges for implicit module references in inputs (but not between modules in same file or from registry/git modules)
    for mid, m in parsed.modules.items():
        # Skip creating edges FROM registry or git modules - they are external dependencies
        if m.source and (_is_registry_module(m.source) or _is_git_source(m.source)):
            continue
            
        for ref_name in m.implicit_module_refs:
            for tgt in parsed.name_index.get(ref_name, []):
                if G.has_node(tgt):
                    # Don't create edges between modules in the same file
                    target_module = parsed.modules.get(tgt)
                    if target_module and target_module.file_path == m.file_path:
                        continue  # Skip - both modules are in the same file
                    G.add_edge(mid, tgt, edge_type="data_dependency", label=f"uses {ref_name}")
    
    # Add edges for resource dependencies (if enabled)
    if include_resources:
        for rid, r in parsed.resources.items():
            # Add edges for explicit depends_on from resources
            targets = _resolve_resource_refs(parsed, r.explicit_deps)
            for tgt in targets:
                if G.has_node(tgt):
                    G.add_edge(rid, tgt, edge_type="depends_on")
    
    # Add registry entities and connect local modules to them
    for mid, m in parsed.modules.items():
        if m.source and _is_registry_module(m.source):
            registry_id = f"registry:{m.source}"
            registry_name, registry_submodule = _parse_registry_source(m.source)
            
            # Create registry entity if it doesn't exist
            if not G.has_node(registry_id):
                registry_label = f"{registry_name}\n{registry_submodule}\n[public registry]"
                G.add_node(
                    registry_id,
                    id=registry_id,
                    kind="registry_entity",
                    module_type="registry_entity", 
                    label=registry_label,
                    name=registry_name,
                    submodule=registry_submodule,
                    source=m.source,
                    registry_source=f"registry.terraform.io/{m.source}",
                    level=3,  # Rightmost layer - registry entities
                )
            
            # Connect the local module to the registry entity
            G.add_edge(mid, registry_id)
    
    # Add Git repository entities and connect modules to them
    for mid, m in parsed.modules.items():
        if m.source and _is_git_source(m.source):
            git_id = f"git:{m.source}"
            git_name, git_path = _parse_git_source(m.source)
            
            # Create Git repository entity if it doesn't exist
            if not G.has_node(git_id):
                git_label = f"{git_name}\n{git_path}\n[git repository]"
                G.add_node(
                    git_id,
                    id=git_id,
                    kind="git_entity",
                    module_type="git_entity", 
                    label=git_label,
                    name=git_name,
                    path=git_path,
                    source=m.source,
                    git_url=_extract_git_url(m.source),
                    level=3,  # Rightmost layer - external entities
                )
            
            # Connect the local module to the Git repository entity
            G.add_edge(mid, git_id)
    
    # Add edges for local module sources (module USES source_module, so source_module -> module)
    for mid, m in parsed.modules.items():
        if m.source and _is_local_source(m.source):
            # Find the source module by looking for source_module entries
            source_modules = _find_source_modules(parsed, m, mid)
            for source_mid in source_modules:
                if G.has_node(source_mid):
                    # Fixed: source module should point TO the module that uses it, not vice versa
                    G.add_edge(source_mid, mid, edge_type="provides", style="solid")
    
    # Add edges from source modules to their contained files (proper hierarchy: source_module -> file -> resource)
    for mid, m in parsed.modules.items():
        if mid.startswith("source_module:"):
            # Connect source module to its terraform files only - be more precise about path matching
            for file_id, file_info in terraform_files.items():
                # Check if this file belongs to the source module's directory (exact directory match)
                if m.dir and file_info['file_path'].startswith(m.dir + "/"):
                    G.add_edge(mid, file_id, edge_type="contains", style="dashed")
                elif m.dir and m.dir == file_info.get('folder_path', '').replace('\\', '/'):
                    # Also handle case where file is directly in the source module directory
                    G.add_edge(mid, file_id, edge_type="contains", style="dashed")

    return G

def _resolve_module_like_refs(parsed: ParsedTerraform, refs: Iterable[str]) -> List[str]:
    targets: List[str] = []
    for r in refs:
        r = str(r)
        if r.startswith("module."):
            name = r.split(".", 1)[1]
            targets.extend(parsed.name_index.get(name, []))
    return targets

def _resolve_resource_refs(parsed: ParsedTerraform, refs: Iterable[str]) -> List[str]:
    targets: List[str] = []
    for r in refs:
        r = str(r)
        if r.startswith("module."):
            # Resource referencing a module
            name = r.split(".", 1)[1]
            targets.extend(parsed.name_index.get(name, []))
        elif "." in r and not r.startswith("var.") and not r.startswith("local.") and not r.startswith("data."):
            # Could be a resource reference like "aws_instance.example"
            targets.extend(parsed.name_index.get(r, []))
    return targets

def find_cycles(G: nx.DiGraph) -> List[List[str]]:
    try:
        return list(nx.simple_cycles(G))
    except nx.NetworkXNoCycle:
        return []

def _is_local_source(source: str) -> bool:
    """Check if a module source is a local path (not registry or git)."""
    if not source:
        return False
    
    # Git/HTTP sources
    if (source.startswith("git::") or source.startswith("http") or 
        source.startswith("https://") or "::" in source):
        return False
    
    # Terraform Registry modules have the format: namespace/name/provider
    # They contain slashes but don't start with ./ or ../
    if "/" in source and not source.startswith("./") and not source.startswith("../"):
        # Count slashes - registry modules typically have 2+ slashes
        slash_count = source.count("/")
        if slash_count >= 2:
            return False  # This is a registry module
    
    # Local sources start with ./ or ../ or are simple relative paths
    return (source.startswith("./") or source.startswith("../") or 
            (not source.startswith("/") and "/" not in source))

def _is_registry_module(source: str) -> bool:
    """Check if a module source is from Terraform Registry."""
    if not source:
        return False
    
    # Git/HTTP sources are not registry modules
    if (source.startswith("git::") or source.startswith("http") or 
        source.startswith("https://") or "::" in source):
        return False
    
    # Registry modules have format: namespace/name/provider or namespace/name/provider//submodule
    # They contain slashes but don't start with ./ or ../
    if "/" in source and not source.startswith("./") and not source.startswith("../"):
        slash_count = source.count("/")
        if slash_count >= 2:
            return True  # This is a registry module
    
    return False

def _parse_registry_source(source: str) -> tuple[str, str]:
    """Parse a registry source into main module name and submodule."""
    if "//" in source:
        # Format: namespace/name/provider//submodule/path
        main_part, sub_part = source.split("//", 1)
        # Extract name from namespace/name/provider
        parts = main_part.split("/")
        if len(parts) >= 2:
            main_name = f"{parts[1]}"  # Just the module name
        else:
            main_name = main_part
        
        # Extract submodule name from path
        sub_parts = sub_part.split("/")
        if sub_parts:
            submodule = f"submodule: {sub_parts[-1]}"  # Last part is usually the submodule name
        else:
            submodule = f"submodule: {sub_part}"
    else:
        # Format: namespace/name/provider
        parts = source.split("/")
        if len(parts) >= 2:
            main_name = f"{parts[1]}"  # Just the module name
        else:
            main_name = source
        submodule = "main module"
    
    return main_name, submodule

def _find_source_modules(parsed: ParsedTerraform, module: any, current_mid: str) -> List[str]:
    """Find source_module entries that match the module's source path."""
    if not module.source or not _is_local_source(module.source):
        return []
    
    # Resolve the source path relative to the current module's directory
    from pathlib import Path
    
    # Get the directory of the current module
    current_module_dir = module.dir
    if current_module_dir == ".":
        base_path = parsed.root_dir
    else:
        base_path = parsed.root_dir / current_module_dir
    
    # Resolve the source path
    try:
        source_full_path = (base_path / module.source).resolve()
        source_dir_name = source_full_path.name
    except Exception:
        return []
    
    source_modules = []
    for mid, m in parsed.modules.items():
        if mid == current_mid:  # Don't link to self
            continue
        
        # Look for source_module entries that match the source directory name
        if mid.startswith("source_module:") and m.name == source_dir_name:
            source_modules.append(mid)
    
    return source_modules

def _is_git_source(source: str) -> bool:
    """Check if a module source is from a Git repository."""
    if not source:
        return False
    
    # Git sources start with git:: or contain git URLs
    return (source.startswith("git::") or 
            source.startswith("github.com") or
            source.startswith("gitlab.com") or
            source.startswith("bitbucket.org") or
            ".git" in source)

def _parse_git_source(source: str) -> tuple[str, str]:
    """Parse a Git source into repository name and path."""
    if source.startswith("git::"):
        # Remove git:: prefix
        git_url = source[5:]
    else:
        git_url = source
    
    # Extract repository name from URL
    if "//" in git_url:
        # Split on // to get path portion
        if git_url.startswith("https://") or git_url.startswith("http://"):
            # Format: https://github.com/owner/repo.git//path
            url_part = git_url.split("//")[0]
            path_part = git_url.split("//")[1] if "//" in git_url else ""
        else:
            # Format: github.com/owner/repo.git//path
            parts = git_url.split("//")
            url_part = parts[0]
            path_part = parts[1] if len(parts) > 1 else ""
    else:
        url_part = git_url
        path_part = ""
    
    # Extract repository name from URL
    repo_name = ""
    if "github.com" in url_part or "gitlab.com" in url_part or "bitbucket.org" in url_part:
        # Extract owner/repo from URL
        url_parts = url_part.replace("https://", "").replace("http://", "").split("/")
        if len(url_parts) >= 3:
            owner = url_parts[1]
            repo = url_parts[2].replace(".git", "")
            repo_name = f"{owner}/{repo}"
        else:
            repo_name = url_part.split("/")[-1].replace(".git", "")
    else:
        repo_name = url_part.split("/")[-1].replace(".git", "")
    
    # Format path
    if path_part:
        path_display = f"path: {path_part}"
    else:
        path_display = "root"
    
    return repo_name, path_display

#def _extract_git_url(source: str) -> str:
#    """Extract and construct the proper GitHub URL from a Terraform Git source."""
#    if source.startswith("git::"):
#        git_url = source[5:]  # Remove git:: prefix
#        
#        # Split on the path separator "//" but be careful with protocol "://"
#        repo_url = ""
#        path = ""
#        
#        # For URLs like https://github.com/user/repo.git//path, we need to be careful
#        if "//" in git_url:
#            # Find the "//" that's not part of protocol (like https://)
#            index = 0
#            while True:
#                index = git_url.find("//", index)
#                if index == -1:
#                    break
#                # Check if this "//" is not part of protocol (like https://)
#                if index > 0 and git_url[index-1] != ':':
#                    repo_url = git_url[:index]
#                    path = git_url[index+2:]  # Get path after "//"
#                    break
#                index += 2
#        
#        if not repo_url:
#            repo_url = git_url
#        
#        # Clean up repo URL (remove .git extension)
#        if repo_url.endswith('.git'):
#            repo_url = repo_url[:-4]
#        
#        # Construct proper GitHub URL with path
#        if path and ("github.com" in repo_url):
#            # Convert to GitHub tree URL format
#            return f"{repo_url}/tree/main/{path}"
#        elif path and ("gitlab.com" in repo_url):
#            # Convert to GitLab tree URL format
#            return f"{repo_url}/-/tree/main/{path}"
#        else:
#            # Return base repository URL
#            return repo_url
#    else:
#        return source

def _extract_git_url(source: str) -> str:
    """
    Normalize a Terraform git module source into a browsable repository URL.

    Accepted input examples:
        git::https://host/org/repo.git?ref=main
        git::https://host/org/repo.git//sub/dir?ref=v1.2.3
        https://host/org/repo.git//sub?ref=feature/foo
        git::ssh://git@host/org/repo.git//module/path?ref=tag
        git::https://host/org/repo.git//?ref=main

    Output (GitHub style):
        https://host/org/repo/tree/<ref>/<sub/dir>

    Output (GitLab style host contains "gitlab'):
        https://host/org/repo/-/tree/<ref>/<sub/dir>

    Rules:
        - Default ref is "main' if absent.
        - If no subpath, still return ... /tree/<ref>
        - Strips trailing .git
    """
    if not source:
        return ""
    raw = source

    # Strip leading terraform git prefix
    if raw.startswith("git::"):
        raw = raw[5:]

    # Quick exit if it does not look like a git style URL
    if ".git" not in raw:
        return source

    # Separate query string (?ref =...)
    if "?" in raw:
        before_q, q = raw.split("?", 1)
        qs = parse_qs(q)
        ref = (qs.get("ref", ["main"])[0] or "main").strip()
    else:
        before_q = raw
        ref = "main"

    # Remove fragment if any
    before_q = before_q.split("#", 1)[0]

    # Extract repo portion and optional subpath (after .git//)
    if ".git//" in before_q:
        repo_part, path_part = before_q.split(".git//", 1)
        repo_url = repo_part + ".git"
        sub_path = path_part.strip("/")

        # Handle edge case of explicit // but empty path
        if sub_path == "":
            sub_path = ""
    else:
        repo_url = before_q
        sub_path = ""

    repo_url = repo_url.rstrip("/")

    # Browser base (strip .git)
    if repo_url.endswith(".git"):
        repo_base = repo_url[:- 4]
    else:
        repo_base = repo_url

    # Ensure we can parse host (prepend scheme if missing)
    parse_target = repo_base
    if not parse_target.startswith(("http://", "https://")):
        parse_target = "https://" + parse_target
    try:
        host = (urlparse(parse_target).hostname or "").lower()
    except Exception:
        host = ""

    # Decide tree segment
    tree_segment = "/-/tree" if "gitlab" in host else "/tree"

    # Build final URL
    if sub_path:
        return f"{repo_base}{tree_segment}/{ref}/{sub_path}"
    else:
        return f"{repo_base}{tree_segment}/{ref}"