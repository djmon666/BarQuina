"""
Locust load testing configuration for BarQuina.

Run with:
    locust -f tests/locustfile.py --host=http://localhost:5000

Or with web UI:
    locust -f tests/locustfile.py --host=http://localhost:5000 --web-host=0.0.0.0

Or headless mode (10 users, 2 users/sec spawn rate, 60s duration):
    locust -f tests/locustfile.py --host=http://localhost:5000 --headless -u 10 -r 2 -t 60s
"""

from __future__ import annotations

import json
import random
from locust import HttpUser, TaskSet, task, between, events
from locust.runners import MasterRunner, WorkerRunner


class MobileTerminalUser(HttpUser):
    """Simulates a waiter using the mobile terminal."""
    
    weight = 3  # 3x more likely than admin users
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        self.client.verify = False  # Disable SSL verification
        self.tables = []
        self.products = []
        self.active_orders = {}  # {table_id: order_id}
        
        # Get real tables from the system
        response = self.client.get("/mobile/tables")
        if response.status_code == 200:
            try:
                # Parse HTML to extract table IDs (simple approach)
                import re
                table_ids = re.findall(r'/mobile/tables/(\d+)', response.text)
                self.tables = [int(tid) for tid in set(table_ids)]
                if not self.tables:
                    self.tables = [1]  # Fallback
            except:
                self.tables = [1]
        else:
            self.tables = [1]
        
        # Get real products from catalog
        response = self.client.get("/catalog/products")
        if response.status_code == 200:
            try:
                # Extract product IDs from the page
                import re
                product_ids = re.findall(r'data-product-id="(\d+)"', response.text)
                if not product_ids:
                    # Try another pattern
                    product_ids = re.findall(r'/catalog/products/(\d+)', response.text)
                self.products = [int(pid) for pid in set(product_ids)]
                if not self.products:
                    self.products = [1, 2, 3]  # Fallback
            except:
                self.products = [1, 2, 3]
    
    @task(5)
    def view_tables(self):
        """View the tables list."""
        self.client.get("/mobile/tables", name="/mobile/tables")
    
    @task(3)
    def view_table_detail(self):
        """View a specific table's orders."""
        table_id = random.choice(self.tables)
        self.client.get(f"/mobile/tables/{table_id}", name="/mobile/tables/[id]")
    
    @task(2)
    def create_order(self):
        """Create a new order for a table."""
        if not self.tables or not self.products:
            return
        
        table_id = random.choice(self.tables)
        
        # Use real product IDs
        num_items = random.randint(1, 3)
        selected_products = random.sample(self.products, min(num_items, len(self.products)))
        
        items = [
            {"product_id": pid, "quantity": random.randint(1, 3)}
            for pid in selected_products
        ]
        
        response = self.client.post(
            f"/mobile/tables/{table_id}/order",
            data={"items": json.dumps(items)},
            name="/mobile/tables/[id]/order",
            catch_response=True
        )
        
        if response.status_code == 200:
            # Try to extract order ID from response
            try:
                import re
                order_match = re.search(r'/mobile/orders/(\d+)', response.text)
                if order_match:
                    order_id = int(order_match.group(1))
                    self.active_orders[table_id] = order_id
            except:
                pass
            response.success()
        elif response.status_code == 404:
            response.failure(f"Table {table_id} not found")
        else:
            response.failure(f"Failed with status {response.status_code}")
    
    @task(1)
    def toggle_item_status(self):
        """Toggle an order item status."""
        if not self.active_orders:
            return
        
        # Get a random active order
        table_id = random.choice(list(self.active_orders.keys()))
        order_id = self.active_orders[table_id]
        
        # Get order details to find item IDs
        response = self.client.get(
            f"/mobile/tables/{table_id}",
            name="/mobile/tables/[id]"
        )
        
        if response.status_code == 200:
            try:
                # Extract item IDs from the response
                import re
                item_ids = re.findall(r'/mobile/orders/\d+/items/(\d+)/toggle', response.text)
                if item_ids:
                    item_id = random.choice(item_ids)
                    self.client.post(
                        f"/mobile/orders/{order_id}/items/{item_id}/toggle",
                        name="/mobile/orders/[id]/items/[id]/toggle"
                    )
            except:
                pass


