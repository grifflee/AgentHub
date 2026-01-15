"""
CLI interface for AgentHub using Click.

This is the main entry point for the agenthub command-line tool.
It provides commands for registering, listing, searching, and
managing agents in the local registry.
"""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from . import __version__
from .database import (
    init_database,
    register_agent,
    get_agent,
    list_agents,
    search_agents,
    update_lifecycle_state,
    delete_agent,
)
from .manifest import load_manifest
from .models import LifecycleState

# Rich console for pretty output
console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="agenthub")
def main():
    """
    AgentHub - A CLI for registering and discovering AI agents.
    
    This tool implements a local agent registry based on the AgentHub
    research paper, supporting capability-based discovery and lifecycle
    management.
    """
    # Initialize database on every command
    init_database()


@main.command()
@click.argument('manifest_path', type=click.Path(exists=True))
def register(manifest_path: str):
    """Register a new agent from a YAML manifest file."""
    try:
        path = Path(manifest_path)
        record = load_manifest(path)
        registered = register_agent(record)
        
        console.print(Panel(
            f"[green]✓[/green] Agent [bold]{registered.name}[/bold] v{registered.version} registered successfully!",
            title="Registered",
            border_style="green"
        ))
        
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)
    except ValueError as e:
        console.print(f"[red]Validation Error:[/red]\n{e}")
        raise SystemExit(1)


@main.command('list')
@click.option('--state', type=click.Choice(['active', 'deprecated', 'retired', 'revoked']),
              help='Filter by lifecycle state')
def list_cmd(state: str):
    """List all registered agents."""
    lifecycle = LifecycleState(state) if state else None
    agents = list_agents(lifecycle_state=lifecycle)
    
    if not agents:
        console.print("[dim]No agents registered yet.[/dim]")
        console.print("Use [bold]agenthub register <manifest.yaml>[/bold] to add one.")
        return
    
    table = Table(title="Registered Agents", box=box.ROUNDED)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Version", style="magenta")
    table.add_column("State", style="green")
    table.add_column("Capabilities", style="yellow")
    table.add_column("Description")
    
    for agent in agents:
        state_color = {
            LifecycleState.ACTIVE: "green",
            LifecycleState.DEPRECATED: "yellow",
            LifecycleState.RETIRED: "dim",
            LifecycleState.REVOKED: "red",
        }.get(agent.lifecycle_state, "white")
        
        caps = ", ".join(agent.capabilities[:3])
        if len(agent.capabilities) > 3:
            caps += f" (+{len(agent.capabilities) - 3})"
        
        table.add_row(
            agent.name,
            agent.version,
            f"[{state_color}]{agent.lifecycle_state.value}[/]",
            caps,
            agent.description[:50] + "..." if len(agent.description) > 50 else agent.description
        )
    
    console.print(table)


@main.command()
@click.option('--capability', '-c', help='Search by capability')
@click.option('--query', '-q', help='Search by name or description')
def search(capability: str, query: str):
    """Search for agents by capability or text query."""
    if not capability and not query:
        console.print("[yellow]Please specify --capability or --query[/yellow]")
        raise SystemExit(1)
    
    agents = search_agents(capability=capability, query=query)
    
    if not agents:
        search_term = capability or query
        console.print(f"[dim]No agents found matching '{search_term}'[/dim]")
        return
    
    console.print(f"[bold]Found {len(agents)} agent(s):[/bold]\n")
    
    for agent in agents:
        console.print(Panel(
            f"[bold]{agent.name}[/bold] v{agent.version}\n"
            f"[dim]{agent.description}[/dim]\n\n"
            f"[cyan]Capabilities:[/cyan] {', '.join(agent.capabilities)}\n"
            f"[magenta]Protocols:[/magenta] {', '.join(p.value for p in agent.protocols)}\n"
            f"[yellow]State:[/yellow] {agent.lifecycle_state.value}",
            border_style="blue"
        ))


@main.command()
@click.argument('name')
def info(name: str):
    """Show detailed information about an agent."""
    agent = get_agent(name)
    
    if not agent:
        console.print(f"[red]Agent '{name}' not found[/red]")
        raise SystemExit(1)
    
    state_color = {
        LifecycleState.ACTIVE: "green",
        LifecycleState.DEPRECATED: "yellow",
        LifecycleState.RETIRED: "dim",
        LifecycleState.REVOKED: "red",
    }.get(agent.lifecycle_state, "white")
    
    console.print(Panel(
        f"[bold cyan]{agent.name}[/bold cyan] v{agent.version}\n"
        f"[dim]by {agent.author}[/dim]\n\n"
        f"{agent.description}\n\n"
        f"[bold]Lifecycle State:[/bold] [{state_color}]{agent.lifecycle_state.value}[/]\n"
        f"[bold]Capabilities:[/bold] {', '.join(agent.capabilities) or '[dim]none[/dim]'}\n"
        f"[bold]Protocols:[/bold] {', '.join(p.value for p in agent.protocols) or '[dim]none[/dim]'}\n"
        f"[bold]Permissions:[/bold] {', '.join(agent.permissions) or '[dim]none[/dim]'}\n\n"
        f"[dim]Created: {agent.created_at}[/dim]\n"
        f"[dim]Updated: {agent.updated_at}[/dim]",
        title=f"Agent: {name}",
        border_style="cyan"
    ))


@main.command()
@click.argument('name')
@click.option('--reason', '-r', help='Reason for deprecation')
def deprecate(name: str, reason: str):
    """Mark an agent as deprecated."""
    agent = get_agent(name)
    if not agent:
        console.print(f"[red]Agent '{name}' not found[/red]")
        raise SystemExit(1)
    
    if update_lifecycle_state(name, LifecycleState.DEPRECATED):
        console.print(f"[yellow]⚠[/yellow] Agent [bold]{name}[/bold] marked as deprecated")
        if reason:
            console.print(f"[dim]Reason: {reason}[/dim]")
    else:
        console.print(f"[red]Failed to update agent state[/red]")
        raise SystemExit(1)


@main.command()
@click.argument('name')
@click.confirmation_option(prompt='Are you sure you want to remove this agent?')
def remove(name: str):
    """Remove an agent from the registry."""
    if delete_agent(name):
        console.print(f"[green]✓[/green] Agent [bold]{name}[/bold] removed")
    else:
        console.print(f"[red]Agent '{name}' not found[/red]")
        raise SystemExit(1)


if __name__ == '__main__':
    main()
