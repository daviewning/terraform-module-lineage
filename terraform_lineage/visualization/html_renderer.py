from __future__ import annotations

from pathlib import Path
from typing import Dict
from pyvis.network import Network

def render_html(G, output_path: Path, hierarchical: bool, color_by: str = "type") -> None:
    net = Network(height="2000px", width="2600px", directed=True, notebook=False)
    
    # Pre-calculate positions for three-column layout
    folders = [(nid, attrs) for nid, attrs in G.nodes(data=True) if attrs.get("kind") == "folder"]
    terraform_files = [(nid, attrs) for nid, attrs in G.nodes(data=True) if attrs.get("kind") == "terraform_file"]
    other_entities = [(nid, attrs) for nid, attrs in G.nodes(data=True) if attrs.get("kind") not in ["folder", "terraform_file"]]
    
    # Use custom three-column layout instead of hierarchical
    net.set_options(_three_column_layout_options())

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
        elif attrs.get("kind") == "resource":
            shape = "triangle"  # Use triangle for terraform resources
        else:
            shape = "ellipse"
            
        # Get the level for hierarchical positioning
        level = attrs.get("level")
        
        # Determine font color based on module type for better readability
        font_color = "black"  # Default font color
        module_type = attrs.get("module_type", "")
        if module_type == "git_module":
            font_color = "white"  # White text for dark Git module backgrounds
        elif module_type == "git_entity":
            font_color = "white"  # White text for Git repository entities
        elif module_type == "registry_module":
            font_color = "white"  # White text for registry modules (brown background)
        elif module_type == "terraform_resource":
            font_color = "black"  # Black text for terraform resources (cyan background)
        
        node_options = {
            "label": str(attrs.get("label", nid)),
            "title": title,
            "color": color,
            "shape": shape,
            "font": {"face": "Segoe UI", "size": 16, "color": font_color},
        }
        
        # Add hierarchical positioning based on entity type
        if attrs.get("kind") == "folder":
            # Separate root folders from subfolders
            display_path = attrs.get("display_path", "")
            folder_name = attrs.get("name", "")
            
            if "/" not in display_path or display_path in [".", "0-bootstrap", "modules"]:
                # Root folders - FAR LEFT (furthest left position)
                root_folders = [(fid, fattrs) for fid, fattrs in folders if 
                               "/" not in fattrs.get("display_path", "") or 
                               fattrs.get("display_path", "") in [".", "0-bootstrap", "modules"]]
                folder_index = next(i for i, (fid, _) in enumerate(root_folders) if fid == nid)
                node_options["x"] = -1200  # Furthest left position for root folders
                node_options["y"] = folder_index * 120 - len(root_folders) * 60
            else:
                # Subfolders - RIGHT of root folders (clear hierarchy)
                sub_folders = [(fid, fattrs) for fid, fattrs in folders if 
                              "/" in fattrs.get("display_path", "") and 
                              fattrs.get("display_path", "") not in [".", "0-bootstrap", "modules"]]
                folder_index = next(i for i, (fid, _) in enumerate(sub_folders) if fid == nid)
                node_options["x"] = -700  # To the right of root folders with 500px gap
                node_options["y"] = folder_index * 80 - len(sub_folders) * 40
            
            node_options["physics"] = False
            node_options["fixed"] = {"x": True, "y": True}
            
        elif attrs.get("kind") == "terraform_file":
            # Terraform files - third column with much more distinct spacing
            tf_index = next(i for i, (tid, _) in enumerate(terraform_files) if tid == nid)
            node_options["x"] = 100  # Slightly right of center for better spacing
            node_options["y"] = tf_index * 160 - len(terraform_files) * 80  # Much more spacing: 160px between terraform files
            node_options["physics"] = False
            node_options["fixed"] = {"x": True, "y": True}
            
        else:
            # Other entities - separate registry modules from registry entities
            module_type = attrs.get("module_type", "")
            
            if module_type == "registry_entity" or "[public registry]" in attrs.get("label", ""):
                # Public registry entities - furthest right
                registry_entities = [(oid, oattrs) for oid, oattrs in other_entities if 
                                   oattrs.get("module_type", "") == "registry_entity" or 
                                   "[public registry]" in oattrs.get("label", "")]
                other_index = next(i for i, (oid, _) in enumerate(registry_entities) if oid == nid)
                node_options["x"] = 1100  # Furthest right for public registry
                node_options["y"] = other_index * 80 - len(registry_entities) * 40
            elif module_type == "registry_module" or "[registry]" in attrs.get("label", ""):
                # Registry modules - right side but before public registry
                registry_modules = [(oid, oattrs) for oid, oattrs in other_entities if 
                                  (oattrs.get("module_type", "") == "registry_module" or 
                                   "[registry]" in oattrs.get("label", "")) and
                                  not (oattrs.get("module_type", "") == "registry_entity" or 
                                       "[public registry]" in oattrs.get("label", ""))]
                other_index = next(i for i, (oid, _) in enumerate(registry_modules) if oid == nid)
                node_options["x"] = 900  # Registry modules column
                node_options["y"] = other_index * 80 - len(registry_modules) * 40
            elif module_type == "git_entity" or "[git repository]" in attrs.get("label", ""):
                # Git repository entities - right of git modules
                git_entities = [(oid, oattrs) for oid, oattrs in other_entities if 
                               oattrs.get("module_type", "") == "git_entity" or 
                               "[git repository]" in oattrs.get("label", "")]
                other_index = next(i for i, (oid, _) in enumerate(git_entities) if oid == nid)
                node_options["x"] = 800  # Right of git modules
                node_options["y"] = other_index * 80 - len(git_entities) * 40
            elif module_type == "git_module" or "[git module]" in attrs.get("label", ""):
                # Git modules - before git repository entities
                git_modules = [(oid, oattrs) for oid, oattrs in other_entities if 
                              (oattrs.get("module_type", "") == "git_module" or 
                               "[git module]" in oattrs.get("label", "")) and
                              not (oattrs.get("module_type", "") == "git_entity" or 
                                   "[git repository]" in oattrs.get("label", ""))]
                other_index = next(i for i, (oid, _) in enumerate(git_modules) if oid == nid)
                node_options["x"] = 700  # Git modules column
                node_options["y"] = other_index * 80 - len(git_modules) * 40
            elif module_type == "terraform_resource" or "[terraform resource]" in attrs.get("label", "") or attrs.get("kind") == "resource":
                # Terraform resources - extra spacing for maximum readability
                terraform_resources = [(oid, oattrs) for oid, oattrs in other_entities if 
                                     (oattrs.get("module_type", "") == "terraform_resource" or 
                                      "[terraform resource]" in oattrs.get("label", "") or
                                      oattrs.get("kind") == "resource")]
                other_index = next(i for i, (oid, _) in enumerate(terraform_resources) if oid == nid)
                node_options["x"] = 600  # Dedicated column for terraform resources
                node_options["y"] = other_index * 140 - len(terraform_resources) * 70  # Much more spacing: 140px between resources
            else:
                # All other entities (local modules, etc.)
                remaining_entities = [(oid, oattrs) for oid, oattrs in other_entities if 
                                    not (oattrs.get("module_type", "") in ["registry_entity", "registry_module", "git_entity", "git_module", "terraform_resource"] or 
                                         "[registry]" in oattrs.get("label", "") or 
                                         "[public registry]" in oattrs.get("label", "") or
                                         "[git module]" in oattrs.get("label", "") or
                                         "[git repository]" in oattrs.get("label", "") or
                                         "[terraform resource]" in oattrs.get("label", "") or
                                         oattrs.get("kind") == "resource")]
                other_index = next(i for i, (oid, _) in enumerate(remaining_entities) if oid == nid)
                node_options["x"] = 500  # Left of resource and git/registry columns
                node_options["y"] = other_index * 80 - len(remaining_entities) * 40
            
            node_options["physics"] = False
            node_options["fixed"] = {"x": True, "y": True}
        
        # Add level information for hierarchical layout (fallback)
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
    
    # JavaScript positioning disabled - using direct node positioning instead
    # Add JavaScript to ensure nodes stay where dropped and add search functionality
    _add_position_lock_script(output_path)
    _add_search_interface(output_path)

