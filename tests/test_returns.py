import unittest
import json
import secrets
from datetime import datetime, timedelta
from fastapi.exceptions import HTTPException

from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.order import Order, OrderItem, Payment
from backend.app.models.product import Product
from backend.app.models.inventory import Inventory, InventoryTransaction
from backend.app.models.returns import (
    Return, ReturnItem, ReturnStatusHistory,
    Refund, RefundTransaction,
    Replacement, ReplacementItem, ReplacementStatusHistory
)
from backend.app.schemas.returns import (
    ReturnCreateRequest,
    ReturnItemCreateRequest,
    ReturnApproveRequest,
    ReturnRejectRequest,
    ReturnInspectRequest,
    ReturnStatusUpdateRequest,
    RefundCreateRequest,
    RefundProcessRequest,
    ReplacementCreateRequest,
    ReplacementStatusUpdateRequest
)
from backend.app.services.return_service import (
    evaluate_order_return_eligibility,
    create_customer_return_request,
    cancel_customer_return,
    approve_return_request,
    reject_return_request,
    inspect_return_items,
    transition_return_status,
    create_refund_for_return,
    process_refund_transaction,
    create_replacement_for_return,
    transition_replacement_status,
    calculate_order_refundable_amount,
    get_return_by_id,
    list_customer_returns,
    list_admin_returns
)

