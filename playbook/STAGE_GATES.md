# Stage gates and evidence rules

Principle: prove that a very small toy works before letting content, art and
production complexity in. More content does not fix a boring core.

## The loop

```text
Hypothesis
  -> kill criteria written down (cannot be edited after results exist)
  -> smallest playable experiment
  -> play / simulate / instrument
  -> blind red team + independent verifier
  -> evidence synthesis
  -> KEEP / REVISE / KILL
  -> next experiment
```

## Stages (example from a game prototype; rename for your product)

| Stage | Question | Do not start yet |
|---|---|---|
| P0 System toy | Does the bare mechanic create real decisions, or is there one obvious answer? | shops, maps, bosses, content |
| P1 Signature moment | Does the defining feature open new choices, or is it a free upgrade? | progression |
| P2 Feel and pacing | Does a 0.1–5 s sequence have anticipation, rhythm and payoff, and stay readable? | final art |
| P3 Micro run | Does a 10–20 minute loop have rhythm and identity? | content volume |
| P4 Ecology | Under random supply, are there several viable, different strategies? | production |
| P5 Human test | Do people ask for another round, and can they say what they want to try? | (this is the gate for any claim of "fun") |

## Gate rules

- Every stage leaves a build the owner can start with one command, listed in
  `PLAY.md`. Later stages must not break it.
- The owner's own play notes go in `owner_feedback.md` and outrank every AI review.
  They can overturn a gate that already passed.
- Kill criteria are written into the decision log before the experiment runs.
  After results exist they cannot be changed; a new round gets new criteria.
- Any stage can roll back. Passing on the first try is not expected.
- If a core hypothesis keeps failing after several revisions, killing it is allowed.

## Evidence labels

Every claim in a review or report is one of:

- **OBSERVED**: someone ran it and saw it (logs, screenshots, recordings).
- **MEASURED**: computed by code that is saved next to the claim.
- **REPORTED**: a human said it.
- **INFERRED**: the reviewer's interpretation.
- **AI_HYPOTHESIS**: what an agent predicts humans will feel.

Never merge these. A table that says "PASS" next to an INFERRED reading is a bug.

## Human validation status

Every Task Spec declares one of:

- `NOT_VALIDATED`: no human data. Every conclusion about fun, comprehension,
  replay or demand is an AI hypothesis.
- `HUMAN_PLAYTEST_PENDING`: a test is planned, no data yet. List the questions
  only humans can answer.
- `HUMAN_EVIDENCE_PROVIDED`: human data is in the allowed context; cite it as
  OBSERVED / REPORTED.

## Human test protocol (short form)

Observe behaviour before asking for opinions.

- Behaviour: first point where they got stuck; which tooltip they reopened; where
  they thought longest; what looked like chores; whether they rearranged on their
  own; what they discovered without being taught; whether they knew why they
  failed; whether they asked for another round.
- Non-leading questions: "What were you doing in that round?", "How would you
  describe your setup?", "Which part was the most boring?", "What would you try next?"
- Not evidence: an agent saying it is fun; a friend saying "nice"; an answer given
  after a hint; an average score without behaviour; testing only expert users.

## Warning signs for the orchestrator

- A dozen agents launched before any tiny prototype exists.
- Lots of content while the core loop is unproven.
- Every review is praise, with no counter-example and no kill criteria.
- An agent says "players will love this" with no human evidence.
- Every task runs on both Claude and Codex regardless of leverage.

## Anti-overconstraint check

Before generating a workflow, the orchestrator answers:

1. What has the owner actually fixed?
2. What in these documents is only a suggested method?
3. What is the biggest unknown this round?
4. What is the cheapest experiment that could prove the current idea wrong?
5. Am I creating agents only so the plan looks complete? If yes, cut it.
