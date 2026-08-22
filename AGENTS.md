# AGENTS.md

## Project
IDX EOD stock analytics terminal.

## Mandatory Skill
For any work under the trading dashboard or chart workspace, read and follow:

`skills/idx-terminal-dashboard/SKILL.md`

For future marketing/landing pages, a separate marketing design skill may be used. Marketing-layout rules must not override the trading dashboard skill.

## Current Milestone
Dashboard V0 only.

Goal:
- thin navigation rail
- collapsible/resizable watchlist with mini sparklines
- single main chart workspace
- fast ticker switching
- candlestick price
- volume
- Frequency Analyzer
- Supabase Postgres
- provider abstraction for Zapi

Do not expand scope unless explicitly requested.

## Ground Rules
- inspect existing code before editing
- preserve unrelated user work
- no force push
- no direct push to main
- no secrets in git
- use feature branch
- test before commit
- do not claim success without verification

## Data
Canonical Frequency Analyzer research formula:

`FA_raw = Volume / Frequency^3`

Store volume in shares as source truth.
Derived lots = shares / 100.
Raw formula and display normalization are separate.

## Database
Supabase is used as managed PostgreSQL.
Use migrations.
Do not add Auth/Storage/Realtime/Edge Functions in V0 unless requested.

## Git
Preferred branch: `codex/dashboard-v0`

When GitHub authentication is available:
- commit coherent completed work
- push feature branch
- create/update PR
- never push directly to main
