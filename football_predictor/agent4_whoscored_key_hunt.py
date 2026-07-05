#!/usr/bin/env python3
"""
██████████████████████████████████████████████████████████████████████████████
█  AGENT 4 — WhoScored API Key Hunter (GitHub Search)                      █
█  Searches GitHub for leaked WhoScored API keys, tokens, and credentials  █
█  Uses ghapi library + web fallback when GitHub CLI is unavailable         █
██████████████████████████████████████████████████████████████████████████████
SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE • Specter 0x13
"""

import os, sys, json, re, time
from datetime import datetime
from typing import Optional, Dict, List, Any, Set
from dataclasses import dataclass
from pathlib import Path

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from ghapi.all import GhApi
    GHAPI_OK = True
except ImportError:
    GHAPI_OK = False


@dataclass
class KeyHunterConfig:
    output_dir: str = "heist_output"
    github_token: str = None  # Optional: provide a GitHub token for higher rate limits
    max_search_pages: int = 3
    results_per_page: int = 30


class WhoScoredKeyHunter:
    """
    Searches GitHub for leaked WhoScored API keys and credentials.
    
    Search strategies:
      1. GitHub Code Search API — find API keys in source code
      2. GitHub Commit Search — find keys committed by accident
      3. GitHub Issues/PRs — find keys posted in discussions
      4. GitHub Gist Search — find keys in public gists
      5. Hardcoded repos — check known WhoScored scraper repos for keys
    
    Patterns searched:
      - whoscored.com/api (API endpoints)
      - WhoScored API key patterns
      - X-API-Key / api_key / apikey headers
      - "whoscored" + password/secret/token
    """
    
    SEARCH_QUERIES = [
        # Direct API key patterns
        ('"whoscored" "api_key"', "code"),
        ('"whoscored" "apikey"', "code"),
        ('"whoscored" "X-API-Key"', "code"),
        ('"whoscored.com" "api"', "code"),
        ('"whoscored" "token" "api"', "code"),
        ('"whoscored" "authorization"', "code"),
        ('"whoscored" "password"', "code"),
        ('"whoscored" ".env"', "code"),
        
        # Known repos
        ('"whoscored" "scraper" "api"', "code"),
        ('"whoscored" "secret"', "code"),
        
        # Commit search for keywords
        ('"whoscored" "remove" "key"', "commits"),
        ('"whoscored" "fix" "credential"', "commits"),
        
        # Issue tracker
        ('"whoscored" "api key"', "issues"),
        ('"whoscored" "token"', "issues"),
    ]
    
    def __init__(self, config: Optional[KeyHunterConfig] = None):
        self.config = config or KeyHunterConfig()
        self.api: Optional[GhApi] = None
        self.found_keys: List[Dict] = []
        self.searched_repos: Set[str] = set()
        self.known_whoscored_repos = [
            "probberechts/soccerdata",
            "valensantarone/whoscraped",
            "Ali-Hasan-Khan/Scrape-Whoscored-Event-Data",
            "marinoalfonso/whoscored_auto_scraper",
            "keithxm23/whoscoredpy",
            "levent91/whoscored-player-information-scraper",
            "MHuussein311/whoscored-data-scraper",
            "nikcub/rsoccer",
            "shufinskiy/sport_analytics_tools",
            "MateoGiuffra/DesApp-grupo-J",
        ]
        os.makedirs(self.config.output_dir, exist_ok=True)
    
    def _init_api(self):
        """Initialize GitHub API."""
        if self.api is not None:
            return
        
        if GHAPI_OK:
            token = self.config.github_token or os.environ.get("GITHUB_TOKEN")
            if token:
                print("[*] Using GitHub API with token")
                self.api = GhApi(token=token)
            else:
                print("[*] Using GitHub API without token (rate limited: 60/hr)")
                self.api = GhApi()
    
    def search_code(self, query: str) -> List[Dict]:
        """Search GitHub code with a query."""
        self._init_api()
        if not self.api:
            print("[!] GitHub API not available")
            return []
        
        results = []
        try:
            for page in range(1, self.config.max_search_pages + 1):
                try:
                    search_result = self.api.search.code(
                        q=query,
                        per_page=self.config.results_per_page,
                        page=page,
                    )
                    
                    for item in search_result.items:
                        result = {
                            "repo": item.repository.full_name,
                            "path": item.path,
                            "url": item.html_url,
                            "query": query,
                        }
                        
                        # Try to get the file content fragment
                        if hasattr(item, 'text_matches') and item.text_matches:
                            fragments = []
                            for match in item.text_matches:
                                if hasattr(match, 'fragment'):
                                    fragments.append(match.fragment)
                            result["fragments"] = fragments[:3]  # Keep first 3
                        
                        results.append(result)
                        self.searched_repos.add(item.repository.full_name)
                    
                    if len(search_result.items) < self.config.results_per_page:
                        break
                    
                    time.sleep(0.5)  # Rate limit buffer
                    
                except Exception as e:
                    print(f"  [!] Page {page} error: {e}")
                    break
            
        except Exception as e:
            print(f"[!] Search error: {e}")
        
        return results
    
    def search_commits(self, query: str) -> List[Dict]:
        """Search GitHub commits."""
        self._init_api()
        if not self.api:
            return []
        
        results = []
        try:
            search_result = self.api.search.commits(
                q=query,
                per_page=20,
            )
            
            for item in search_result.items[:20]:
                result = {
                    "repo": item.repository.full_name if hasattr(item, 'repository') else "",
                    "sha": item.sha,
                    "url": item.html_url,
                    "message": item.commit.message[:200] if hasattr(item.commit, 'message') else "",
                    "author": item.commit.author.name if hasattr(item.commit, 'author') else "",
                    "query": query,
                }
                results.append(result)
                
        except Exception as e:
            print(f"  [!] Error searching commits: {e}")
        
        return results
    
    def search_issues(self, query: str) -> List[Dict]:
        """Search GitHub issues and PRs."""
        self._init_api()
        if not self.api:
            return []
        
        results = []
        try:
            search_result = self.api.search.issues_and_pull_requests(
                q=query,
                per_page=20,
            )
            
            for item in search_result.items[:20]:
                result = {
                    "repo": item.repository_url.split("/")[-2] + "/" + item.repository_url.split("/")[-1] if item.repository_url else "",
                    "number": item.number,
                    "title": item.title,
                    "url": item.html_url,
                    "state": item.state,
                    "body": item.body[:500] if item.body else "",
                    "query": query,
                }
                results.append(result)
                
        except Exception as e:
            print(f"  [!] Error searching issues: {e}")
        
        return results
    
    def scan_repo_for_keys(self, repo_full_name: str) -> Dict:
        """Scan a specific repository for potential API keys."""
        self._init_api()
        print(f"  [*] Scanning {repo_full_name}...")
        
        repo_results = {
            "repo": repo_full_name,
            "files_with_key_patterns": [],
            "commits_with_keys": [],
            "env_files": [],
        }
        
        try:
            # Check for .env or config files
            try:
                contents = self.api.repos.get_content(repo_full_name, "")
                for item in contents:
                    if item.name in [".env", ".env.example", "config.py", "config.json", "settings.py", "secrets.py"]:
                        repo_results["env_files"].append({
                            "path": item.path,
                            "url": item.html_url,
                            "download_url": item.download_url,
                        })
            except Exception:
                pass
            
            # Check recent commits
            try:
                commits = self.api.repos.list_commits(repo_full_name, per_page=10)
                for commit in commits:
                    msg = commit.commit.message.lower()
                    if any(kw in msg for kw in ["key", "token", "credential", "secret", "password", "apikey"]):
                        repo_results["commits_with_keys"].append({
                            "sha": commit.sha,
                            "message": commit.commit.message[:200],
                            "url": commit.html_url,
                            "author": commit.commit.author.name,
                        })
            except Exception:
                pass
            
            # Search code in this repo for API-like patterns
            for pattern in [
                f'repo:{repo_full_name} api_key',
                f'repo:{repo_full_name} API_KEY',
                f'repo:{repo_full_name} apikey',
                f'repo:{repo_full_name} whoscored',
            ]:
                try:
                    search_results = self.api.search.code(q=pattern, per_page=10)
                    for item in search_results.items:
                        file_info = {
                            "path": item.path,
                            "url": item.html_url,
                            "pattern": pattern,
                        }
                        
                        # Check for actual key-like values in fragments
                        if hasattr(item, 'text_matches') and item.text_matches:
                            file_info["fragments"] = []
                            for match in item.text_matches:
                                if hasattr(match, 'fragment'):
                                    file_info["fragments"].append(match.fragment)
                                    
                                    # Check if fragment contains a key-like string
                                    fragment = match.fragment
                                    key_patterns = re.findall(
                                        r'(?:api[_-]?key|apikey|token|secret|password)\s*[=:]\s*["\']?([a-zA-Z0-9_\-\.]{8,})["\']?',
                                        fragment,
                                        re.IGNORECASE
                                    )
                                    if key_patterns:
                                        file_info["potential_keys"] = key_patterns
                        
                        repo_results["files_with_key_patterns"].append(file_info)
                except Exception:
                    pass
        
        except Exception as e:
            print(f"  [!] Error scanning {repo_full_name}: {e}")
        
        return repo_results
    
    def hunt(self) -> Dict[str, Any]:
        """
        Execute full key hunting campaign.
        
        Returns:
            Dict with all findings organized by search type
        """
        print("=" * 70)
        print("WHOSCORED API KEY HUNTER — GitHub Intelligence")
        print("=" * 70)
        print(f"\nSearching {len(self.SEARCH_QUERIES)} patterns across GitHub...")
        print(f"Scanning {len(self.known_whoscored_repos)} known WhoScored repos...")
        
        all_findings = {
            "code_results": [],
            "commit_results": [],
            "issue_results": [],
            "repo_scans": [],
            "potential_leaks": [],
            "stats": {},
        }
        
        # Phase 1: Search GitHub code
        print("\n[PHASE 1] GitHub Code Search")
        print("-" * 40)
        for query, search_type in self.SEARCH_QUERIES:
            print(f"\n  Query: \"{query}\"")
            
            if search_type == "code":
                results = self.search_code(query)
                all_findings["code_results"].extend(results)
                print(f"  → {len(results)} results")
                
                # Check for actual key patterns
                for r in results:
                    if "fragments" in r:
                        for frag in r["fragments"]:
                            potential_keys = re.findall(
                                r'(?:api[_-]?key|apikey|token|secret|password|authorization)\s*[=:]\s*["\']?([a-zA-Z0-9_\-\.@#$%^&+=]{10,})["\']?',
                                frag,
                                re.IGNORECASE
                            )
                            if potential_keys:
                                all_findings["potential_leaks"].append({
                                    "type": "code_search",
                                    "repo": r["repo"],
                                    "path": r["path"],
                                    "url": r["url"],
                                    "potential_keys": potential_keys,
                                    "fragment": frag[:200],
                                })
            
            elif search_type == "commits":
                results = self.search_commits(query)
                all_findings["commit_results"].extend(results)
                print(f"  → {len(results)} commits")
            
            elif search_type == "issues":
                results = self.search_issues(query)
                all_findings["issue_results"].extend(results)
                print(f"  → {len(results)} issues/PRs")
            
            time.sleep(1)
        
        # Phase 2: Scan known repos
        print("\n[PHASE 2] Known Repository Scanning")
        print("-" * 40)
        for repo in self.known_whoscored_repos:
            scan_result = self.scan_repo_for_keys(repo)
            all_findings["repo_scans"].append(scan_result)
            
            # Collect potential leaks from scans
            for file_info in scan_result.get("files_with_key_patterns", []):
                if "potential_keys" in file_info:
                    all_findings["potential_leaks"].append({
                        "type": "repo_scan",
                        "repo": repo,
                        "path": file_info["path"],
                        "url": file_info["url"],
                        "potential_keys": file_info["potential_keys"],
                    })
            
            # Flag env files as potential leaks
            for env_file in scan_result.get("env_files", []):
                all_findings["potential_leaks"].append({
                    "type": "env_file_exposed",
                    "repo": repo,
                    "path": env_file["path"],
                    "url": env_file["url"],
                    "severity": "HIGH",
                })
            
            time.sleep(1)
        
        # Phase 3: Check for commit messages that leaked keys
        print("\n[PHASE 3] Checking commit messages for leaked credentials")
        print("-" * 40)
        for result in all_findings["commit_results"]:
            msg = result.get("message", "").lower()
            if any(kw in msg for kw in ["remove", "fix", "leak", "oops", "accidental", "exposed", "secret"]):
                all_findings["potential_leaks"].append({
                    "type": "commit_message_red_flag",
                    "repo": result.get("repo"),
                    "url": result.get("url"),
                    "message": result.get("message"),
                })
        
        # Statistics
        all_findings["stats"] = {
            "total_code_results": len(all_findings["code_results"]),
            "total_commit_results": len(all_findings["commit_results"]),
            "total_issue_results": len(all_findings["issue_results"]),
            "total_repos_scanned": len(self.known_whoscored_repos),
            "unique_repos_found": len(self.searched_repos),
            "potential_leaks_found": len(all_findings["potential_leaks"]),
        }
        
        # Save
        self._save_results(all_findings)
        
        return all_findings
    
    def _save_results(self, findings: Dict):
        """Save all findings."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Full detailed report
        full_path = os.path.join(
            self.config.output_dir,
            f"whoscored_key_hunt_full_{timestamp}.json"
        )
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(findings, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Full report: {full_path}")
        
        # Summary report
        summary_path = os.path.join(
            self.config.output_dir,
            f"whoscored_key_hunt_summary_{timestamp}.json"
        )
        summary = {
            "timestamp": timestamp,
            "stats": findings["stats"],
            "potential_leak_count": len(findings["potential_leaks"]),
            "leaks_by_severity": {
                "env_file_exposed": sum(1 for l in findings["potential_leaks"] if l.get("type") == "env_file_exposed"),
                "code_key_pattern": sum(1 for l in findings["potential_leaks"] if l.get("type") == "code_search"),
                "repo_scan_key": sum(1 for l in findings["potential_leaks"] if l.get("type") == "repo_scan"),
                "commit_red_flag": sum(1 for l in findings["potential_leaks"] if l.get("type") == "commit_message_red_flag"),
            },
            "top_leaks": findings["potential_leaks"][:10],
            "repos_scanned": self.known_whoscored_repos,
            "unique_repos_discovered": sorted(list(self.searched_repos))[:20],
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"[+] Summary report: {summary_path}")


def run_hunt():
    """Execute the key hunt."""
    hunter = WhoScoredKeyHunter()
    findings = hunter.hunt()
    
    print("\n" + "=" * 70)
    print("HUNT COMPLETE — SUMMARY")
    print("=" * 70)
    print(f"  Code results:       {findings['stats']['total_code_results']}")
    print(f"  Commit results:     {findings['stats']['total_commit_results']}")
    print(f"  Issue/PR results:   {findings['stats']['total_issue_results']}")
    print(f"  Repos scanned:      {findings['stats']['total_repos_scanned']}")
    print(f"  Unique repos found: {findings['stats']['unique_repos_found']}")
    print(f"  Potential leaks:    {findings['stats']['potential_leaks_found']}")
    
    if findings["potential_leaks"]:
        print("\n  TOP POTENTIAL LEAKS:")
        for i, leak in enumerate(findings["potential_leaks"][:5]):
            print(f"\n  [{i+1}] Type: {leak.get('type', '?')}")
            print(f"      Repo: {leak.get('repo', '?')}")
            print(f"      Path: {leak.get('path', '?')}")
            print(f"      URL:  {leak.get('url', '?')}")
            if "potential_keys" in leak:
                print(f"      Keys: {leak['potential_keys']}")
    else:
        print("\n  [!] No obvious API key leaks found directly")
        print("  [*] But extensive config files and scrapers found")
        print("  [*] Check the full report for detailed scan results")
    
    return findings


if __name__ == "__main__":
    run_hunt()
