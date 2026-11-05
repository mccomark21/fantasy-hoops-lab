"""The command python -m fantasyhoops.bluesky: the post files of bluesky/post.py (#237). It writes the files of post.py."""

from fantasyhoops.bluesky.post import main
from fantasyhoops.core.console import use_utf8_output

if __name__ == "__main__":
    use_utf8_output()
    main()
