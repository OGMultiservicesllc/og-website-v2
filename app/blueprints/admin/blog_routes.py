import re
from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for

from app.auth import admin_required, validate_csrf
from app.blueprints.admin.routes import admin_bp
from app.extensions import db
from app.models import BLOG_CATEGORIES, BlogMedia, BlogPost
from app.uploads import delete_course_media, save_course_media


def _slugify(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "post"


def _unique_slug(base_slug, post_id=None):
    slug = base_slug
    n = 2
    while True:
        query = BlogPost.query.filter_by(slug=slug)
        if post_id:
            query = query.filter(BlogPost.id != post_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{n}"
        n += 1


def _next_sort_order(items):
    return (max((i.sort_order for i in items), default=0)) + 1


def _swap_sort_order(siblings, item, direction):
    index = siblings.index(item)
    if direction == "up" and index > 0:
        other = siblings[index - 1]
    elif direction == "down" and index < len(siblings) - 1:
        other = siblings[index + 1]
    else:
        return
    item.sort_order, other.sort_order = other.sort_order, item.sort_order
    db.session.commit()


@admin_bp.route("/blog")
@admin_required
def blog_list():
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template("admin/blog_list.html", posts=posts)


@admin_bp.route("/blog/new", methods=["GET", "POST"])
@admin_required
def blog_new():
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        title_en = request.form.get("title_en", "").strip()
        title_es = request.form.get("title_es", "").strip()
        category = request.form.get("category", "").strip()
        if not title_en or not title_es:
            flash("Title (EN and ES) is required.", "error")
            return render_template("admin/blog_form.html", post=None, categories=BLOG_CATEGORIES)
        if category not in BLOG_CATEGORIES:
            flash("Choose a category.", "error")
            return render_template("admin/blog_form.html", post=None, categories=BLOG_CATEGORIES)

        cover = request.files.get("cover_image")
        cover_filename = None
        if cover and cover.filename:
            try:
                cover_filename = save_course_media(cover, "image")
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template("admin/blog_form.html", post=None, categories=BLOG_CATEGORIES)

        is_published = request.form.get("is_published") == "on"
        post = BlogPost(
            slug=_unique_slug(_slugify(title_en)),
            title_en=title_en,
            title_es=title_es,
            excerpt_en=request.form.get("excerpt_en", "").strip(),
            excerpt_es=request.form.get("excerpt_es", "").strip(),
            content_en=request.form.get("content_en", "").strip(),
            content_es=request.form.get("content_es", "").strip(),
            category=category,
            author_name=request.form.get("author_name", "").strip() or None,
            cover_image=cover_filename,
            is_published=is_published,
            published_at=datetime.utcnow() if is_published else None,
        )
        db.session.add(post)
        db.session.commit()
        flash("Post created.", "success")
        return redirect(url_for("admin.blog_edit", post_id=post.id))

    return render_template("admin/blog_form.html", post=None, categories=BLOG_CATEGORIES)


@admin_bp.route("/blog/<int:post_id>/edit", methods=["GET", "POST"])
@admin_required
def blog_edit(post_id):
    post = BlogPost.query.get_or_404(post_id)

    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        title_en = request.form.get("title_en", "").strip()
        title_es = request.form.get("title_es", "").strip()
        category = request.form.get("category", "").strip()
        if not title_en or not title_es:
            flash("Title (EN and ES) is required.", "error")
            return render_template("admin/blog_form.html", post=post, categories=BLOG_CATEGORIES)
        if category not in BLOG_CATEGORIES:
            flash("Choose a category.", "error")
            return render_template("admin/blog_form.html", post=post, categories=BLOG_CATEGORIES)

        cover = request.files.get("cover_image")
        if cover and cover.filename:
            try:
                new_cover = save_course_media(cover, "image")
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template("admin/blog_form.html", post=post, categories=BLOG_CATEGORIES)
            if post.cover_image:
                delete_course_media(post.cover_image)
            post.cover_image = new_cover

        was_published = post.is_published
        post.title_en = title_en
        post.title_es = title_es
        post.excerpt_en = request.form.get("excerpt_en", "").strip()
        post.excerpt_es = request.form.get("excerpt_es", "").strip()
        post.content_en = request.form.get("content_en", "").strip()
        post.content_es = request.form.get("content_es", "").strip()
        post.category = category
        post.author_name = request.form.get("author_name", "").strip() or None
        post.is_published = request.form.get("is_published") == "on"
        if post.is_published and not was_published:
            post.published_at = datetime.utcnow()
        db.session.commit()
        flash("Post updated.", "success")
        return redirect(url_for("admin.blog_edit", post_id=post.id))

    return render_template("admin/blog_form.html", post=post, categories=BLOG_CATEGORIES)


@admin_bp.route("/blog/<int:post_id>/cover/delete", methods=["POST"])
@admin_required
def blog_cover_delete(post_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    post = BlogPost.query.get_or_404(post_id)
    if post.cover_image:
        delete_course_media(post.cover_image)
        post.cover_image = None
        db.session.commit()
        flash("Cover image removed.", "success")
    return redirect(url_for("admin.blog_edit", post_id=post.id))


@admin_bp.route("/blog/<int:post_id>/delete", methods=["POST"])
@admin_required
def blog_delete(post_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    post = BlogPost.query.get_or_404(post_id)

    if post.cover_image:
        delete_course_media(post.cover_image)
    for m in post.media:
        delete_course_media(m.filename)

    db.session.delete(post)
    db.session.commit()
    flash("Post deleted.", "success")
    return redirect(url_for("admin.blog_list"))


@admin_bp.route("/blog/<int:post_id>/media/new", methods=["POST"])
@admin_required
def blog_media_new(post_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    post = BlogPost.query.get_or_404(post_id)

    media_type = request.form.get("media_type", "image")
    if media_type not in ("image", "audio", "video"):
        abort(400)

    uploaded = request.files.get("file")
    external_url = request.form.get("external_url", "").strip()
    filename = None

    if uploaded and uploaded.filename:
        try:
            filename = save_course_media(uploaded, media_type)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.blog_edit", post_id=post.id))
    elif not external_url:
        flash("Provide a file or a URL.", "error")
        return redirect(url_for("admin.blog_edit", post_id=post.id))

    media = BlogMedia(
        post_id=post.id,
        media_type=media_type,
        filename=filename,
        external_url=external_url or None,
        caption_en=request.form.get("caption_en", "").strip() or None,
        caption_es=request.form.get("caption_es", "").strip() or None,
        sort_order=_next_sort_order(post.media),
    )
    db.session.add(media)
    db.session.commit()
    flash("Media added.", "success")
    return redirect(url_for("admin.blog_edit", post_id=post.id))


@admin_bp.route("/blog/media/<int:media_id>/delete", methods=["POST"])
@admin_required
def blog_media_delete(media_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    media = BlogMedia.query.get_or_404(media_id)
    post_id = media.post_id
    delete_course_media(media.filename)
    db.session.delete(media)
    db.session.commit()
    flash("Media removed.", "success")
    return redirect(url_for("admin.blog_edit", post_id=post_id))


@admin_bp.route("/blog/media/<int:media_id>/move", methods=["POST"])
@admin_required
def blog_media_move(media_id):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    media = BlogMedia.query.get_or_404(media_id)
    direction = request.form.get("direction")
    siblings = list(BlogMedia.query.filter_by(post_id=media.post_id).order_by(BlogMedia.sort_order).all())
    _swap_sort_order(siblings, media, direction)
    return redirect(url_for("admin.blog_edit", post_id=media.post_id))
