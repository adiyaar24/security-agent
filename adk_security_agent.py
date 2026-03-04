#!/usr/bin/env python3
"""
ADK Security Agent - Polyglot Autonomous Fixer
Uses Google ADK, Vertex AI (Claude 4.5), and GitHub API
"""

import os
import sys
import subprocess
import asyncio
import requests
import shutil
from pathlib import Path

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
# GITHUB CLIENT 
# =============================================================================

class GitHubClient:
    def __init__(self, token: str):
        self.headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        self.api = "https://api.github.com"
    
    def get_user(self):
        r = requests.get(f"{self.api}/user", headers=self.headers)
        r.raise_for_status()
        return r.json()
    
    def fork_repo(self, owner: str, repo: str):
        r = requests.post(f"{self.api}/repos/{owner}/{repo}/forks", headers=self.headers)
        r.raise_for_status()
        return r.json()
    
    def create_pr(self, owner: str, repo: str, title: str, head: str, base: str, body: str):
        r = requests.post(
            f"{self.api}/repos/{owner}/{repo}/pulls",
            headers=self.headers,
            json={"title": title, "head": head, "base": base, "body": body}
        )
        r.raise_for_status()
        return r.json()

# =============================================================================
# EXPANDABLE ADK TOOLS (Language Agnostic)
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
def run_command(command: str, repo_dir: str) -> str:
    """
    Executes a generic shell command in the repository directory.
    Use this to run tests (e.g., 'go test ./...', 'npm test', 'pytest'), 
    install dependencies, or run linters.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=repo_dir,
            capture_output=True,
            timeout=300
        )
        output = f"Exit Code: {result.returncode}\nSTDOUT:\n{result.stdout.decode()[:1500]}\nSTDERR:\n{result.stderr.decode()[:1500]}"
        return output
    except Exception as e:
        return f"Command execution error: {str(e)}"

@tool
def search_codebase(repo_dir: str, pattern: str) -> str:
    """Searches the codebase for a specific string pattern."""
    try:
        result = subprocess.run(["grep", "-rnw", repo_dir, "-e", pattern], capture_output=True, text=True)
        return result.stdout[:2000] if result.stdout else "No matches found."
    except Exception as e:
        return f"Search error: {str(e)}"

# =============================================================================
# ADK AGENT WORKFLOW
# =============================================================================

class ADKSecurityPlatform:
    def __init__(self, org: str, model: str, github_token: str):
        self.org = org
        self.github = GitHubClient(github_token)
        
        # Expandable, language-agnostic agent
        self.agent = LlmAgent(
            name="PolyglotSecurityFixer",
            model=model,
            tools=[read_file, write_file, run_command, search_codebase],
            instruction="""You are an autonomous expert security researcher and polyglot software engineer.
