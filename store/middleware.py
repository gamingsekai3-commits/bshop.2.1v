from django.utils import translation

from .translations import get_language


class SiteLanguageMiddleware:
    """Tells Django itself which language the visitor picked.

    The storefront translates its own text with the plain `T` dict in
    store/translations.py, so it never needed this. The admin panel is
    different: most of its text ("Home", "Add", "Save", "Log out", the
    breadcrumbs, filters, pagination, action messages...) comes from inside
    Django, which only translates it when a language is switched on for the
    request.

    Django already ships compiled Mongolian translations for the admin, so
    there is nothing to install and no .po files to compile - we just have to
    activate 'mn' or 'en' based on the same `site_lang` cookie the storefront
    language button already sets. One button, both sides of the site.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = get_language(request)          # reads the site_lang cookie
        translation.activate(lang)
        request.LANGUAGE_CODE = lang
        try:
            response = self.get_response(request)
        finally:
            # Always switch back off, otherwise the language could leak into
            # the next request handled by this same worker thread.
            translation.deactivate()
        response.setdefault('Content-Language', lang)
        return response
