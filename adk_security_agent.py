#!/usr/bin/env python3
"""
ADK Security Agent - Powered by Google Agent Development Kit & Vertex AI (Claude)
"""

import os
import sys
import json
import subprocess
import asyncio
from pathlib import Path
from typing import List, Dict

import click
from rich.console import Console
from rich.panel import Panel

try:
    from google.adk.agents import LlmAgent
    from google.adk.engine import Runner
    from google.adk.tools import tool
except ImportError:
    print("Please install google-adk: pip install google-adk")
    sys.exit(1)

console = Console()

# =============================================================================
# ADK TOOLS
# =============================================================================

@tool
def read_file(file_path: str) -> str:
    """Reads the content of a file in the repository."""
    try:
        return Path(file_path).read_text()
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
def write_file(file_path: str, content: str) -> str:
    """Writes new content to a file in the repository."""
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(file_path).write_text(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

@tool
def run_go_tests(repo_dir: str) -> str:
    """Runs go tests in the specified repository directory."""
    try:
        result = subprocess.run(
            ["go", "test", "-short", "./..."],
            cwd=repo_dir,
            capture_output=True,
            timeout=300
        )
        if result.returncode == 0:
            return "Tests passed successfully.\n" + result.stdout.decode()[:500]
        else:
            return "Tests failed:\n" + result.stderr.decode()[:1000]
    except Exception as e:
        return f"Test execution error: {str(e)}"

@tool
def search_codebase(repo_dir: str, pattern: str) -> str:
    """Searches the codebase for a specific string pattern."""
    try:
        result = subprocess.run(
            ["grep", "-rnw", repo_dir, "-e", pattern],
            capture_output=True,
            text=True
        )
        return result.stdout[:2000] if result.stdout else "No matches found."
    except Exception as e:
        return f"Search error: {str(e)}"

# =============================================================================
# ADK AGENT SETUP
# =============================================================================

class ADKSecurityPlatform:
    def __init__(self, org: str, model: str):
        self.org = org
        self.model = model
        
        # Initialize the ADK LlmAgent configured for Vertex AI Claude
        self.agent = LlmAgent(
            name="SecurityFixer",
            model=self.model,
            tools=[read_file, write_file, run_go_tests, search_codebase],
            instruction="""You are an autonomous expert security researcher and Go developer.
Your goal is to analyze repositories, find security vulnerabilities (like EOL SDKs, deprecated packages, or vulnerable patterns), and apply minimal, precise fixes.
You have tools to read code, write code, run tests, and search the codebase.
Always verify your fixes by running tests before concluding.
When dealing with AWS SDK v1, upgrade it to AWS SDK v2 safely."""
        )
        self.runner = Runner(agent=self.agent)

    async def run_fix_workflow(self, repo_name: str, repo_path: str):
        """Executes the ADK Runner workflow on a specific repository."""
        console.print(Panel.fit(f"🤖 ADK Agent Analyzing & Fixing: {self.org}/{repo_name}", style="cyan"))
        
        prompt = f"""
        Please review the repository located at {repo_path}.
        1. Search for deprecated 'io/ioutil' and 'github.com/aws/aws-sdk-go' usage.
        2. Read the identified files.
        3. Write the fixed code back using the write_file tool.
        4. Run go tests to verify nothing is broken.
        Report a summary of what you fixed.
        """
        
        # ADK handles the reasoning loop, tool calling, and execution autonomously
        console.print("[dim]Agent is thinking and executing tools...[/dim]")
        
        final_response = ""
        async for event in self.runner.run(message=prompt):
            # Stream the ADK event loop to console
            if hasattr(event, "tool_call"):
                console.print(f"  [yellow]🛠️  Calling Tool: {event.tool_call.name}[/yellow]")
            elif hasattr(event, "text") and event.text:
                final_response += event.text
                
        console.print("\n[bold green]Agent Finished Execution. Summary:[/bold green]")
        console.print(final_response)

# =============================================================================
# CLI
# =============================================================================

@click.group()
def cli():
    """Google ADK Security Agent"""
    pass

@cli.command()
@click.option("--org", required=True, help="GitHub organization")
@click.option("--repo", required=True, help="Repository to fix")
@click.option("--model", default="vertex_ai/claude-3-5-sonnet-v2@20241022", help="LiteLLM/Vertex Model String")
def fix(org, repo, model):
    # Ensure ADC is setup for Vertex
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not os.environ.get("VERTEX_PROJECT"):
        console.print("[red]Vertex AI requires Application Default Credentials. Run: gcloud auth application-default login[/red]")
    
    # Normally we would clone the repo here. For brevity, assuming the path:
    repo_path = Path(f"./forks/{repo}")
    repo_path.mkdir(parents=True, exist_ok=True)
    
    platform = ADKSecurityPlatform(org=org, model=model)
    asyncio.run(platform.run_fix_workflow(repo, str(repo_path.absolute())))

if __name__ == "__main__":
    cli()
