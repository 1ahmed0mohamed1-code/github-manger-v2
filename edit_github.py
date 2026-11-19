#!/usr/bin/env python3
import os
import getpass
import requests

# Read token from environment variable, or prompt securely if not set
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or getpass.getpass("Enter your GitHub Token: ").strip()

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def get_all_repos():
    repos = []
    page = 1
    while True:
        # Fetch only repositories owned by the authenticated user
        url = f"https://api.github.com/user/repos?affiliation=owner&per_page=100&page={page}"
        response = requests.get(url, headers=HEADERS)
        
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
    response = requests.patch(url, json=updates, headers=HEADERS)
    
    if response.status_code == 200:
        print("\n✅ Repository updated successfully!")
        return response.json()
    else:
        print(f"\n❌ Update failed: {response.json().get('message')}")
        return None

def main():
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

        # 1. Select repository
        while True:
            try:
                choice = int(input("\nSelect repository number to edit (or 0 to exit): "))
                if choice == 0:
                    print("Exiting...")
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

        # 2. Change visibility
        print("\nSet repository visibility:")
        print("1. Public")
        print("2. Private")
        print("3. Keep current")
        vis_choice = input("Your choice (1/2/3): ").strip()

        if vis_choice == "1":
            updates["private"] = False
        elif vis_choice == "2":
            updates["private"] = True

        # 3. Rename repository
        rename_choice = input("\nDo you want to rename it? (y/n): ").strip().lower()
        if rename_choice == "y":
            new_name = input("Enter new repository name: ").strip()
            if new_name:
                updates["name"] = new_name

        # Apply changes
        if updates:
            update_repo(owner, current_name, updates)
        else:
            print("\nℹ️ No changes were made.")

        # Continue loop?
        again = input("\nDo you want to edit another repository? (y/n): ").strip().lower()
        if again != "y":
            print("Done. Goodbye!")
            break

if __name__ == "__main__":
    main()