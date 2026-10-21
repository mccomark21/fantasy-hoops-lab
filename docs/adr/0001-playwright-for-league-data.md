# 1. Read league data with Playwright and a manual sign-in

Date: 2026-10-20

Status: Accepted

## Context

The weekly adds planner needs data that only the league's own Yahoo pages show: your roster, the other rosters, the free agents and the adds that you used this week. These pages need a Yahoo sign-in.

In October 2026, a sign-in from an automated Playwright browser failed. Because of this, `fetch/yahoo.py` reads only the public Yahoo draft pages.

The other option is the Yahoo Fantasy API with yfpy and OAuth. The user's baseball project uses it, and it works there. It gives structured data that does not change when Yahoo changes its page layout.

## Decision

Use Playwright. You sign in by hand one time in a visible browser window. Playwright keeps the session, and later runs use it without a new sign-in. The tool reads the league pages from that session.

## Consequences

- A manual sign-in can possibly get past the block that stopped the automated sign-in. This is not tested yet.
- The page readers depend on the Yahoo page layout. A Yahoo redesign can break them.
- The session expires. Then you must sign in again by hand.
- If Playwright does not work, the Yahoo Fantasy API (yfpy) is the fallback.
