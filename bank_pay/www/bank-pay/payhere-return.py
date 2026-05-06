import frappe


no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    order_name = frappe.form_dict.get("order_name")
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

    if order.student != frappe.session.user:
        context.order = None
        return

    # Redirect to payment-failed page if order is cancelled
    if order.status == "Cancelled":
        frappe.local.flags.redirect_location = f"/bank-pay/payment-failed/{order_name}"
        raise frappe.Redirect

    context.order = order
