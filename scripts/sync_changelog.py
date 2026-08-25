import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def sync_changelog():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    changelog_path = os.path.join(base_dir, "CHANGELOG.md")
    readme_path = os.path.join(base_dir, "README.md")

    if not os.path.exists(changelog_path) or not os.path.exists(readme_path):
        print("❌ CHANGELOG.md or README.md missing.")
        return

    with open(changelog_path, "r", encoding="utf-8") as f:
        changelog_content = f.read().strip()

    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read()

    marker = "## 📜 변경 이력 (CHANGELOG)"
    if marker in readme_content:
        base_readme = readme_content.split(marker)[0].strip()
    else:
        base_readme = readme_content.strip()

    # Re-format changelog header for README embedding
    formatted_changelog = changelog_content.replace("# 📜 BingX 자연어 자동 매매 & AI 텔레그램 봇 - 변경 이력 (CHANGELOG)", "").strip()

    new_readme = f"{base_readme}\n\n---\n\n{marker}\n\n{formatted_changelog}\n"

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_readme)

    print("✅ Successfully synced CHANGELOG.md to README.md!")

if __name__ == "__main__":
    sync_changelog()
