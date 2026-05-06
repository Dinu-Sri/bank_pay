"""
Override for lms.lms.payments.get_payment_link.

Lets the original LMS function create the LMS Payment record (so it shows
in LMS Settings → Transactions), then returns our checkout URL instead of
the payment gateway URL.
"""

import frappe
from frappe.utils import cstr

_lms_patched = False


def _bank_pay_get_payment_link(_original, **kwargs):
    """Create LMS Payment via original logic, then redirect to Bank Pay."""
    doctype = kwargs.get("doctype")
    docname = kwargs.get("docname")

    if doctype != "LMS Course" or not docname:
        return _original(**kwargs)

    # Let the original function run — it will:
    # 1. Call record_payment() → creates LMS Payment doc
    # 2. Try to get payment gateway controller → this will fail
    # We catch the gateway error and return our URL instead.
    try:
        result = _original(**kwargs)
        # If it somehow succeeds (gateway configured), still redirect to us
        return "/bank-pay/checkout/" + cstr(docname)
    except Exception:
        # Expected: gateway not configured error after LMS Payment is created
        # Check if LMS Payment was created before the error
        lms_payment = frappe.db.get_value(
            "LMS Payment",
            {
                "member": frappe.session.user,
                "payment_for_document_type": "LMS Course",
                "payment_for_document": docname,
                "payment_received": 0,
            },
            "name",
        )
        if not lms_payment:
            # record_payment itself failed (e.g. address validation).
            # Create a minimal LMS Payment record ourselves.
            try:
                payment = frappe.get_doc({
                    "doctype": "LMS Payment",
                    "member": frappe.session.user,
                    "billing_name": frappe.session.user,
                    "amount": kwargs.get("amount", 0),
                    "currency": kwargs.get("currency", "LKR"),
                    "payment_for_document_type": doctype,
                    "payment_for_document": docname,
                })
                payment.flags.ignore_mandatory = True
                payment.insert(ignore_permissions=True)
                frappe.db.commit()
            except Exception:
                frappe.log_error("Bank Pay: fallback LMS Payment creation failed")

        return "/bank-pay/checkout/" + cstr(docname)


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
            return _bank_pay_get_payment_link(_original, **kwargs)

        lms_payments.get_payment_link = patched_get_payment_link
        _lms_patched = True
    except Exception:
        pass


@frappe.whitelist()
def get_payment_link(**kwargs):
    """Fallback for override_whitelisted_method hook."""
    from lms.lms.payments import get_payment_link as original
    return _bank_pay_get_payment_link(original, **kwargs)
