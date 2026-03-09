import frappe


no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/bank-pay/my-payments"
        raise frappe.Redirect

    orders = frappe.get_all(
        "Bank Pay Order",
        filters={"student": frappe.session.user},
        fields=[
            "name",
            "course",
            "course_title",
            "amount",
            "currency",
            "payment_method",
            "status",
            "receipt_image",
            "admin_note",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=50,
    )

    context.orders = orders
