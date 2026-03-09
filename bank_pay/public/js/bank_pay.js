/**
 * Bank Pay — Frontend interception script.
 *
 * Injected via web_include_js on every page.
 * Detects navigation to /lms/billing/course/{name} and redirects
 * to our checkout page at /bank-pay/checkout/{name}.
 *
 * Works with LMS Vue SPA router (history mode).
 */
(function () {
	"use strict";

	const LMS_BILLING_PREFIX = "/lms/billing/course/";
	const BANK_PAY_CHECKOUT = "/bank-pay/checkout/";

	function getCourseName(path) {
		if (path.startsWith(LMS_BILLING_PREFIX)) {
			return path.slice(LMS_BILLING_PREFIX.length).split("?")[0];
		}
		return null;
	}

	function interceptNavigation(path) {
		const course = getCourseName(path);
		if (course) {
			window.location.href = BANK_PAY_CHECKOUT + encodeURIComponent(course);
			return true;
		}
		return false;
	}

	// --- 1. Check on page load (direct URL visit or refresh) ---
	if (interceptNavigation(window.location.pathname)) {
		return;
	}

	// --- 2. Intercept Vue Router navigation via popstate ---
	window.addEventListener("popstate", function () {
		interceptNavigation(window.location.pathname);
	});

	// --- 3. Intercept pushState / replaceState (Vue Router uses these) ---
	const origPushState = history.pushState;
	const origReplaceState = history.replaceState;

	history.pushState = function () {
		origPushState.apply(this, arguments);
		const url = arguments[2];
		if (url && typeof url === "string") {
			interceptNavigation(new URL(url, window.location.origin).pathname);
		}
	};

	history.replaceState = function () {
		origReplaceState.apply(this, arguments);
		const url = arguments[2];
		if (url && typeof url === "string") {
			interceptNavigation(new URL(url, window.location.origin).pathname);
		}
	};

	// --- 4. Hide "State/Province" and "Postal Code" on Billing page ---
	// The LMS Billing.vue may briefly render before redirect fires.
	// We hide these fields and auto-fill Postal Code (which is required).
	function hideBillingFields() {
		var labels = document.querySelectorAll("label");
		labels.forEach(function (lbl) {
			var text = (lbl.textContent || "").trim();
			if (text === "State/Province" || text === "Postal Code") {
				var wrapper = lbl.closest("div.space-y-4")
					? lbl.parentElement
					: lbl.parentElement;
				if (wrapper) {
					wrapper.style.display = "none";
				}
				// Auto-fill Postal Code with a default so validation passes
				if (text === "Postal Code") {
					var input = wrapper
						? wrapper.querySelector("input")
						: null;
					if (input && !input.value) {
						var nativeSet = Object.getOwnPropertyDescriptor(
							window.HTMLInputElement.prototype,
							"value"
						).set;
						nativeSet.call(input, "00000");
						input.dispatchEvent(
							new Event("input", { bubbles: true })
						);
					}
				}
			}
		});
	}

	// Run repeatedly for a few seconds to catch Vue rendering
	var attempts = 0;
	var billingInterval = setInterval(function () {
		if (
			window.location.pathname.indexOf("/lms/billing") !== -1
		) {
			hideBillingFields();
		}
		attempts++;
		if (attempts > 50) clearInterval(billingInterval);
	}, 200);
})();
