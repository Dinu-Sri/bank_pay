# Bank Pay — Deployment & Operations Guide

> **App**: Bank Pay v2.0.0  
> **Repo**: https://github.com/Dinu-Sri/bank_pay  
> **Domain**: academy.sltaxsolution.lk  
> **Stack**: Frappe v15.88.0 + LMS v2.40.0 + Docker/Portainer  
> **Site name** (internal): `frontend`  
> **Currency**: LKR (Sri Lankan Rupee)

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Docker Container Map](#2-docker-container-map)
3. [Fresh Installation](#3-fresh-installation)
4. [Deploying Updates](#4-deploying-updates)
5. [Frontend Asset Fix (Critical)](#5-frontend-asset-fix-critical)
6. [Configuration](#6-configuration)
7. [How It Works (Flow)](#7-how-it-works-flow)
8. [File Structure](#8-file-structure)
9. [Key Files Explained](#9-key-files-explained)
10. [Quick Diagnostic Commands](#10-quick-diagnostic-commands)
11. [Common Issues & Fixes](#11-common-issues--fixes)
12. [Uninstalling Old Apps](#12-uninstalling-old-apps)
13. [PayHere Integration (Future)](#13-payhere-integration-future)
14. [Useful Links](#14-useful-links)

---

## 1. System Architecture

```
Student Browser
    │
    ├─ /lms/courses/{name}          → LMS Vue SPA (CourseCardOverlay.vue)
    │       │
    │       ├─ "Buy this course"    → /lms/billing/course/{name} (LMS Billing.vue)
    │       │       │
    │       │       └─ "Proceed to Payment"
    │       │               │
    │       │               ▼
    │       │     get_payment_link() ─── overridden by bank_pay ───┐
    │       │               │                                       │
    │       │     Creates LMS Payment record                        │
    │       │     (shows in LMS Transactions)                       │
    │       │               │                                       │
    │       │               ▼                                       ▼
    │       │     Returns: /bank-pay/checkout/{name}     (our page)
    │       │
    │       └─ "Continue Learning"  → /lms/courses/{name}/learn/1-1
    │
    ├─ /bank-pay/checkout/{name}    → Bank Pay checkout page (Jinja)
    │       │
    │       ├─ Bank Transfer: show bank details → upload receipt
    │       └─ PayHere: redirect to PayHere gateway (future)
    │
    ├─ /bank-pay/my-payments        → Student payment history
    └─ /bank-pay/payhere-return     → PayHere return page (future)


Admin (Frappe Desk):
    │
    ├─ /app/bank-pay-order          → View/manage all orders
    │       └─ Change status to "Paid" → auto-creates:
    │               1. LMS Payment (payment_received = 1)
    │               2. LMS Enrollment
    │               3. Button changes to "Continue Learning"
    │
    └─ /app/bank-pay-settings       → Configure bank details, PayHere keys
```

---

## 2. Docker Container Map

| Container | Role | Key Paths |
|---|---|---|
| `lms-backend-1` | Frappe/LMS Python backend | `/home/frappe/frappe-bench/` |
| `lms-frontend-1` | Nginx (serves static files + proxy) | `/home/frappe/frappe-bench/sites/` |
| `lms-db-1` | MariaDB database | — |
| `lms-redis-*` | Redis cache/queue | — |
| `lms-scheduler-1` | Background job scheduler | — |
| `lms-worker-short-1` | Background workers | — |
| `lms-websocket-1` | Websocket server | — |
| `lms-cloudflared-1` | Cloudflare tunnel | — |

### Important volume info:
- `sites/` folder is **shared** between backend and frontend via a Docker volume
- `apps/` folder is **NOT shared** — only exists in the backend container
- Static assets (`sites/assets/`) use **symlinks** in backend → point to `apps/` folder
- Frontend (nginx) **cannot follow these symlinks** because `apps/` doesn't exist there
- **This is why we must manually copy assets** (see Section 5)

---

## 3. Fresh Installation

### Step 1: Install app from GitHub

In **Portainer → `lms-backend-1` → Console** (exec as `frappe`):

```bash
cd /home/frappe/frappe-bench

# Install from GitHub
bench get-app https://github.com/Dinu-Sri/bank_pay.git

# Install on site
bench --site frontend install-app bank_pay

# Create DocTypes in database
bench --site frontend migrate

# Build frontend assets (JS/CSS)
bench build --app bank_pay

# Clear all caches
bench --site frontend clear-cache
```

### Step 2: Fix frontend assets (REQUIRED)

The `bench build` creates a symlink that nginx can't follow. Fix it:

```bash
# In lms-backend-1:
rm /home/frappe/frappe-bench/sites/assets/bank_pay
cp -r /home/frappe/frappe-bench/apps/bank_pay/bank_pay/public /home/frappe/frappe-bench/sites/assets/bank_pay
```

### Step 3: Restart containers

Restart these in Portainer:
- `lms-backend-1`
- `lms-frontend-1`

### Step 4: Verify

1. Open browser: `https://academy.sltaxsolution.lk/assets/bank_pay/js/bank_pay.js`  
   → Should show JavaScript code (NOT 404)

2. Check installed apps:
```bash
bench --site frontend list-apps
```
→ Should show `bank_pay 2.0.0 master`

### Step 5: Configure

Go to: `https://academy.sltaxsolution.lk/app/bank-pay-settings`
- Enable Bank Transfer ✅
- Fill bank details (name, account number, branch, etc.)
- Save

---

## 4. Deploying Updates

After code changes are pushed to GitHub:

### On your PC (push changes):
```powershell
cd "c:\Users\User\Desktop\PayApp\bank_pay"
git add .
git commit -m "Description of change"
git push
```

### On server (lms-backend-1 console):
```bash
cd /home/frappe/frappe-bench/apps/bank_pay
git pull
cd /home/frappe/frappe-bench
bench --site frontend migrate
bench --site frontend clear-cache
```

### If JS/CSS files changed, also run:
```bash
bench build --app bank_pay

# Then fix symlink (backend):
rm /home/frappe/frappe-bench/sites/assets/bank_pay
cp -r /home/frappe/frappe-bench/apps/bank_pay/bank_pay/public /home/frappe/frappe-bench/sites/assets/bank_pay
```

Then restart `lms-backend-1` (always) and `lms-frontend-1` (only if JS/CSS changed).

### If only Python files changed:
Just restart `lms-backend-1`. No need to touch frontend.

---

## 5. Frontend Asset Fix (Critical)

### Why is this needed?

In Docker, `bench build` creates a symlink:
```
sites/assets/bank_pay → apps/bank_pay/bank_pay/public
```

The `apps/` directory only exists in the **backend** container. The **frontend** container (nginx) shares only the `sites/` volume. So the symlink is broken in nginx → 404 on JS files.

### Fix command (run in lms-backend-1):
```bash
rm /home/frappe/frappe-bench/sites/assets/bank_pay
cp -r /home/frappe/frappe-bench/apps/bank_pay/bank_pay/public /home/frappe/frappe-bench/sites/assets/bank_pay
```

### Alternative: Create files directly in lms-frontend-1

If the above doesn't work (rare), create the file directly in the frontend container:

```bash
# In lms-frontend-1 console:
mkdir -p /home/frappe/frappe-bench/sites/assets/bank_pay/js/
# Then paste the JS content using cat > ... << 'EOF'
```

### Verify:
```bash
# In lms-frontend-1:
ls -la /home/frappe/frappe-bench/sites/assets/bank_pay/js/
# Should show bank_pay.js

# In browser:
# https://academy.sltaxsolution.lk/assets/bank_pay/js/bank_pay.js
# Should show JS code, NOT 404
```

---

## 6. Configuration

### Bank Pay Settings

URL: `/app/bank-pay-settings`

| Field | Description |
|---|---|
| Enable Bank Transfer | Toggle bank transfer payment method |
| Enable PayHere | Toggle PayHere gateway (future) |
| Bank Name | e.g. "Bank of Ceylon" |
| Account Name | Account holder name |
| Account Number | Bank account number |
| Branch | Bank branch |
| Additional Instructions | Shown to student on checkout page |
| PayHere Merchant ID | From PayHere dashboard (future) |
| PayHere Secret | Merchant secret key (future) |
| Sandbox Mode | Use PayHere sandbox for testing (future) |

### LMS Course Setup

For a course to use Bank Pay:
1. Go to `/app/lms-course/{name}`
2. Check **"Paid Course"**
3. Set **"Course Price"** (in LKR)
4. Set **"Currency"** to LKR
5. Save

---

## 7. How It Works (Flow)

### Bank Transfer (Manual Approval):

```
1. Student → Course page → "Buy this course"
2. → LMS Billing page (fills address) → "Proceed to Payment"
3. → Our override creates LMS Payment record
4. → Redirects to /bank-pay/checkout/{course}
5. Student sees bank details + step-by-step instructions
6. Student transfers money via bank
7. Student uploads receipt screenshot + reference number
8. → Bank Pay Order created (status: Pending)
9. Admin opens /app/bank-pay-order → sees order with receipt
10. Admin changes status to "Paid" → Save
11. → Automatically:
    a. LMS Payment marked as payment_received = 1
    b. LMS Enrollment created
    c. Button changes to "Continue Learning"
```

### PayHere (Auto Approval — Future):

```
1-4. Same as above
5. Student selects "Pay with PayHere"
6. → Redirected to PayHere payment gateway
7. Student pays via card/mobile banking
8. PayHere sends server-to-server callback → /api/method/bank_pay.payhere.notify
9. → Automatically verifies signature → marks order as "Paid"
10. → Same auto-enrollment as step 11 above
11. Zero admin involvement
```

### Button State Logic (LMS built-in):

The "Buy this course" / "Continue Learning" button is controlled by LMS:
- LMS calls `get_membership()` → checks if `LMS Enrollment` exists  
- If enrollment exists → "Continue Learning"
- If no enrollment + paid course → "Buy this course"
- This is in `CourseCardOverlay.vue` in the LMS frontend
- After enrollment is created, user may need to **refresh the page** (Vue SPA caches data)

---

## 8. File Structure

```
bank_pay/
├── setup.py                    # Package setup
├── pyproject.toml              # Build config
├── requirements.txt            # Dependencies
├── MANIFEST.in                 # Package manifest
├── .gitignore
├── DEPLOYMENT.md               # This file
│
└── bank_pay/                   # Main app module
    ├── __init__.py             # Version string
    ├── hooks.py                # Frappe hooks (JS injection, overrides, routes)
    ├── modules.txt             # "Bank Pay"
    ├── patches.txt             # Migration patches
    ├── api.py                  # Whitelisted API endpoints
    ├── overrides.py            # LMS payment override (monkey-patch)
    ├── payhere.py              # PayHere integration (future)
    │
    ├── bank_pay/               # Module directory
    │   └── doctype/
    │       ├── bank_pay_order/
    │       │   ├── bank_pay_order.json    # DocType definition
    │       │   └── bank_pay_order.py      # Server logic (auto-enrollment)
    │       └── bank_pay_settings/
    │           ├── bank_pay_settings.json  # Settings DocType
    │           └── bank_pay_settings.py    # Settings controller
    │
    ├── public/
    │   └── js/
    │       └── bank_pay.js     # Frontend JS (route interception)
    │
    └── www/
        └── bank-pay/           # Web pages (served at /bank-pay/*)
            ├── checkout.html   # Checkout page template
            ├── checkout.py     # Checkout page context
            ├── my-payments.html    # Student payment history
            ├── my-payments.py
            ├── payhere-return.html # PayHere return page
            └── payhere-return.py
```

---

## 9. Key Files Explained

### `hooks.py`
- `web_include_js`: Injects `bank_pay.js` on every page
- `override_whitelisted_method`: Overrides `lms.lms.payments.get_payment_link`
- `before_request`: Monkey-patches the LMS function (fallback if override hook doesn't work)
- `website_route_rules`: Maps `/bank-pay/checkout/<course_name>` to the checkout template

### `overrides.py`
- `_bank_pay_get_payment_link()`: Intercepts when student clicks "Proceed to Payment"
  - Calls the original LMS function (which creates `LMS Payment` record)
  - Catches the gateway error (no gateway configured)
  - Returns `/bank-pay/checkout/{course}` instead of gateway URL
  - If LMS Payment creation fails, creates a minimal record as fallback

### `bank_pay_order.py`
- `before_save()`: When status changes to "Paid":
  1. `_mark_lms_payment_received()`: Finds the LMS Payment record and sets `payment_received = 1`
  2. `_enroll_student()`: Creates `LMS Enrollment` record

### `api.py`
- `get_checkout_context()`: Returns course info + settings for checkout page
- `create_order()`: Creates a new Bank Pay Order
- `upload_receipt()`: Attaches receipt to existing order
- `get_order()`: Get order status
- `get_my_orders()`: Get all orders for current user

### `bank_pay.js`
- Intercepts navigation to `/lms/billing/course/{name}` via `pushState`/`popstate` hooks
- Redirects to `/bank-pay/checkout/{name}`
- Acts as a secondary redirect mechanism (primary is the server-side override)

---

## 10. Quick Diagnostic Commands

Run these in **`lms-backend-1` console**:

### Check installed apps:
```bash
bench --site frontend list-apps
```

### Check if override is registered:
```bash
bench --site frontend console
```
```python
frappe.get_hooks("override_whitelisted_method")
# Should show: {'lms.lms.payments.get_payment_link': ['bank_pay.overrides.get_payment_link']}
```

### Check if JS is being injected:
```python
frappe.get_hooks("web_include_js")
# Should include: '/assets/bank_pay/js/bank_pay.js'
```

### Check if a student is enrolled:
```python
frappe.db.exists("LMS Enrollment", {"member": "student@email.com", "course": "course-name"})
```

### Check LMS Payment records:
```python
frappe.get_all("LMS Payment", filters={"payment_for_document": "course-name"}, fields=["name", "member", "payment_received"])
```

### Check Bank Pay Orders:
```python
frappe.get_all("Bank Pay Order", filters={"course": "course-name"}, fields=["name", "student", "status", "payment_method"])
```

### Check if DocTypes exist:
```python
frappe.db.exists("DocType", "Bank Pay Order")
frappe.db.exists("DocType", "Bank Pay Settings")
```

### Check for errors in logs:
```bash
# Recent error logs
tail -50 /home/frappe/frappe-bench/logs/frappe.log

# Search for bank_pay specific errors
grep -i "bank.pay" /home/frappe/frappe-bench/logs/frappe.log | tail -20
```

### Check if assets exist (backend):
```bash
ls -la /home/frappe/frappe-bench/sites/assets/bank_pay/js/
file /home/frappe/frappe-bench/sites/assets/bank_pay
# If it says "symbolic link" → needs the copy fix (Section 5)
```

### Test from browser:
```
# JS file accessible?
https://academy.sltaxsolution.lk/assets/bank_pay/js/bank_pay.js

# Checkout page works?
https://academy.sltaxsolution.lk/bank-pay/checkout/{course-name}

# Settings page?
https://academy.sltaxsolution.lk/app/bank-pay-settings

# Orders list?
https://academy.sltaxsolution.lk/app/bank-pay-order
```

---

## 11. Common Issues & Fixes

### Issue: 404 on JS file
**Cause**: Symlink not resolved by nginx  
**Fix**: See [Section 5](#5-frontend-asset-fix-critical)

### Issue: "Bank Transfer Settings not found" toast
**Cause**: Old V1 app (`bank_transfer_gateway`) still has JS cached  
**Fix**: 
1. Uninstall old app (Section 12)
2. Clear browser cache: `Ctrl+Shift+Delete`
3. Hard refresh: `Ctrl+Shift+R`

### Issue: Billing page shows instead of checkout
**Cause**: Override not registered or server not restarted  
**Fix**:
1. Check override: `frappe.get_hooks("override_whitelisted_method")`
2. Run `bench --site frontend migrate`
3. Restart `lms-backend-1`

### Issue: "Buy this course" button doesn't change after enrollment
**Cause**: LMS Vue SPA caches course data  
**Fix**: 
- User needs to refresh page (`F5`)
- Or navigate away and come back
- The enrollment IS created — this is just a frontend cache issue
- If clicked, our checkout page shows "🎉 You're already enrolled!"

### Issue: Phone number validation error on Billing page
**Cause**: Frappe validates phone field strictly — "NWP" is not a valid phone  
**Fix**: User must enter a valid phone number on the billing form

### Issue: `ModuleNotFoundError` for old DocType
**Cause**: Stale DB references to removed DocTypes  
**Fix**:
```bash
bench --site frontend console
```
```python
# Delete stale Payment Gateway entry
if frappe.db.exists("Payment Gateway", "Bank Transfer"):
    frappe.delete_doc("Payment Gateway", "Bank Transfer", force=True)
    frappe.db.commit()
```

### Issue: Changes not reflecting after deploy
**Fix**: Full reset sequence:
```bash
cd /home/frappe/frappe-bench/apps/bank_pay && git pull
cd /home/frappe/frappe-bench
bench --site frontend migrate
bench build --app bank_pay
rm /home/frappe/frappe-bench/sites/assets/bank_pay
cp -r /home/frappe/frappe-bench/apps/bank_pay/bank_pay/public /home/frappe/frappe-bench/sites/assets/bank_pay
bench --site frontend clear-cache
# Restart both lms-backend-1 and lms-frontend-1
```

---

## 12. Uninstalling Old Apps

### Remove bank_transfer_gateway (V1):
```bash
# Step 1: Uninstall from site
bench --site frontend uninstall-app bank_transfer_gateway --yes --force

# Step 2: Remove from bench
bench remove-app bank_transfer_gateway --force

# Step 3: Clean stale DB entries
bench --site frontend console
```
```python
if frappe.db.exists("Payment Gateway", "Bank Transfer"):
    frappe.delete_doc("Payment Gateway", "Bank Transfer", force=True)
    frappe.db.commit()
    print("Cleaned up")
```
```bash
# Step 4: Clear cache
bench --site frontend clear-cache
```

### Remove bank_pay (if needed):
```bash
bench --site frontend uninstall-app bank_pay --yes --force
bench remove-app bank_pay --force
bench --site frontend clear-cache
```

---

## 13. PayHere Integration (Future)

### Setup Steps:
1. Register at https://www.payhere.lk for a merchant account
2. Get Merchant ID and Merchant Secret from PayHere dashboard
3. Go to Bank Pay Settings → Enable PayHere
4. Enter Merchant ID and Secret
5. Enable Sandbox Mode for testing first
6. Set Notify URL in PayHere dashboard to: `https://academy.sltaxsolution.lk/api/method/bank_pay.payhere.notify`
7. Test with sandbox, then disable sandbox for live

### How it will work:
- Student selects "Pay with PayHere" on checkout
- Form data with MD5 hash signature is POSTed to PayHere
- Student pays on PayHere's page
- PayHere sends callback to our notify endpoint
- We verify the MD5 signature
- If valid and status_code == 2 (success), mark order as "Paid"
- Auto-enrollment happens (same as bank transfer approval)

### Files involved:
- `bank_pay/payhere.py` — `initiate_payment()` and `notify()`
- `bank_pay/www/bank-pay/checkout.html` — PayHere form submission
- `bank_pay/www/bank-pay/payhere-return.html` — Return page after payment

---

## 14. Useful Links

| Resource | URL |
|---|---|
| Bank Pay GitHub | https://github.com/Dinu-Sri/bank_pay |
| Live Site | https://academy.sltaxsolution.lk |
| Bank Pay Settings | https://academy.sltaxsolution.lk/app/bank-pay-settings |
| Bank Pay Orders | https://academy.sltaxsolution.lk/app/bank-pay-order |
| LMS Settings | https://academy.sltaxsolution.lk/app/lms-settings |
| LMS Courses | https://academy.sltaxsolution.lk/app/lms-course |
| Frappe Docs | https://frappeframework.com/docs |
| LMS GitHub | https://github.com/frappe/lms |
| PayHere Docs | https://support.payhere.lk/api-&-mobile-sdk/payhere-checkout |

---

## Git History (for reference)

```
ae9ff61 Fix LMS Payment integration: create record + mark paid on approval
9eb5f96 Redesign checkout UI + add already-enrolled view
cd0dceb Add website_route_rules for dynamic checkout URL
4fb67e2 Add monkey-patch fallback for LMS payment override via before_request
0621c81 Fix www routing: move pages to bank-pay subfolder
b5c2a1b Add server-side override for LMS payment endpoint
95b17e2 Initial commit - Bank Pay v2.0.0
```
