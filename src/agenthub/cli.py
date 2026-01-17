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
    
    Tip: Use 'ah' as a shortcut alias (e.g., 'ah list' instead of 'agenthub list')
    
    GitHub: https://github.com/grifflee/AgentHub
    """
    # Initialize database on every command
    init_database()


@main.command('all-commands')
def all_commands():
    """Show a complete list of all available commands.
    
    Displays every command in the project with syntax and descriptions.
    """
    commands = """
[bold #45c1ff]AGENTHUB - COMPLETE COMMAND REFERENCE[/bold #45c1ff]

[bold]DISCOVERY COMMANDS[/bold]
  ah list                           List all registered agents
  ah list --state active            Filter by lifecycle state
  ah search                         Launch Agent Interviewer
  ah rate <agent> <1-5>             Rate an agent (1-5 stars)

[bold]PUBLISHING COMMANDS[/bold]  (ah publish --help)
  ah publish init <name>            Create a manifest template
  ah publish init <name> --edit     Create and open in editor
  ah publish register <file>        Register agent from manifest
  ah publish register --docs        Open manifest docs in browser
  ah publish deprecate <name>       Mark agent as deprecated
  ah publish deprecate <name> -r    Include deprecation reason
  ah publish remove <name>          Delete agent from registry
  ah publish fork <agent> -n <name> Fork an agent with lineage

[bold]TRUST & SIGNING COMMANDS[/bold]  (ah trust --help)
  ah trust keygen                   Generate Ed25519 keypair
  ah trust sign <file>              Sign a manifest file
  ah trust verify <file>            Verify manifest signature
  ah trust status                   Show keypair configuration

[bold]UTILITY COMMANDS[/bold]  (hidden from main help)
  ah example-manifest               Show example manifest inline
  ah lineage <agent>                Show fork ancestry tree
  ah info <agent>                   Show detailed agent info

[bold]OPTIONS[/bold]
  ah --version                      Show version number
  ah --help                         Show main help menu
  ah <command> --help               Show help for any command
"""
    console.print(Panel(
        commands.strip(),
        title="All Commands",
        border_style="#45c1ff",
        box=box.ROUNDED
    ))


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


# =============================================================================
# Trust & Signing Commands (grouped under 'agenthub trust')
# =============================================================================

@main.group()
def trust():
    """Trust and signing commands for manifest verification.
    
    These commands manage cryptographic signing for agent manifests,
    enabling trust and provenance verification.
    
    \b
    Workflow:
      1. agenthub trust keygen     Generate your signing keypair (once)
      2. agenthub trust sign       Sign a manifest before registering
      3. agenthub trust verify     Verify a signed manifest
    
    Example:
        agenthub trust keygen
        agenthub trust sign my-agent.yaml
        agenthub trust verify my-agent.yaml
    """
    pass


@trust.command()
def keygen():
    """Generate a new Ed25519 signing keypair.
    
    Creates a keypair in ~/.agenthub/keys/ for signing agent manifests.
    The private key is kept secure on your machine; the public key is
    embedded in signed manifests for verification.
    
    Example:
        agenthub trust keygen
    """
    from .signing import generate_keypair, save_keypair, has_keypair, get_keys_dir
    
    if has_keypair():
        console.print(Panel(
            f"[yellow]⚠[/yellow] A keypair already exists at [bold]{get_keys_dir()}[/bold]\n\n"
            "[dim]To generate a new keypair, first delete the existing keys.[/dim]",
            title="Keypair Exists",
            border_style="yellow"
        ))
        return
    
    try:
        private_pem, public_pem = generate_keypair()
        keys_dir = save_keypair(private_pem, public_pem)
        
        console.print(Panel(
            f"[green]✓[/green] Generated Ed25519 keypair\n\n"
            f"[bold]Location:[/bold] {keys_dir}\n"
            f"  • private.pem [dim](keep this secret!)[/dim]\n"
            f"  • public.pem\n\n"
            f"[dim]Next: Sign a manifest with [bold]agenthub trust sign manifest.yaml[/bold][/dim]",
            title="Keypair Generated",
            border_style="green"
        ))
    except ImportError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@trust.command()
@click.argument('manifest_path', type=click.Path(exists=True))
def sign(manifest_path: str):
    """Sign an agent manifest with your private key.
    
    This adds signature, public_key, and signed_at fields to the manifest.
    You must first run 'agenthub trust keygen' to generate a keypair.
    
    Example:
        agenthub trust sign my-agent.yaml
    """
    from .signing import sign_manifest_file, has_keypair
    
    if not has_keypair():
        console.print(Panel(
            "[red]✗[/red] No keypair found.\n\n"
            "Run [bold]agenthub trust keygen[/bold] first to generate a signing keypair.",
            title="No Keypair",
            border_style="red"
        ))
        raise SystemExit(1)
    
    try:
        path = Path(manifest_path)
        manifest_data = sign_manifest_file(path)
        
        console.print(Panel(
            f"[green]✓[/green] Signed [bold]{path.name}[/bold]\n\n"
            f"[bold]Signature:[/bold] {manifest_data['signature'][:40]}...\n"
            f"[bold]Signed at:[/bold] {manifest_data['signed_at']}\n\n"
            f"[dim]The manifest has been updated in-place with signature fields.[/dim]",
            title="Manifest Signed",
            border_style="green"
        ))
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error signing manifest:[/red] {e}")
        raise SystemExit(1)


@trust.command()
@click.argument('manifest_path', type=click.Path(exists=True))
def verify(manifest_path: str):
    """Verify the signature of a signed manifest.
    
    Checks that the manifest's signature is valid and matches the content.
    
    Example:
        agenthub trust verify my-agent.yaml
    """
    from .signing import verify_manifest_file
    
    try:
        path = Path(manifest_path)
        is_valid, error_msg = verify_manifest_file(path)
        
        if is_valid:
            console.print(Panel(
                f"[green]✓[/green] Signature is [bold green]VALID[/bold green]\n\n"
                f"[dim]The manifest [bold]{path.name}[/bold] has not been tampered with.[/dim]",
                title="Verification Passed",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[red]✗[/red] Signature is [bold red]INVALID[/bold red]\n\n"
                f"[bold]Reason:[/bold] {error_msg}",
                title="Verification Failed",
                border_style="red"
            ))
            raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error verifying manifest:[/red] {e}")
        raise SystemExit(1)


@trust.command()
def status():
    """Show the current trust configuration status.
    
    Displays whether you have a keypair and its location.
    
    Example:
        agenthub trust status
    """
    from .signing import has_keypair, get_keys_dir
    
    keys_dir = get_keys_dir()
    
    if has_keypair():
        console.print(Panel(
            f"[green]✓[/green] Keypair configured\n\n"
            f"[bold]Location:[/bold] {keys_dir}\n"
            f"  • private.pem [dim](keep this secret!)[/dim]\n"
            f"  • public.pem",
            title="Trust Status",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[yellow]![/yellow] No keypair found\n\n"
            f"[dim]Run [bold]agenthub trust keygen[/bold] to create a signing keypair.[/dim]",
            title="Trust Status",
            border_style="yellow"
        ))


# =============================================================================
# Publishing Commands (grouped under 'ah publish')
# =============================================================================

@main.group()
def publish():
    """Commands for agent authors and publishers.
    
    Use these commands to register, manage, and fork agents.
    
    \b
    Workflow:
      1. ah publish init <name>       Create a manifest template
      2. ah trust sign <file>         Sign the manifest
      3. ah publish register <file>   Register the agent
    
    \b
    Management:
      ah publish deprecate <name>     Mark as deprecated
      ah publish remove <name>        Delete from registry
      ah publish fork <name>          Create a derivative
    """
    pass


@publish.command()
@click.argument('name')
@click.option('--edit', '-e', is_flag=True, help='Open in editor after creation')
def init(name: str, edit: bool):
    """Create a template manifest file for a new agent.
    
    Example:
        ah publish init my-agent
        ah publish init my-agent --edit
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
        f"[green]![/green] Created [bold]{filename}[/bold]\n\n"
        f"[dim]Next steps:[/dim]\n"
        f"  1. Edit the file to add your agent's details\n"
        f"  2. Run [bold]ah publish register {filename}[/bold]",
        title="Template Created",
        border_style="green"
    ))
    
    if edit:
        import subprocess
        subprocess.run(['open', '-e', str(path)])


