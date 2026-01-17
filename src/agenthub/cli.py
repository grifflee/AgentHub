"""
CLI interface for AgentHub using Click.

This is the main entry point for the agenthub command-line tool.
It provides commands for registering, listing, searching, and
managing agents in the local registry.
"""

from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

# Configure dark orange theme for CLI help
click.rich_click.STYLE_OPTION = "#45c1ff"
click.rich_click.STYLE_ARGUMENT = "#45c1ff"
click.rich_click.STYLE_COMMAND = "bold #45c1ff"
click.rich_click.STYLE_USAGE = "bold #45c1ff"
click.rich_click.STYLE_USAGE_COMMAND = "bold #45c1ff"
click.rich_click.STYLE_HELPTEXT = "#45c1ff"
click.rich_click.STYLE_HEADER_TEXT = "bold #45c1ff"
click.rich_click.STYLE_OPTIONS_PANEL_BORDER = "#45c1ff"
click.rich_click.STYLE_COMMANDS_PANEL_BORDER = "#45c1ff"

from . import __version__
from .database import (
    init_database,
    register_agent,
    get_agent,
    list_agents,
    update_lifecycle_state,
    delete_agent,
)
from .manifest import load_manifest
from .models import LifecycleState
from .help import get_template_manifest, open_docs_in_browser

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
    
    GitHub: https://github.com/grifflee/AgentHub
    """
    # Initialize database on every command
    init_database()


@main.command(hidden=True)
@click.argument('name')
@click.option('--edit', '-e', is_flag=True, help='Open the file in your default editor after creation')
def init(name: str, edit: bool):
    """Create a template manifest file for a new agent.
    
    Example:
        agenthub init my-agent
        agenthub init my-agent --edit
    """
    # Normalize the name for the filename
    filename = f"{name}.yaml" if not name.endswith('.yaml') else name
    agent_name = name.replace('.yaml', '')
    
    path = Path(filename)
    
    if path.exists():
        console.print(f"[red]Error:[/red] File '{filename}' already exists")
        raise SystemExit(1)
    
    # Write the template
    template = get_template_manifest(agent_name)
    path.write_text(template)
    
    console.print(Panel(
        f"[green]✓[/green] Created [bold]{filename}[/bold]\n\n"
        f"[dim]Next steps:[/dim]\n"
        f"  1. Edit the file to add your agent's details\n"
        f"  2. Run [bold]agenthub register {filename}[/bold]",
        title="Template Created",
        border_style="green"
    ))
    
    if edit:
        import subprocess
        subprocess.run(['open', '-e', str(path)])


@main.command()
def example_manifest():
    """Show an example of a complete agent manifest."""
    manifest_content = '''[bold cyan]# Example Agent Manifest[/bold cyan]

[yellow]name:[/yellow] code-reviewer
[yellow]version:[/yellow] 1.0.0
[yellow]description:[/yellow] An AI agent that reviews code for bugs, style issues, and security vulnerabilities
[yellow]author:[/yellow] agenthub-team

[dim]# Capabilities - what this agent can do[/dim]
[yellow]capabilities:[/yellow]
  - code-review
  - bug-detection
  - style-checking
  - security-analysis

[dim]# Protocols - how to communicate with this agent[/dim]
[yellow]protocols:[/yellow]
  - MCP

[dim]# Permissions - what resources this agent needs[/dim]
[yellow]permissions:[/yellow]
  - read-files
  - network-access'''
    
    console.print(Panel(
        manifest_content,
        title="[bold]Sample Manifest[/bold]",
        border_style="#45c1ff",
        box=box.ROUNDED
    ))


@main.command()
@click.argument('manifest_path', type=click.Path(exists=True), required=False)
@click.option('--docs', is_flag=True, help='Open manifest documentation in browser')
def register(manifest_path: str, docs: bool):
    """Register a new agent from a YAML manifest file.
    
    Example:
        agenthub register my-agent.yaml
    
    If no file is provided, shows options to help you get started.
    """
    # Handle --docs flag
    if docs:
        if open_docs_in_browser():
            console.print("[green]✓[/green] Opened documentation in browser")
        else:
            console.print("[red]Error:[/red] Could not find documentation file")
            raise SystemExit(1)
        return
    
    # If no manifest path provided, show helpful options
    if not manifest_path:
        console.print(Panel(
            "[bold]How to register an agent:[/bold]\n\n"
            "1. View an example manifest:\n"
            "   [#45c1ff]agenthub example-manifest[/#45c1ff]\n\n"
            "2. Create your manifest file (e.g., my-agent.yaml)\n\n"
            "3. Register it:\n"
            "   [#45c1ff]agenthub register my-agent.yaml[/#45c1ff]\n\n"
            "[dim]Shortcut: [bold]agenthub init my-agent[/bold] generates a template file for you.[/dim]\n"
            "[dim]Run [bold]agenthub register --docs[/bold] to view the full manifest format in your browser.[/dim]",
            title="[bold #45c1ff]📋 Registration Help[/bold #45c1ff]",
            border_style="#45c1ff",
            box=box.ROUNDED
        ))
        return
    
    # Normal registration flow
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
    
    # Display available commands
    console.print()
    commands_panel = Panel(
        "[bold #45c1ff]agenthub info <name>[/]      Show detailed information about an agent\n"
        "[bold #45c1ff]agenthub search[/]           Launch Agent Interviewer to find agents\n"
        "[bold #45c1ff]agenthub deprecate <name>[/] Mark an agent as deprecated\n"
        "[bold #45c1ff]agenthub remove <name>[/]    Remove an agent from the registry\n"
        "[bold #45c1ff]agenthub register <file>[/]  Register a new agent from manifest",
        title="[bold]Available Commands[/]",
        border_style="#45c1ff",
        box=box.ROUNDED
    )
    console.print(commands_panel)


@main.command()
def search():
    """Launch the Agent Interviewer to find agents for your task."""
    agents = list_agents()
    
    if not agents:
        console.print("[dim]No agents registered yet.[/dim]")
        console.print("Use [bold]agenthub register <manifest.yaml>[/bold] to add one.")
        return
    
    # Display the Agent Interviewer header
    console.print()
    console.print(Panel(
        "[bold]Welcome to the Agent Interviewer[/bold]\n\n"
        "[dim]This intelligent discovery system helps you find the right agent for your task.\n"
        "Describe what you need, and the interviewer will analyze registered agents\n"
        "to recommend the best match based on capabilities and behavioral evidence.[/dim]\n\n"
        "[yellow]⚠ Coming Soon:[/yellow] A fine-tuned model will be integrated here to:\n"
        "  • Understand your task requirements through conversation\n"
        "  • Query agents about their capabilities\n"
        "  • Evaluate agents using structured interviews\n"
        "  • Provide ranked recommendations with explanations",
        title="[bold #45c1ff]🔍 Agent Interviewer[/bold #45c1ff]",
        border_style="#45c1ff",
        box=box.ROUNDED
    ))
    
    # Show currently available agents
    console.print()
    console.print(f"[bold]Registered Agents ({len(agents)} available):[/bold]")
    for agent in agents:
        caps = ", ".join(agent.capabilities[:3])
        if len(agent.capabilities) > 3:
            caps += f" (+{len(agent.capabilities) - 3})"
        console.print(f"  [cyan]•[/cyan] [bold]{agent.name}[/bold] - {caps}")
    
    # Placeholder for future interaction
    console.print()
    console.print(Panel(
        "[dim]Interactive agent discovery is not yet implemented.\n"
        "For now, use [bold]agenthub info <name>[/bold] to learn more about specific agents.[/dim]",
        border_style="dim"
    ))


@main.command(hidden=True)
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
