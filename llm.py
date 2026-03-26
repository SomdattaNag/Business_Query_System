import os
import json
import re
import mysql.connector
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.getenv('GROQ_API_KEY'))

# Database config
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'business_graph'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'port': int(os.getenv('DB_PORT', 3306))
}

# System prompt for the LLM - STRICT about returning ONLY SQL
SYSTEM_PROMPT = """
You are a SQL query generator. Convert the user's question into a MySQL query.

CRITICAL RULES:
1. Return ONLY the SQL query. NO explanations, NO text before or after.
2. Do NOT include phrases like "Here is the query", "To show", "You can use", etc.
3. The response must start with SELECT, WITH, SHOW, or DESCRIBE.
4. Always use DISTINCT when joining tables that can have multiple rows per invoice/order.
5. IMPORTANT: Use sales_order_items.quantity for sales quantity (units sold). Use billing_items.amount for revenue (money).

Database Schema:
- billing_documents: invoice_id, invoice_date, amount, status, partner_id
- billing_items: invoice_id, delivery_id, product_id, quantity, amount
- deliveries: delivery_id, delivery_date, status  
- delivery_items: delivery_id, order_id, product_id, quantity
- sales_orders: order_id, partner_id, order_date, status, total_amount
- sales_order_items: order_id, product_id, quantity, unit_price
- business_partners: partner_id, partner_name
- products: product_id, product_name
- payments: payment_id, invoice_id, payment_date, amount

Examples:

Question: "Show me orders that were delivered but not billed"
SQL: SELECT DISTINCT so.order_id, so.order_date, so.total_amount, bp.partner_name FROM sales_orders so JOIN delivery_items di ON so.order_id = di.order_id LEFT JOIN billing_items bi ON di.delivery_id = bi.delivery_id LEFT JOIN business_partners bp ON so.partner_id = bp.partner_id WHERE bi.invoice_id IS NULL;

Question: "Which products have the most invoices?"
SQL: SELECT p.product_id, p.product_name, COUNT(DISTINCT bi.invoice_id) as invoice_count FROM products p JOIN billing_items bi ON p.product_id = bi.product_id GROUP BY p.product_id, p.product_name ORDER BY invoice_count DESC LIMIT 5;

Question: "What are the top 5 products by sales quantity?"
SQL: SELECT p.product_id, p.product_name, SUM(soi.quantity) as total_quantity FROM products p JOIN sales_order_items soi ON p.product_id = soi.product_id GROUP BY p.product_id, p.product_name ORDER BY total_quantity DESC LIMIT 5;

Question: "Which product has the highest total revenue?"
SQL: SELECT p.product_id, p.product_name, SUM(bi.amount) as total_revenue FROM products p JOIN billing_items bi ON p.product_id = bi.product_id GROUP BY p.product_id, p.product_name ORDER BY total_revenue DESC LIMIT 1;

Question: "Trace invoice 90504298"
SQL: SELECT DISTINCT bd.invoice_id, bd.invoice_date, bd.amount as invoice_amount, bi.delivery_id, d.delivery_date, di.order_id, so.order_date, so.total_amount as order_total, bp.partner_name as customer_name, p.payment_id, p.payment_date FROM billing_documents bd LEFT JOIN billing_items bi ON bd.invoice_id = bi.invoice_id LEFT JOIN deliveries d ON bi.delivery_id = d.delivery_id LEFT JOIN delivery_items di ON d.delivery_id = di.delivery_id LEFT JOIN sales_orders so ON di.order_id = so.order_id LEFT JOIN business_partners bp ON so.partner_id = bp.partner_id LEFT JOIN payments p ON bd.invoice_id = p.invoice_id WHERE bd.invoice_id = '90504298';

Question: "How many invoices have no payment?"
SQL: SELECT COUNT(DISTINCT bd.invoice_id) as unpaid_invoices FROM billing_documents bd LEFT JOIN payments p ON bd.invoice_id = p.invoice_id WHERE p.payment_id IS NULL;

Question: "Show unpaid invoices"
SQL: SELECT DISTINCT bd.invoice_id, bd.invoice_date, bd.amount, bp.partner_name as customer FROM billing_documents bd LEFT JOIN payments p ON bd.invoice_id = p.invoice_id LEFT JOIN business_partners bp ON bd.partner_id = bp.partner_id WHERE p.payment_id IS NULL LIMIT 10;

Question: "Show me products that have never been sold"
SQL: SELECT p.product_id, p.product_name FROM products p LEFT JOIN sales_order_items soi ON p.product_id = soi.product_id WHERE soi.product_id IS NULL;

Question: "Which month had the highest sales?"
SQL: SELECT MONTH(order_date) as sales_month, SUM(total_amount) as total_sales FROM sales_orders GROUP BY sales_month ORDER BY total_sales DESC LIMIT 1;

Question: "What is the revenue trend for March and April?"
SQL: SELECT MONTH(order_date) as month, SUM(total_amount) as total_revenue FROM sales_orders WHERE MONTH(order_date) IN (3, 4) GROUP BY month ORDER BY month;

Question: "Which customer has the most unpaid invoices, and what is the total amount?"
SQL: SELECT bp.partner_name, COUNT(DISTINCT bd.invoice_id) as invoice_count, SUM(bd.amount) as total_unpaid FROM billing_documents bd LEFT JOIN payments p ON bd.invoice_id = p.invoice_id JOIN business_partners bp ON bd.partner_id = bp.partner_id WHERE p.payment_id IS NULL GROUP BY bp.partner_name ORDER BY total_unpaid DESC LIMIT 1;

Question: "Show me all deliveries for order 740598"
SQL: SELECT d.delivery_id, d.delivery_date, d.status FROM deliveries d JOIN delivery_items di ON d.delivery_id = di.delivery_id WHERE di.order_id = '740598';

Question: "Which sales order is linked to delivery 80738109"
SQL: SELECT so.order_id, so.order_date, so.total_amount, bp.partner_name FROM sales_orders so JOIN delivery_items di ON so.order_id = di.order_id JOIN deliveries d ON di.delivery_id = d.delivery_id JOIN business_partners bp ON so.partner_id = bp.partner_id WHERE d.delivery_id = '80738109';

Question: "Who are my top 5 customers by order value?"
SQL: SELECT bp.partner_name, SUM(so.total_amount) as total_spent FROM business_partners bp JOIN sales_orders so ON bp.partner_id = so.partner_id GROUP BY bp.partner_name ORDER BY total_spent DESC LIMIT 5;

Now generate ONLY the SQL query for this question (no other text):
"""

