from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from typing import List
import math

app = FastAPI()

orders = []
order_counter = 1
wishlist = []

products = [
    {"id": 1, "name": "Classic White Shirt", "brand": "Zara", "category": "Shirt", "price": 1200, "sizes_available": ["S","M","L"], "in_stock": True},
    {"id": 2, "name": "Blue Denim Jeans", "brand": "Levis", "category": "Jeans", "price": 2500, "sizes_available": ["M","L","XL"], "in_stock": True},
    {"id": 3, "name": "Black Running Shoes", "brand": "Nike", "category": "Shoes", "price": 4500, "sizes_available": ["8","9","10"], "in_stock": True},
    {"id": 4, "name": "Summer Floral Dress", "brand": "H&M", "category": "Dress", "price": 1800, "sizes_available": ["S","M"], "in_stock": False},
    {"id": 5, "name": "Leather Jacket", "brand": "Zara", "category": "Jacket", "price": 6000, "sizes_available": ["M","L"], "in_stock": True},
    {"id": 6, "name": "Casual Sneakers", "brand": "Adidas", "category": "Shoes", "price": 3200, "sizes_available": ["7","8","9"], "in_stock": False}
]


class OrderRequest(BaseModel):
    customer_name: str = Field(..., min_length=2)
    product_id: int = Field(..., gt=0)
    size: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0, le=10)
    delivery_address: str = Field(..., min_length=10)
    gift_wrap: bool = False
    season_sale: bool = False


class NewProduct(BaseModel):
    name: str = Field(..., min_length=2)
    brand: str = Field(..., min_length=2)
    category: str = Field(..., min_length=2)
    price: int = Field(..., gt=0)
    sizes_available: List[str]
    in_stock: bool = True


class WishlistOrderRequest(BaseModel):
    customer_name: str
    delivery_address: str


# ------------------ Helper Functions ------------------

def find_product(product_id):
    for product in products:
        if product["id"] == product_id:
            return product
    return None


def calculate_order_total(price, quantity, gift_wrap, season_sale):

    subtotal = price * quantity
    season_discount = 0
    bulk_discount = 0
    gift_wrap_cost = 0

    if season_sale:
        season_discount = subtotal * 0.15

    discounted_price = subtotal - season_discount

    if quantity >= 5:
        bulk_discount = discounted_price * 0.05

    if gift_wrap:
        gift_wrap_cost = 50 * quantity

    total = discounted_price - bulk_discount + gift_wrap_cost

    return {
        "subtotal": subtotal,
        "season_discount": season_discount,
        "bulk_discount": bulk_discount,
        "gift_wrap_cost": gift_wrap_cost,
        "total": total
    }


def filter_products_logic(category=None, brand=None, max_price=None, in_stock=None):

    filtered = products

    if category is not None:
        filtered = [p for p in filtered if p["category"].lower() == category.lower()]

    if brand is not None:
        filtered = [p for p in filtered if p["brand"].lower() == brand.lower()]

    if max_price is not None:
        filtered = [p for p in filtered if p["price"] <= max_price]

    if in_stock is not None:
        filtered = [p for p in filtered if p["in_stock"] == in_stock]

    return filtered


# ------------------ Basic get ------------------

@app.get("/")
def home():
    return {"message": "Welcome to Veloura Fashion Store"}


@app.get("/products")
def get_products():

    total = len(products)
    in_stock_count = sum(1 for p in products if p["in_stock"])

    return {
        "products": products,
        "total": total,
        "in_stock_count": in_stock_count
    }


@app.get("/products/summary")
def products_summary():

    total = len(products)
    in_stock = sum(1 for p in products if p["in_stock"])
    out_stock = total - in_stock

    brands = list(set(p["brand"] for p in products))

    category_count = {}

    for p in products:
        category = p["category"]
        category_count[category] = category_count.get(category, 0) + 1

    return {
        "total_products": total,
        "in_stock": in_stock,
        "out_of_stock": out_stock,
        "brands": brands,
        "count_by_category": category_count
    }


