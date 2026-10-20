"""Publish output/draft/draft_board.html to GitHub Pages at /draft/, with the pages of the other playoff windows."""
from fantasyhoops.core import publish as site
from fantasyhoops.core.common import ROOT
from fantasyhoops.draft import OUT

URL = site.URL + "draft/"


def publish(repo, board, others=()):
    """Push the board to /draft/index.html on gh-pages in origin. The pages of the other tools stay.

    others: more pages (the other playoff windows). Each one goes to /draft/ with its own file name.
    """
    if not board.exists():
        raise FileNotFoundError(f"{board} does not exist. Run python -m fantasyhoops.draft.board first.")
    site.publish(repo, "draft", board, others)


def main():
    publish(ROOT, OUT / "draft_board.html", sorted(OUT.glob("draft_board_*.html")))
    print(f"Published the draft board to {URL}. GitHub can take a few minutes to show the new board.")


if __name__ == "__main__":
    main()
