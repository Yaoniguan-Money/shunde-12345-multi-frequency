param(
  [Parameter(Mandatory=$true)][string]$RepoName
)
$ErrorActionPreference = "Stop"

gh auth status
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not authenticated. Run: gh auth login" }

if (-not (Test-Path .git)) { git init -b main }

if (-not (git remote get-url origin 2>$null)) {
  gh repo create $RepoName --private --source . --remote origin
}

git push -u origin main
if ($LASTEXITCODE -ne 0) {
  throw "Push failed. If GitHub rejected the CI workflow, run: gh auth refresh -h github.com -s workflow"
}

git remote -v
git status
