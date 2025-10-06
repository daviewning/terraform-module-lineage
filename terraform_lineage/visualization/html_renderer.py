from __future__ import annotations

from pathlib import Path
from typing import Dict
from pyvis.network import Network

def render_html(G, output_path: Path, hierarchical: bool, color_by: str = "type") -> None:
    net = Network(height="850px", width="100%", directed=True, notebook=False)
    net.set_options(_net_options(hierarchical))

    for nid, attrs in G.nodes(data=True):
        color = _color_for(attrs, color_by)
        title = _tooltip(attrs)
        
        # Determine shape based on entity type
        if attrs.get("kind") == "folder":
            shape = "ellipse"  # Use ellipse for folders (distinct from boxes and diamonds)
        elif attrs.get("kind") == "terraform_file":
            shape = "diamond"
        elif attrs.get("kind") == "module":
            shape = "box"
        else:
            shape = "ellipse"
            
        # Get the level for hierarchical positioning
        level = attrs.get("level")
        node_options = {
            "label": str(attrs.get("label", nid)),
            "title": title,
            "color": color,
            "shape": shape,
            "font": {"face": "Segoe UI", "size": 16},
        }
        
        # Add level information for hierarchical layout
        if level is not None:
            node_options["level"] = level
            
        net.add_node(nid, **node_options)

    for src, dst, edge_attrs in G.edges(data=True):
        # Handle different edge types
        edge_style = edge_attrs.get("style", "solid")
        edge_type = edge_attrs.get("edge_type", "dependency")
        edge_label = edge_attrs.get("label", "")
        
        if edge_style == "dashed":
            # Dotted/dashed line for file-to-module containment
            net.add_edge(src, dst, arrows="to", dashes=True, color="#666666", width=2)
        elif edge_type == "data_dependency":
            # Data dependency with label
            net.add_edge(src, dst, arrows="to", color="#ff6b6b", width=1.5, 
                        label=edge_label, font={"color": "#ff6b6b", "size": 10})
        else:
            # Solid line for module dependencies
            net.add_edge(src, dst, arrows="to")

    output_path = Path(output_path)
    net.write_html(str(output_path))
    
    # Add JavaScript to ensure nodes stay where dropped and add search functionality
    _add_position_lock_script(output_path)
    _add_search_interface(output_path)

