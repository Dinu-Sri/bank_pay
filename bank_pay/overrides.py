"""
Override for lms.lms.payments.get_payment_link.

When a student clicks "Proceed to Payment" on the LMS Billing page,
this intercepts the call and redirects to our Bank Pay checkout page.
"""

import frappe


@frappe.whitelist()
def get_payment_link(**kwargs):
    """Redirect to Bank Pay checkout instead of LMS default payment gateway."""
    doctype = kwargs.get("doctype")
    docname = kwargs.get("docname")

    if doctype == "LMS Course":
        return "/bank-pay/checkout/{0}".format(docname)

    # Fallback: if not a course, try calling the original LMS function
    from lms.lms.payments import get_payment_link as original_get_payment_link
    return original_get_payment_link(**kwargs)