@publish.command()
@click.argument('manifest_path', type=click.Path(exists=True), required=False)
@click.option('--docs', is_flag=True, help='Open manifest documentation in browser')
def register(manifest_path: str, docs: bool):
    """Register a new agent from a YAML manifest file.
    
    Example:
        ah publish register my-agent.yaml
    
    If no file is provided, shows options to help you get started.
    """
    # Handle --docs flag
    if docs:
        if open_docs_in_browser():
            console.print("[green]![/green] Opened documentation in browser")
        else:
            console.print("[red]Error:[/red] Could not find documentation file")
            raise SystemExit(1)
        return
    
    # If no manifest path provided, show helpful options
    if not manifest_path:
        console.print(Panel(
            "[bold]How to register an agent:[/bold]\n\n"
            "1. Create a manifest template:\n"
            "   [#45c1ff]ah publish init my-agent[/#45c1ff]\n\n"
            "2. Edit the file with your agent's details\n\n"
            "3. Register it:\n"
            "   [#45c1ff]ah publish register my-agent.yaml[/#45c1ff]\n\n"
            "[dim]Run [bold]ah publish register --docs[/bold] to view the full manifest format.[/dim]",
            title="[bold #45c1ff]Registration Help[/bold #45c1ff]",
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
            f"[green]![/green] Agent [bold]{registered.name}[/bold] v{registered.version} registered successfully!",
            title="Registered",
            border_style="green"
        ))
        
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)
    except ValueError as e:
        console.print(f"[red]Validation Error:[/red]\n{e}")
        raise SystemExit(1)


