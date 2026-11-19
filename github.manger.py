import os
import getpass
import subprocess
import shutil
import requests
from pathlib import Path


def github_uploader():
    # 1. Check required tools (git & gh)
    for cmd in ("git", "gh"):
        if shutil.which(cmd) is None:
            print(f"Missing {cmd}. Install with:")
            print("sudo pacman -S git github-cli")
            return

    # 2. Login to GitHub if needed
    auth_check = subprocess.run(["gh", "auth", "status"], capture_output=True)
    if auth_check.returncode != 0:
        subprocess.run(["gh", "auth", "login"])

    subprocess.run(["gh", "auth", "status"])

    # 3. Get project folder path
    raw_path = input("\nProject folder path: ").strip()
    project = Path(os.path.expanduser(raw_path)).resolve()

    if not project.is_dir():
        print("Error: folder not found.")
        return

    # 4. Ask for repository name & visibility
    default_name = project.name
    repo = input(f"GitHub repository name [{default_name}]: ").strip() or default_name

    visibility = input("Visibility: public or private [private]: ").strip().lower() or "private"
    if visibility not in ("public", "private"):
        print("Choose public or private.")
        return

    # 5. Create push.sh inside the project
    push_file = project / "push.sh"
    push_script_content = """#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$(readlink -f "$0")")"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: this folder is not a Git repository."
    exit 1
fi

git add -A

if ! git diff --cached --quiet; then
    git commit -m "Update Python code"
else
    echo "No changes to commit."
fi

git push
"""
    push_file.write_text(push_script_content)
    push_file.chmod(0o755)

    # 6. Initialize Git if necessary
    is_git = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=project, capture_output=True)
    if is_git.returncode != 0:
        subprocess.run(["git", "init"], cwd=project, check=True)

    # 7. Configure commit identity if missing
    git_name = subprocess.run(["git", "config", "user.name"], cwd=project, capture_output=True, text=True).stdout.strip()
    if not git_name:
        new_name = input("Your Git name: ").strip()
        subprocess.run(["git", "config", "user.name", new_name], cwd=project, check=True)

    git_email = subprocess.run(["git", "config", "user.email"], cwd=project, capture_output=True, text=True).stdout.strip()
    if not git_email:
        new_email = input("Your Git email: ").strip()
        subprocess.run(["git", "config", "user.email", new_email], cwd=project, check=True)

    # 8. Stage files and create initial commit
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    has_changes = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=project)
    if has_changes.returncode != 0:
        subprocess.run(["git", "commit", "-m", "First upload"], cwd=project, check=True)

    has_head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=project, capture_output=True)
    if has_head.returncode != 0:
        print("Error: no commit exists. Check whether the folder contains files.")
        return

    # 9. Connect to GitHub or reuse existing remote
    has_origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=project, capture_output=True, text=True)
    if has_origin.returncode == 0:
        print("Using existing origin:")
        print(has_origin.stdout.strip())
    else:
        login = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True).stdout.strip()
        repo_exists = subprocess.run(["gh", "repo", "view", f"{login}/{repo}"], capture_output=True)
        
        if repo_exists.returncode == 0:
            repo_url = subprocess.run(
                ["gh", "repo", "view", f"{login}/{repo}", "--json", "url", "--jq", ".url"],
                capture_output=True, text=True
            ).stdout.strip()
            subprocess.run(["git", "remote", "add", "origin", f"{repo_url}.git"], cwd=project, check=True)
        else:
            subprocess.run(
                ["gh", "repo", "create", repo, f"--{visibility}", "--source=.", "--remote=origin"],
                cwd=project, check=True
            )

    # 10. Push the current branch
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=project, capture_output=True, text=True).stdout.strip() or "main"
    subprocess.run(["git", "push", "-u", "origin", branch], cwd=project, check=True)

    print(f"\nUpload complete!\nProject: {project}\nUpdate later by running:\ncd \"{project}\" && ./push.sh")


def editer():
    github_token = os.getenv("GITHUB_TOKEN") or getpass.getpass("Enter your GitHub Token: ").strip()

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    def get_all_repos():
        repos = []
        page = 1
        while True:
            url = f"https://api.github.com/user/repos?affiliation=owner&per_page=100&page={page}"
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"❌ Connection/Auth Error: {response.json().get('message')}")
                return []
            data = response.json()
            if not data:
                break
            repos.extend(data)
            page += 1
        return repos

    def update_repo(owner, repo_name, updates):
        url = f"https://api.github.com/repos/{owner}/{repo_name}"
        response = requests.patch(url, json=updates, headers=headers)
        if response.status_code == 200:
            print("\n✅ Repository updated successfully!")
            return response.json()
        else:
            print(f"\n❌ Update failed: {response.json().get('message')}")
            return None

    while True:
        print("\n⏳ Fetching your repositories from GitHub...")
        repos = get_all_repos()
        if not repos:
            print("No repositories found or invalid token.")
            break

        print(f"\nFound {len(repos)} repositories:\n")
        for idx, repo in enumerate(repos, start=1):
            status = "🔒 Private" if repo["private"] else "🌍 Public"
            print(f"{idx}. {repo['name']}  [{status}]")

        while True:
            try:
                choice = int(input("\nSelect repository number to edit (or 0 to exit): "))
                if choice == 0:
                    print("Returning to main menu...")
                    return
                if 1 <= choice <= len(repos):
                    selected_repo = repos[choice - 1]
                    break
                else:
                    print("⚠️ Invalid number. Please choose from the list.")
            except ValueError:
                print("⚠️ Please enter a valid integer.")

        owner = selected_repo["owner"]["login"]
        current_name = selected_repo["name"]
        is_private = selected_repo["private"]

        print(f"\n--- Selected: {current_name} ({'Private' if is_private else 'Public'}) ---")
        updates = {}

        print("\nSet repository visibility:")
        print("1. Public")
        print("2. Private")
        print("3. Keep current")
        vis_choice = input("Your choice (1/2/3): ").strip()

        if vis_choice == "1":
            updates["private"] = False
        elif vis_choice == "2":
            updates["private"] = True

        rename_choice = input("\nDo you want to rename it? (y/n): ").strip().lower()
        if rename_choice == "y":
            new_name = input("Enter new repository name: ").strip()
            if new_name:
                updates["name"] = new_name

        if updates:
            update_repo(owner, current_name, updates)
        else:
            print("\nℹ️ No changes were made.")

        again = input("\nDo you want to edit another repository? (y/n): ").strip().lower()
        if again != "y":
            break
def list_github():
    while True:
        print("1. editer_github")
        print("2. github_uploader")
        print("3. exit")
        choice = input("choose (1/2/3): ")
        if choice == "1":
            github_uploader()
        elif choice == "2":
            editer()
        elif choice == "3":
            print("goodbye")
            break
    else:
     print("Invalid choice, try again.\n")
list_github()
