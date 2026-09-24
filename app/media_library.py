"""Media Library: one place to upload, reuse and replace the images used across the
public site. Pages/services reference a MediaAsset by id through named image slots,
so swapping a photo never needs a code change and replacing an asset updates every
place that uses it.

Files are stored with the existing secure upload helper (random filenames, image
extension allow-list) and are served publicly, because they are site imagery.
Client documents and course media use separate, access-controlled routes.
"""

import os

from flask import current_app, url_for
from PIL import Image

from app.extensions import db
from app.models import MediaAsset, Service, ServiceCategory
from app.uploads import course_media_full_path, delete_course_media, save_course_media

THUMB_WIDTHS = (480, 960, 1600)
SLOT_COLUMNS = ("hero_image_id", "hero_mobile_image_id", "card_image_id", "overview_image_id", "social_image_id")
MIME_BY_EXT = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


MAX_IMAGE_BYTES = 15 * 1024 * 1024


def _save_verified_image(file_storage):
    """Store the upload, then confirm it really is an image of acceptable size
    (the extension allow-list alone is not proof). Removes the file on failure."""
    stored = save_course_media(file_storage, "image")
    if not stored:
        return None
    full = course_media_full_path(stored)
    try:
        if os.path.getsize(full) > MAX_IMAGE_BYTES:
            raise ValueError("Image is larger than 15 MB.")
        with Image.open(full) as img:
            img.verify()
    except ValueError:
        delete_course_media(stored)
        raise
    except Exception:
        delete_course_media(stored)
        raise ValueError("That file is not a valid image.")
    return stored


def _probe(stored_path):
    try:
        with Image.open(course_media_full_path(stored_path)) as img:
            return img.width, img.height
    except Exception:
        return None, None


def create_asset(file_storage, title=None, alt_en=None, alt_es=None, tag=None):
    """Saves an uploaded image and returns the new MediaAsset (not committed)."""
    stored = _save_verified_image(file_storage)
    if not stored:
        return None
    ext = stored.rsplit(".", 1)[-1].lower()
    width, height = _probe(stored)
    asset = MediaAsset(
        stored_path=stored,
        original_filename=(file_storage.filename or stored)[:255],
        title=(title or "").strip() or None,
        alt_en=(alt_en or "").strip() or None,
        alt_es=(alt_es or "").strip() or None,
        tag=(tag or "").strip() or None,
        mime_type=MIME_BY_EXT.get(ext),
        size_bytes=os.path.getsize(course_media_full_path(stored)),
        width=width,
        height=height,
    )
    db.session.add(asset)
    return asset


def replace_asset_file(asset, file_storage):
    """Swap the picture behind an existing asset. Every slot that uses the asset
    picks up the new image; ids and alt text stay."""
    new_stored = _save_verified_image(file_storage)
    if not new_stored:
        return False
    old = asset.stored_path
    asset.stored_path = new_stored
    asset.original_filename = (file_storage.filename or new_stored)[:255]
    ext = new_stored.rsplit(".", 1)[-1].lower()
    asset.mime_type = MIME_BY_EXT.get(ext)
    asset.size_bytes = os.path.getsize(course_media_full_path(new_stored))
    asset.width, asset.height = _probe(new_stored)
    _drop_thumbs(asset.id)
    delete_course_media(old)
    return True


def _thumb_dir():
    path = os.path.join(current_app.config["COURSE_MEDIA_DIR"], "thumbs")
    os.makedirs(path, exist_ok=True)
    return path


def _drop_thumbs(asset_id):
    directory = _thumb_dir()
    for name in os.listdir(directory):
        if name.startswith(f"{asset_id}_"):
            try:
                os.remove(os.path.join(directory, name))
            except OSError:
                pass


def thumbnail_path(asset, width):
    """Path of a cached, downscaled WebP of the asset (never upscales)."""
    if width not in THUMB_WIDTHS:
        return None
    source = course_media_full_path(asset.stored_path)
    if not os.path.isfile(source):
        return None
    target = os.path.join(_thumb_dir(), f"{asset.id}_{width}_{asset.stored_path.rsplit('/', 1)[-1].split('.')[0]}.webp")
    if os.path.isfile(target):
        return target
    with Image.open(source) as img:
        if img.width <= width:
            return source
        img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
        ratio = width / img.width
        img = img.resize((width, max(1, int(img.height * ratio))), Image.LANCZOS)
        img.save(target, "WEBP", quality=82, method=4)
    return target


def usages(asset_id):
    """Every place an asset is used: [(label, edit_url)]."""
    found = []
    for model, label_attr, endpoint in ((ServiceCategory, "title_en", "admin.service_category_edit"), (Service, "title_en", "admin.service_edit")):
        for column in SLOT_COLUMNS:
            for row in model.query.filter(getattr(model, column) == asset_id).all():
                key = {"admin.service_category_edit": "category_id", "admin.service_edit": "service_id"}[endpoint]
                found.append((f"{'Category' if model is ServiceCategory else 'Service'}: {getattr(row, label_attr)} ({column.replace('_image_id', '').replace('_', ' ')})", url_for(endpoint, **{key: row.id})))
    from app.site_content import site_image_usages

    found += site_image_usages(asset_id)
    return found


def delete_asset(asset):
    """Delete only when nothing references the asset. Returns (ok, message)."""
    used = usages(asset.id)
    if used:
        return False, f"Still used in {len(used)} place(s); replace those first."
    delete_course_media(asset.stored_path)
    _drop_thumbs(asset.id)
    db.session.delete(asset)
    return True, "Deleted."


def media_url(asset, width=None):
    """Public URL for an asset (or None). `width` picks a cached downscale."""
    if not asset:
        return None
    name = asset.original_filename.rsplit(".", 1)[0].lower().replace(" ", "-")[:60] or "image"
    ext = "webp" if width else asset.stored_path.rsplit(".", 1)[-1]
    if width:
        return url_for("media_asset", asset_id=asset.id, name=f"{name}.{ext}", w=width, v=asset.size_bytes or 0)
    return url_for("media_asset", asset_id=asset.id, name=f"{name}.{ext}", v=asset.size_bytes or 0)
