"""
PayHere Sri Lanka payment gateway integration.
Docs: https://support.payhere.lk/api-&-mobile-sdk/payhere-checkout

Two flows:
1. initiate_payment() — called by frontend to get PayHere form data + hash
2. notify()           — server-to-server callback from PayHere after payment
"""

import hashlib

import frappe


PAYHERE_LIVE_URL = "https://www.payhere.lk/pay/checkout"
PAYHERE_SANDBOX_URL = "https://sandbox.payhere.lk/pay/checkout"


@frappe.whitelist()
def initiate_payment(order_name):
    """Generate PayHere checkout form data with HMAC hash."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Please log in first.", frappe.AuthenticationError)

    order = frappe.get_doc("Bank Pay Order", order_name)

    if order.student != user:
        frappe.throw("This order does not belong to you.", frappe.PermissionError)

    if order.payment_method != "PayHere":
        frappe.throw("This order is not a PayHere order.")

    if order.status != "Pending":
        frappe.throw("This order is no longer pending.")

    settings = frappe.get_single("Bank Pay Settings")

    if not settings.enable_payhere:
        frappe.throw("PayHere payments are not enabled.")

    if not settings.payhere_merchant_id or not settings.payhere_secret:
        frappe.throw("PayHere credentials not configured.")

    merchant_id = settings.payhere_merchant_id
    merchant_secret = settings.get_password("payhere_secret")
    currency = settings.payhere_currency or "LKR"

    site_url = frappe.utils.get_url()
    amount_formatted = f"{float(order.amount):.2f}"

    # PayHere hash: merchant_id + order_id + amount + currency + md5(secret)
    secret_hash = (
        hashlib.md5(merchant_secret.encode("utf-8")).hexdigest().upper()
    )
    raw = merchant_id + order.name + amount_formatted + currency + secret_hash
    pay_hash = hashlib.md5(raw.encode("utf-8")).hexdigest().upper()

    student_name = order.student_name or frappe.db.get_value(
        "User", user, "full_name"
    )
    first_name = student_name.split(" ")[0] if student_name else ""
    last_name = " ".join(student_name.split(" ")[1:]) if student_name else ""
    email = user

    checkout_url = PAYHERE_SANDBOX_URL if settings.payhere_sandbox else PAYHERE_LIVE_URL

    return {
        "checkout_url": checkout_url,
        "form_data": {
            "merchant_id": merchant_id,
            "return_url": f"{site_url}/bank-pay/payhere-return/{order.name}",
            "cancel_url": f"{site_url}/bank-pay/checkout/{order.course}",
            "notify_url": f"{site_url}/api/method/bank_pay.payhere.notify",
            "order_id": order.name,
            "items": order.course_title or order.course,
            "currency": currency,
            "amount": amount_formatted,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": "",
            "address": "",
            "city": "",
            "country": "Sri Lanka",
            "hash": pay_hash,
        },
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def notify(**kwargs):
    """
    Server-to-server callback from PayHere.
    PayHere POSTs: merchant_id, order_id, payhere_amount, payhere_currency,
                   status_code, md5sig, payment_id, status_message, method, etc.
    status_code: 2 = success, 0 = pending, -1 = canceled, -2 = failed, -3 = chargeback
    """
    form = frappe.form_dict

    order_id = form.get("order_id", "")
    payment_id = form.get("payment_id", "")
    payhere_amount = form.get("payhere_amount", "")
    payhere_currency = form.get("payhere_currency", "")
    status_code = form.get("status_code", "")
    merchant_id = form.get("merchant_id", "")
    md5sig = form.get("md5sig", "")
    status_message = form.get("status_message", "")
    payment_method = form.get("method", "")

    if not order_id or not frappe.db.exists("Bank Pay Order", order_id):
        frappe.log_error(
            message=f"PayHere notify: invalid order_id={order_id}",
            title="Bank Pay - PayHere Notify",
        )
        return

    settings = frappe.get_single("Bank Pay Settings")
    merchant_secret = settings.get_password("payhere_secret")

    # Verify signature
    secret_hash = (
        hashlib.md5(merchant_secret.encode("utf-8")).hexdigest().upper()
    )
    raw = (
        merchant_id
        + order_id
        + payhere_amount
        + payhere_currency
        + status_code
        + secret_hash
    )
    expected_sig = hashlib.md5(raw.encode("utf-8")).hexdigest().upper()

    if md5sig.upper() != expected_sig:
        frappe.log_error(
            message=f"PayHere notify: signature mismatch for order={order_id}",
            title="Bank Pay - PayHere Signature Fail",
        )
        return

    order = frappe.get_doc("Bank Pay Order", order_id)
    order.payhere_payment_id = payment_id
    order.payhere_status_code = status_code
    order.payhere_status_message = status_message
    order.payhere_method = payment_method
    order.payhere_order_id = form.get("order_id", "")

    # Set status based on PayHere status code
    if str(status_code) == "2":
        # Payment successful
        order.status = "Paid"
    elif str(status_code) == "-1":
        # Customer canceled the payment
        order.status = "Cancelled"
        frappe.log_error(
            message=f"Order {order_id}: Payment cancelled by customer. Message: {status_message}",
            title="Bank Pay - PayHere Cancelled",
        )
    elif str(status_code) == "-2":
        # Payment failed
        order.status = "Rejected"
        frappe.log_error(
            message=f"Order {order_id}: Payment failed. Method: {payment_method}. Message: {status_message}",
            title="Bank Pay - PayHere Failed",
        )
    elif str(status_code) == "-3":
        # Payment chargedback/disputed
        order.status = "Chargeback"
        frappe.log_error(
            message=f"Order {order_id}: Chargeback detected. Message: {status_message}",
            title="Bank Pay - PayHere Chargeback",
        )
    # status_code 0 = pending, leave as is

    order.save(ignore_permissions=True)
    frappe.db.commit()
