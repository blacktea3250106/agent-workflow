# agent-workflow

Tools and rules for one Claude Code session that coordinates several Claude
and Codex workers on one machine. The orchestrator decides what to do. The gates
decide when work counts as done.

I pulled this out of two personal projects from October 2026: a Blender-rendered
interactive short film for the web, and a roguelite game prototype. The game
assets, renders and project-specific content are not included. What is left is the
tooling and the rules, with every rule linked to the incident that produced it.

## What is in here

```
playbook/
  ORCHESTRATOR_RULES.md   drop-in CLAUDE.md / AGENTS.md for the coordinating session
  DISPATCH.md             dispatch, hand-back, wrap-up, health check, two-track review
  PROMPT_CONTRACT.md      tiers, independence modes, Claude vs Codex routing
  STAGE_GATES.md          prototype-first gates, evidence labels, human test rules
tools/
  run_locked.py           one heavy job at a time across all worktrees; logs out of context
  health.py               measures the orchestrator session from its transcript
  health-review-prompt.md fixed prompt for the independent Codex health report
  dispatch_codex.sh       Codex worker in its own git worktree pinned to HEAD
  hooks/                  Claude Code hook config that runs health.py on every message
contracts/
  task_spec.py            stdlib JSON-Schema validator (fails on unsupported keywords)
  build_task_packet.py    Task Spec -> exact worker prompt; injects owner invariants; sha256 registry
  audit_task_specs.py     lint every spec in a folder
  codex_exec_adapter.py   runs a packet through `codex exec` without overriding sandbox settings
  schema/, templates/     spec schema, example specs, the markdown task brief
decisions/                what broke, the numbers, and the fix that was settled on
examples/acceptance-harness/  offline demo: check business outcomes, not API status codes
tests/                    17 tests for the lock, the contracts and the health check
```

Only Python 3.10+ standard library and bash. `codex` and `claude` CLIs are needed
only for the parts that call them.

## How it fits together

```
                 user
                  | messages                      ^ one-line status: "waiting on X / Y running"
                  v                               |
     +---------------------------+   hook on every message   +----------------------+
     | Orchestrator (Claude Code)|<--------------------------| tools/health.py      |
     | answers, queues P0/P1/P2, |   warnings + required     | context, waits, P1s, |
     | dispatches, verifies,     |   actions                 | worker age, jobs     |
     | merges, owns NOTES.md     |                           +----------+-----------+
     +---+-----------+-----------+                                      | every ~30 min
         |           |  Task Spec -> build_task_packet.py               v
         |           |  (schema check, invariants, sha256)   fresh read-only Codex
         v           v                                       writes health report
   Claude worker   Codex worker  (dispatch_codex.sh)
   worktree A      worktree B    pinned to base SHA
         |           |
         +-----+-----+---- heavy jobs ----> tools/run_locked.py (1 at a time, logs to file)
               |
               v  ~10-line hand-back + diff + paths
     orchestrator re-runs acceptance  ->  verified?  ->  cherry-pick  ->  merged
                                            | no
                                            v
                                   returned with output (max 2 rounds)
```

## Quick start

```sh
# 1. Rules for the orchestrator
cp playbook/ORCHESTRATOR_RULES.md  your-project/CLAUDE.md
cp -r tools contracts              your-project/

# 2. Health check on every user message
cp tools/hooks/claude-settings.example.json your-project/.claude/settings.json

# 3. Serialize heavy jobs from any worktree
python3 tools/run_locked.py --lane render -- blender -b scene.blend -P render.py

# 4. A contract-checked prompt for an important task
cp contracts/concerns.example.json   contracts/concerns.json     # edit for your project
cp contracts/invariants.example.md   contracts/invariants.md     # edit for your project
python3 contracts/audit_task_specs.py contracts/templates/*.json
python3 contracts/build_task_packet.py contracts/templates/spec-tier-S-verify.json \
        tasks/prompts/verify.md --registry tasks/prompts/REGISTRY.jsonl

# 5. A Codex worker in its own worktree (run in the background, wait for exit)
$EDITOR tasks/fix-x.md                 # from contracts/templates/task-brief.md
tools/dispatch_codex.sh fix-x

# Tests
python3 -m unittest discover -s tests -v
```

## The rules in one screen

1. The orchestrator answers first and only controls. Heavy work runs in the background.
2. New requests go into a queue as P0 / P1 / P2. At most two P1 at a time.
3. One status file, one writer. Overwrite state; never append "done" under "running".
4. No fixed worker cap. A worker may start if it does not run a heavy job outside the
   lock, its files do not overlap anyone else's, and its hand-back fits in about 10 lines.
5. "Handed back" is not "verified" is not "merged". The orchestrator re-runs acceptance itself.
6. Structure is decided on a cheap draft; only sections the user locks go to the expensive version.
7. Two automatic retries per failure, then report with evidence.
8. An AI review is not a human test. Nothing is called fun, intuitive or wanted without one.
9. Every workflow change gets a decision record with the numbers behind it.

## What it does not do

- It does not make the orchestrator preemptible. The health hook only fires when the
  user sends a message, so during a long model turn the warning is late too.
- Most rules are enforced by convention, not code. Code enforces the job lock, log
  truncation, spec validation, worktree pinning and the measurements.
- It does not claim a speed-up. The decision records list what was measured and
  what is still unverified.

See [ARTICLE.md](ARTICLE.md) for the full story ([繁體中文](ARTICLE_zh-TW.md)).


## License

MIT. See [LICENSE](LICENSE).
