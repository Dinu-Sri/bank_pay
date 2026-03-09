"""
Bank Pay API — shared endpoints for both Bank Transfer and PayHere flows.
All methods are whitelisted and permission-checked.
"""

import frappe


@frappe.whitelist()
def get_checkout_context(course_name):
    """Return everything the checkout page needs: course info, settings, existing orders."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Please log in first.", frappe.AuthenticationError)

    course = frappe.db.get_value(
        "LMS Course",
        course_name,
        ["name", "title", "paid_course", "course_price", "currency", "image"],
        as_dict=True,
    )
    if not course:
        frappe.throw("Course not found.", frappe.DoesNotExistError)

    if not course.paid_course:
        frappe.throw("This course is free. No payment needed.")

    # Check if already enrolled
    enrolled = frappe.db.exists(
        "LMS Enrollment", {"member": user, "course": course_name}
    )
    if enrolled:
        frappe.throw("You are already enrolled in this course.")

    # Check for existing pending order
    pending_order = frappe.db.get_value(
        "Bank Pay Order",
        {"student": user, "course": course_name, "status": "Pending"},
        ["name", "payment_method"],
        as_dict=True,
    )

    settings = frappe.get_single("Bank Pay Settings")

    return {
        "course": course,
        "pending_order": pending_order,
        "enable_bank_transfer": bool(settings.enable_bank_transfer),
        "enable_payhere": bool(settings.enable_payhere),
        "bank_details": {
            "bank_name": settings.bank_name,
            "account_name": settings.account_name,
            "account_number": settings.account_number,
            "branch": settings.branch,
            "instructions": settings.bank_instructions,
        }
        if settings.enable_bank_transfer
        else None,
    }


@frappe.whitelist()
def create_order(course_name, payment_method):
    """Create a new Bank Pay Order. Returns the order name."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Please log in first.", frappe.AuthenticationError)

    if payment_method not in ("Bank Transfer", "PayHere"):
        frappe.throw("Invalid payment method.")

    course = frappe.db.get_value(
        "LMS Course",
        course_name,
        ["name", "title", "paid_course", "course_price", "currency"],
        as_dict=True,
    )
    if not course or not course.paid_course:
        frappe.throw("Invalid course or course is free.")

    # Check existing enrollment
    if frappe.db.exists("LMS Enrollment", {"member": user, "course": course_name}):
        frappe.throw("You are already enrolled in this course.")

    # Check existing pending order for same method
    existing = frappe.db.exists(
        "Bank Pay Order",
        {
            "student": user,
            "course": course_name,
            "payment_method": payment_method,
            "status": "Pending",
        },
    )
    if existing:
        return {"order": existing, "existing": True}

    order = frappe.get_doc(
        {
            "doctype": "Bank Pay Order",
            "student": user,
            "course": course_name,
            "amount": course.course_price,
            "currency": course.currency or "LKR",
            "payment_method": payment_method,
            "status": "Pending",
        }
    )
    order.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"order": order.name, "existing": False}


@frappe.whitelist()
def upload_receipt(order_name, receipt_file, bank_reference=None, transfer_date=None):
    """Attach receipt image to a bank transfer order."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Please log in first.", frappe.AuthenticationError)

    order = frappe.get_doc("Bank Pay Order", order_name)

    if order.student != user:
        frappe.throw("This order does not belong to you.", frappe.PermissionError)

    if order.payment_method != "Bank Transfer":
        frappe.throw("Receipt upload is only for bank transfer orders.")

    if order.status != "Pending":
        frappe.throw("This order is no longer pending.")

    order.receipt_image = receipt_file
    if bank_reference:
        order.bank_reference = bank_reference
    if transfer_date:
        order.transfer_date = transfer_date

    order.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def get_order(order_name):
    """Get order details (student can only see own orders)."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Please log in first.", frappe.AuthenticationError)

    order = frappe.get_doc("Bank Pay Order", order_name)

    is_admin = "System Manager" in frappe.get_roles(user)
    if order.student != user and not is_admin:
        frappe.throw("You don't have permission to view this order.", frappe.PermissionError)

    return {
        "name": order.name,
        "student": order.student,
        "student_name": order.student_name,
        "course": order.course,
        "course_title": order.course_title,
        "amount": order.amount,
        "currency": order.currency,
        "payment_method": order.payment_method,
        "status": order.status,
        "receipt_image": order.receipt_image,
        "bank_reference": order.bank_reference,
        "transfer_date": order.transfer_date,
        "admin_note": order.admin_note if is_admin else None,
        "creation": order.creation,
    }


@frappe.whitelist()
def get_my_orders():
    """Get all orders for the current student."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Please log in first.", frappe.AuthenticationError)

    orders = frappe.get_all(
        "Bank Pay Order",
        filters={"student": user},
        fields=[
            "name",
            "course",
            "course_title",
            "amount",
            "currency",
            "payment_method",
            "status",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=50,
    )

    return orders