def validate_question(question):
    """Check if question is about business data"""
    question_lower = question.lower()
    
    off_topic = ['weather', 'sports', 'politics', 'movie', 'song', 'poem', 
                 'story', 'write', 'create', 'what is your name', 'who made you']
    
    for keyword in off_topic:
        if keyword in question_lower:
            return False, "I can only answer questions about business data (orders, deliveries, invoices, payments, products, customers)."
    
    business_keywords = ['order', 'delivery', 'invoice', 'payment', 'product', 
                         'customer', 'sale', 'bill', 'shipment', 'item', 'total', 'amount',
                         'revenue', 'trend', 'month', 'year', 'date', 'quarter',
                         'unpaid', 'paid', 'pending', 'complete', 'flow', 'trace',
                         'top', 'most', 'highest', 'lowest', 'average', 'count']
    
    if not any(keyword in question_lower for keyword in business_keywords):
        return False, "Please ask questions related to the business data: orders, deliveries, invoices, payments, products, or customers."
    
    return True, None

def question_to_sql(question):
    """Convert natural language to SQL using Groq - returns ONLY SQL"""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        sql = response.choices[0].message.content.strip()
        
        if '```sql' in sql:
            sql = sql.split('```sql')[1].split('```')[0]
        elif '```' in sql:
            sql = sql.split('```')[1] if len(sql.split('```')) > 1 else sql
        
        sql = sql.strip()
        
        first_word = sql.split()[0].upper() if sql.split() else ''
        if first_word not in ['SELECT', 'WITH', 'SHOW', 'DESCRIBE']:
            select_match = re.search(r'(SELECT\s+.*?;)', sql, re.IGNORECASE | re.DOTALL)
            if select_match:
                sql = select_match.group(1)
            else:
                print(f"Warning: Could not extract SQL from: {sql[:100]}")
                return None
        
        sql = sql.strip()
        
        if sql.endswith(';'):
            sql = sql[:-1]
        
        return sql
        
    except Exception as e:
        print(f"Error generating SQL: {e}")
        return None