class TestReturnsRefundsReplacements(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        # Find customer and admin users
        self.customer = self.db.query(User).filter(User.role == "customer").first()
        self.admin = self.db.query(User).filter(User.role == "admin").first()
        if not self.customer:
            self.customer = self.db.query(User).first()
        if not self.admin:
            self.admin = self.db.query(User).first()

    def tearDown(self):
        self.db.close()

    def _get_or_create_delivered_order(self):
        # Create a fresh delivered test order to ensure independent returnable quota
        prod = self.db.query(Product).first()
        order_no = f"ORD-TEST-{secrets.token_hex(4).upper()}"
        order = Order(
            order_number=order_no,
            user_id=self.customer.id,
            status="delivered",
            payment_status="paid",
            payment_method="card",
            subtotal=2000.0,
            tax_amount=100.0,
            shipping_amount=50.0,
            discount_amount=0.0,
            total_amount=2150.0,
            currency="INR",
            shipping_address_json=json.dumps({"full_name": "Test Customer", "address_line1": "123 Main St", "city": "Mumbai", "postal_code": "400001", "country": "India"}),
            updated_at=datetime.utcnow()
        )
        self.db.add(order)
        self.db.flush()

        item = OrderItem(
            order_id=order.id,
            product_id=prod.id,
            product_name=prod.name,
            sku=prod.sku or f"SKU-{prod.id}",
            unit_price=400.0,
            mrp=500.0,
            quantity=5,
            total_price=2000.0,
            line_total=2000.0
        )
        self.db.add(item)

        payment = Payment(
            order_id=order.id,
            user_id=self.customer.id,
            provider="standard",
            method="card",
            amount=2150.0,
            currency="INR",
            status="paid",
            provider_payment_id=f"PAY_{secrets.token_hex(6).upper()}"
        )
        self.db.add(payment)

        self.db.commit()
        self.db.refresh(order)
        return order

    def test_01_return_eligibility_evaluation(self):
        order = self._get_or_create_delivered_order()
        self.assertIsNotNone(order, "Should have at least one order in DB")

        eligibility = evaluate_order_return_eligibility(self.db, order_id=order.id, user_id=order.user_id)
        self.assertIsNotNone(eligibility)
        self.assertEqual(eligibility.order_id, order.id)
        self.assertEqual(eligibility.order_status, "delivered")
        self.assertTrue(len(eligibility.items) > 0)
        for itm in eligibility.items:
            self.assertGreater(itm.purchased_quantity, 0)
            self.assertGreaterEqual(itm.returnable_quantity, 0)

    def test_02_create_customer_return_request(self):
        order = self._get_or_create_delivered_order()
        order_item = order.items[0]

        # Calculate remaining returnable quantity
        eligibility = evaluate_order_return_eligibility(self.db, order_id=order.id, user_id=order.user_id)
        item_el = next((i for i in eligibility.items if i.order_item_id == order_item.id), None)
        
        if item_el and item_el.returnable_quantity > 0:
            user = self.db.query(User).filter(User.id == order.user_id).first()
            payload = ReturnCreateRequest(
                reason="defective",
                resolution_type="refund",
                customer_note="Item stopped working after 2 days",
                items=[
                    ReturnItemCreateRequest(
                        order_item_id=order_item.id,
                        quantity=1,
                        reason="defective",
                        resolution="refund"
                    )
                ]
            )

            ret = create_customer_return_request(self.db, order_id=order.id, user=user, data=payload)
            self.assertIsNotNone(ret.id)
            self.assertTrue(ret.return_number.startswith("RET-"))
            self.assertEqual(ret.status, "requested")
            self.assertEqual(ret.reason, "defective")
            self.assertEqual(len(ret.items), 1)
            self.assertGreater(ret.items[0].refund_amount, 0)

            # Verify history record
            self.assertTrue(len(ret.status_history) >= 1)
            self.assertEqual(ret.status_history[0].new_status, "requested")

    def test_03_customer_cancellation_lifecycle(self):
        order = self._get_or_create_delivered_order()
        user = self.db.query(User).filter(User.id == order.user_id).first()
        order_item = order.items[0]

        eligibility = evaluate_order_return_eligibility(self.db, order_id=order.id)
        item_el = next((i for i in eligibility.items if i.order_item_id == order_item.id), None)

        if item_el and item_el.returnable_quantity > 0:
            payload = ReturnCreateRequest(
                reason="not_as_expected",
                resolution_type="refund",
                customer_note="Testing customer cancellation",
                items=[
                    ReturnItemCreateRequest(
                        order_item_id=order_item.id,
                        quantity=1,
                        reason="not_as_expected"
                    )
                ]
            )
            ret = create_customer_return_request(self.db, order_id=order.id, user=user, data=payload)
            self.assertEqual(ret.status, "requested")

            # Cancel
            cancelled_ret = cancel_customer_return(self.db, return_id=ret.id, user_id=user.id, reason="Customer changed mind")
            self.assertEqual(cancelled_ret.status, "cancelled")

            # Double cancellation should fail
            with self.assertRaises(HTTPException):
                cancel_customer_return(self.db, return_id=ret.id, user_id=user.id)

    def test_04_admin_approval_and_inspection_with_restock(self):
        order = self._get_or_create_delivered_order()
        user = self.db.query(User).filter(User.id == order.user_id).first()
        order_item = order.items[0]

        eligibility = evaluate_order_return_eligibility(self.db, order_id=order.id)
        item_el = next((i for i in eligibility.items if i.order_item_id == order_item.id), None)

        if item_el and item_el.returnable_quantity > 0:
            # Create a return
            payload = ReturnCreateRequest(
                reason="wrong_item",
                resolution_type="refund",
                items=[
                    ReturnItemCreateRequest(
                        order_item_id=order_item.id,
                        quantity=1,
                        reason="wrong_item"
                    )
                ]
            )
            ret = create_customer_return_request(self.db, order_id=order.id, user=user, data=payload)

            # Admin approves
            ret = approve_return_request(self.db, return_id=ret.id, admin_user=self.admin, data=ReturnApproveRequest(admin_note="Approved for return pickup"))
            self.assertEqual(ret.status, "approved")
            self.assertIsNotNone(ret.approved_at)

            # Transition to received
            ret = transition_return_status(
                self.db, return_id=ret.id, 
                data=ReturnStatusUpdateRequest(status="received", reason="Package received at warehouse"), 
                admin_user=self.admin
            )
            self.assertEqual(ret.status, "received")

            # Inspect and Restock
            if order_item.variant_id:
                inv = self.db.query(Inventory).filter(Inventory.product_id == order_item.product_id, Inventory.variant_id == order_item.variant_id).first()
            else:
                inv = self.db.query(Inventory).filter(Inventory.product_id == order_item.product_id, Inventory.variant_id.is_(None)).first()
            stock_before = inv.on_hand_quantity if inv else 0

            ret = inspect_return_items(
                self.db,
                return_id=ret.id,
                admin_user=self.admin,
                data=ReturnInspectRequest(condition="resellable", inspection_note="Original sealed packaging", restock=True)
            )
            self.assertEqual(ret.status, "inspection")
            self.assertEqual(ret.inspection_condition, "resellable")

            if inv:
                self.db.refresh(inv)
                self.assertEqual(inv.on_hand_quantity, stock_before + 1)
                
                # Verify InventoryTransaction record
                tx = (
                    self.db.query(InventoryTransaction)
                    .filter(InventoryTransaction.reference_id == ret.return_number)
                    .first()
                )
                self.assertIsNotNone(tx)
                self.assertEqual(tx.transaction_type, "RECEIVE")
                self.assertEqual(tx.reference_type, "return_restock")

    def test_05_refund_creation_and_processing(self):
        # Create a fresh delivered order and return for testing refund settlement
        order = self._get_or_create_delivered_order()
        user = self.db.query(User).filter(User.id == order.user_id).first()
        order_item = order.items[0]
        ret = create_customer_return_request(
            self.db,
            order_id=order.id,
            user=user,
            data=ReturnCreateRequest(
                reason="damaged",
                items=[ReturnItemCreateRequest(order_item_id=order_item.id, quantity=1)]
            )
        )
        ret = approve_return_request(self.db, return_id=ret.id, admin_user=self.admin)
        ret = transition_return_status(self.db, return_id=ret.id, data=ReturnStatusUpdateRequest(status="received"), admin_user=self.admin)
        ret = inspect_return_items(self.db, return_id=ret.id, admin_user=self.admin, data=ReturnInspectRequest(condition="damaged"))

        # Create refund
        refund = create_refund_for_return(self.db, return_id=ret.id, admin_user=self.admin)
        self.assertIsNotNone(refund.id)
        self.assertTrue(refund.refund_number.startswith("REF-"))
        self.assertGreater(refund.amount, 0)
        self.assertEqual(refund.status, "requested")

        # Process refund
        processed = process_refund_transaction(
            self.db, 
            refund_id=refund.id, 
            admin_user=self.admin,
            data=RefundProcessRequest(notes="Settled to original payment instrument")
        )
        self.assertEqual(processed.status, "completed")
        self.assertIsNotNone(processed.processed_at)
        self.assertTrue(len(processed.transactions) >= 1)
        self.assertEqual(processed.transactions[0].status, "success")

        # Verify linked return transitioned to refunded
        self.db.refresh(ret)
        self.assertEqual(ret.status, "refunded")

    def test_06_replacement_creation_and_shipment_dispatch(self):
        # Create a replacement-requested return
        order = self._get_or_create_delivered_order()
        user = self.db.query(User).filter(User.id == order.user_id).first()
        order_item = order.items[0]

        # Ensure inventory is available for product
        inv = self.db.query(Inventory).filter(Inventory.product_id == order_item.product_id).first()
        if inv and inv.available_quantity < 2:
            inv.on_hand_quantity += 10
            inv.available_quantity = inv.on_hand_quantity - inv.reserved_quantity
            self.db.commit()

        ret = create_customer_return_request(
            self.db,
            order_id=order.id,
            user=user,
            data=ReturnCreateRequest(
                reason="defective",
                resolution_type="replacement",
                items=[ReturnItemCreateRequest(order_item_id=order_item.id, quantity=1, resolution="replacement")]
            )
        )
        ret = approve_return_request(self.db, return_id=ret.id, admin_user=self.admin)
        ret = transition_return_status(self.db, return_id=ret.id, data=ReturnStatusUpdateRequest(status="received"), admin_user=self.admin)
        ret = inspect_return_items(self.db, return_id=ret.id, admin_user=self.admin, data=ReturnInspectRequest(condition="defective"))

        # Create replacement
        rep = create_replacement_for_return(self.db, return_id=ret.id, admin_user=self.admin)
        self.assertIsNotNone(rep.id)
        self.assertTrue(rep.replacement_number.startswith("REP-"))
        self.assertEqual(rep.status, "requested")
        self.assertEqual(len(rep.items), 1)

        # Transition to approved
        rep = transition_replacement_status(
            self.db,
            replacement_id=rep.id,
            data=ReplacementStatusUpdateRequest(status="approved", notes="Replacement approved"),
            admin_user=self.admin
        )
        self.assertEqual(rep.status, "approved")

        # Transition to processing (authoritative stock deduction)
        rep = transition_replacement_status(
            self.db,
            replacement_id=rep.id,
            data=ReplacementStatusUpdateRequest(status="processing", notes="Allocating replacement item"),
            admin_user=self.admin
        )
        self.assertEqual(rep.status, "processing")
        self.assertTrue(rep.items[0].allocated)

        # Transition to shipped (creates shipment record)
        rep = transition_replacement_status(
            self.db,
            replacement_id=rep.id,
            data=ReplacementStatusUpdateRequest(status="shipped", notes="Dispatched with express courier"),
            admin_user=self.admin
        )
        self.assertEqual(rep.status, "shipped")
        self.assertIsNotNone(rep.shipment_id)
        self.assertIsNotNone(rep.shipment)
        self.assertTrue(rep.shipment.tracking_number.startswith("REP-"))

        # Transition to delivered
        rep = transition_replacement_status(
            self.db,
            replacement_id=rep.id,
            data=ReplacementStatusUpdateRequest(status="delivered", notes="Replacement package delivered"),
            admin_user=self.admin
        )
        self.assertEqual(rep.status, "delivered")

        # Return should now be closed
        self.db.refresh(ret)
        self.assertEqual(ret.status, "closed")

if __name__ == "__main__":
    unittest.main()