def _force_three_column_layout(output_path: Path, folders, terraform_files, other_entities) -> None:
    """Force four-column hierarchical layout by directly positioning nodes with JavaScript."""
    with open(output_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Separate root folders from subfolders
    root_folders = []
    sub_folders = []
    
    for nid, attrs in folders:
        display_path = attrs.get("display_path", "")
        # Root folders have no '/' in display_path or are single names
        if "/" not in display_path or display_path in [".", "0-bootstrap", "modules"]:
            root_folders.append((nid, attrs))
        else:
            sub_folders.append((nid, attrs))
    
    # Create positioning data for JavaScript
    root_folder_positions = {}
    sub_folder_positions = {}
    tf_positions = {}
    other_positions = {}
    
    # Column 1: Root folders (leftmost)
    for i, (nid, attrs) in enumerate(root_folders):
        root_folder_positions[nid] = {"x": -800, "y": i * 100 - len(root_folders) * 50}
    
    # Column 2: Subfolders (middle-left) 
    for i, (nid, attrs) in enumerate(sub_folders):
        sub_folder_positions[nid] = {"x": -400, "y": i * 80 - len(sub_folders) * 40}
    
    # Column 3: Terraform files (middle)
    for i, (nid, attrs) in enumerate(terraform_files):
        tf_positions[nid] = {"x": 0, "y": i * 80 - len(terraform_files) * 40}
        
    # Column 4: Other entities (rightmost)
    for i, (nid, attrs) in enumerate(other_entities):
        other_positions[nid] = {"x": 600, "y": i * 60 - len(other_entities) * 30}
    
    # JavaScript to force positioning
    force_layout_script = f"""
    <script>
    // Force four-column hierarchical layout after network initialization
    network.on('stabilizationIterationsDone', function() {{
        console.log('Forcing four-column hierarchical layout...');
        
        var rootFolderPositions = {root_folder_positions};
        var subFolderPositions = {sub_folder_positions};
        var tfPositions = {tf_positions};
        var otherPositions = {other_positions};
        
        var allPositions = Object.assign({{}}, rootFolderPositions, subFolderPositions, tfPositions, otherPositions);
        
        // Update node positions
        network.setData({{
            nodes: nodes,
            edges: edges
        }});
        
        // Move nodes to exact positions
        for (var nodeId in allPositions) {{
            network.moveNode(nodeId, allPositions[nodeId].x, allPositions[nodeId].y);
        }}
        
        // Disable physics to prevent movement
        network.setOptions({{
            physics: {{ enabled: false }}
        }});
        
        console.log('Four-column hierarchical layout applied!');
    }});
    </script>
    """
    
    # Insert before closing body tag
    html_content = html_content.replace('</body>', force_layout_script + '\n</body>')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

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

def _three_column_layout_options() -> str:
    """Options for four-column hierarchical layout."""
    return """{
      "physics": {
        "enabled": false
      },
      "layout": {
        "hierarchical": {
          "enabled": false
        },
        "randomSeed": 42,
        "improvedLayout": false
      },
      "interaction": {
        "dragNodes": true,
        "dragView": true,
        "zoomView": true
      },
      "nodes": {
        "physics": false,
        "fixed": {
          "x": true,
          "y": true
        },
        "chosen": false
      },
      "edges": { 
        "arrows": { "to": { "enabled": true } }, 
        "smooth": { "type": "cubicBezier" },
        "physics": false
      }
    }"""

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
    is_git_module = module_type == "git_module" or "[git module]" in str(attrs.get("label", ""))
    is_git_entity = module_type == "git_entity" or "[git repository]" in str(attrs.get("label", ""))
    is_terraform_file = kind == "terraform_file" or module_type == "terraform_file"
    is_terraform_resource = kind == "resource" or module_type == "terraform_resource" or "[resource]" in str(attrs.get("label", ""))
    
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
        elif is_terraform_resource:
            return "#00bcd4"  # Cyan for terraform resources
        elif is_source_module:
            return _darken_color(base_color)
        elif is_registry_module:
            return "#795548"  # Brown for registry modules
        elif is_registry_entity:
            return "#4caf50"  # Green for registry entities (better readability)
        elif is_git_module:
            return "#3f51b5"  # Indigo for git modules (better readability with black text)
        elif is_git_entity:
            return "#2196f3"  # Blue for git repositories (better readability)
        return base_color
    
    if color_by == "status":
        if is_folder:
            return "#ffc107"  # Amber for folders
        elif is_terraform_file:
            return "#9e9e9e"  # Gray for terraform files
        elif is_terraform_resource:
            return "#00bcd4"  # Cyan for terraform resources
        elif is_source_module:
            return "#e91e63"  # Pink for source modules
        elif is_registry_module:
            return "#795548"  # Brown for registry modules
        elif is_registry_entity:
            return "#4caf50"  # Green for registry entities
        elif is_git_module:
            return "#3f51b5"  # Indigo for git modules (better readability with black text)
        elif is_git_entity:
            return "#2196f3"  # Blue for git repositories (better readability)
        return "#03a9f4" if kind == "module" else "#8bc34a"
    
    # Default color scheme by type
    if is_folder:
        return "#ffc107"  # Amber for folders
    elif is_terraform_file:
        return "#9e9e9e"  # Gray for terraform files
    elif is_terraform_resource:
        return "#00bcd4"  # Cyan for terraform resources
    elif is_source_module:
        return "#2196f3"  # Blue for source modules (better contrast with black text)
    elif is_registry_module:
        return "#795548"  # Brown for registry modules
    elif is_registry_entity:
        return "#4caf50"  # Green for registry entities (better readability)
    elif is_git_module:
        return "#3f51b5"  # Indigo for git modules (better readability with black text)
    elif is_git_entity:
        return "#2196f3"  # Blue for git repositories (better readability)
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
    """Build tooltip content for nodes, including clickable file, registry, and git links."""
    file_path = attrs.get("file_path", "")
    folder_path = attrs.get("folder_path", "")
    d = attrs.get("dir", "")
    registry_source = attrs.get("registry_source", "")
    git_url = attrs.get("git_url", "")
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
    
    # For Git repositories, create a clickable link to the Git URL
    if kind == "git_entity" and git_url:
        return f'<a href="{git_url}" target="_blank" style="color: #0066cc; text-decoration: underline; font-weight: bold;">{git_url}</a>'
    
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
