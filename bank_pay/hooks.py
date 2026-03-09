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

# --- Website routes ---
website_route_rules = [
    {"from_route": "/bank-pay/<path:app_path>", "to_route": "bank_pay"},
]

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
