import unittest
from datetime import datetime
from fastapi.exceptions import HTTPException
from backend.app.core.database import SessionLocal
from backend.app.models.order import Order, OrderStatusHistory
from backend.app.models.shipment import Shipment, ShipmentTrackingEvent
from backend.app.models.inventory import InventoryTransaction
from backend.app.services.shipping_service import (
    create_shipment_for_order,
    transition_shipment_status,
    add_tracking_event,
    get_customer_tracking_details,
    list_admin_shipments
)
from backend.app.schemas.shipment import (
    ShipmentCreateRequest, 
    ShipmentStatusUpdateRequest, 
    TrackingEventCreateRequest
)

class TestShippingLifecycle(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_shipping_operations(self):
        # Pick an order without an existing shipment, or order 2
        orders_without_shipment = [
            o for o in self.db.query(Order).all() 
            if not self.db.query(Shipment).filter(Shipment.order_id == o.id).first()
        ]
        
        if orders_without_shipment:
            order = orders_without_shipment[0]
        else:
            order = self.db.query(Order).all()[0]

        existing_shipment = self.db.query(Shipment).filter(Shipment.order_id == order.id).first()
        if not existing_shipment:
            req = ShipmentCreateRequest(
                carrier="Blue Dart Express",
                shipping_method="standard",
                tracking_number="BD-123456789IN",
                notes="Warehouse dispatched"
            )
            shipment = create_shipment_for_order(db=self.db, order_id=order.id, data=req)
            self.assertIsNotNone(shipment.id)
            self.assertTrue(shipment.shipment_number.startswith("SHP-"))
        else:
            shipment = existing_shipment

        # Test duplicate shipment prevention
        with self.assertRaises(HTTPException) as ctx:
            duplicate_req = ShipmentCreateRequest(
                carrier="Delhivery",
                shipping_method="express"
            )
            create_shipment_for_order(db=self.db, order_id=order.id, data=duplicate_req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("already exists", str(ctx.exception.detail).lower())

        # Test customer tracking isolation
        # Order belongs to order.user_id. Accessing with another user_id should raise 404
        unauthorized_user_id = 99999
        with self.assertRaises(HTTPException) as auth_ctx:
            get_customer_tracking_details(db=self.db, order_id=order.id, user_id=unauthorized_user_id)
        self.assertEqual(auth_ctx.exception.status_code, 404)

        # Accessing with authorized user_id should succeed
        tracking_info = get_customer_tracking_details(db=self.db, order_id=order.id, user_id=order.user_id)
        self.assertIsNotNone(tracking_info)
        self.assertIsNotNone(tracking_info.shipment)
        self.assertEqual(tracking_info.order_id, order.id)

        # Test manual tracking event addition
        evt_req = TrackingEventCreateRequest(
            status="pending",
            location="Warehouse Dock A",
            description="Package labeled and ready for packing",
            source="courier_scan"
        )
        evt = add_tracking_event(db=self.db, shipment_id=shipment.id, data=evt_req)
        self.assertIsNotNone(evt.id)

        # Step through valid transitions:
        # 1. pending -> packed
        if shipment.status == "pending":
            shipment = transition_shipment_status(
                db=self.db, 
                shipment_id=shipment.id, 
                data=ShipmentStatusUpdateRequest(status="packed", location="Fulfillment Center", description="Package verified and packed in corrugated carton")
            )
            self.assertEqual(shipment.status, "packed")

        # 2. packed -> shipped (synchronizes order to shipped)
        if shipment.status == "packed":
            shipment = transition_shipment_status(
                db=self.db, 
                shipment_id=shipment.id, 
                data=ShipmentStatusUpdateRequest(status="shipped", location="Fulfillment Center", description="Dispatched to carrier sorting facility")
            )
            self.assertEqual(shipment.status, "shipped")
            self.db.refresh(order)
            self.assertEqual(order.status, "shipped")

        # 3. shipped -> in_transit
        if shipment.status == "shipped":
            shipment = transition_shipment_status(
                db=self.db, 
                shipment_id=shipment.id, 
                data=ShipmentStatusUpdateRequest(status="in_transit", location="Bhiwandi Linehaul Hub", description="Arrived at regional hub for linehaul transport")
            )
            self.assertEqual(shipment.status, "in_transit")

        # 4. in_transit -> out_for_delivery
        if shipment.status == "in_transit":
            shipment = transition_shipment_status(
                db=self.db, 
                shipment_id=shipment.id, 
                data=ShipmentStatusUpdateRequest(status="out_for_delivery", location="Bandra Delivery Station", description="Assigned to delivery agent")
            )
            self.assertEqual(shipment.status, "out_for_delivery")

        # 5. out_for_delivery -> delivered (synchronizes order to delivered)
        if shipment.status == "out_for_delivery":
            shipment = transition_shipment_status(
                db=self.db, 
                shipment_id=shipment.id, 
                data=ShipmentStatusUpdateRequest(status="delivered", location="Customer Doorstep, Mumbai", description="Delivered to recipient")
            )
            self.assertEqual(shipment.status, "delivered")
            self.assertIsNotNone(shipment.delivered_at)
            self.db.refresh(order)
            self.assertEqual(order.status, "delivered")

        # Check order status history recorded transitions
        histories = self.db.query(OrderStatusHistory).filter(OrderStatusHistory.order_id == order.id).all()
        status_names = [h.new_status for h in histories]
        self.assertIn("delivered", status_names)

        # Test invalid backwards transition: delivered -> processing should fail with 400
        invalid_req = ShipmentStatusUpdateRequest(
            status="processing",
            description="Attempting invalid backwards move"
        )
        with self.assertRaises(HTTPException) as invalid_ctx:
            transition_shipment_status(db=self.db, shipment_id=shipment.id, data=invalid_req)
        self.assertEqual(invalid_ctx.exception.status_code, 400)

        # Verify admin listing
        items, total = list_admin_shipments(db=self.db)
        self.assertGreaterEqual(total, 1)
        self.assertTrue(any(item["id"] == shipment.id for item in items))

    def test_inventory_integrity_during_shipping(self):
        # Verify that shipping operations NEVER deduct inventory or create inventory transactions
        initial_inv_tx_count = self.db.query(InventoryTransaction).count()

        shipments = self.db.query(Shipment).all()
        if shipments:
            s = shipments[0]
            # Add tracking event
            add_tracking_event(
                db=self.db,
                shipment_id=s.id,
                data=TrackingEventCreateRequest(
                    status="in_transit",
                    location="Test Location",
                    description="Test check",
                    source="manual"
                )
            )

        final_inv_tx_count = self.db.query(InventoryTransaction).count()
        self.assertEqual(
            initial_inv_tx_count, 
            final_inv_tx_count, 
            "Inventory transactions must NOT be created during shipping operations"
        )

if __name__ == "__main__":
    unittest.main()