@app.get("/products/filter")
def filter_products(
    category: str = Query(None),
    brand: str = Query(None),
    max_price: int = Query(None),
    in_stock: bool = Query(None)
):

    results = filter_products_logic(category, brand, max_price, in_stock)

    return {
        "results": results,
        "total": len(results)
    }


# ------------------ Product CRUD ------------------

@app.post("/products", status_code=201)
def create_product(product: NewProduct):

    for p in products:
        if p["name"].lower() == product.name.lower() and p["brand"].lower() == product.brand.lower():
            return {"error": "Product with same name and brand already exists"}

    new_id = len(products) + 1

    new_product = product.dict()
    new_product["id"] = new_id

    products.append(new_product)

    return {"message": "Product created successfully", "product": new_product}


@app.put("/products/{product_id}")
def update_product(product_id: int, price: int = Query(None), in_stock: bool = Query(None)):

    product = find_product(product_id)

    if not product:
        return {"error": "Product not found"}

    if price is not None:
        product["price"] = price

    if in_stock is not None:
        product["in_stock"] = in_stock

    return {"message": "Product updated", "product": product}


@app.delete("/products/{product_id}")
def delete_product(product_id: int):

    product = find_product(product_id)

    if not product:
        return {"error": "Product not found"}

    for order in orders:
        if order["product"] == product["name"]:
            return {"error": "Cannot delete product with order history"}

    products.remove(product)

    return {"message": "Product deleted successfully"}


@app.get("/products/{product_id}")
def get_product(product_id: int):

    product = find_product(product_id)

    if product:
        return product

    return {"error": "Product not found"}


# ------------------ Product Search / Sort / Page ------------------

@app.get("/products/search")
def search_products(keyword: str):

    keyword = keyword.lower()

    results = [
        p for p in products
        if keyword in p["name"].lower()
        or keyword in p["brand"].lower()
        or keyword in p["category"].lower()
    ]

    if not results:
        return {"message": "No products found", "total_found": 0}

    return {"results": results, "total_found": len(results)}


@app.get("/products/sort")
def sort_products(sort_by: str = "price", order: str = "asc"):

    valid_fields = ["price", "name", "brand", "category"]

    if sort_by not in valid_fields:
        return {"error": "Invalid sort field"}

    reverse = order == "desc"

    sorted_products = sorted(products, key=lambda x: x[sort_by], reverse=reverse)

    return {
        "sorted_by": sort_by,
        "order": order,
        "results": sorted_products
    }


@app.get("/products/page")
def paginate_products(page: int = 1, limit: int = 3):

    total_products = len(products)
    total_pages = math.ceil(total_products / limit)

    start = (page - 1) * limit
    end = start + limit

    return {
        "current_page": page,
        "total_pages": total_pages,
        "results": products[start:end]
    }


# ------------------ Browse ------------------

@app.get("/products/browse")
def browse_products(
    keyword: str = None,
    category: str = None,
    brand: str = None,
    in_stock: bool = None,
    max_price: int = None,
    sort_by: str = "price",
    order: str = "asc",
    page: int = 1,
    limit: int = 3
):

    filtered = products

    if keyword:
        filtered = [
            p for p in filtered
            if keyword.lower() in p["name"].lower()
            or keyword.lower() in p["brand"].lower()
            or keyword.lower() in p["category"].lower()
        ]

    if category:
        filtered = [p for p in filtered if p["category"].lower() == category.lower()]

    if brand:
        filtered = [p for p in filtered if p["brand"].lower() == brand.lower()]

    if in_stock is not None:
        filtered = [p for p in filtered if p["in_stock"] == in_stock]

    if max_price:
        filtered = [p for p in filtered if p["price"] <= max_price]

    reverse = order == "desc"

    filtered = sorted(filtered, key=lambda x: x[sort_by], reverse=reverse)

    total = len(filtered)
    total_pages = math.ceil(total / limit)

    start = (page - 1) * limit
    end = start + limit

    return {
        "total_results": total,
        "total_pages": total_pages,
        "current_page": page,
        "results": filtered[start:end]
    }


# ------------------ Orders ------------------

@app.get("/orders")
def get_orders():

    total_orders = len(orders)
    total_revenue = sum(order["total"] for order in orders) if orders else 0

    return {
        "orders": orders,
        "total": total_orders,
        "total_revenue": total_revenue
    }