def _add_position_lock_script(output_path: Path) -> None:
    """Add JavaScript to ensure nodes stay where they are dropped."""
    # Read the generated HTML
    with open(output_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # JavaScript to handle both hierarchical and flat layouts
    position_lock_script = """
    <script>
    // Wait for network to be stabilized
    network.on('stabilizationIterationsDone', function() {
        console.log('Network stabilized - enabling free movement');
        
        // Get current positions of all nodes
        var allPositions = network.getPositions();
        
        // Update all nodes to be freely movable
        var allNodeIds = Object.keys(allPositions);
        var nodeUpdates = allNodeIds.map(function(nodeId) {
            return {
                id: nodeId,
                x: allPositions[nodeId].x,
                y: allPositions[nodeId].y,
                physics: false,
                fixed: false
            };
        });
        
        // Apply updates to all nodes
        nodes.update(nodeUpdates);
        
        // Disable physics and hierarchical layout (if present)
        network.setOptions({
            physics: { enabled: false },
            layout: { hierarchical: { enabled: false } },
            interaction: {
                dragNodes: true,
                dragView: true,
                zoomView: true
            }
        });
    });
    
    // Handle dragging to keep nodes where dropped
    network.on('dragEnd', function(params) {
        if (params.nodes.length > 0) {
            console.log('Drag ended - locking positions');
            
            // Get the final positions of dragged nodes
            var positions = network.getPositions(params.nodes);
            
            // Update nodes to stay at their new positions
            var nodeUpdates = params.nodes.map(function(nodeId) {
                return {
                    id: nodeId,
                    x: positions[nodeId].x,
                    y: positions[nodeId].y,
                    physics: false,
                    fixed: false
                };
            });
            
            // Apply the updates to keep nodes in place
            nodes.update(nodeUpdates);
        }
    });
    
    // Fallback: Force override after delay if stabilization doesn't trigger
    setTimeout(function() {
        console.log('Timeout override - ensuring free movement');
        
        var allPositions = network.getPositions();
        var allNodeIds = Object.keys(allPositions);
        
        if (allNodeIds.length > 0) {
            var nodeUpdates = allNodeIds.map(function(nodeId) {
                return {
                    id: nodeId,
                    x: allPositions[nodeId].x,
                    y: allPositions[nodeId].y,
                    physics: false,
                    fixed: false
                };
            });
            
            nodes.update(nodeUpdates);
            
            network.setOptions({
                physics: { enabled: false },
                layout: { hierarchical: { enabled: false } },
                interaction: {
                    dragNodes: true,
                    dragView: true,
                    zoomView: true
                }
            });
        }
    }, 2000);
    </script>
    """
    
    # Insert the script before the closing </body> tag
    html_content = html_content.replace('</body>', position_lock_script + '\n</body>')
    
    # Write the modified HTML back
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

def _add_search_interface(output_path: Path) -> None:
    """Add search interface to the HTML visualization."""
    # Read the generated HTML
    with open(output_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Search box HTML and CSS
    search_interface = """
    <style>
    .search-container {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 1000;
        background: white;
        border: 2px solid #ddd;
        border-radius: 8px;
        padding: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        font-family: 'Segoe UI', sans-serif;
    }
    
    .search-input {
        padding: 8px 12px;
        border: 1px solid #ccc;
        border-radius: 4px;
        font-size: 14px;
        width: 200px;
        outline: none;
    }
    
    .search-input:focus {
        border-color: #0066cc;
        box-shadow: 0 0 5px rgba(0,102,204,0.3);
    }
    
    .search-results {
        margin-top: 8px;
        font-size: 12px;
        color: #666;
    }
    
    .clear-button {
        margin-left: 8px;
        padding: 8px 12px;
        background: #f44336;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
    }
    
    .clear-button:hover {
        background: #d32f2f;
    }
    </style>
    
    <div class="search-container">
        <input type="text" id="searchInput" class="search-input" placeholder="Search entities..." />
        <button id="clearButton" class="clear-button">Clear</button>
        <div id="searchResults" class="search-results"></div>
    </div>
    
    <script>
    // Search functionality
    let originalNodeColors = {};
    let originalNodeBorders = {};
    
    // Store original colors when network is ready
    network.once('afterDrawing', function() {
        nodes.forEach(function(node) {
            originalNodeColors[node.id] = node.color;
            originalNodeBorders[node.id] = node.borderWidth || 2;
        });
    });
    
    function searchEntities(searchTerm) {
        if (!searchTerm) {
            clearSearch();
            return;
        }
        
        searchTerm = searchTerm.toLowerCase();
        let matchedNodes = [];
        let totalNodes = 0;
        
        // Reset all nodes to original appearance
        let nodeUpdates = [];
        nodes.forEach(function(node) {
            totalNodes++;
            let label = (node.label || '').toLowerCase();
            let isMatch = label.includes(searchTerm);
            
            if (isMatch) {
                matchedNodes.push(node);
                // Highlight matched nodes
                nodeUpdates.push({
                    id: node.id,
                    color: {
                        background: '#ffeb3b',  // Yellow highlight
                        border: '#ff9800'      // Orange border
                    },
                    borderWidth: 4,
                    font: {
                        color: '#000000',
                        size: 18,
                        face: 'Segoe UI'
                    }
                });
            } else {
                // Dim non-matched nodes
                nodeUpdates.push({
                    id: node.id,
                    color: {
                        background: '#f5f5f5',  // Light gray
                        border: '#e0e0e0'      // Lighter border
                    },
                    borderWidth: 1,
                    font: {
                        color: '#999999',
                        size: 16,
                        face: 'Segoe UI'
                    }
                });
            }
        });
        
        // Update all nodes
        nodes.update(nodeUpdates);
        
        // Update search results
        const resultsDiv = document.getElementById('searchResults');
        if (matchedNodes.length > 0) {
            resultsDiv.textContent = `Found ${matchedNodes.length} of ${totalNodes} entities`;
            
            // Focus on first match if available
            if (matchedNodes.length > 0) {
                network.focus(matchedNodes[0].id, {
                    scale: 1.2,
                    animation: {
                        duration: 500,
                        easingFunction: 'easeInOutQuart'
                    }
                });
            }
        } else {
            resultsDiv.textContent = `No matches found for "${searchTerm}"`;
        }
    }
    
    function clearSearch() {
        // Reset all nodes to original appearance
        let nodeUpdates = [];
        nodes.forEach(function(node) {
            nodeUpdates.push({
                id: node.id,
                color: originalNodeColors[node.id] || node.color,
                borderWidth: originalNodeBorders[node.id] || 2,
                font: {
                    color: '#000000',
                    size: 16,
                    face: 'Segoe UI'
                }
            });
        });
        
        // Update all nodes
        nodes.update(nodeUpdates);
        
        // Clear search results
        document.getElementById('searchResults').textContent = '';
        document.getElementById('searchInput').value = '';
        
        // Reset view
        network.fit({
            animation: {
                duration: 500,
                easingFunction: 'easeInOutQuart'
            }
        });
    }
    
    // Event listeners
    document.getElementById('searchInput').addEventListener('input', function(e) {
        searchEntities(e.target.value);
    });
    
    document.getElementById('clearButton').addEventListener('click', function() {
        clearSearch();
    });
    
    // Allow Enter key to trigger search
    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchEntities(e.target.value);
        }
    });
    </script>
    """
    
    # Insert the search interface before the closing </body> tag
    html_content = html_content.replace('</body>', search_interface + '\n</body>')
    
    # Write the modified HTML back
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

def _net_options(hierarchical: bool) -> str:
    if hierarchical:
        return """{
          "physics": {
            "enabled": false
          },
          "layout": {
            "hierarchical": {
              "enabled": true,
              "levelSeparation": 200,
              "nodeSpacing": 120,
              "treeSpacing": 180,
              "direction": "LR",
              "sortMethod": "directed",
              "shakeTowards": "roots"
            }
          },
          "interaction": {
            "dragNodes": true,
            "dragView": true,
            "zoomView": true
          },
          "nodes": {
            "physics": false,
            "fixed": {
              "x": false,
              "y": false
            }
          },
          "edges": { "arrows": { "to": { "enabled": true } }, "smooth": { "type": "cubicBezier" } }
        }"""
    else:
        return """{
          "physics": { 
            "enabled": true,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
              "gravitationalConstant": -26,
              "centralGravity": 0.005,
              "springLength": 230,
              "springConstant": 0.18,
              "damping": 0.4,
              "avoidOverlap": 1.5
            },
            "stabilization": {
              "enabled": true,
              "iterations": 1000,
              "updateInterval": 25
            }
          },
          "interaction": {
            "dragNodes": true,
            "dragView": true,
            "zoomView": true,
            "selectConnectedEdges": false
          },
          "nodes": {
            "physics": true,
            "borderWidth": 2,
            "borderWidthSelected": 3,
            "font": {
              "size": 16,
              "face": "Segoe UI"
            },
            "margin": {
              "top": 10,
              "bottom": 10,
              "left": 15,
              "right": 15
            }
          },
          "edges": { 
            "arrows": { "to": { "enabled": true, "scaleFactor": 0.8 } }, 
            "smooth": { 
              "type": "continuous",
              "forceDirection": "none",
              "roundness": 0.1
            },
            "length": 200,
            "width": 2
          }
        }"""

def _color_for(attrs: Dict, color_by: str) -> str:
    kind = attrs.get("kind", "module")
    dir_ = attrs.get("dir", "")
    name = attrs.get("name", "")
    module_id = attrs.get("id", "")
    
    # Check module type
    module_type = attrs.get("module_type", "local_module")
    is_folder = kind == "folder" or module_type == "folder"
    is_source_module = module_id.startswith("source_module:") or "[source module]" in str(attrs.get("label", ""))
    is_registry_module = module_type == "registry_module" or "[registry]" in str(attrs.get("label", ""))
    is_registry_entity = module_type == "registry_entity" or "[public registry]" in str(attrs.get("label", ""))
    is_terraform_file = kind == "terraform_file" or module_type == "terraform_file"
    
    if color_by == "environment":
        env = _infer_env(dir_)
        base_colors = {
            "dev": "#4caf50",
            "test": "#2196f3",
            "stage": "#9c27b0",
            "staging": "#9c27b0",
            "prod": "#f44336",
        }
        base_color = base_colors.get(env, "#607d8b")
        # Make source modules darker/different shade
        if is_folder:
            return "#ffc107"  # Amber for folders
        elif is_terraform_file:
            return "#9e9e9e"  # Gray for terraform files
        elif is_source_module:
            return _darken_color(base_color)
        elif is_registry_module:
            return "#795548"  # Brown for registry modules
        elif is_registry_entity:
            return "#4caf50"  # Green for registry entities (better readability)
        return base_color
    
    if color_by == "status":
        if is_folder:
            return "#ffc107"  # Amber for folders
        elif is_terraform_file:
            return "#9e9e9e"  # Gray for terraform files
        elif is_source_module:
            return "#e91e63"  # Pink for source modules
        elif is_registry_module:
            return "#795548"  # Brown for registry modules
        elif is_registry_entity:
            return "#4caf50"  # Green for registry entities
        return "#03a9f4" if kind == "module" else "#8bc34a"
    
    # Default color scheme by type
    if is_folder:
        return "#ffc107"  # Amber for folders
    elif is_terraform_file:
        return "#9e9e9e"  # Gray for terraform files
    elif is_source_module:
        return "#2196f3"  # Blue for source modules (better contrast with black text)
    elif is_registry_module:
        return "#795548"  # Brown for registry modules
    elif is_registry_entity:
        return "#4caf50"  # Green for registry entities (better readability)
    return "#ff9800" if kind == "module" else "#00bcd4"

def _darken_color(hex_color: str) -> str:
    """Darken a hex color by reducing RGB values by 30%."""
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    darkened = tuple(int(c * 0.7) for c in rgb)
    return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"

def _infer_env(path_str: str) -> str:
    s = path_str.lower()
    for key in ("dev", "test", "stage", "staging", "prod"):
        if f"/{key}" in s or s.endswith(key):
            return key
    return ""

def _build_registry_url(registry_source: str) -> str:
    """Build a URL for registry modules."""
    if registry_source.startswith("registry.terraform.io/"):
        # Extract the module path
        module_path = registry_source.replace("registry.terraform.io/", "")
        return f"https://registry.terraform.io/modules/{module_path}"
    return ""

def _build_vscode_url(file_path: str) -> str:
    """Build a VS Code URL to open a file or folder."""
    if not file_path:
        return ""
    
    # Convert backslashes to forward slashes for URL
    normalized_path = file_path.replace("\\", "/")
    
    # VS Code protocol to open file or folder
    return f"vscode://file/{normalized_path}"

def _tooltip(attrs: Dict) -> str:
    """Build tooltip content for nodes, including clickable file and registry links."""
    file_path = attrs.get("file_path", "")
    folder_path = attrs.get("folder_path", "")
    d = attrs.get("dir", "")
    registry_source = attrs.get("registry_source", "")
    kind = attrs.get("kind", "")
    
    # For folders, create a clickable link to open in VS Code
    if kind == "folder":
        if folder_path:
            vscode_url = _build_vscode_url(folder_path)
            return f'<a href="{vscode_url}" style="color: #0066cc; text-decoration: underline; font-weight: bold;">{folder_path}</a>'
        return attrs.get("name", "")
    
    # For terraform files, create a clickable link to open in VS Code
    if kind == "terraform_file":
        if file_path:
            vscode_url = _build_vscode_url(file_path)
            return f'<a href="{vscode_url}" style="color: #0066cc; text-decoration: underline; font-weight: bold;">{file_path}</a>'
        return attrs.get("name", "")
    
    # For registry modules, create a clickable link to registry
    if registry_source:
        url = _build_registry_url(registry_source)
        if url:
            return f'<a href="{url}" target="_blank" style="color: #0066cc; text-decoration: underline; font-weight: bold;">{registry_source}</a>'
        else:
            return registry_source
    
    # For regular modules, create a clickable link to open file in VS Code
    if file_path and not file_path.endswith("[source module]"):
        vscode_url = _build_vscode_url(file_path)
        return f'<a href="{vscode_url}" style="color: #0066cc; text-decoration: underline; font-weight: bold;">{file_path}</a>'
    
    # For source modules, create a clickable link to open directory in VS Code
    if d and d != ".":
        vscode_url = _build_vscode_url(d)
        return f'<a href="{vscode_url}" style="color: #0066cc; text-decoration: underline; font-weight: bold;">{d}</a>'
    
    # Fallback to module name if no path available
    return attrs.get("name", "")
