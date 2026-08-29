# DELTAX — getting the repo shared

Two parts: **Part A** is done once by the repo owner (US member). **Part B** is what
each teammate in Latvia and Denmark does.

---

# Part A — repo owner (do this yourself)

## A1. Create your GitHub account

Go to **https://github.com/signup** and complete it in your own browser.

- Use an email you'll keep access to.
- Pick a username — it becomes part of your repo URL, so keep it professional;
  it'll appear in the hackathon submission.
- Verify the email GitHub sends you.
- **Turn on two-factor authentication** when prompted. GitHub requires it for
  contributors, and you'll be locked out of pushing later if you skip it.

The free plan is enough. Unlimited private repos, unlimited collaborators.

> Nobody else should do this step for you, and no password or 2FA code should be
> typed by anyone but you.

## A2. Authenticate the GitHub CLI

Back in the terminal:

```bash
gh auth login
```

Answer the prompts:

| Prompt | Choose |
|---|---|
| What account do you want to log into? | **GitHub.com** |
| Preferred protocol | **HTTPS** |
| Authenticate Git with your GitHub credentials? | **Yes** |
| How would you like to authenticate? | **Login with a web browser** |

It shows a one-time code, then opens your browser. Paste the code, approve, done.

Confirm it worked:

```bash
gh auth status
```

## A3. Create the repo and push

Once `gh auth status` is happy, this single command creates the repository and
uploads everything:

```bash
gh repo create DELTAX --private --source=. --remote=origin --push
```

**Private on purpose.** The hackathon requires a *public* repo at submission, but
publishing your strategy mid-competition hands it to everyone else. Stay private
until Friday, then flip it (step A5).

Verify:

```bash
gh repo view --web
```

## A4. Invite your teammates

You need each teammate's GitHub username (have them do step A1 too, then send it
to you).

```bash
gh repo edit --add-collaborator THEIR_USERNAME
```

Run it once per teammate. They'll get an email invite they need to accept.

To check who has access:

```bash
gh api repos/:owner/DELTAX/collaborators --jq '.[].login'
```

## A5. Before the deadline — go public

The hackathon requires a public repository. Do this **on Friday 4 Sept, before
11:00 AM EDT**:

```bash
gh repo edit --visibility public --accept-visibility-change-consequences
```

Then double-check the credentials never leaked:

```bash
git log -p --all | grep -c "PKVEV2" && echo "LEAK — do not publish" || echo "clean"
```

---

# Part B — teammates in 🇱🇻 Latvia and 🇩🇰 Denmark

## B1. GitHub account

Sign up at **https://github.com/signup**, enable 2FA, and send your username to
the repo owner. Accept the email invitation when it arrives.

## B2. Install the tools

**macOS:**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install gh git
brew install alpacahq/tap/cli
```

**Linux:** install `git` and `gh` from your package manager, then:
```bash
go install github.com/alpacahq/cli/cmd/alpaca@latest
```

**Windows:** use WSL2 and follow the Linux steps, or install Git for Windows plus
the `gh` MSI, then the Alpaca CLI release binary.

## B3. Clone the repo

```bash
gh auth login          # same prompts as A2
gh repo clone pautax007/DELTAX
cd DELTAX
```

### "I need the SSH keys" — no, you don't (and nobody sends keys)

Two separate facts:

1. **You don't need SSH at all.** `gh auth login` with HTTPS (the steps above)
   authenticates cloning, pulling and pushing. If a clone fails, the cause is
   an unaccepted invite or a not-logged-in `gh` — check `gh auth status` —
   never a missing key.
2. **SSH keys are never shared or sent.** If you prefer SSH anyway, you
   generate your own keypair on your own machine and upload only the *public*
   half to your *own* GitHub account:

```bash
ssh-keygen -t ed25519 -C "you@example.com"     # Enter to accept defaults
gh ssh-key add ~/.ssh/id_ed25519.pub --title "elsa-laptop"
git clone git@github.com:pautax007/DELTAX.git
```

The private key (`~/.ssh/id_ed25519`, no `.pub`) stays on your machine
forever. Anyone who asks you to email a private key — or offers to send you
one — is describing a security incident, not a setup step.

## B4. Get your OWN Alpaca paper account

**Do not ask for the team's API keys.** The hackathon rules explicitly allow any
paper account during development, and the competition account is locked.

1. Sign up at **https://alpaca.markets** and open a **paper trading** account.
2. Generate API keys from the paper dashboard.
3. Enable options trading (level 3 if offered) so you can test spreads.

```bash
cp .env.alpaca.example .env.alpaca
# open .env.alpaca and paste YOUR OWN key and secret
chmod 600 .env.alpaca
```

## B5. Verify your setup

```bash
set -a; . ./.env.alpaca; set +a
alpaca doctor
```

Expect `profile: paper`, `trading API: connected`, `All checks passed`. If it says
anything about live trading, stop and re-check your keys.

## B6. Start working

Open Claude Code in the project folder — CLI, desktop app, claude.ai/code, or the
VS Code / JetBrains extension. Each of you needs your own Claude account.

`CLAUDE.md` loads automatically, so your session starts already knowing the
hackathon constraints, the risk gates, the account lock, and the build order. You
don't need to re-explain the project.

**Read before writing code:** `HACKATHON-RULES.md`, then `STRATEGY.md`, then
`research/options/golden-rules.md`.

---

# Day-to-day

```bash
git pull                        # start of your session
git checkout -b your-feature    # work on a branch
git add -A && git commit -m "what you did"
git push -u origin your-feature
gh pr create                    # open a pull request
```

Coordination happens through commits and pull requests. **Claude Code sessions are
not shared** — each of you has your own conversation. `CLAUDE.md` is what keeps the
three sessions consistent, so if the team agrees a new rule or constraint, put it
in `CLAUDE.md` and commit it. That's how a decision reaches everyone's assistant.

## Never commit

- `.env.alpaca` or any real API key (already gitignored — keep it that way)
- Raw video captions or third-party PDFs
- Anything touching the competition account's credentials

Check before pushing if unsure:

```bash
git status --short && git diff --cached --stat
```
