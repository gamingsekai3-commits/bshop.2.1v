from django import template
from store.translations import translate_category_name

register = template.Library()


@register.filter
def category_name(name, lang):
    """Usage: {{ cat.name|category_name:LANG }}
    Translates a category's display name based on the current site
    language (LANG comes from the language context processor). The
    underlying `name` used for URLs (e.g. {% url 'category' cat.name %})
    is left untouched so links keep working regardless of language."""
    return translate_category_name(name, lang)


@register.filter
def position_name(name, lang):
    """Usage: {{ employee.employee_profile.position|position_name:LANG }}"""
    from store.translations import translate_position
    return translate_position(name, lang)