@app.post("/orders")
def create_order(order: OrderRequest):

    global order_counter

    product = find_product(order.product_id)

    if not product:
        return {"error": "Product not found"}

    if not product["in_stock"]:
        return {"error": "Product out of stock"}

    if order.size not in product["sizes_available"]:
        return {"error": "Size not available", "available_sizes": product["sizes_available"]}

    price_details = calculate_order_total(
        product["price"],
        order.quantity,
        order.gift_wrap,
        order.season_sale
    )

    new_order = {
        "order_id": order_counter,
        "customer_name": order.customer_name,
        "product": product["name"],
        "brand": product["brand"],
        "size": order.size,
        "quantity": order.quantity,
        "gift_wrap": order.gift_wrap,
        "total": price_details["total"]
    }

    orders.append(new_order)
    order_counter += 1

    return new_order


@app.get("/orders/search")
def search_orders(customer_name: str):

    results = [o for o in orders if customer_name.lower() in o["customer_name"].lower()]

    return {"results": results, "total_found": len(results)}


@app.get("/orders/sort")
def sort_orders(sort_by: str = "total", order: str = "asc"):

    valid_fields = ["total", "quantity"]

    if sort_by not in valid_fields:
        return {"error": "Invalid sort field"}

    reverse = order == "desc"

    sorted_orders = sorted(orders, key=lambda x: x[sort_by], reverse=reverse)

    return {
        "sorted_by": sort_by,
        "order": order,
        "results": sorted_orders
    }


@app.get("/orders/page")
def paginate_orders(page: int = 1, limit: int = 2):

    total = len(orders)
    total_pages = math.ceil(total / limit)

    start = (page - 1) * limit
    end = start + limit

    return {
        "current_page": page,
        "total_pages": total_pages,
        "results": orders[start:end]
    }


# ------------------ Wishlist Workflow ------------------

@app.post("/wishlist/add")
def add_to_wishlist(customer_name: str = Query(...), product_id: int = Query(...), size: str = Query(...)):

    product = find_product(product_id)

    if not product:
        return {"error": "Product not found"}

    if size not in product["sizes_available"]:
        return {"error": "Invalid size", "available_sizes": product["sizes_available"]}

    for item in wishlist:
        if item["customer_name"] == customer_name and item["product_id"] == product_id and item["size"] == size:
            return {"error": "Item already in wishlist"}

    wishlist_item = {
        "customer_name": customer_name,
        "product_id": product_id,
        "product_name": product["name"],
        "price": product["price"],
        "size": size
    }

    wishlist.append(wishlist_item)

    return {"message": "Item added to wishlist", "wishlist_item": wishlist_item}


@app.get("/wishlist")
def get_wishlist():

    total_value = sum(item["price"] for item in wishlist)

    return {
        "wishlist": wishlist,
        "total_items": len(wishlist),
        "total_value": total_value
    }


@app.delete("/wishlist/remove")
def remove_from_wishlist(customer_name: str, product_id: int):

    for item in wishlist:
        if item["customer_name"] == customer_name and item["product_id"] == product_id:
            wishlist.remove(item)
            return {"message": "Item removed"}

    return {"error": "Wishlist item not found"}


@app.post("/wishlist/order-all", status_code=201)
def order_all_wishlist(request: WishlistOrderRequest):

    global order_counter

    customer_items = [item for item in wishlist if item["customer_name"] == request.customer_name]

    if not customer_items:
        return {"message": "No wishlist items"}

    created_orders = []
    grand_total = 0

    for item in customer_items:

        order = {
            "order_id": order_counter,
            "customer_name": request.customer_name,
            "product": item["product_name"],
            "size": item["size"],
            "quantity": 1,
            "total": item["price"]
        }

        orders.append(order)
        created_orders.append(order)

        grand_total += item["price"]
        order_counter += 1

    wishlist[:] = [w for w in wishlist if w["customer_name"] != request.customer_name]

    return {
        "orders_created": created_orders,
        "total_orders": len(created_orders),
        "grand_total": grand_total
    }