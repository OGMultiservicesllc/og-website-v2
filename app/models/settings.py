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

    # Alternate checkout payment methods (2026-09-23). Public information shown to customers at Academy
    # checkout — never a secret. Empty = fall back to app.business_info.CASH_APP_TAG_DEFAULT (same
    # "empty field = built-in default" convention as PageBlock), so this is configurable without code but
    # never required to be set.
    cash_app_tag = db.Column(db.String(60))

    # System & SEO
    ga_measurement_id = db.Column(db.String(40))
    search_console_verification = db.Column(db.String(200))
    block_search_indexing = db.Column(db.Boolean, nullable=False, default=False)

    @staticmethod
    def get():
        settings = SiteSettings.query.get(1)
        if not settings:
            settings = SiteSettings(id=1)
            db.session.add(settings)
            db.session.commit()
        return settings
