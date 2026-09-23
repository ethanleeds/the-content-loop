# Feedback Log

Your verdict on every video the agent gives you. The agent reads this first, every run. A rejection with a reason is the fastest teaching signal in the system: it tells the agent what it got wrong before a single view.

Statuses: `approved` (hook is good, move it to ready), `in progress`, `done` (posted), `rejected` (reason required).

Log with: `node scripts/status.mjs "<video title> | <status> | <why>"`

## Log

| date | video | status | why |
|---|---|---|---|

## Rejection patterns (agent maintains)

One rejection is a note. Two with the same reason is a rule. Each rule cites the rows it came from.

- (none yet)
