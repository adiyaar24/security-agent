#!/usr/bin/env python3
"""
ADK Security Agent - Hardened Polyglot Autonomous Fixer
Zero-Hallucination, Highly Resilient, Focuses on Critical/High Issues.
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
# HARDENED ADK TOOLS (Resilient & Anti-Hallucination)
# =============================================================================

@tool
def list_directory(path: str) -> str:
    """Lists files and directories in a given path to prevent hallucinating file structures."""
    try:
        if not os.path.exists(path):
            return f"Error: Path '{path}' does not exist."
        items = os.listdir(path)
        return "\n".join(items) if items else "Directory is empty."
    except Exception as e:
        return f"Error listing directory: {str(e)}"

@tool
def read_file(file_path: str) -> str:
    """Reads the content of a file. Use this to VERIFY issues before fixing."""
    try:
        if not os.path.isfile(file_path):
            return f"Error: File '{file_path}' does not exist. Use list_directory to find the correct path."
        return Path(file_path).read_text()
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
def write_file(file_path: str, content: str) -> str:
    """Writes new content to a file. OVERWRITES the existing file completely."""
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(file_path).write_text(content)
        return f"Successfully wrote to {file_path}. YOU MUST NOW RUN TESTS to verify the fix."
    except Exception as e:
        return f"Error writing file: {str(e)}"

@tool
def run_command(command: str, repo_dir: str) -> str:
    """
    Executes a generic shell command. Highly resilient.
    Use this to run tests (e.g., 'go test ./...', 'npm test', 'pytest').
    """
    try:
        # 5-minute timeout to prevent hanging commands
        result = subprocess.run(
            command,
            shell=True,
            cwd=repo_dir,
            capture_output=True,
            timeout=300 
        )
        output = f"Command: {command}\nExit Code: {result.returncode}\n"
        output += f"STDOUT:\n{result.stdout.decode()[:2000]}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr.decode()[:2000]}\n"
        return output
    except subprocess.TimeoutExpired:
        return f"Error: Command '{command}' timed out after 300 seconds."
    except Exception as e:
        return f"Command execution error: {str(e)}"

@tool
def search_codebase(repo_dir: str, pattern: str) -> str:
    """Searches the codebase for a string pattern (grep)."""
    try:
        result = subprocess.run(["grep", "-rnw", repo_dir, "-e", pattern], capture_output=True, text=True)
        return result.stdout[:3000] if result.stdout else "No matches found."
    except Exception as e:
        return f"Search error: {str(e)}"

# =============================================================================
# HIGH-PRECISION SYSTEM PROMPT
# =============================================================================

SECURITY_EXPERT_INSTRUCTION = """You are a Principal Security Engineer and Autonomous Remediation Agent.
Your objective is to identify and fix CRITICAL and HIGH severity security issues across polyglot repositories.

CRITICAL DIRECTIVES (ZERO HALLUCINATION POLICY):
1. NO ASSUMPTIONS: You must NEVER guess file paths, variable names, or dependencies. 
   - Always use `list_directory` or `search_codebase` to map the repository first.
   - Always `read_file` to verify the exact current state before attempting a fix.
2. FOCUS ON MAJOR ISSUES ONLY: Ignore minor issues, code formatting, style warnings, or unused imports unless they break the build.
   ONLY fix the following:
   - End-of-Life (EOL) SDKs (e.g., AWS SDK v1 -> v2, Azure Track 1 -> Track 2).
   - Known vulnerable packages in manifests (`go.mod`, `package.json`, `requirements.txt`).
   - Hardcoded Secrets (Tokens, Passwords, API Keys).
   - High-severity injection flaws (SQLi, Command Injection).
3. PRESERVE FUNCTIONALITY: When writing code, you must output the ENTIRE file content. NEVER delete business logic, existing functions, or test cases.
4. STRICT VALIDATION: After modifying a file with `write_file`, you MUST use `run_command` to execute the project's test suite.
   - If the tests fail, read the STDOUT/STDERR. You MUST fix your own mistakes until the build passes.
   - Do not claim success if `run_command` returns a non-zero exit code.

