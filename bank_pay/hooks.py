app_name = "bank_pay"
app_title = "Bank Pay"
app_publisher = "SL Tax Solution"
app_description = "Unified payment gateway for Frappe LMS - Bank Transfer & PayHere"
app_email = "info@sltaxsolution.lk"
app_license = "MIT"

# Apps required to run this app
required_apps = ["frappe", "lms"]

# --- JS injection (single entry point) ---
web_include_js = "/assets/bank_pay/js/bank_pay.js"

# --- Override LMS payment endpoint ---
# When user clicks "Proceed to Payment" on the LMS billing page,
# redirect them to our checkout page instead.
override_whitelisted_method = {
    "lms.lms.payments.get_payment_link": "bank_pay.overrides.get_payment_link",
}

# --- Website routes ---
# www/bank-pay/ folder maps to /bank-pay/* URLs automatically

# --- Fixtures (export settings for easy migration) ---
fixtures = [
    {
        "doctype": "Bank Pay Settings",
    },
]

# --- Scheduled Tasks ---
# scheduler_events = {
#     "daily": [
#         "bank_pay.tasks.expire_stale_orders"
#     ],
# }