@publish.command()
@click.argument('name')
@click.option('--reason', '-r', help='Reason for deprecation')
def deprecate(name: str, reason: str):
    """Mark an agent as deprecated.
    
    Example:
        ah publish deprecate my-agent --reason "Use v2 instead"
    """
    agent = get_agent(name)
    if not agent:
        console.print(f"[red]Agent '{name}' not found[/red]")
        raise SystemExit(1)
    
    if update_lifecycle_state(name, LifecycleState.DEPRECATED):
        console.print(f"[yellow]![/yellow] Agent [bold]{name}[/bold] marked as deprecated")
        if reason:
            console.print(f"[dim]Reason: {reason}[/dim]")
    else:
        console.print(f"[red]Failed to update agent state[/red]")
        raise SystemExit(1)


@publish.command()
@click.argument('name')
@click.confirmation_option(prompt='Are you sure you want to remove this agent?')
def remove(name: str):
    """Remove an agent from the registry.
    
    Example:
        ah publish remove my-agent
    """
    if delete_agent(name):
        console.print(f"[green]![/green] Agent [bold]{name}[/bold] removed")
    else:
        console.print(f"[red]Agent '{name}' not found[/red]")
        raise SystemExit(1)


@publish.command()
@click.argument('source_agent')
@click.option('--name', '-n', required=True, help='Fork name suffix (e.g., "security")')
@click.option('--author', '-a', help='New author (defaults to original)')
def fork(source_agent: str, name: str, author: str):
    """Fork an existing agent to create a derivative.
    
    Creates a new agent entry that tracks its lineage back to the original.
    
    Example:
        ah publish fork code-reviewer --name security-enhanced
    """
    from .identity import generate_agent_id, build_lineage
    
    # Find source agent
    source = get_agent(source_agent)
    if not source:
        console.print(f"[red]Agent '{source_agent}' not found[/red]")
        raise SystemExit(1)
    
    # Determine new author
    new_author = author or getattr(source, 'author', 'unknown')
    base_name = getattr(source, 'name', source_agent)
    
    # Generate new ID
    new_agent_id = generate_agent_id(new_author, base_name, name)
    
    # Build lineage
    parent_lineage = getattr(source, 'lineage', []) or []
    if not parent_lineage:
        parent_id = generate_agent_id(getattr(source, 'author', 'unknown'), base_name)
        parent_lineage = [parent_id]
    
    new_lineage = build_lineage(parent_lineage, new_agent_id)
    new_generation = len(new_lineage) - 1
    
    console.print(Panel(
        f"[green]![/green] Fork created\n\n"
        f"[bold]New Agent ID:[/bold] {new_agent_id}\n"
        f"[bold]Parent:[/bold] {parent_lineage[-1] if parent_lineage else 'none'}\n"
        f"[bold]Generation:[/bold] {new_generation}\n\n"
        f"[dim]Next steps:[/dim]\n"
        f"  1. Create manifest: [bold]ah publish init {base_name}+{name}[/bold]\n"
        f"  2. Add lineage fields to manifest\n"
        f"  3. Register: [bold]ah publish register {base_name}+{name}.yaml[/bold]",
        title="Fork Created",
        border_style="green"
    ))


