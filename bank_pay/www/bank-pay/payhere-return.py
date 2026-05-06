import frappe


no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    order_name = (
        frappe.form_dict.get("order_name")
        or frappe.form_dict.get("order_id")
        or frappe.form_dict.get("order")
    )
    if not order_name or not frappe.db.exists("Bank Pay Order", order_name):
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
