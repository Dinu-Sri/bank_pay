import frappe
from urllib.parse import unquote


no_cache = 1


def _extract_order_name():
    candidates = [
        frappe.form_dict.get("order_name"),
        frappe.form_dict.get("order_id"),
        frappe.form_dict.get("order"),
    ]

    path = getattr(getattr(frappe, "request", None), "path", "") or ""
    if "/bank-pay/payment-failed/" in path:
        candidates.append(path.rsplit("/", 1)[-1])

    for value in candidates:
        if not value:
            continue
        cleaned = unquote(str(value)).strip()
        cleaned = cleaned.split("?", 1)[0].split("&", 1)[0]
        if cleaned:
            return cleaned

    return None


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    order_name = _extract_order_name()
    if not order_name or not frappe.db.exists("Bank Pay Order", order_name):
        frappe.log_error(
            message=(
                f"Payment failed page order not found. resolved_order={order_name}, "
                f"form_dict={dict(frappe.form_dict)}, "
                f"path={getattr(getattr(frappe, 'request', None), 'path', '')}"
            ),
            title="Bank Pay - Payment Failed Order Lookup",
        )
        context.order = None
        return

    order = frappe.db.get_value(
        "Bank Pay Order",
        order_name,
        ["name", "student", "course", "course_title", "status", "amount", "currency"],
        as_dict=True,
    )

    if order.student != frappe.session.user:
        frappe.log_error(
            message=(
                f"Payment failed page user mismatch: order={order_name}, "
                f"order.student={order.student}, session.user={frappe.session.user}"
            ),
            title="Bank Pay - Payment Failed User Mismatch",
        )

    context.order = order
    context.support_email = "edu@sltaxsolution.lk"
    context.support_whatsapp = "+94 77 400 4879"
    context.support_phone = "+94 34 221 5393"
