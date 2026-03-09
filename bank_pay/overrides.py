"""
Override for lms.lms.payments.get_payment_link.

Two-layer interception:
1. override_whitelisted_method hook (if supported by this Frappe version)
2. before_request monkey-patch (guaranteed fallback)
"""

import frappe

_lms_patched = False


def before_request():
    """Monkey-patch LMS get_payment_link before the handler resolves it."""
    global _lms_patched
    if _lms_patched:
        return

    try:
        import lms.lms.payments as lms_payments

        _original = lms_payments.get_payment_link

        @frappe.whitelist(allow_guest=False)
        def patched_get_payment_link(**kwargs):
            doctype = kwargs.get("doctype")
            docname = kwargs.get("docname")
            if doctype == "LMS Course" and docname:
                return "/bank-pay/checkout/" + frappe.utils.cstr(docname)
            return _original(**kwargs)

        lms_payments.get_payment_link = patched_get_payment_link
        _lms_patched = True
    except Exception:
        pass


@frappe.whitelist()
def get_payment_link(**kwargs):
    """Fallback for override_whitelisted_method hook."""
    doctype = kwargs.get("doctype")
    docname = kwargs.get("docname")

    if doctype == "LMS Course":
        return "/bank-pay/checkout/{0}".format(docname)

    from lms.lms.payments import get_payment_link as original_get_payment_link
    return original_get_payment_link(**kwargs)
