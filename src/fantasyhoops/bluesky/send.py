"""The weekly job of the Schedule Skyline post (#238): make the post files, then post them to Bluesky or do a dry run.

The Monday workflow (.github/workflows/bluesky.yml) runs this module after python -m fantasyhoops.fetch.espn.
The module makes the post of the week with bluesky/post.py. It posts only when the environment variable
BLUESKY_POST is "true". Else it does a dry run: it writes the files and posts nothing. A week with missing schedule
days gives no post and no error. The module sends plain AT Protocol HTTP calls with urllib. It never prints the
app password.

The module writes the files of post.py in output/bluesky/<first day of the week>/:
  skyline.png, ladder.png and post.json
In GitHub Actions, it also adds the post text and the 2 alt texts to the job summary (GITHUB_STEP_SUMMARY).
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

from fantasyhoops.bluesky.post import HEIGHT, WIDTH, MissingDays, build, next_week_start, write_post
from fantasyhoops.core import common
from fantasyhoops.core.console import use_utf8_output
from fantasyhoops.core.schedule import read_schedule

SERVICE = "https://bsky.social"  # the Bluesky host of the owner's account
SWITCH = "BLUESKY_POST"  # "true" switches on real posting. Any other value or no value gives a dry run.
HANDLE = "BLUESKY_HANDLE"  # the account handle, from a GitHub secret
PASSWORD = "BLUESKY_APP_PASSWORD"  # the app password, from a GitHub secret
TAG = re.compile(r"#(\w+)")


def posting_on(env):
    """True only when the switch BLUESKY_POST of env is "true". The default is a dry run."""
    return env.get(SWITCH, "").strip().lower() == "true"


class Client:
    """The 3 AT Protocol calls of one post: log in, upload each image, make the post record.

    opener sends a urllib Request and returns a file-like answer. A test gives a fake opener.
    """

    def __init__(self, service=SERVICE, opener=urllib.request.urlopen):
        self.service = service.rstrip("/")
        self.opener = opener
        self.token = None

    def _call(self, method, body, content_type="application/json"):
        headers = {"Content-Type": content_type}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if content_type == "application/json":
            body = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(f"{self.service}/xrpc/{method}", data=body, headers=headers, method="POST")
        try:
            with self.opener(request, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            # The error names the method and the answer of Bluesky only. It never shows the request body.
            raise RuntimeError(f"Bluesky {method} answered HTTP {e.code}: {e.read().decode('utf-8', 'replace')}")

    def login(self, handle, password):
        """Start a session. Return the DID of the account."""
        session = self._call("com.atproto.server.createSession", {"identifier": handle, "password": password})
        self.token = session["accessJwt"]
        return session["did"]

    def upload_image(self, data):
        """Upload the bytes of one PNG. Return the blob reference for the post record."""
        return self._call("com.atproto.repo.uploadBlob", data, content_type="image/png")["blob"]

    def create_post(self, did, record):
        """Make the post record. Return {"uri", "cid"} of the post."""
        return self._call(
            "com.atproto.repo.createRecord", {"repo": did, "collection": "app.bsky.feed.post", "record": record}
        )


def tag_facets(text):
    """The facet of each #tag of text, so that Bluesky links the tags. The offsets count UTF-8 bytes."""
    facets = []
    for m in TAG.finditer(text):
        start = len(text[: m.start()].encode("utf-8"))
        facets.append(
            {
                "index": {"byteStart": start, "byteEnd": start + len(m.group(0).encode("utf-8"))},
                "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}],
            }
        )
    return facets


def post_record(data, blobs, now):
    """The app.bsky.feed.post record: the text of post.json and its images in order, each with its alt text."""
    return {
        "$type": "app.bsky.feed.post",
        "text": data["text"],
        "facets": tag_facets(data["text"]),
        "langs": ["en"],
        "createdAt": now.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "embed": {
            "$type": "app.bsky.embed.images",
            "images": [
                {"alt": image["alt"], "image": blob, "aspectRatio": {"width": WIDTH, "height": HEIGHT}}
                for image, blob in zip(data["images"], blobs)
            ],
        },
    }


def send(folder, client, handle, password, now=None):
    """Post the files of folder (post.json and its images, in the post.json order). Return {"uri", "cid"}."""
    data = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    did = client.login(handle, password)
    blobs = [client.upload_image((folder / image["file"]).read_bytes()) for image in data["images"]]
    return client.create_post(did, post_record(data, blobs, now or datetime.now(timezone.utc)))


def summary(data, mode):
    """The job summary in Markdown: the mode, the post text and the alt text of each image."""
    lines = [f"## Schedule Skyline post: {mode}", "", "Post text:", "", "```text", data["text"], "```", ""]
    for i, image in enumerate(data["images"], 1):
        lines += [f"Alt text of image {i} ({image['file']}):", "", f"> {image['alt']}", ""]
    return "\n".join(lines)


def _summary(env, text):
    path = env.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def run(folder, env, client=None, now=None):
    """Post the files of folder when the switch is on. Else post nothing. Return the post {"uri", "cid"} or None."""
    data = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    if not posting_on(env):
        print(f"Dry run: posted nothing. To post, set {SWITCH}=true (docs/bluesky/README.md).")
        _summary(env, summary(data, "dry run, posted nothing"))
        return None
    handle, password = env.get(HANDLE, ""), env.get(PASSWORD, "")
    if not handle or not password:
        sys.exit(f"{SWITCH} is true, but the secret {HANDLE} or {PASSWORD} is empty. Add both secrets.")
    result = send(folder, client or Client(), handle, password, now)
    print(f"Posted to Bluesky: {result['uri']}")
    _summary(env, summary(data, f"posted, {result['uri']}"))
    return result


def main(argv=None, env=None, client=None):
    parser = argparse.ArgumentParser(description="Make the weekly Schedule Skyline post and post it, or do a dry run.")
    parser.add_argument(
        "--week",
        type=date.fromisoformat,
        help="the Monday of the week, YYYY-MM-DD. Default: the Monday of the next fantasy week.",
    )
    args = parser.parse_args(argv)
    env = os.environ if env is None else env
    start = args.week or next_week_start(date.today())
    try:
        post = build(read_schedule(), start, common.load_config())
    except MissingDays as e:
        # Not an error: the NBA has not set the games of these days yet. The job posts nothing and stays green.
        print(e)
        if env.get("GITHUB_ACTIONS") == "true":
            print(f"::notice title=No Skyline post this week::{e}")
        return None
    except FileNotFoundError as e:
        sys.exit(f"{e}. Run python -m fantasyhoops.fetch.espn first.")
    except ValueError as e:
        sys.exit(str(e))
    folder = common.OUT / "bluesky" / start.isoformat()
    files, _ = write_post(post, folder)
    for f in files:
        print(f"  {f} ({f.stat().st_size / 1024:.0f} KB)")
    return run(folder, env, client)


if __name__ == "__main__":
    use_utf8_output()
    main()
