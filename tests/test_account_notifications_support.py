import unittest
from datetime import datetime
from fastapi.exceptions import HTTPException

from backend.app.core.database import SessionLocal
from backend.app.models.user import User, Address
from backend.app.models.notifications import Notification, NotificationPreference
from backend.app.models.support import SupportTicket, SupportMessage
from backend.app.schemas.account import (
    UserProfileUpdate,
    PasswordChangeRequest,
    NotificationPreferencesUpdate,
    SupportTicketCreate
)
from backend.app.services.account_service import AccountService
from backend.app.core.security import verify_password

class TestAccountNotificationsAndSupport(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.customer = self.db.query(User).filter(User.role == "customer").first()
        self.admin = self.db.query(User).filter(User.role == "admin").first()
        self.assertIsNotNone(self.customer, "Customer user must exist")
        self.assertIsNotNone(self.admin, "Admin user must exist")

    def tearDown(self):
        self.db.close()

    def test_profile_and_dashboard(self):
        # 1. Test profile retrieval
        prof = AccountService.get_profile(self.customer)
        self.assertEqual(prof.id, self.customer.id)

        # 2. Test profile update
        orig_name = self.customer.full_name
        updated = AccountService.update_profile(
            self.db,
            self.customer,
            UserProfileUpdate(full_name="Rahul Sharma Updated", phone="+91 9876543210")
        )
        self.assertEqual(updated.full_name, "Rahul Sharma Updated")
        self.assertEqual(updated.phone, "+91 9876543210")

        # Revert back
        AccountService.update_profile(
            self.db,
            self.customer,
            UserProfileUpdate(full_name=orig_name)
        )

        # 3. Test dashboard summary
        dash = AccountService.get_dashboard_summary(self.db, self.customer)
        self.assertIsNotNone(dash.customer_name)
        self.assertGreaterEqual(dash.profile_completion_percent, 0)
        self.assertIn("orders_count", dash.stats)
        self.assertIn("unread_notifications_count", dash.stats)
        self.assertIn("open_tickets_count", dash.stats)

    def test_notifications_lifecycle(self):
        # 1. Create test notification
        notif = AccountService.create_notification(
            db=self.db,
            user_id=self.customer.id,
            type="order",
            title="Order Shipped Successfully",
            message="Your order is in transit to destination.",
            reference_type="order",
            reference_id="1"
        )
        self.assertIsNotNone(notif.id)
        self.assertFalse(notif.is_read)

        # 2. List notifications
        items, total, unread = AccountService.list_notifications(
            db=self.db,
            user_id=self.customer.id,
            page=1,
            page_size=10
        )
        self.assertGreaterEqual(total, 1)
        self.assertGreaterEqual(unread, 1)

        # 3. Mark single as read
        read_notif = AccountService.mark_notification_as_read(
            db=self.db,
            user_id=self.customer.id,
            notification_id=notif.id
        )
        self.assertTrue(read_notif.is_read)
        self.assertIsNotNone(read_notif.read_at)

        # 4. Mark all as read
        AccountService.mark_all_notifications_as_read(db=self.db, user_id=self.customer.id)
        unread_after = AccountService.get_unread_count(self.db, self.customer.id)
        self.assertEqual(unread_after, 0)

        # 5. Preferences
        pref = AccountService.get_or_create_preferences(self.db, self.customer.id)
        self.assertTrue(pref.order_updates)

        updated_pref = AccountService.update_preferences(
            self.db,
            self.customer.id,
            NotificationPreferencesUpdate(promotional_updates=False)
        )
        self.assertFalse(updated_pref.promotional_updates)

        # Clean up test notification
        AccountService.delete_notification(self.db, self.customer.id, notif.id)

    def test_support_tickets_lifecycle(self):
        # 1. Create support ticket
        ticket = AccountService.create_support_ticket(
            db=self.db,
            user=self.customer,
            data=SupportTicketCreate(
                subject="Need assistance with return pickup scheduling",
                category="return",
                priority="high",
                description="The delivery agent has not arrived yet for pickup."
            )
        )
        self.assertIsNotNone(ticket.id)
        self.assertTrue(ticket.ticket_number.startswith("TKT-"))
        self.assertEqual(ticket.status, "open")
        self.assertEqual(len(ticket.messages), 1)

        # 2. Customer message
        msg = AccountService.add_user_message(
            db=self.db,
            user=self.customer,
            ticket_id=ticket.id,
            message_text="Please contact courier partner ASAP."
        )
        self.assertEqual(msg.sender_role, "customer")
        self.assertEqual(msg.ticket_id, ticket.id)

        # 3. Admin message and status update
        admin_msg = AccountService.add_admin_message(
            db=self.db,
            admin_user=self.admin,
            ticket_id=ticket.id,
            message_text="We have contacted the courier team. Pickup scheduled today by 4 PM."
        )
        self.assertEqual(admin_msg.sender_role, "support")

        updated_ticket = AccountService.update_admin_ticket_status(
            db=self.db,
            ticket_id=ticket.id,
            new_status="in_progress"
        )
        self.assertEqual(updated_ticket.status, "in_progress")

        # 4. Close ticket
        closed_ticket = AccountService.close_user_ticket(
            db=self.db,
            user=self.customer,
            ticket_id=ticket.id
        )
        self.assertEqual(closed_ticket.status, "closed")

        # 5. Data isolation: Cannot access ticket with invalid user_id
        with self.assertRaises(HTTPException):
            AccountService.get_user_ticket(self.db, user_id=999999, ticket_id=ticket.id)

    def test_coupons_and_questions(self):
        # 1. List available coupons
        coupons = AccountService.list_available_coupons(self.db, self.customer.id)
        self.assertIsInstance(coupons, list)

        # 2. List customer questions
        questions, total = AccountService.list_user_questions(self.db, self.customer.id)
        self.assertIsInstance(questions, list)
        self.assertGreaterEqual(total, 0)

if __name__ == "__main__":
    unittest.main()
