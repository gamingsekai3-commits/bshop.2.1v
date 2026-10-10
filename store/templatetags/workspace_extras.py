from django import template

from store.workspaces import get_workspaces

register = template.Library()


@register.simple_tag(takes_context=True)
def user_workspaces(context):
    """{% user_workspaces as spaces %} -> the sites this user can open.
    Looked up only where a template asks for it (admin / driver headers),
    not on every storefront page."""
    request = context.get('request')
    return get_workspaces(request.user) if request is not None else []
