import base64
import os
import re
import secrets
import shutil

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {
    "video": {"mp4", "webm", "mov", "m4v"},
    "image": {"jpg", "jpeg", "png", "webp"},
    "audio": {"mp3", "m4a", "wav", "ogg"},
    "document": {"pdf", "doc", "docx", "txt", "rtf", "xls", "xlsx", "jpg", "jpeg", "png", "webp"},
}


def _ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def save_course_media(file_storage, kind):
    """Save an uploaded file under COURSE_MEDIA_DIR/<kind>s/ with a random
    filename. Returns the stored filename (not the full path) or None if
    no file was provided."""
    if not file_storage or not file_storage.filename:
        return None

    ext = _ext(secure_filename(file_storage.filename))
    if ext not in ALLOWED_EXTENSIONS[kind]:
        raise ValueError(f"Unsupported {kind} file type: .{ext}")

    subdir = f"{kind}s"
    target_dir = os.path.join(current_app.config["COURSE_MEDIA_DIR"], subdir)
    os.makedirs(target_dir, exist_ok=True)

    stored_name = f"{secrets.token_hex(16)}.{ext}"
    file_storage.save(os.path.join(target_dir, stored_name))
    return f"{subdir}/{stored_name}"


def delete_course_media(stored_path):
    if not stored_path:
        return
    full_path = os.path.join(current_app.config["COURSE_MEDIA_DIR"], stored_path)
    try:
        os.remove(full_path)
    except OSError:
        pass


def course_media_full_path(stored_path):
    return os.path.join(current_app.config["COURSE_MEDIA_DIR"], stored_path)


DATA_URL_RE = re.compile(r"^data:image/(png|jpeg);base64,(.+)$")


def save_data_url_image(data_url, kind="image"):
    """Decodes a `data:image/png;base64,...` string (e.g. from a signature
    canvas) and saves it the same way as any other upload. Returns the
    stored path, or None if `data_url` isn't a recognized image data URL."""
    match = DATA_URL_RE.match((data_url or "").strip())
    if not match:
        return None
    image_format, encoded = match.groups()
    ext = "jpg" if image_format == "jpeg" else image_format
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error):
        return None
    if not raw or len(raw) > 5 * 1024 * 1024:  # 5MB sanity cap
        return None

    subdir = f"{kind}s"
    target_dir = os.path.join(current_app.config["COURSE_MEDIA_DIR"], subdir)
    os.makedirs(target_dir, exist_ok=True)
    stored_name = f"{secrets.token_hex(16)}.{ext}"
    with open(os.path.join(target_dir, stored_name), "wb") as fh:
        fh.write(raw)
    return f"{subdir}/{stored_name}"


def duplicate_course_media(stored_path):
    """Copies an already-uploaded file to a new random filename in the same
    subdir and returns the new stored path, or None if the source is missing.
    Used when duplicating content (e.g. a Case Simulation) so the copy owns
    an independent file — deleting one copy's document later must never
    remove a file the other copy still references."""
    if not stored_path:
        return None
    full_src = os.path.join(current_app.config["COURSE_MEDIA_DIR"], stored_path)
    if not os.path.isfile(full_src):
        return None

    subdir = stored_path.split("/", 1)[0]
    ext = _ext(stored_path)
    target_dir = os.path.join(current_app.config["COURSE_MEDIA_DIR"], subdir)
    os.makedirs(target_dir, exist_ok=True)

    stored_name = f"{secrets.token_hex(16)}.{ext}"
    shutil.copy2(full_src, os.path.join(target_dir, stored_name))
    return f"{subdir}/{stored_name}"