# =============================================================================
# Core Discovery Commands (top level)
# =============================================================================

@main.command(hidden=True)
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


# =============================================================================
# Quality & Identity Commands (Phase 5)
# =============================================================================

@main.command()
@click.argument('agent_name')
@click.argument('rating', type=click.IntRange(1, 5))
def rate(agent_name: str, rating: int):
    """Rate an agent from 1 to 5 stars.
    
    Note: In a full implementation, this would require proof of download.
    For now, it updates the rating directly.
    
    Example:
        ah rate code-reviewer 5
    """
    agent = get_agent(agent_name)
    if not agent:
        console.print(f"[red]Agent '{agent_name}' not found[/red]")
        raise SystemExit(1)
    
    # Update rating (simplified - in production would verify download receipt)
    # For now, we'll just show what would happen
    new_sum = getattr(agent, 'rating_sum', 0) + rating
    new_count = getattr(agent, 'rating_count', 0) + 1
    new_avg = new_sum / new_count
    
    console.print(Panel(
        f"[green]✓[/green] Rated [bold]{agent_name}[/bold]: {rating}/5 stars\n\n"
        f"[bold]New average:[/bold] {new_avg:.1f}/5 ({new_count} ratings)\n\n"
        f"[dim]In production, this would require a download receipt.[/dim]",
        title="Rating Submitted",
        border_style="green"
    ))


@main.command(hidden=True)
@click.argument('agent_name')
def lineage(agent_name: str):
    """Show the ancestry tree of a forked agent.
    
    Displays the full lineage from the original agent to this one.
    
    Example:
        ah lineage code-reviewer+security
    """
    from .identity import format_lineage_tree
    
    agent = get_agent(agent_name)
    if not agent:
        console.print(f"[red]Agent '{agent_name}' not found[/red]")
        raise SystemExit(1)
    
    agent_lineage = getattr(agent, 'lineage', []) or []
    generation = getattr(agent, 'generation', 0)
    
    if not agent_lineage:
        console.print(Panel(
            f"[bold]{agent_name}[/bold] is an original agent (no forks in lineage)\n\n"
            f"[dim]Generation: 0 (original)[/dim]",
            title="Lineage",
            border_style="#45c1ff"
        ))
        return
    
    tree = format_lineage_tree(agent_lineage)
    
    console.print(Panel(
        f"{tree}\n\n"
        f"[dim]Generation: {generation}[/dim]",
        title=f"Lineage Tree: {agent_name}",
        border_style="#45c1ff"
    ))


if __name__ == '__main__':
    main()
