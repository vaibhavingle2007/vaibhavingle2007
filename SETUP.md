# Neofetch GitHub Profile Setup

This repository generates a colorful neofetch-style GitHub profile README. Your profile photo is converted to RGB ASCII art inside `assets/profile-terminal.svg`, live GitHub stats appear on the right, and graph sections show language share plus activity meters.

## 1. Create The Profile Repo

Create a public repository named exactly:

```text
vaibhavingle2007
```

GitHub will show `README.md` from `vaibhavingle2007/vaibhavingle2007` on your profile page.

## 2. Add Your Photo

Keep your profile photo in the repository root as:

```text
profile.png
```

The generator converts it to colored ASCII at about 40 columns wide. You can tweak `ASCII_WIDTH`, `CHAR_RAMP`, and `BACKGROUND_CUTOFF` at the top of `scripts/generate_readme.py`.

## 3. Customize The Fields

Edit the `CONFIG` dictionary near the top of `scripts/generate_readme.py` to change:

- `OS`
- `Uptime`
- `Host`
- `Kernel`
- `IDE`
- `Languages.Programming`
- `Hobbies`
- `Contact.Email`
- `Contact.LinkedIn`
- `Contact.Discord`

## 4. Enable Actions

Push the repo to GitHub, open the `Actions` tab, and enable workflows if GitHub asks.

The workflow runs:

- every 6 hours
- when you manually click `Run workflow`
- when you push to `main`

## 5. Optional Personal Token

The workflow uses GitHub's built-in `GITHUB_TOKEN` by default.

For fuller private contribution visibility, create a personal access token and add it as a repository secret named:

```text
PERSONAL_TOKEN
```

For a classic token, use `repo` and `read:user` scopes. For a fine-grained token, grant read access to the repositories you want counted.

## 6. Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the generator:

```bash
GH_TOKEN=your_token_here python scripts/generate_readme.py
```

On PowerShell:

```powershell
$env:GH_TOKEN="your_token_here"
python scripts/generate_readme.py
```

The script updates `assets/profile-terminal.svg` and only rewrites the README section between:

```text
<!--START_SECTION:stats-->
<!--END_SECTION:stats-->
```

## Notes

- Lines of code are approximate because they are derived from GitHub language byte counts.
- ASCII and per-repo LOC data are cached under `.cache/profile-readme`.
- If `requests` is not installed locally, the script creates a visual preview with last-known stats. GitHub Actions installs `requests` and replaces those values with live stats.
- Missing or invalid tokens are handled gracefully with clear terminal messages.
