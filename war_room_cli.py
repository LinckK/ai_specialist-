"""
War Room CLI - Command-line interface for the Neural Boardroom

Usage:
    python -m agent_project.war_room_cli --input "Your strategic question" --mode GROWTH
    python -m agent_project.war_room_cli --file input.txt --mode SPEED
"""

import asyncio
import click
import sys
from pathlib import Path
from datetime import datetime

from agent_project.war_room_kernel import WarRoomKernel


@click.command()
@click.option(
    '--input', '-i', 
    help='Direct text input (strategic question or problem)',
    type=str
)
@click.option(
    '--file', '-f',
    help='Input file path (txt, md)',
    type=click.Path(exists=True)
)
@click.option(
    '--mode', '-m',
    default='SPEED',
    type=click.Choice(['SPEED', 'GROWTH', 'SCALE'], case_sensitive=False),
    help='Decision mode: SPEED (ship fast), GROWTH (market domination), SCALE (stability)'
)
@click.option(
    '--client', '-c',
    default='unnamed_client',
    help='Client name for report naming'
)
@click.option(
    '--output', '-o',
    help='Output file path (default: auto-generated)',
    type=str
)
@click.option(
    '--demo',
    is_flag=True,
    help='Run demo scenario'
)
def warroom(input, file, mode, client, output, demo):
    """
    WAR ROOM V2.0 - Neural Boardroom Multi-Agent Strategy System
    
    Executes 3 domain specialists in isolation, then synthesizes their
    outputs using cross-validation and mode-based decision hierarchies.
    """
    
    # Handle input sources
    if demo:
        user_input = get_demo_scenario()
        client = "demo_client"
    elif file:
        with open(file, 'r', encoding='utf-8') as f:
            user_input = f.read()
    elif input:
        user_input = input
    else:
        click.echo("Error: Must provide --input, --file, or --demo")
        sys.exit(1)
    
    # Normalize mode to uppercase
    mode = mode.upper()
    
    # Generate output path if not provided
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"war_room_report_{client}_{mode.lower()}_{timestamp}.md"
    
    # Execute War Room
    try:
        result = asyncio.run(execute_war_room(user_input, mode, client))
        
        # Generate and save report
        kernel = WarRoomKernel()  # For report generation method
        report = kernel.generate_report(result)
        
        with open(output, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # Display summary
        display_summary(result, output)
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def execute_war_room(user_input: str, mode: str, client: str):
    """Execute War Room analysis."""
    kernel = WarRoomKernel()
    
    result = await kernel.execute(
        user_input=user_input,
        mode=mode,
        client_name=client
    )
    
    return result


def display_summary(result: dict, output_path: str):
    """Display execution summary."""
    resolution = result.get('resolution')
    
    click.echo("\n" + "="*70)
    click.echo("WAR ROOM EXECUTION SUMMARY")
    click.echo("="*70)
    
    click.echo(f"\n📋 Mode: {result['mode']}")
    click.echo(f"👤 Client: {result['client_name']}")
    
    if resolution:
        click.echo(f"\n🏆 Winning Specialist: {resolution.winning_specialist}")
        click.echo(f"📊 Confidence: {resolution.metadata.get('confidence', 'N/A')}")
        click.echo(f"⚠️  Risk Level: {resolution.metadata.get('risk_level', 'N/A')}")
        click.echo(f"💰 Estimated Cost: {resolution.metadata.get('estimated_cost', 'N/A')}")
        click.echo(f"⏱️  Estimated Timeline: {resolution.metadata.get('estimated_timeline', 'N/A')}")
        
        if resolution.cross_validation_flags:
            click.echo(f"\n⚡ Cross-Validation Flags: {len(resolution.cross_validation_flags)}")
    
    click.echo(f"\n📄 Report saved to: {output_path}")
    click.echo("="*70 + "\n")


def get_demo_scenario():
    """Return a demo scenario for testing."""
    return """
I want to build an AI-powered email assistant for dentists that helps them write
patient follow-up emails after appointments.

Key features I'm considering:
1. AI-generated personalized follow-up emails
2. Integration with dental practice management software
3. Automated appointment reminder scheduling
4. Patient satisfaction surveys

We have 3 months until our Series A pitch and a team of 2 developers.
Should we focus on all features or prioritize differently?
    """.strip()


@click.command()
def test():
    """Run War Room test suite."""
    click.echo("Running War Room tests...")
    
    # Test 1: Agent loading
    click.echo("\n[Test 1] Loading specialists...")
    kernel = WarRoomKernel()
    
    if len(kernel.specialists) == 3:
        click.echo("✅ All 3 specialists loaded")
    else:
        click.echo(f"❌ Only {len(kernel.specialists)}/3 specialists loaded")
    
    # Test 2: ConflictResolver
    click.echo("\n[Test 2] Testing ConflictResolver...")
    from agent_project.conflict_resolver import ConflictResolver
    
    resolver = ConflictResolver()
    click.echo("✅ ConflictResolver initialized")
    
    click.echo("\n✅ All tests passed!")


# CLI group
@click.group()
def cli():
    """War Room V2.0 - Neural Boardroom System"""
    pass


cli.add_command(warroom, name='run')
cli.add_command(test)


if __name__ == "__main__":
    cli()
