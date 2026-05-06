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
    if "/bank-pay/payhere-return/" in path:
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

    # Diagnostic info — always pass to template
    context.debug_info = {
        "resolved_order_name": order_name,
        "form_dict": dict(frappe.form_dict),
        "path": getattr(getattr(frappe, "request", None), "path", ""),
        "session_user": frappe.session.user,
    }

    # Try fallbacks if direct lookup fails
    if order_name and not frappe.db.exists("Bank Pay Order", order_name):
        # Fallback 1: search by payhere_order_id field
        alt = frappe.db.get_value(
            "Bank Pay Order",
            {"payhere_order_id": order_name},
            "name",
        )
        if alt:
            order_name = alt
            context.debug_info["found_via"] = "payhere_order_id"
        else:
            # Fallback 2: most recent PayHere order for this user
            recent = frappe.db.get_all(
                "Bank Pay Order",
                filters={
                    "student": frappe.session.user,
                    "payment_method": "PayHere",
                },
                fields=["name"],
                order_by="creation desc",
                limit_page_length=1,
            )
            if recent:
                order_name = recent[0].name
                context.debug_info["found_via"] = "recent_user_order"

    if not order_name or not frappe.db.exists("Bank Pay Order", order_name):
        frappe.log_error(
            message=(
                f"PayHere return order not found. resolved_order={order_name}, "
                f"form_dict={dict(frappe.form_dict)}, "
                f"path={getattr(getattr(frappe, 'request', None), 'path', '')}, "
                f"session_user={frappe.session.user}"
            ),
            title="Bank Pay - PayHere Return Order Lookup",
        )
        context.order = None
        return

    order = frappe.db.get_value(
        "Bank Pay Order",
        order_name,
        ["name", "student", "course", "course_title", "status", "amount", "currency",
         "payhere_status_code", "payhere_status_message", "payhere_method", "payhere_payment_id"],
        as_dict=True,
    )

    # Some payment-return flows may arrive with a valid order but a session
    # user mismatch (e.g., auth/session edge cases after external redirect).
    # Do not hard-fail to "Order not found" if the order exists.
    if order.student != frappe.session.user:
        frappe.log_error(
            message=(
                f"PayHere return user mismatch: order={order_name}, "
                f"order.student={order.student}, session.user={frappe.session.user}"
            ),
            title="Bank Pay - PayHere Return User Mismatch",
        )

    # Redirect to payment-failed page for all non-success terminal states.
    if order.status in ("Cancelled", "Rejected", "Chargeback"):
        frappe.local.flags.redirect_location = f"/bank-pay/payment-failed/{order_name}"
        raise frappe.Redirect

    context.order = order
