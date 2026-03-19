#!/usr/bin/env python3
"""
GitHub Enterprise API Client.

Usage:
    # Load tokens from .env file or environment variables
    python3 api_client.py github whoami
"""

import os
import sys
import json
import argparse
import urllib3
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: 'requests' library required. Install with: pip install requests")
    sys.exit(1)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Load .env file if present (no extra dependency needed)
# ---------------------------------------------------------------------------
def load_env(env_file=None):
    """Load environment variables from .env file."""
    if env_file is None:
        env_file = Path(__file__).parent / ".env"
    if not Path(env_file).exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key.strip(), value)

load_env()


# ===========================================================================
#  GitHub Enterprise Client
# ===========================================================================
class GitHubClient:
    """GitHub Enterprise REST API v3 client."""

    def __init__(self, host=None, token=None, verify_ssl=False):
        self.host = (host or os.environ.get("GITHUB_HOST", "")).rstrip("/")
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.base = f"{self.host}/api/v3"
        self.verify = verify_ssl
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def _get(self, path, params=None):
        r = requests.get(f"{self.base}{path}", headers=self.headers,
                         params=params, verify=self.verify, timeout=30)
        r.raise_for_status()
        return r.json()

    def _post(self, path, data=None):
        r = requests.post(f"{self.base}{path}", headers=self.headers,
                          json=data, verify=self.verify, timeout=30)
        r.raise_for_status()
        return r.json()

    def _patch(self, path, data=None):
        r = requests.patch(f"{self.base}{path}", headers=self.headers,
                           json=data, verify=self.verify, timeout=30)
        r.raise_for_status()
        return r.json()

    # --- User ---
    def whoami(self):
        """Get authenticated user info."""
        return self._get("/user")

    # --- Repositories ---
    def list_repos(self, org=None, per_page=30, page=1):
        """List repositories (user's or org's)."""
        if org:
            return self._get(f"/orgs/{org}/repos", {"per_page": per_page, "page": page})
        return self._get("/user/repos", {"per_page": per_page, "page": page})

    def get_repo(self, owner, repo):
        """Get repository details."""
        return self._get(f"/repos/{owner}/{repo}")

    def search_repos(self, query, per_page=10):
        """Search repositories."""
        return self._get("/search/repositories", {"q": query, "per_page": per_page})

    # --- Issues ---
    def list_issues(self, owner, repo, state="open", per_page=30, page=1):
        """List issues in a repository."""
        return self._get(f"/repos/{owner}/{repo}/issues",
                         {"state": state, "per_page": per_page, "page": page})

    def get_issue(self, owner, repo, number):
        """Get a specific issue."""
        return self._get(f"/repos/{owner}/{repo}/issues/{number}")

    def create_issue(self, owner, repo, title, body="", labels=None, assignees=None):
        """Create a new issue."""
        data = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        if assignees:
            data["assignees"] = assignees
        return self._post(f"/repos/{owner}/{repo}/issues", data)

    def add_issue_comment(self, owner, repo, number, body):
        """Add a comment to an issue."""
        return self._post(f"/repos/{owner}/{repo}/issues/{number}/comments", {"body": body})

    # --- Pull Requests ---
    def list_pulls(self, owner, repo, state="open", per_page=30, page=1):
        """List pull requests."""
        return self._get(f"/repos/{owner}/{repo}/pulls",
                         {"state": state, "per_page": per_page, "page": page})

    def get_pull(self, owner, repo, number):
        """Get a specific pull request."""
        return self._get(f"/repos/{owner}/{repo}/pulls/{number}")

    def create_pull(self, owner, repo, title, head, base, body="", draft=False):
        """Create a pull request."""
        return self._post(f"/repos/{owner}/{repo}/pulls", {
            "title": title, "head": head, "base": base,
            "body": body, "draft": draft,
        })

    # --- Branches ---
    def list_branches(self, owner, repo, per_page=30):
        """List branches."""
        return self._get(f"/repos/{owner}/{repo}/branches", {"per_page": per_page})

    # --- Search ---
    def search_issues(self, query, per_page=10):
        """Search issues and PRs."""
        return self._get("/search/issues", {"q": query, "per_page": per_page})

    def search_code(self, query, per_page=10):
        """Search code."""
        return self._get("/search/code", {"q": query, "per_page": per_page})


# ===========================================================================
#  CLI Interface
# ===========================================================================
def pp(data):
    """Pretty print JSON."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cli_github(args):
    gh = GitHubClient()
    cmd = args.command

    if cmd == "whoami":
        pp(gh.whoami())
    elif cmd == "repos":
        pp(gh.list_repos(org=args.org))
    elif cmd == "repo":
        pp(gh.get_repo(args.owner, args.repo))
    elif cmd == "issues":
        pp(gh.list_issues(args.owner, args.repo, state=args.state))
    elif cmd == "issue":
        pp(gh.get_issue(args.owner, args.repo, args.number))
    elif cmd == "create-issue":
        pp(gh.create_issue(args.owner, args.repo, args.title, body=args.body or ""))
    elif cmd == "pulls":
        pp(gh.list_pulls(args.owner, args.repo, state=args.state))
    elif cmd == "pull":
        pp(gh.get_pull(args.owner, args.repo, args.number))
    elif cmd == "branches":
        pp(gh.list_branches(args.owner, args.repo))
    elif cmd == "search-issues":
        pp(gh.search_issues(args.query))
    elif cmd == "search-code":
        pp(gh.search_code(args.query))
    elif cmd == "search-repos":
        pp(gh.search_repos(args.query))


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Enterprise API Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s github whoami
  %(prog)s github issues --owner myorg --repo myrepo
  %(prog)s github search-repos --query "org:MyOrg language:python"
""")
    sub = parser.add_subparsers(dest="service", required=True)

    # --- GitHub ---
    gh_parser = sub.add_parser("github", aliases=["gh"], help="GitHub Enterprise")
    gh_parser.add_argument("command", choices=[
        "whoami", "repos", "repo", "issues", "issue", "create-issue",
        "pulls", "pull", "branches", "search-issues", "search-code", "search-repos",
    ])
    gh_parser.add_argument("--owner", "-o")
    gh_parser.add_argument("--repo", "-r")
    gh_parser.add_argument("--org")
    gh_parser.add_argument("--number", "-n", type=int)
    gh_parser.add_argument("--title", "-t")
    gh_parser.add_argument("--body", "-b")
    gh_parser.add_argument("--query", "-q")
    gh_parser.add_argument("--state", default="open", choices=["open", "closed", "all"])

    args = parser.parse_args()

    if args.service in ("github", "gh"):
        cli_github(args)


if __name__ == "__main__":
    main()
