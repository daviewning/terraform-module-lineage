from __future__ import annotations

import sys
import traceback
import argparse
from pathlib import Path
from datetime import datetime
from rich import print
from rich.panel import Panel

from terraform_lineage.parsing.terraform_parser import parse_directory
from terraform_lineage.analysis.dependency_graph import build_graph, find_cycles
from terraform_lineage.visualization.html_renderer import render_html


def main():
    """Parse Terraform, build a dependency graph, and render interactive HTML."""
    parser = argparse.ArgumentParser(description="Terraform module relationship visualizer")
    
    # Add subparsers for commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate visualization')
    gen_parser.add_argument('--input', required=True, type=Path, help='Terraform root directory')
    gen_parser.add_argument('--output', required=True, type=Path, help='Output HTML file path')
    gen_parser.add_argument('--include-resources', action='store_true', help='Include Terraform resource nodes in the visualization')
    gen_parser.add_argument('--layout', default='hierarchical', choices=['hierarchical', 'flat'], help='Layout mode')
    gen_parser.add_argument('--color-by', default='type', choices=['type', 'environment', 'status'], help='Color strategy')
    gen_parser.add_argument('--debug', action='store_true', help='Print full tracebacks on errors')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'generate':
        try:
            root_dir = args.input.resolve()
            
            # Add timestamp to output filename
            original_output = args.output.resolve()
            timestamp = datetime.now().strftime("%H%M%S%d%m%Y")
            
            # Insert timestamp before file extension
            stem = original_output.stem
            suffix = original_output.suffix
            timestamped_name = f"{stem}_{timestamp}{suffix}"
            out_path = original_output.parent / timestamped_name

            print(Panel.fit(f"[bold]Parsing Terraform directory[/bold]\n{root_dir}"))
            parsed = parse_directory(root_dir)
            if args.include_resources:
                print(f"[dim]Parsed modules: {len(parsed.modules)}, resources: {len(parsed.resources)} (names: {len(parsed.name_index)})[/dim]")
            else:
                print(f"[dim]Parsed modules: {len(parsed.modules)} (names: {len(parsed.name_index)})[/dim]")

            print("[bold]Building dependency graph[/bold]")
            if args.debug:
                print(f"[dim]Modules found:[/dim]")
                for mid, m in parsed.modules.items():
                    print(f"[dim]  {mid}: source='{m.source}'[/dim]")
            
            G = build_graph(parsed, include_resources=args.include_resources)
            print(f"[dim]Graph nodes: {G.number_of_nodes()}, edges: {G.number_of_edges()}[/dim]")
            
            if args.debug and G.number_of_edges() > 0:
                print(f"[dim]Edges:[/dim]")
                for src, dst in G.edges():
                    print(f"[dim]  {src} -> {dst}[/dim]")

            cycles = list(find_cycles(G))
            if cycles:
                print(f"[yellow]Detected circular dependencies ({len(cycles)} cycles)[/yellow]")

            print("[bold]Rendering HTML visualization[/bold]")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            hierarchical = (args.layout.lower() == "hierarchical")
            render_html(G, out_path, hierarchical=hierarchical, color_by=args.color_by)

            print(Panel.fit(f"[green]Done[/green] → {out_path}"))
        except Exception as err:
            print(Panel.fit(f"[red]Error[/red]: {err}"))
            if args.debug:
                print(traceback.format_exc())
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
