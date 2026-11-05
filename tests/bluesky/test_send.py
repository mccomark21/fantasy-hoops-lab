"""Tests of bluesky/send.py (#238): the posting switch, the AT Protocol requests with a fake opener and the job summary.

The tests send no request to Bluesky. A fake opener records each request and gives a fixed answer.
"""

import io
import json
import urllib.error
from datetime import datetime, timezone

import pytest

from fantasyhoops.bluesky import send
from fantasyhoops.bluesky.post import HEIGHT, WIDTH, MissingDays
from fantasyhoops.bluesky.send import Client, posting_on, run, tag_facets

TEXT = "Schedule Skyline · Nov 9–15, 2026\n\nA line.\n\n#FantasyBasketball #MahhhkDraft"
SECRET = "abcd-efgh-ijkl-mnop"  # a fake app password
ENV_ON = {"BLUESKY_POST": "true", "BLUESKY_HANDLE": "owner.bsky.social", "BLUESKY_APP_PASSWORD": SECRET}
NOW = datetime(2026, 11, 9, 13, 0, tzinfo=timezone.utc)


@pytest.fixture
def folder(tmp_path):
    """A post folder like the one of post.write_post: 2 PNG files and post.json."""
    (tmp_path / "skyline.png").write_bytes(b"\x89PNG skyline")
    (tmp_path / "ladder.png").write_bytes(b"\x89PNG ladder")
    data = {
        "first_day": "2026-11-09",
        "last_day": "2026-11-15",
        "text": TEXT,
        "images": [
            {"file": "skyline.png", "alt": "Alt of the skyline."},
            {"file": "ladder.png", "alt": "Alt of the ladder."},
        ],
    }
    (tmp_path / "post.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return tmp_path


class FakeOpener:
    """Records each urllib Request and gives the answer of its AT Protocol method."""

    ANSWERS = {
        "com.atproto.server.createSession": {"accessJwt": "TOKEN", "did": "did:plc:owner"},
        "com.atproto.repo.createRecord": {"uri": "at://did:plc:owner/app.bsky.feed.post/1", "cid": "cid1"},
    }

    def __init__(self, feed=()):
        self.requests = []
        self.feed = list(feed)  # the items of the author feed

    @staticmethod
    def method(request):
        return request.full_url.rsplit("/", 1)[1].split("?", 1)[0]

    def __call__(self, request, timeout):
        self.requests.append(request)
        method = self.method(request)
        if method == "com.atproto.repo.uploadBlob":
            answer = {"blob": {"$type": "blob", "ref": {"$link": f"blob{len(self.requests)}"}, "size": 1}}
        elif method == "app.bsky.feed.getAuthorFeed":
            answer = {"feed": self.feed}
        else:
            answer = self.ANSWERS[method]
        return io.BytesIO(json.dumps(answer).encode("utf-8"))

    def methods(self):
        return [self.method(r) for r in self.requests]


def item(text, did="did:plc:owner", repost=False):
    """One item of an author feed: a post of did with text, or a repost of it."""
    entry = {"post": {"author": {"did": did}, "record": {"text": text}}}
    if repost:
        entry["reason"] = {"$type": "app.bsky.feed.defs#reasonRepost"}
    return entry


@pytest.mark.parametrize(
    "env, on",
    [({}, False), ({"BLUESKY_POST": ""}, False), ({"BLUESKY_POST": "false"}, False), ({"BLUESKY_POST": "1"}, False)]
    + [({"BLUESKY_POST": "true"}, True), ({"BLUESKY_POST": " True "}, True)],
)
def test_the_switch_is_off_unless_it_is_true(env, on):
    assert posting_on(env) is on


def test_with_the_switch_off_the_job_posts_nothing(folder, tmp_path, capsys):
    opener = FakeOpener()
    summary = tmp_path / "summary.md"
    env = {**ENV_ON, "BLUESKY_POST": "false", "GITHUB_STEP_SUMMARY": str(summary)}
    assert run(folder, env, Client(opener=opener)) is None
    assert opener.requests == []
    assert "Dry run: posted nothing" in capsys.readouterr().out
    text = summary.read_text(encoding="utf-8")
    assert "dry run" in text and TEXT in text
    assert "Alt of the skyline." in text and "Alt of the ladder." in text


def test_with_the_switch_on_the_job_posts_the_text_and_the_2_images_in_order(folder, capsys):
    # The feed has an older week, and a repost and a post of another account with the same title line.
    title = TEXT.split("\n", 1)[0]
    feed = [item("Schedule Skyline · Nov 2–8, 2026\n\n..."), item(title, repost=True), item(title, did="did:plc:x")]
    opener = FakeOpener(feed)
    result = run(folder, ENV_ON, Client(opener=opener), now=NOW)
    assert result["uri"] == "at://did:plc:owner/app.bsky.feed.post/1"
    assert opener.methods() == [
        "com.atproto.server.createSession",
        "app.bsky.feed.getAuthorFeed",
        "com.atproto.repo.uploadBlob",
        "com.atproto.repo.uploadBlob",
        "com.atproto.repo.createRecord",
    ]
    login, read, sky, ladder, create = opener.requests
    assert json.loads(login.data) == {"identifier": "owner.bsky.social", "password": SECRET}
    assert "Authorization" not in login.headers
    assert read.get_method() == "GET" and read.data is None
    assert "actor=did%3Aplc%3Aowner" in read.full_url
    # Image 1 is the skyline, image 2 is the ladder.
    assert sky.data == b"\x89PNG skyline" and ladder.data == b"\x89PNG ladder"
    for r in (read, sky, ladder, create):
        assert r.get_header("Authorization") == "Bearer TOKEN"
    assert sky.get_header("Content-type") == "image/png"
    body = json.loads(create.data)
    assert body["repo"] == "did:plc:owner" and body["collection"] == "app.bsky.feed.post"
    record = body["record"]
    assert record["text"] == TEXT
    assert record["createdAt"] == "2026-11-09T13:00:00.000Z"
    images = record["embed"]["images"]
    assert [i["alt"] for i in images] == ["Alt of the skyline.", "Alt of the ladder."]
    assert [i["image"]["ref"]["$link"] for i in images] == ["blob3", "blob4"]  # the blobs of request 3 and 4
    assert all(i["aspectRatio"] == {"width": WIDTH, "height": HEIGHT} for i in images)
    assert [f["features"][0]["tag"] for f in record["facets"]] == ["FantasyBasketball", "MahhhkDraft"]
    # The password goes only in the login request and never in the output.
    assert all(SECRET.encode() not in (r.data or b"") and SECRET not in r.full_url for r in opener.requests[1:])
    assert SECRET not in capsys.readouterr().out


def test_a_rerun_does_not_post_the_same_week_again(folder, tmp_path, capsys):
    # The account already has the post of this week, with other text after the title line.
    opener = FakeOpener([item("Schedule Skyline · Nov 9–15, 2026\n\nAn older text of the post.")])
    summary = tmp_path / "summary.md"
    assert run(folder, {**ENV_ON, "GITHUB_STEP_SUMMARY": str(summary)}, Client(opener=opener), now=NOW) is None
    assert opener.methods() == ["com.atproto.server.createSession", "app.bsky.feed.getAuthorFeed"]
    line = 'Already posted: a recent post has the title "Schedule Skyline · Nov 9–15, 2026". Posted nothing.'
    assert line in capsys.readouterr().out
    assert line in summary.read_text(encoding="utf-8")


def test_with_the_switch_on_and_no_secret_the_job_stops_before_a_request(folder):
    opener = FakeOpener()
    with pytest.raises(SystemExit) as e:
        run(folder, {"BLUESKY_POST": "true", "BLUESKY_HANDLE": "owner.bsky.social"}, Client(opener=opener))
    assert "BLUESKY_APP_PASSWORD" in str(e.value)
    assert opener.requests == []


def test_an_http_error_does_not_show_the_password():
    def opener(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"error":"AuthFailed"}'))

    with pytest.raises(RuntimeError) as e:
        Client(opener=opener).login("owner.bsky.social", SECRET)
    assert "401" in str(e.value) and "AuthFailed" in str(e.value)
    assert SECRET not in str(e.value)


def test_the_tag_facets_count_utf8_bytes():
    facets = tag_facets(TEXT)
    raw = TEXT.encode("utf-8")
    tags = [raw[f["index"]["byteStart"] : f["index"]["byteEnd"]].decode("utf-8") for f in facets]
    assert tags == ["#FantasyBasketball", "#MahhhkDraft"]


def test_a_week_with_missing_days_posts_nothing_and_does_not_fail(monkeypatch, capsys):
    def missing(*args):
        raise MissingDays("No post for the week of Dec 7–13, 2026.")

    monkeypatch.setattr(send, "read_schedule", lambda: None)
    monkeypatch.setattr(send, "build", missing)
    monkeypatch.setattr(send, "write_post", lambda *a: pytest.fail("write_post ran"))
    opener = FakeOpener()
    env = {**ENV_ON, "GITHUB_ACTIONS": "true"}
    assert send.main(["--week", "2026-12-07"], env=env, client=Client(opener=opener)) is None
    assert opener.requests == []
    out = capsys.readouterr().out
    assert "::notice title=No Skyline post this week::No post for the week of Dec 7–13, 2026." in out
