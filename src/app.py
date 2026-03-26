from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import os
import mysql.connector
from dotenv import load_dotenv
from llm import process_question, validate_question


def get_db_connection():
    # Check if Railway provides MYSQL_URL
    if os.getenv('MYSQL_URL'):
        import re
        url = os.getenv('MYSQL_URL')
        # Parse mysql://user:pass@host:port/database
        match = re.match(r'mysql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', url)
        if match:
            config = {
                'host': match.group(3),
                'database': match.group(5),
                'user': match.group(1),
                'password': match.group(2),
                'port': int(match.group(4))
            }
            return mysql.connector.connect(**config)
    else:
        # Local development
        return mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'business_graph'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            port=int(os.getenv('DB_PORT', 3306))
        )
        
load_dotenv()

app = Flask(__name__)
CORS(app)

# Database config
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'business_graph'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'port': int(os.getenv('DB_PORT', 3306))
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'message': 'Business Graph Query System is running!'})

@app.route('/api/graph-data')
def graph_data():
    """Return real graph data from MySQL"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get nodes (limited for performance)
    nodes = []
    
    # Customers
    cursor.execute("SELECT partner_id as id, partner_name as label, 'customer' as type FROM business_partners LIMIT 20")
    nodes.extend(cursor.fetchall())
    
    # Orders
    cursor.execute("SELECT order_id as id, order_id as label, 'order' as type FROM sales_orders LIMIT 50")
    nodes.extend(cursor.fetchall())
    
    # Products
    cursor.execute("SELECT product_id as id, product_name as label, 'product' as type FROM products LIMIT 30")
    nodes.extend(cursor.fetchall())
    
    # Deliveries
    cursor.execute("SELECT delivery_id as id, delivery_id as label, 'delivery' as type FROM deliveries LIMIT 30")
    nodes.extend(cursor.fetchall())
    
    # Invoices
    cursor.execute("SELECT invoice_id as id, invoice_id as label, 'invoice' as type FROM billing_documents LIMIT 30")
    nodes.extend(cursor.fetchall())
    
    # Get edges (relationships)
    edges = []
    
    # Order → Customer
    cursor.execute("""
        SELECT so.order_id as source, so.partner_id as target, 'placed_by' as type
        FROM sales_orders so LIMIT 50
    """)
    edges.extend(cursor.fetchall())
    
    # Order → Product (via order items)
    cursor.execute("""
        SELECT soi.order_id as source, soi.product_id as target, 'contains' as type
        FROM sales_order_items soi LIMIT 100
    """)
    edges.extend(cursor.fetchall())
    
    # Delivery → Order (via delivery items)
    cursor.execute("""
        SELECT di.delivery_id as source, di.order_id as target, 'fulfills' as type
        FROM delivery_items di LIMIT 100
    """)
    edges.extend(cursor.fetchall())
    
    # Invoice → Delivery (via billing items)
    cursor.execute("""
        SELECT bi.invoice_id as source, bi.delivery_id as target, 'bills' as type
        FROM billing_items bi LIMIT 100
    """)
    edges.extend(cursor.fetchall())
    
    cursor.close()
    conn.close()
    
    # Convert to format expected by vis.js
    vis_nodes = []
    for node in nodes:
        vis_nodes.append({
            'id': node['id'],
            'label': node['label'],
            'type': node['type']
        })
    
    vis_edges = []
    for edge in edges:
        vis_edges.append({
            'from': edge['source'],
            'to': edge['target'],
            'label': edge['type']
        })
    
    return jsonify({'nodes': vis_nodes, 'edges': vis_edges})

@app.route('/api/node/<node_id>')
def node_details(node_id):
    """Get details for a specific node"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    result = None
    
    # Check customers
    cursor.execute("SELECT * FROM business_partners WHERE partner_id = %s", (node_id,))
    result = cursor.fetchone()
    
    if not result:
        cursor.execute("SELECT * FROM sales_orders WHERE order_id = %s", (node_id,))
        result = cursor.fetchone()
    
    if not result:
        cursor.execute("SELECT * FROM products WHERE product_id = %s", (node_id,))
        result = cursor.fetchone()
    
    if not result:
        cursor.execute("SELECT * FROM deliveries WHERE delivery_id = %s", (node_id,))
        result = cursor.fetchone()
    
    if not result:
        cursor.execute("SELECT * FROM billing_documents WHERE invoice_id = %s", (node_id,))
        result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if result:
        # Convert datetime objects to strings for JSON serialization
        for key, value in result.items():
            if hasattr(value, 'isoformat'):
                result[key] = value.isoformat()
        return jsonify({'details': result})
    else:
        return jsonify({'error': 'Node not found'}), 404

@app.route('/api/query', methods=['POST'])
def process_user_query():
    """Process natural language query using Groq LLM"""
    data = request.json
    question = data.get('question', '')
    
    # First, validate with guardrails
    is_valid, error_msg = validate_question(question)
    if not is_valid:
        return jsonify({
            'answer': error_msg,
            'is_off_topic': True
        })
    
    # Process with LLM
    result = process_question(question)
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)