from app.extensions import db


class SiteSettings(db.Model):
    """Singleton row (id=1) holding sitewide settings editable from /admin/settings."""

    __tablename__ = "site_settings"

    id = db.Column(db.Integer, primary_key=True)

    facebook_url = db.Column(db.String(300))
    instagram_url = db.Column(db.String(300))
    tiktok_url = db.Column(db.String(300))
    youtube_url = db.Column(db.String(300))
    linkedin_url = db.Column(db.String(300))

    logo_filename = db.Column(db.String(255))

    # Branding, beyond the primary logo above (2026-09-26) — see docs/BRANDING.md for the full audit
    # of what each of these actually controls. All four are optional references into the Media
    # Library (MediaAsset), picked with the same reusable image_slot()/_media_modal.html picker
    # already used for Home/Services hero images — never a second upload mechanism. Every one of
    # them falls back to the primary logo (or its own static default) when unset, in
    # app/branding.py, so leaving them blank changes nothing visually from today.
    admin_logo_media_id = db.Column(db.Integer, db.ForeignKey("media_assets.id", name="fk_site_settings_admin_logo_media_id"))
    favicon_media_id = db.Column(db.Integer, db.ForeignKey("media_assets.id", name="fk_site_settings_favicon_media_id"))
    email_logo_media_id = db.Column(db.Integer, db.ForeignKey("media_assets.id", name="fk_site_settings_email_logo_media_id"))
    social_logo_media_id = db.Column(db.Integer, db.ForeignKey("media_assets.id", name="fk_site_settings_social_logo_media_id"))

    # Alternate checkout payment methods (2026-09-23). Public information shown to customers at Academy
    # checkout — never a secret. Empty = fall back to app.business_info.CASH_APP_TAG_DEFAULT (same
    # "empty field = built-in default" convention as PageBlock), so this is configurable without code but
    # never required to be set.
    cash_app_tag = db.Column(db.String(60))

    # System & SEO
    ga_measurement_id = db.Column(db.String(40))
    search_console_verification = db.Column(db.String(200))
    block_search_indexing = db.Column(db.Boolean, nullable=False, default=False)

    # Admin Notification Center (2026-09-24) — the recipient for administrative alert emails, configurable
    # from Admin -> Settings -> Notifications. Empty = falls back to business_info.EMAIL (the same
    # "empty field = built-in default" convention as cash_app_tag above), never hardcoded in notify logic.
    notification_recipient_email = db.Column(db.String(200))

    @staticmethod
    def get():
        settings = SiteSettings.query.get(1)
        if not settings:
            settings = SiteSettings(id=1)
            db.session.add(settings)
            db.session.commit()
        return settings
