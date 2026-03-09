import frappe


def get_context(context):
    """Checkout page context — /bank-pay/checkout/<course_name>"""
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=" + frappe.request.path
        raise frappe.Redirect

    # Extract course name from path or query param
    course_name = frappe.form_dict.get("course_name")
    if not course_name:
        path_parts = frappe.request.path.strip("/").split("/")
        course_name = path_parts[2] if len(path_parts) > 2 else None

    if not course_name:
        frappe.throw("Course not specified.", frappe.DoesNotExistError)

    course = frappe.db.get_value(
        "LMS Course",
        course_name,
        ["name", "title", "paid_course", "course_price", "currency", "image"],
        as_dict=True,
    )
    if not course:
        frappe.throw("Course not found.", frappe.DoesNotExistError)

    # Check enrollment
    enrolled = frappe.db.exists(
        "LMS Enrollment", {"member": frappe.session.user, "course": course_name}
    )
    if enrolled:
        context.no_cache = 1
        context.already_enrolled = True
        context.course = course
        return

    # Check existing pending order
    pending_order = frappe.db.get_value(
        "Bank Pay Order",
        {"student": frappe.session.user, "course": course_name, "status": "Pending"},
        ["name", "payment_method", "receipt_image"],
        as_dict=True,
    )

    settings = frappe.get_single("Bank Pay Settings")

    context.no_cache = 1
    context.course = course
    context.pending_order = pending_order
    context.enable_bank_transfer = bool(settings.enable_bank_transfer)
    context.enable_payhere = bool(settings.enable_payhere)
    context.bank_name = settings.bank_name or ""
    context.account_name = settings.account_name or ""
    context.account_number = settings.account_number or ""
    context.branch = settings.branch or ""
    context.bank_instructions = settings.bank_instructions or ""