Your goal is to analyze repositories, find security vulnerabilities (EOL SDKs, deprecated packages, vulnerable patterns, hardcoded secrets), and apply minimal, precise fixes.
You are language-agnostic. Use the `run_command` tool to figure out how to build and test the repository (e.g., looking for package.json, go.mod, requirements.txt, etc.) and run the appropriate test commands.
Always verify your fixes by running tests before concluding. Ensure you do not delete any existing tests or business logic."""
        )
        self.runner = Runner(agent=self.agent)

    async def fix_and_pr(self, repo_name: str, create_pr: bool):
        """Forks, clones, fixes via ADK, and creates a PR."""
        console.print(Panel.fit(f"🤖 ADK Agent (Claude 4.5) Processing: {self.org}/{repo_name}", style="cyan"))
        
        # 1. Fork & Clone
        user = self.github.get_user()
        username = user["login"]
        try:
            self.github.fork_repo(self.org, repo_name)
        except Exception:
            pass # Already forked
            
        fork_path = Path(f"./forks/{repo_name}")
        if fork_path.exists():
            shutil.rmtree(fork_path)
            
        clone_url = f"https://{username}:{self.github.headers['Authorization'].split()[1]}@github.com/{username}/{repo_name}.git"
        subprocess.run(["git", "clone", "--depth", "1", clone_url, str(fork_path)], capture_output=True)
        subprocess.run(["git", "-C", str(fork_path), "checkout", "-b", "adk-security-updates"], capture_output=True)

        # 2. ADK Agent Execution
        prompt = f"""
        Please review the repository located at {fork_path.absolute()}.
        1. Search the codebase for deprecated dependencies, EOL SDKs, or security issues.
        2. Read the identified files.
        3. Write the fixed code back using the write_file tool.
        4. Run the appropriate build/test commands using run_command to verify nothing is broken.
        Report a summary of exactly what you fixed.
        """
        
        console.print("[dim]Agent is thinking and executing tools...[/dim]")
        final_summary = ""
        
        # Run ADK loop
        async for event in self.runner.run(message=prompt):
            if hasattr(event, "tool_call"):
                console.print(f"  [yellow]🛠️  Calling Tool: {event.tool_call.name}[/yellow]")
            elif hasattr(event, "text") and event.text:
                final_summary += event.text

        console.print("\n[bold green]Agent Finished. Summary:[/bold green]")
        console.print(final_summary)

        # 3. Commit and PR
        if create_pr:
            # Check if files were actually changed
            status = subprocess.run(["git", "-C", str(fork_path), "status", "--porcelain"], capture_output=True, text=True)
            if not status.stdout.strip():
                console.print("[yellow]No changes made by agent. Skipping PR.[/yellow]")
                return

            subprocess.run(["git", "-C", str(fork_path), "add", "-A"], capture_output=True)
            subprocess.run(["git", "-C", str(fork_path), "commit", "-m", "fix: Autonomous security updates via ADK"], capture_output=True)
            subprocess.run(["git", "-C", str(fork_path), "push", "-u", "origin", "adk-security-updates", "--force"], capture_output=True)

            try:
                pr = self.github.create_pr(
                    self.org, repo_name,
                    "fix: Autonomous security updates (ADK / Claude 4.5)",
                    f"{username}:adk-security-updates",
                    "master", # You may want to dynamically fetch default branch here
                    f"## Security Updates Applied\n\n{final_summary}\n\n*Generated autonomously by Google ADK & Claude 4.5*"
                )
                console.print(f"[green]✓ PR Created: {pr['html_url']}[/green]")
            except Exception as e:
                console.print(f"[red]Failed to create PR: {e}[/red]")

# =============================================================================
# CLI
# =============================================================================

@click.group()
def cli():
    pass

@cli.command()
@click.option("--org", required=True, help="GitHub organization")
@click.option("--limit", default=5, help="Max repos to fix")
@click.option("--model", default="vertex_ai/claude-4-5-sonnet", help="Vertex Model String")
@click.option("--create-pr/--no-pr", default=True, help="Create PR")
def fix_all(org, limit, model, create_pr):
    """Autonomously fix all repositories in an organization."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        console.print("[red]GITHUB_TOKEN environment variable required.[/red]")
        sys.exit(1)
        
    github = GitHubClient(token)
    repos = github.get_org_repos(org)
    
    console.print(f"[bold cyan]Found {len(repos)} public repositories. Processing up to {limit}...[/bold cyan]")
    
    platform = ADKSecurityPlatform(org=org, model=model, github_token=token)
    
    for repo in repos[:limit]:
        console.print(f"\n[bold yellow]=======================================================[/bold yellow]")
        console.print(f"[bold yellow]Starting autonomous workflow for: {repo['name']}[/bold yellow]")
        console.print(f"[bold yellow]=======================================================[/bold yellow]\n")
        
        try:
            asyncio.run(platform.fix_and_pr(repo["name"], create_pr))
        except Exception as e:
            console.print(f"[bold red]Critical failure processing {repo['name']}: {e}[/bold red]")
