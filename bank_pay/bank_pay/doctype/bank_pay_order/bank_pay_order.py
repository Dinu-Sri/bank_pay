import frappe
from frappe.model.document import Document


class BankPayOrder(Document):
    def before_save(self):
        if self.has_value_changed("status") and self.status == "Paid":
            self._mark_lms_payment_received()
            self._enroll_student()

    def _mark_lms_payment_received(self):
        """Mark the LMS Payment record as received so LMS UI updates correctly."""
        lms_payment = frappe.db.get_value(
            "LMS Payment",
            {
                "member": self.student,
                "payment_for_document_type": "LMS Course",
                "payment_for_document": self.course,
                "payment_received": 0,
            },
            "name",
        )
        if lms_payment:
            frappe.db.set_value("LMS Payment", lms_payment, "payment_received", 1)
            self.lms_payment = lms_payment

    def _enroll_student(self):
        """Create LMS Enrollment when order is marked as Paid."""
        if self.enrollment:
            return

        existing = frappe.db.exists(
            "LMS Enrollment",
            {"member": self.student, "course": self.course},
        )
        if existing:
            self.enrollment = existing
            return

        enrollment = frappe.get_doc(
            {
                "doctype": "LMS Enrollment",
                "course": self.course,
                "member": self.student,
            }
        )
        enrollment.insert(ignore_permissions=True)
        self.enrollment = enrollment.name
        frappe.msgprint(
            f"Student {self.student_name or self.student} enrolled in {self.course_title or self.course}.",
            alert=True,
            indicator="green",
        )
