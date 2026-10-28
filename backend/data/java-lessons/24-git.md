## Introduction to Git
**Git** is a distributed **version control system**. It records snapshots of your project over time so you can see who changed what and why, go back to any earlier version, work on features in parallel and merge everyone's work. Every developer has the full history locally, so most operations are fast and work offline.

Install Git from git-scm.com (Windows includes Git Bash), then set your identity once:

```bash
git --version
git config --global user.name "Asha Kumar"
git config --global user.email "asha@example.com"
git config --global init.defaultBranch main
```

### The three areas
```
Working directory  --git add-->  Staging area (index)  --git commit-->  Repository (.git history)
```

- **Working directory** - the files you edit.
- **Staging area** - the changes you have selected for the next commit.
- **Repository** - the committed history stored in the hidden `.git` folder.

## Repository
A **repository (repo)** is a project folder tracked by Git.

```bash
mkdir training-portal && cd training-portal
git init                        # create a new repo
# or copy an existing remote repo:
git clone https://github.com/org/training-portal.git
```

Tell Git what to ignore with a `.gitignore` file in the root:

```
build/
node_modules/
.idea/
*.log
.env
```

Never commit build output, dependencies, IDE settings or secrets.

## Essential Git commands
| Command | What it does |
| --- | --- |
| `git status` | Show changed, staged and untracked files |
| `git add <file>` / `git add .` | Stage changes |
| `git commit -m "message"` | Record staged changes as a commit |
| `git log --oneline --graph` | Show history compactly |
| `git diff` / `git diff --staged` | Show unstaged / staged changes |
| `git restore <file>` | Discard working-directory changes to a file |
| `git restore --staged <file>` | Unstage a file |
| `git rm <file>` / `git mv a b` | Remove / rename a tracked file |
| `git remote -v` | List remote repositories |
| `git fetch` | Download remote history without changing your branch |
| `git pull` | Fetch and integrate remote changes into your branch |
| `git push` | Upload your commits to the remote |
| `git show <commit>` | Show one commit's changes |
| `git revert <commit>` | Create a new commit that undoes an earlier one (safe on shared branches) |
| `git reset` | Move the branch pointer (rewrites history - use carefully) |

## Commit
A **commit** is a snapshot with a unique hash, an author, a timestamp, a message and a pointer to its parent commit(s).

```bash
git add src/CourseService.java
git commit -m "Add course search by title"
```

Good commits are **small and focused** (one logical change) and have clear messages:

```
Add pagination to course list endpoint

Limit page size to 50 and sort by id as a tiebreaker so results are stable.
```

Write the subject in the imperative mood ("Add", "Fix", "Refactor"), under ~50 characters. Many teams use Conventional Commits: `feat: add course search`, `fix: handle empty title`.

`git commit --amend` changes the most recent commit (only before you have pushed it).

## Branch
A **branch** is a lightweight movable pointer to a commit. Branches let you develop features in isolation without breaking `main`.

```bash
git branch                          # list branches (* marks the current one)
git switch -c feature/course-search # create and switch
git switch main                     # switch back
git branch -d feature/course-search # delete a merged branch
git push -u origin feature/course-search   # publish and track
```

`HEAD` is a pointer to the branch (or commit) you currently have checked out. A typical team flow: create a branch per feature or fix from `main`, commit, push, open a pull request (Module 25), merge after review.

## Merge
**Merging** integrates another branch's changes into the current branch.

```bash
git switch main
git pull                            # make sure main is current
git merge feature/course-search
```

- **Fast-forward merge** - if `main` has no new commits, Git just moves the pointer forward.
- **Three-way merge** - if both branches have new commits, Git creates a **merge commit** with two parents.

### Merge conflicts
When both branches change the same lines, Git cannot decide and marks a conflict:

```
<<<<<<< HEAD
int pageSize = 20;
=======
int pageSize = 50;
>>>>>>> feature/course-search
```

Resolve by editing the file to the correct final content (understanding both intentions), removing the markers, then:

```bash
git add CourseService.java
git commit                 # completes the merge
# or abandon: git merge --abort
```

Run the tests after resolving - a conflict-free merge can still be logically wrong.

## Rebase
**Rebasing** replays your branch's commits on top of another branch, producing a linear history.

```bash
git switch feature/course-search
git rebase main            # move my commits on top of the latest main
# if conflicts: fix, git add <file>, git rebase --continue   (or git rebase --abort)
```

```
Before:  main:    A---B---C
                       \
         feature:       D---E

After:   main:    A---B---C
                           \
         feature:           D'---E'
```

| Merge | Rebase |
| --- | --- |
| Preserves exact history with merge commits | Creates a clean, linear history |
| Safe for shared branches | Rewrites commits (new hashes) |
| Can produce a noisy graph | Easier to read and bisect |

**Golden rule:** never rebase commits that others have already pulled (shared/public branches). Interactive rebase (`git rebase -i`) can squash and reword your own local commits before sharing them.

## Cherry-pick
**Cherry-pick** applies the changes from one specific commit onto your current branch, creating a new commit.

```bash
git log --oneline main
# a1b2c3d Fix null pointer in enrollment
git switch release/1.2
git cherry-pick a1b2c3d
```

Typical use: bringing a hotfix from `main` into a release branch without merging everything else. Overusing it duplicates commits across branches, so prefer merges for regular integration.

## Stash
**Stash** temporarily shelves uncommitted changes so you can switch context with a clean working directory.

```bash
git stash push -m "half-done search UI"    # save and clean the working directory
git switch main                            # fix an urgent bug...
git switch feature/course-search
git stash list                             # stash@{0}: On feature...: half-done search UI
git stash pop                              # reapply and remove from the stash
# git stash apply keeps it in the stash; git stash drop deletes it
```

Use `git stash -u` to include untracked files.

## Common mistakes
- Committing secrets (`.env`, passwords) - removing them from history is hard; rotate the secret immediately.
- Giant commits mixing unrelated changes.
- Working directly on `main` in a team.
- Rebasing or force-pushing a shared branch.
- Resolving conflicts by blindly choosing one side.

## Practice exercise
1. Initialise a repo for your Module 1 Java project with a proper `.gitignore`; make three focused commits.
2. Create `feature/average` and `feature/validation` branches that both edit the same method; merge one, then resolve the conflict when merging the other.
3. Create another branch and rebase it onto `main`; compare `git log --graph` with the merge result.
4. Cherry-pick a single bug-fix commit onto a `release` branch.
5. Stash an unfinished change, switch branches, then restore it with `git stash pop`.

## Key takeaways
- Git moves changes from working directory → staging area → repository.
- Make small, well-described commits and ignore generated files and secrets.
- Branches isolate work; merges integrate it; conflicts need human judgement and re-testing.
- Rebase gives linear history but never rebase shared commits.
- Cherry-pick copies individual commits; stash shelves unfinished work.