class KitchenStaffUser(HttpUser):
    """Simulates kitchen staff monitoring the queue."""
    
    weight = 2
    wait_time = between(1, 3)
    
    @task(10)
    def view_kitchen_queue(self):
        """View the kitchen queue."""
        self.client.get("/kitchen/", name="/kitchen/")
    
    def on_start(self):
        self.client.verify = False
        self.pending_items = []
    
    @task(10)
    def view_kitchen_queue(self):
        """View the kitchen queue and extract pending items."""
        response = self.client.get("/kitchen/", name="/kitchen/")
        if response.status_code == 200:
            try:
                # Extract order and item IDs from kitchen queue
                import re
                matches = re.findall(r'/kitchen/orders/(\d+)/items/(\d+)/ready', response.text)
                self.pending_items = [(int(oid), int(iid)) for oid, iid in matches]
            except:
                pass
    
    @task(1)
    def mark_item_ready(self):
        """Mark an item as ready."""
        if not self.pending_items:
            return
        
        order_id, item_id = random.choice(self.pending_items)
        
        response = self.client.post(
            f"/kitchen/orders/{order_id}/items/{item_id}/ready",
            name="/kitchen/orders/[id]/items/[id]/ready"
        )
        
        # Remove from pending list if successful
        if response.status_code == 200:
            try:
                self.pending_items.remove((order_id, item_id))
            except:
                pass


class BarStaffUser(HttpUser):
    """Simulates bar staff monitoring drinks queue."""
    
    weight = 2
    wait_time = between(1, 3)
    
    @task(10)
    def view_bar_queue(self):
        """View the bar queue."""
        self.client.get("/bar/", name="/bar/")


class AdminUser(HttpUser):
    """Simulates admin users accessing management features."""
    
    weight = 1  # Less frequent than staff
    wait_time = between(1, 3)
    
    @task(5)
    def view_dashboard(self):
        """View the main dashboard."""
        self.client.get("/", name="/dashboard")
    
    @task(3)
    def view_orders(self):
        """View orders page."""
        self.client.get("/tables", name="/tables")
    
    @task(2)
    def view_products(self):
        """View products catalog."""
        self.client.get("/catalog/products", name="/catalog/products")
    
    @task(2)
    def view_cash_sessions(self):
        """View cash sessions."""
        self.client.get("/cash/sessions", name="/cash/sessions")
    
    @task(1)
    def view_reports(self):
        """View reports."""
        self.client.get("/reports/", name="/reports/")
    
    @task(1)
    def view_users(self):
        """View users management."""
        self.client.get("/users/", name="/users/")


# Event handlers for custom statistics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    if not isinstance(environment.runner, WorkerRunner):
        print("\n" + "="*60)
        print("🚀 BarQuina Load Test Starting")
        print("="*60)
        print(f"Host: {environment.host}")
        print(f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
        print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    if not isinstance(environment.runner, WorkerRunner):
        print("\n" + "="*60)
        print("✅ BarQuina Load Test Completed")
        print("="*60)
        stats = environment.stats
        print(f"Total requests: {stats.total.num_requests}")
        print(f"Total failures: {stats.total.num_failures}")
        print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
        print(f"Min response time: {stats.total.min_response_time:.2f}ms")
        print(f"Max response time: {stats.total.max_response_time:.2f}ms")
        print(f"Requests per second: {stats.total.total_rps:.2f}")
        print("="*60 + "\n")


# Optional: Custom load shape for realistic traffic patterns
# Uncomment to use custom traffic patterns (overrides --users and --run-time)
# from locust import LoadTestShape

# class RestaurantTrafficShape(LoadTestShape):
#     """
#     Simulates realistic restaurant traffic patterns:
#     - Slow start (restaurant opening)
#     - Peak hours (lunch/dinner rush)
#     - Gradual decline
#     """
#     
#     stages = [
#         # (duration_seconds, users, spawn_rate)
#         (60, 5, 1),      # Warm up: 5 users over 1 min
#         (120, 20, 2),    # Rush starts: 20 users over 2 min
#         (180, 50, 5),    # Peak: 50 users over 3 min
#         (240, 40, 2),    # Slight decline: 40 users
#         (300, 20, 5),    # Winding down: 20 users
#         (360, 5, 2),     # Closing: 5 users
#     ]
#     
#     def tick(self):
#         """Return the target user count and spawn rate for the current time."""
#         run_time = self.get_run_time()
#         
#         for duration, users, spawn_rate in self.stages:
#             if run_time < duration:
#                 return users, spawn_rate
#         
#         return None  # Test complete
