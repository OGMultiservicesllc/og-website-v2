import re


def to_embed_url(url):
    if not url:
        return url

    youtube_match = re.search(r"(?:youtu\.be/|youtube\.com/watch\?v=|youtube\.com/embed/)([\w-]+)", url)
    if youtube_match:
        return f"https://www.youtube.com/embed/{youtube_match.group(1)}"

    vimeo_match = re.search(r"vimeo\.com/(\d+)", url)
    if vimeo_match:
        return f"https://player.vimeo.com/video/{vimeo_match.group(1)}"

    return url
