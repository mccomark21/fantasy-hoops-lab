# Bluesky tool

## Goal

The Bluesky tool makes the weekly Schedule Skyline post: 2 images, the post text and 1 alt text for each image. The post is team-agnostic. It shows one roster spot that is open each day, with 1 to 4 adds, from the NBA schedule only. The command reads no Yahoo data and no roster file. It posts nothing. A GitHub Actions job makes the post each Monday and posts it only when the owner switches on posting. See [The Monday job](#the-monday-job). The design is in [docs/wiki/schedule-map-2026-11-04.md](../wiki/schedule-map-2026-11-04.md).

## Usage

```sh
python -m fantasyhoops.bluesky                     # The post of the next fantasy week.
python -m fantasyhoops.bluesky --week 2026-11-09   # The post of the week that starts on Monday 2026-11-09.
```

1. The command reads `data/schedule.csv`. To make this file, run `python -m fantasyhoops.fetch.espn`.
2. The default week starts on today if today is a Monday. Else it starts on the next Monday.
3. Chromium for Playwright must be installed: `python -m playwright install chromium`.

## Output

The command writes these files in `output/bluesky/<first day of the week>/`:

| File | Content |
| --- | --- |
| `skyline.png` | Image 1: the skyline. 1080x1350, under 1 MB. |
| `ladder.png` | Image 2: the add ladder. 1080x1350, under 1 MB. |
| `post.json` | The first and the last day of the week, the post text, and the file and the alt text of each image in the post order. |

The terminal shows the dates of the week, the path and the size of each file, the smallest text of each image at a 390 px display width, the post text and the 2 alt texts.

### The images

`core/skyline_svg.py` draws the 2 images (`post_images()`). The days go from top to bottom, Monday at the top. The title line gives the dates of the week, for example "Nov 9–15, 2026", not a week number. Bluesky readers play in leagues with other week numbers (owner decision of 2026-11-05). The bottom-right corner of each image has the sign-off "Mahhhk Draft" in the text ink (owner request of 2026-11-05). Playwright Chromium opens each SVG with the Archivo font of `core/fonts/` and saves a 1080x1350 screenshot.

The command stops with an error in these cases:

1. Chromium does not load the Archivo font.
2. A text of an image is smaller than 11 px at a 390 px display width (DESIGN.md, "The Phone Legibility Rule").
3. An image is 1 MB or more.

### The post text

The post text has 3 parts: the title line with the dates of the week, one line about the Skyline, and the tags `#FantasyBasketball #MahhhkDraft`. It has 300 characters or fewer (the Bluesky limit). An example:

```text
Schedule Skyline · Nov 2–8, 2026

The NBA games of each night, and the most games that one open roster spot gets with 1 to 4 adds.

#FantasyBasketball #MahhhkDraft
```

### The alt texts

1. The alt text of image 1 gives the games of each night, the light nights and the anchor nights.
2. The alt text of image 2 gives each rung of the ladder: its games, its gain and its legs. A leg gives its days, its games, and its teams or the count of its teams.

## Settings

The settings are in `[skyline]` of `config.toml`:

| Setting | Use |
| --- | --- |
| `unscheduled` | The ranges (first, last) of days that `data/schedule.csv` does not have yet. |
| `max_adds` | The ladder shows 1 to this number of adds. The post text gives this number. |

## Missing days

On 2026-11-04, `data/schedule.csv` had no games on Dec 4-11, 2026: the NBA Cup knockout days. `unscheduled` lists these days. A week with a day in `unscheduled` and 0 games on that day gives no post. The command writes no files, stops with exit code 1 and names the days. For example:

```text
No post for the week of Dec 7–13, 2026. The schedule has no games on Mon Dec 7, Tue Dec 8, Wed Dec 9, Thu Dec 10, Fri Dec 11. These days are in [skyline] unscheduled of config.toml. Run python -m fantasyhoops.fetch.espn again after the NBA sets the games of these days.
```

When the schedule has games on these days, the post runs again. A no-game day outside `unscheduled`, for example Tue Nov 3, 2026, shows the "NO NBA GAMES" hatch.

## The Monday job

The workflow `.github/workflows/bluesky.yml` makes the post each Monday at 13:00 UTC (8:00 US Eastern in winter, 9:00 in summer). It uses GitHub Actions only. It needs no Yahoo login.

1. The job runs `python -m fantasyhoops.fetch.espn`. This script reads the public ESPN site API with no login and no key. If the fetch fails, the job fails and posts nothing.
2. The job runs `python -m fantasyhoops.bluesky.send`. This command makes the post files of `python -m fantasyhoops.bluesky`. Then it posts them, or it does a dry run.
3. The job uploads the files of `output/bluesky/` as the artifact `skyline-post`. GitHub keeps the artifact for 30 days.

The job also runs as a dry run on each PR that changes the workflow, `src/fantasyhoops/bluesky/` or `src/fantasyhoops/core/skyline*.py`.

### The dry run

The dry run is the default. It makes the files and posts nothing. To read a dry run:

1. Open the run on the Actions tab of the repo (workflow "bluesky").
2. Read the job summary. It gives the post text and the alt text of each image.
3. Download the artifact `skyline-post`. It holds `skyline.png`, `ladder.png` and `post.json`.

A week with missing schedule days (see [Missing days](#missing-days)) gives no files and no post. The run stays green and shows the notice "No Skyline post this week".

### The secrets

The owner adds 2 repository secrets. The dry run does not need them.

| Secret | Value |
| --- | --- |
| `BLUESKY_HANDLE` | The handle of the Bluesky account, for example `name.bsky.social`. |
| `BLUESKY_APP_PASSWORD` | An app password of the account. Do not use the account password. |

1. In Bluesky, open Settings, then Privacy and security, then App passwords.
2. Add an app password. Do not give it access to direct messages.
3. In GitHub, open the repo Settings, then Secrets and variables, then Actions.
4. On the Secrets tab, add `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD`.

The job gives the secrets to the post step only when posting is on. The command never prints the app password.

### Switch on posting

Only a run on `main` can post. A run on another branch is always a dry run.

1. Check the dry runs of some Mondays first.
2. To post one time, run the workflow by hand: Actions, then "bluesky", then "Run workflow". Select `main` and turn on "post".
3. To post each Monday, add the repository variable `BLUESKY_POST` with the value `true`. Use the Variables tab, next to the Secrets tab.
4. To go back to the dry run, delete the variable or set it to `false`.

The manual input "week" makes the post of another week, for example `2026-11-16`. Each run that posts makes a new post. Do not run the job again after a post, or Bluesky shows the week 2 times.

### The post

The post has the post text and 2 images in order: image 1 is the skyline, image 2 is the ladder. Each image has its own alt text, from `post.json`. Each tag of the post text is a link. The command sends plain AT Protocol HTTP calls to `https://bsky.social` (`com.atproto.server.createSession`, `com.atproto.repo.uploadBlob`, `com.atproto.repo.createRecord`). It needs no added library.
