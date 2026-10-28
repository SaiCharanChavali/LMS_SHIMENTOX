## Introduction to GitHub
**Git** is the version control tool; **GitHub** is a hosting platform for Git repositories with collaboration features: pull requests, code review, issues, project boards, automation (GitHub Actions) and package hosting. Alternatives include GitLab and Bitbucket, which offer similar workflows.

Set up:
1. Create an account and enable two-factor authentication.
2. Authenticate Git with GitHub using **SSH keys** or HTTPS with a personal access token / GitHub CLI (`gh auth login`). Passwords are not accepted for Git operations.

```bash
ssh-keygen -t ed25519 -C "asha@example.com"   # then add the .pub key in GitHub Settings → SSH keys
ssh -T git@github.com                          # test the connection
```

## Repositories on GitHub
Create a repository on GitHub (public or private), then connect your local project:

```bash
git remote add origin git@github.com:asha/training-portal.git
git branch -M main
git push -u origin main         # -u sets upstream so later "git push" needs no arguments
```

A good repository includes:
- `README.md` - what the project does, how to set it up, run and test it.
- `.gitignore` and a `LICENSE` (for open source).
- `CONTRIBUTING.md` and issue/PR templates for teams.

**Branch protection rules** (Settings → Branches) can require pull requests, passing checks and approvals before anything reaches `main`, and block force pushes.

## Pull requests
A **pull request (PR)** proposes merging one branch into another and is the centre of code review.

Workflow:
1. Create a branch, commit and push: `git push -u origin feature/course-search`.
2. Open a PR on GitHub (or `gh pr create`) from `feature/course-search` into `main`.
3. Write a clear description: what changed, why, how it was tested, screenshots for UI, linked issue (`Closes #42`).
4. Automated checks (GitHub Actions) run; reviewers comment line by line, approve or request changes.
5. Push more commits to the same branch to address feedback - the PR updates automatically.
6. Merge when approved and green.

Merge options:

| Option | Result |
| --- | --- |
| Create a merge commit | Keeps all commits plus a merge commit |
| Squash and merge | Combines the PR into one commit on `main` |
| Rebase and merge | Replays commits linearly without a merge commit |

Reviewer tips: check correctness, tests, security (input validation, authorisation, secrets), readability and naming. Author tips: keep PRs small, self-review the diff first and respond to every comment. **Draft PRs** share work in progress early.

## Fork
A **fork** is your own copy of someone else's repository under your account. It is how you contribute to projects where you do not have write access (most open source).

```bash
# 1. Click "Fork" on GitHub, then clone YOUR fork
git clone git@github.com:asha/spring-petclinic.git
cd spring-petclinic
# 2. Track the original repository
git remote add upstream https://github.com/spring-projects/spring-petclinic.git
# 3. Keep your fork current
git fetch upstream
git switch main
git merge upstream/main
# 4. Work on a branch, push to your fork, open a PR to the upstream repository
```

| Clone | Fork |
| --- | --- |
| A local copy of a repo | A server-side copy under your account |
| Git feature | GitHub feature |
| You push only if you have access | You can always push to your fork |

## Issues
**Issues** track bugs, feature requests and tasks.

A good bug report includes: steps to reproduce, expected result, actual result, environment (browser, OS, version), logs or screenshots.

Useful features:
- **Labels** (`bug`, `enhancement`, `good first issue`), **assignees** and **milestones**.
- **Task lists** (`- [ ] write tests`) inside the issue body.
- Linking: writing `Fixes #42` in a PR description or commit closes issue 42 automatically when merged.
- **GitHub Projects** boards organise issues into columns such as To do / In progress / Done.
- Issue templates guide reporters to provide the right information.

## GitHub Actions
**GitHub Actions** runs automated workflows on events such as pushes and pull requests - building, testing, scanning and deploying your code (Continuous Integration / Continuous Delivery, Module 36).

A workflow is a YAML file in `.github/workflows/`:

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '21'
          cache: gradle
      - name: Build and test
        run: ./gradlew build

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm test
      - run: npm run build
```

Vocabulary:
- **Workflow** - the automated process (one YAML file).
- **Event/trigger** - `on: push`, `pull_request`, `schedule`, `workflow_dispatch` (manual).
- **Job** - a set of steps on one runner; jobs run in parallel unless `needs:` creates an order.
- **Step** - a shell command (`run`) or a reusable **action** (`uses`).
- **Runner** - the machine (GitHub-hosted Ubuntu/Windows/macOS or self-hosted).
- **Secrets** - encrypted values (Settings → Secrets) available as `${{ secrets.DEPLOY_TOKEN }}`; never print them in logs.

Make the CI check **required** in branch protection so broken code cannot be merged.

## Common mistakes
- Pushing directly to `main` instead of opening a PR.
- Huge PRs that nobody can review properly.
- Forgetting to sync a fork with `upstream`, causing large conflicts.
- Putting secrets in workflow files instead of GitHub Secrets.
- Vague issues ("it doesn't work") without reproduction steps.

## Practice exercise
1. Push your Java project to a new GitHub repository with a README describing setup and usage.
2. Enable branch protection on `main` requiring a PR and a passing check.
3. Add the CI workflow above (adjusted to your project) and confirm it runs on a PR.
4. Create two issues with labels; open a PR that fixes one and closes it automatically with `Fixes #n`.
5. Fork a small open-source repository, sync it with `upstream` and open a draft PR (you can close it afterwards).

## Key takeaways
- GitHub hosts Git repositories and adds collaboration: PRs, reviews, issues, Actions.
- Pull requests are where code is reviewed, tested and discussed before merging.
- Forks let you contribute without write access; keep them synced with `upstream`.
- Issues track work and link to PRs; good reports are reproducible.
- GitHub Actions automates build and test on every push and PR; store secrets as GitHub Secrets.