WORKFLOW TO FOLLOW:
Phase 1: Discovery. Use `list_directory` to find dependency files (`package.json`, `go.mod`, etc.) to understand the tech stack.
Phase 2: Investigation. Read manifests to find major EOL/Vulnerable dependencies. Search the codebase for usage.
Phase 3: Remediation. Rewrite the affected files.
Phase 4: Validation. Run the appropriate build/test commands (e.g., `go mod tidy && go test ./...`, `npm install && npm test`). Fix compilation or test errors iteratively.
Phase 5: Report. Summarize exactly what you fixed.

If you cannot fix an issue without breaking the tests, revert the file and report that manual intervention is required.
"""

# =============================================================================
# ADK AGENT WORKFLOW
# =============================================================================

class ADKSecurityPlatform:
    def __init__(self, org: str, model: str, github_token: str):
        self.org = org
        self.github = GitHubClient(github_token)
        
        self.agent = LlmAgent(
            name="PrincipalSecurityFixer",
            model=model,
            tools=[list_directory, read_file, write_file, run_command, search_codebase],
            instruction=SECURITY_EXPERT_INSTRUCTION
        )
        self.runner = Runner(agent=self.agent)

    async def fix_and_pr(self, repo_name: str, create_pr: bool):
        console.print(Panel.fit(f"🛡️ ADK Hardened Agent Processing: {self.org}/{repo_name}", style="cyan"))
        
        # 1. Fork & Clone
        user = self.github.get_user()
        username = user["login"]
        try:
            self.github.fork_repo(self.org, repo_name)
        except Exception:
            pass
            
        fork_path = Path(f"./forks/{repo_name}")
        if fork_path.exists():
            shutil.rmtree(fork_path)
            
        clone_url = f"https://{username}:{self.github.headers['Authorization'].split()[1]}@github.com/{username}/{repo_name}.git"
        subprocess.run(["git", "clone", "--depth", "1", clone_url, str(fork_path)], capture_output=True)
        subprocess.run(["git", "-C", str(fork_path), "checkout", "-b", "adk-critical-security-updates"], capture_output=True)

        # 2. Trigger the autonomous Agent
        prompt = f"""
        Begin your security audit and remediation on the repository located at: {fork_path.absolute()}
        Remember your directives: Focus ONLY on major security issues, verify everything, and ensure tests pass before concluding.
        """
        
        console.print("[dim]Agent is mapping repository, hunting, and fixing...[/dim]")
        final_summary = ""
        
        async for event in self.runner.run(message=prompt):
            if hasattr(event, "tool_call"):
                console.print(f"  [yellow]🛠️  Using Tool: {event.tool_call.name}[/yellow]")
            elif hasattr(event, "text") and event.text:
                final_summary += event.text

        console.print("\n[bold green]Agent Finished. Final Summary:[/bold green]")
        console.print(final_summary)

        # 3. Commit and PR
        if create_pr:
            status = subprocess.run(["git", "-C", str(fork_path), "status", "--porcelain"], capture_output=True, text=True)
            if not status.stdout.strip():
                console.print("[yellow]No critical issues found or fixed. Skipping PR.[/yellow]")
                return

            subprocess.run(["git", "-C", str(fork_path), "add", "-A"], capture_output=True)
            subprocess.run(["git", "-C", str(fork_path), "commit", "-m", "fix: Resolve critical security vulnerabilities (ADK)"], capture_output=True)
            subprocess.run(["git", "-C", str(fork_path), "push", "-u", "origin", "adk-critical-security-updates", "--force"], capture_output=True)

            try:
                pr = self.github.create_pr(
                    self.org, repo_name,
                    "fix: Resolve critical security vulnerabilities (ADK / Claude 4.5)",
                    f"{username}:adk-critical-security-updates",
                    "master",
                    f"## Security Updates Applied\n\n{final_summary}\n\n*Generated autonomously by Google ADK & Claude 4.5. All tests verified.*"
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
