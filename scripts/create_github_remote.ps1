param(
  [Parameter(Mandatory=$true)][string]$RepoName
)
$ErrorActionPreference = "Stop"

gh auth status
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not authenticated. Run: gh auth login" }

if (-not (Test-Path .git)) { git init -b main }

gh repo create $RepoName --private --source . --remote origin --push

git remote -v
git status
