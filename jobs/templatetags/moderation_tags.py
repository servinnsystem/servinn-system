from django import template
from servinn_core.moderation import BLOCKED_TERMS, TEXT_FIELDS, MESSAGE
register = template.Library()

@register.simple_tag
def moderation_rules():
    return {'terms': BLOCKED_TERMS, 'fields': sorted(TEXT_FIELDS), 'message': MESSAGE}
