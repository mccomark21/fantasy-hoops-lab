# Bluesky tool

## Goal

The Bluesky tool makes the weekly Schedule Skyline post: 2 images, the post text and 1 alt text for each image. The post is team-agnostic. It shows one roster spot that is open each day, with 1 to 4 adds, from the NBA schedule only. The command reads no Yahoo data and no roster file. It posts nothing. The design is in [docs/wiki/schedule-map-2026-11-04.md](../wiki/schedule-map-2026-11-04.md).

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
| `post.json` | The week number, the first and the last day, the post text, and the file and the alt text of each image in the post order. |

The terminal shows the week, the path and the size of each file, the smallest text of each image at a 390 px display width, the post text and the 2 alt texts.

### The images

`core/skyline_svg.py` draws the 2 images (`post_images()`). The days go from top to bottom, Monday at the top. Playwright Chromium opens each SVG with the Archivo font of `core/fonts/` and saves a 1080x1350 screenshot.

The command stops with an error in these cases:

1. Chromium does not load the Archivo font.
2. A text of an image is smaller than 11 px at a 390 px display width (DESIGN.md, "The Phone Legibility Rule").
3. An image is 1 MB or more.

### The post text

The post text has 3 parts: the title line with the week number and the dates, one line about the Skyline, and `#FantasyBasketball`. It has 300 characters or fewer (the Bluesky limit). An example:

```text
Schedule Skyline · Week 3 · Nov 2–8, 2026

The NBA games of each night, and the most games that one open roster spot gets with 1 to 4 adds.

#FantasyBasketball
```

### The alt texts

1. The alt text of image 1 gives the games of each night, the light nights and the anchor nights.
2. The alt text of image 2 gives each rung of the ladder: its games, its gain and its legs. A leg gives its days, its games, and its teams or the count of its teams.

## Settings

The settings are in `[skyline]` of `config.toml`:

| Setting | Use |
| --- | --- |
| `week_1` | The Monday of fantasy week 1. The week number counts weeks of 7 days from this Monday. |
| `unscheduled` | The ranges (first, last) of days that `data/schedule.csv` does not have yet. |
| `max_adds` | The ladder shows 1 to this number of adds. The post text gives this number. |

## Missing days

On 2026-11-04, `data/schedule.csv` had no games on Dec 4-11, 2026: the NBA Cup knockout days. `unscheduled` lists these days. A week with a day in `unscheduled` and 0 games on that day gives no post. The command writes no files, stops with exit code 1 and names the days. For example:

```text
No post for week 8 (Dec 7–13, 2026). The schedule has no games on Mon Dec 7, Tue Dec 8, Wed Dec 9, Thu Dec 10, Fri Dec 11. These days are in [skyline] unscheduled of config.toml. Run python -m fantasyhoops.fetch.espn again after the NBA sets the games of these days.
```

When the schedule has games on these days, the post runs again. A no-game day outside `unscheduled`, for example Tue Nov 3, 2026, shows the "NO NBA GAMES" hatch.