def execute_sql(sql):
    """Execute SQL query and return results"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        return {'error': str(e)}

def results_to_answer(question, results, sql):
    """Convert SQL results to natural language answer"""
    
    question_lower = question.lower()
    
    # Handle empty results for delivery-specific queries
    if not results and ('delivery' in question_lower or 'deliveries' in question_lower):
        order_match = re.search(r'order\s+(\d+)', question_lower)
        if order_match:
            order_id = order_match.group(1)
            return f"No deliveries found for order {order_id}. This could mean the order has not been shipped yet or delivery hasn't been recorded."
        
        delivery_match = re.search(r'delivery\s+(\d+)', question_lower)
        if delivery_match:
            delivery_id = delivery_match.group(1)
            return f"No order found for delivery {delivery_id}. This could mean the delivery is not linked to any order or the ID is incorrect."
    
    # FIRST: Check for "never been sold" type queries BEFORE checking if results are empty
    if 'never' in question_lower and ('sold' in question_lower or 'ordered' in question_lower or 'bought' in question_lower):
        if not results:
            return "All products have been sold! Every product in the database has been ordered at least once. No unsold products found."
        else:
            return format_generic_list(results, question)
    
    # THEN: Check if results are empty
    if not results:
        return "I couldn't find any results for your question. Try rephrasing or asking about different data."
    
    if isinstance(results, dict) and 'error' in results:
        return f"I ran into an issue: {results['error']}. Could you try a different question?"
    
    # ---------- MONTHLY SALES QUERIES ----------
    if 'month' in question_lower and ('sales' in question_lower or 'revenue' in question_lower or 'highest' in question_lower):
        return format_monthly_sales(results, question)
    
    # ---------- REVENUE TREND QUERIES ----------
    if 'trend' in question_lower or ('march' in question_lower and 'april' in question_lower):
        return format_revenue_trend(results, question)
    
    # ---------- UNPAID INVOICES BY CUSTOMER ----------
    if 'unpaid invoices' in question_lower and ('customer' in question_lower or 'total amount' in question_lower):
        return format_unpaid_by_customer(results, question)
    
    # ---------- PRODUCT QUERIES ----------
    if 'product' in question_lower and ('most' in question_lower or 'top' in question_lower):
        if 'invoice' in question_lower:
            return format_top_products_by_invoices(results)
        elif 'quantity' in question_lower or 'sold' in question_lower:
            return format_top_products_by_quantity(results)
        elif 'revenue' in question_lower or 'value' in question_lower:
            return format_top_products_by_revenue(results)
    
    # ---------- CUSTOMER QUERIES ----------
    if 'customer' in question_lower and ('top' in question_lower or 'most' in question_lower):
        return format_top_customers(results)
    
    # ---------- TRACE / FLOW QUERIES ----------
    if 'trace' in question_lower or 'flow' in question_lower or 'follow' in question_lower:
        return format_trace_flow(results, question)
    
    # ---------- BROKEN FLOW QUERIES ----------
    if 'broken' in question_lower or 'incomplete' in question_lower or 'not billed' in question_lower or 'not paid' in question_lower:
        return format_broken_flows(results, question)
    
    # ---------- COUNT QUERIES ----------
    if 'how many' in question_lower or 'count' in question_lower or 'total number' in question_lower:
        return format_count_result(results, question)
    
    # ---------- INVOICE/PAYMENT QUERIES ----------
    if 'unpaid' in question_lower or ('invoice' in question_lower and 'payment' in question_lower):
        return format_unpaid_invoices(results)
    
    if 'total revenue' in question_lower or 'total payment' in question_lower:
        return format_total_amount(results)
    
    # ---------- LIST QUERIES (default) ----------
    return format_generic_list(results, question)

# ---------- FORMATTING FUNCTIONS ----------

def format_top_products_by_invoices(results):
    """Format top products by invoice count"""
    if not results:
        return "No product data found."
    
    answer = "Top Products by Number of Invoices\n\n"
    for i, row in enumerate(results[:5], 1):
        product_name = row.get('product_name', row.get('product_id', 'Unknown'))
        count = row.get('invoice_count', row.get('count', 0))
        answer += f"{i}. {product_name} - {count} invoice(s)\n"
    
    if len(results) > 5:
        answer += f"\n...and {len(results) - 5} more products."
    
    return answer

def format_top_products_by_quantity(results):
    """Format top products by quantity sold"""
    if not results:
        return "No product data found."
    
    answer = "Best-Selling Products by Quantity\n\n"
    for i, row in enumerate(results[:5], 1):
        product_name = row.get('product_name', row.get('product_id', 'Unknown'))
        quantity = row.get('total_quantity', row.get('quantity', 0))
        answer += f"{i}. {product_name} - {quantity} units sold\n"
    
    return answer

def format_top_products_by_revenue(results):
    """Format top products by revenue"""
    if not results:
        return "No product data found."
    
    answer = "Top Products by Revenue\n\n"
    for i, row in enumerate(results[:5], 1):
        product_name = row.get('product_name', row.get('product_id', 'Unknown'))
        revenue_value = None
        for key, value in row.items():
            if 'revenue' in key.lower() or 'amount' in key.lower() or 'total' in key.lower():
                revenue_value = value
                break
        if revenue_value is None:
            revenue_value = list(row.values())[-1]
        try:
            revenue = float(revenue_value)
            answer += f"{i}. {product_name} - Rs {revenue:,.2f}\n"
        except (ValueError, TypeError):
            answer += f"{i}. {product_name} - {revenue_value}\n"
    
    return answer

def format_top_customers(results):
    """Format top customers by order value"""
    if not results:
        return "No customer data found."
    
    answer = "Top Customers by Order Value\n\n"
    for i, row in enumerate(results[:5], 1):
        customer = row.get('partner_name', row.get('customer', 'Unknown'))
        total = float(row.get('total_spent', row.get('total_amount', 0)))
        answer += f"{i}. {customer} - Rs {total:,.2f}\n"
    
    return answer

def format_trace_flow(results, question):
    """Format complete flow trace for invoice/order"""
    if not results:
        return "I couldn't trace that document. Please check the ID and try again."
    
    first = results[0]
    
    id_match = re.search(r'(\d+)', question)
    doc_id = id_match.group(1) if id_match else "your document"
    
    answer = f"Complete Flow for Document {doc_id}\n\n"
    
    if first.get('invoice_id'):
        answer += f"Invoice: {first.get('invoice_id')}\n"
        answer += f"  Date: {first.get('invoice_date')}\n"
        answer += f"  Amount: Rs {float(first.get('invoice_amount', 0)):,.2f}\n"
    
    if first.get('delivery_id'):
        answer += f"\nDelivery: {first.get('delivery_id')}\n"
        answer += f"  Date: {first.get('delivery_date')}\n"
    
    if first.get('order_id'):
        answer += f"\nSales Order: {first.get('order_id')}\n"
        answer += f"  Date: {first.get('order_date')}\n"
        answer += f"  Total: Rs {float(first.get('order_total', 0)):,.2f}\n"
    
    if first.get('customer_name'):
        answer += f"\nCustomer: {first.get('customer_name')}\n"
    
    if first.get('payment_id'):
        answer += f"\nPayment: {first.get('payment_id')}\n"
        answer += f"  Date: {first.get('payment_date')}\n"
        answer += f"  Amount: Rs {float(first.get('payment_amount', 0)):,.2f}\n"
    else:
        answer += f"\nPayment: Not yet received\n"
    
    answer += f"\nStatus: "
    if first.get('payment_id'):
        answer += "Complete flow - Order to Delivery to Invoice to Payment"
    elif first.get('invoice_id'):
        answer += "Pending payment - Invoice issued, awaiting payment"
    elif first.get('delivery_id'):
        answer += "Pending billing - Delivered, invoice not yet created"
    else:
        answer += "Order placed, awaiting processing"
    
    return answer

def format_broken_flows(results, question):
    """Format broken/incomplete flows"""
    if not results:
        return "No broken flows found! All orders are complete."
    
    count = len(results)
    question_lower = question.lower()
    
    if 'delivered not billed' in question_lower or 'delivered but not billed' in question_lower:
        answer = f"Delivered but Not Billed\n\n"
        answer += f"I found {count} orders that have been delivered but not yet billed:\n\n"
    elif 'billed not paid' in question_lower:
        answer = f"Billed but Not Paid\n\n"
        answer += f"I found {count} invoices that have been issued but not paid:\n\n"
    else:
        answer = f"Incomplete Flows\n\n"
        answer += f"I found {count} orders with incomplete flows:\n\n"
    
    for i, row in enumerate(results[:10], 1):
        order_id = row.get('order_id', row.get('invoice_id', 'Unknown'))
        customer = row.get('customer', row.get('partner_name', 'Unknown'))
        
        if row.get('delivery_id') and not row.get('invoice_id'):
            answer += f"{i}. Order {order_id} - {customer} - Delivered, No invoice\n"
        elif row.get('invoice_id') and not row.get('payment_id'):
            answer += f"{i}. Invoice {order_id} - {customer} - Invoiced, Not paid\n"
        else:
            answer += f"{i}. {order_id} - {customer}\n"
    
    if count > 10:
        answer += f"\n...and {count - 10} more."
    
    answer += f"\n\nRecommendation: Review these {count} orders to complete the flow."
    
    return answer

def format_count_result(results, question):
    """Format count results naturally"""
    if not results:
        return "I couldn't find any results to count."
    
    count = results[0].get(list(results[0].keys())[0], 0)
    question_lower = question.lower()
    
    if 'order' in question_lower:
        if count == 0:
            return "No orders found matching your criteria."
        elif count == 1:
            return f"I found 1 order matching your query."
        else:
            return f"I found {count} orders matching your criteria."
    
    elif 'product' in question_lower:
        if count == 0:
            return "No products found."
        elif count == 1:
            return f"I found 1 product matching your query."
        else:
            return f"I found {count} products in total."
    
    elif 'invoice' in question_lower:
        if count == 0:
            return "No invoices found."
        elif count == 1:
            return f"I found 1 invoice matching your query."
        else:
            return f"I found {count} invoices matching your criteria."
    
    elif 'customer' in question_lower:
        if count == 0:
            return "No customers found."
        elif count == 1:
            return f"I found 1 customer matching your query."
        else:
            return f"I found {count} customers in total."
    
    elif 'payment' in question_lower:
        if count == 0:
            return "No payments found."
        else:
            return f"I found {count} payments in total."
    
    else:
        return f"The answer is: {count}"

def format_unpaid_invoices(results):
    """Format unpaid invoices"""
    if not results:
        return "Great news! All invoices have been paid."
    
    total_amount = sum(float(row.get('amount', row.get('invoice_amount', 0))) for row in results)
    count = len(results)
    
    answer = f"Unpaid Invoices\n\n"
    answer += f"There are {count} unpaid invoices totaling Rs {total_amount:,.2f}\n\n"
    answer += f"Here are the most recent ones:\n\n"
    
    for i, row in enumerate(results[:5], 1):
        invoice = row.get('invoice_id', 'Unknown')
        amount = float(row.get('amount', row.get('invoice_amount', 0)))
        customer = row.get('customer', row.get('partner_name', 'Unknown'))
        answer += f"{i}. Invoice {invoice} - {customer} - Rs {amount:,.2f}\n"
    
    if count > 5:
        answer += f"\n...and {count - 5} more unpaid invoices."
    
    return answer

def format_total_amount(results):
    """Format total amount results"""
    if not results:
        return "No amount data found."
    
    first_row = results[0]
    amount_value = None
    
    for key, value in first_row.items():
        key_lower = key.lower()
        if any(term in key_lower for term in ['revenue', 'total', 'amount', 'sum']):
            amount_value = value
            break
    
    if amount_value is None:
        last_key = list(first_row.keys())[-1]
        amount_value = first_row[last_key]
    
    try:
        total = float(amount_value)
        return f"Total: Rs {total:,.2f}"
    except (ValueError, TypeError):
        return format_generic_list(results, "total amount")

def format_generic_list(results, question):
    """Generic list formatter"""
    if not results:
        return "No results found."
    
    answer = f"Results\n\n"
    
    for i, row in enumerate(results[:10], 1):
        parts = []
        for key, value in row.items():
            if value is None:
                continue
            if hasattr(value, 'strftime'):
                parts.append(f"{key}: {value.strftime('%Y-%m-%d')}")
            elif hasattr(value, 'quantize'):
                parts.append(f"{key}: Rs {float(value):,.2f}")
            else:
                parts.append(f"{key}: {value}")
        
        answer += f"{i}. " + " | ".join(parts) + "\n"
    
    if len(results) > 10:
        answer += f"\n...and {len(results) - 10} more results."
    
    return answer

def format_monthly_sales(results, question):
    """Format monthly sales results"""
    if not results:
        return "No sales data found for the requested period."
    
    month_names = {1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 
                   6: 'June', 7: 'July', 8: 'August', 9: 'September', 10: 'October', 
                   11: 'November', 12: 'December'}
    
    def get_month_from_row(row):
        for key in ['month', 'sales_month', 'month_num', 0, '0']:
            if key in row:
                return row[key]
        first_key = list(row.keys())[0]
        return row[first_key]
    
    def get_total_from_row(row):
        for key in ['total_sales', 'total_revenue', 'sales', 'revenue']:
            if key in row:
                return row[key]
        last_value = list(row.values())[-1]
        return last_value
    
    if len(results) == 1 and ('highest' in question.lower() or 'high' in question.lower()):
        row = results[0]
        month = get_month_from_row(row)
        total = float(get_total_from_row(row))
        month_name = month_names.get(int(month), month)
        return f"{month_name} 2025 had the highest sales with Rs {total:,.2f}"
    
    answer = "Monthly Sales\n\n"
    for row in results[:6]:
        month = get_month_from_row(row)
        total = float(get_total_from_row(row))
        month_name = month_names.get(int(month), month)
        answer += f"- {month_name}: Rs {total:,.2f}\n"
    
    return answer

def format_revenue_trend(results, question):
    """Format revenue trend results"""
    if not results:
        return "No revenue data found for the requested period."
    
    month_names = {1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 
                   6: 'June', 7: 'July', 8: 'August', 9: 'September', 10: 'October', 
                   11: 'November', 12: 'December'}
    
    answer = "Revenue Trend\n\n"
    month_data = []
    
    for row in results:
        month = None
        for key in ['month', 'sales_month', 'month_num', 0, '0']:
            if key in row:
                month = row[key]
                break
        if month is None and row:
            month = list(row.keys())[0]
        
        total = None
        for key in ['total_revenue', 'total_sales', 'revenue', 'sales']:
            if key in row:
                total = row[key]
                break
        if total is None and row:
            total = list(row.values())[-1]
        
        try:
            total = float(total)
            month_int = int(month) if month else 0
            month_name = month_names.get(month_int, str(month) if month else 'Unknown')
            answer += f"- {month_name} 2025: Rs {total:,.2f}\n"
            month_data.append((month_name, total, month_int))
        except (ValueError, TypeError):
            continue
    
    if not month_data:
        return "No valid revenue data found for the requested period."
    
    if len(month_data) >= 2:
        first_name, first_total, first_month = month_data[0]
        last_name, last_total, last_month = month_data[-1]
        growth = ((last_total - first_total) / first_total * 100) if first_total > 0 else 0
        arrow = "+" if growth > 0 else ""
        answer += f"\nGrowth: {arrow}{growth:.1f}% from {first_name} to {last_name}"
    
    return answer

def format_unpaid_by_customer(results, question):
    """Format unpaid invoices by customer"""
    if not results:
        return "No unpaid invoices found. All invoices have been paid!"
    
    if len(results) == 1:
        customer = results[0].get('partner_name', results[0].get('customer', 'Unknown'))
        total = float(results[0].get('total_unpaid', results[0].get('amount', 0)))
        count = results[0].get('invoice_count', 1)
        
        return f"Customer with Most Unpaid Invoices\n\n{customer} has {count} unpaid invoices totaling Rs {total:,.2f}"
    
    answer = "Unpaid Invoices by Customer\n\n"
    for i, row in enumerate(results[:5], 1):
        customer = row.get('partner_name', row.get('customer', 'Unknown'))
        total = float(row.get('total_unpaid', row.get('amount', 0)))
        count = row.get('invoice_count', 1)
        answer += f"{i}. {customer} - {count} invoices - Rs {total:,.2f}\n"
    
    if len(results) > 5:
        answer += f"\n...and {len(results) - 5} more customers."
    
    return answer

def process_question(question):
    """Main function to process user question"""
    is_valid, error_msg = validate_question(question)
    if not is_valid:
        return {'answer': error_msg, 'is_off_topic': True}
    
    sql = question_to_sql(question)
    if not sql:
        return {'answer': "Sorry, I couldn't generate a query for that question. Please rephrase.", 'sql': None}
    
    print(f"Generated SQL: {sql}")
    
    results = execute_sql(sql)
    answer = results_to_answer(question, results, sql)
    
    return {
        'answer': answer,
        'sql': sql,
        'results': results if isinstance(results, list) else None
    }