import json
import os
from pathlib import Path
import mysql.connector
from dotenv import load_dotenv


load_dotenv()

# database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'business_graph'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'port': int(os.getenv('DB_PORT', 3306))
}

#dataset
BASE_PATH = Path('dataset/sap-o2c-data')

# TABLE MAPPING
TABLE_MAPPING = {
    'business_partners': {
        'table': 'business_partners',
        'columns': ['partner_id', 'partner_name', 'partner_type'],
        'json_keys': ['businessPartner', 'organizationBpName1', 'businessPartnerCategory']
    },
    'products': {
        'table': 'products',
        'columns': ['product_id', 'product_name'],
        'json_keys': ['product', 'productOldId']
    },
    'sales_order_headers': {
        'table': 'sales_orders',
        'columns': ['order_id', 'partner_id', 'order_date', 'status', 'total_amount'],
        'json_keys': ['salesOrder', 'soldToParty', 'creationDate', 'overallDeliveryStatus', 'totalNetAmount']
    },
    'sales_order_items': {
        'table': 'sales_order_items',
        'columns': ['order_id', 'product_id', 'quantity', 'unit_price'],
        'json_keys': ['salesOrder', 'material', 'requestedQuantity', 'netAmount']
    },
    'outbound_delivery_headers': {
        'table': 'deliveries',
        'columns': ['delivery_id', 'delivery_date', 'status'],
        'json_keys': ['deliveryDocument', 'creationDate', 'overallGoodsMovementStatus']
    },
    'outbound_delivery_items': {
        'table': 'delivery_items',
        'columns': ['delivery_id', 'order_id', 'product_id', 'quantity'],
        'json_keys': ['deliveryDocument', 'referenceSdDocument', 'material', 'actualDeliveryQuantity']
    },
    'billing_document_headers': {
        'table': 'billing_documents',
        'columns': ['invoice_id', 'invoice_date', 'amount', 'status', 'partner_id'],
        'json_keys': ['billingDocument', 'billingDocumentDate', 'totalNetAmount', 'billingDocumentIsCancelled', 'soldToParty']
    },
    'billing_document_items': {
        'table': 'billing_items',
        'columns': ['invoice_id', 'delivery_id', 'product_id', 'quantity', 'amount'],
        'json_keys': ['billingDocument', 'referenceSdDocument', 'material', 'billingQuantity', 'netAmount']
    },
    'payments_accounts_receivable': {
        'table': 'payments',
        'columns': ['payment_id', 'invoice_id', 'payment_date', 'amount'],
        'json_keys': ['accountingDocument', 'invoiceReference', 'clearingDate', 'amountInTransactionCurrency']
    }
}

def test_connection():
    #Test MySQL connection
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        print("successfully connected to mySQL")
        conn.close()
        return True
    except Exception as e:
        print(f"Cannot connect to MySQL: {e}")
        return False

def load_table(folder_name, config):
    
    print(f"\n📦 Loading {folder_name}...")
    
    # Check folder
    folder_path = BASE_PATH / folder_name
    if not folder_path.exists():
        print(f" Folder not found: {folder_path}")
        return 0
    
    # Find JSONL files
    jsonl_files = list(folder_path.glob("*.jsonl"))
    if not jsonl_files:
        print(f"no JSONL files found")
        return 0
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    count = 0
    error_count = 0
    
    #build SQL query
    placeholders = ', '.join(['%s'] * len(config['columns']))
    columns = ', '.join(config['columns'])
    sql = f"INSERT IGNORE INTO {config['table']} ({columns}) VALUES ({placeholders})"
    
    for file_path in jsonl_files:
        print(f' Reading {file_path.name}')
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        record = json.loads(line)
                        
                        #extract values based on JSON keys
                        values = []
                        for key in config['json_keys']:
                            value = record.get(key)
                            # Handle date conversion (remove timestamp)
                            if isinstance(value, str) and 'T' in value and 'Date' in key:
                                value = value.split('T')[0]
                            values.append(value)
                        
                        cursor.execute(sql, values)
                        count += 1
                        
                        if count % 500 == 0:
                            conn.commit()
                            print(f"Loaded {count} records...")
                            
                    except Exception as e:
                        error_count += 1
                        if error_count <= 5:
                            print(f"Error at line {line_num}: {e}")
                        continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"   ✅ Loaded {count} records into {config['table']}")
    if error_count > 0:
        print(f'Skipped {error_count} records')
    
    return count

def main():
    
    print("BUSINESS GRAPH DATA LOADER")

    
    # Check if dataset exists
    if not BASE_PATH.exists():
        print(f"\n dataset folder not found: {BASE_PATH}")
        return
    
    # Test connection
    if not test_connection():
        return
    
    # Show what will be loaded
    print(f"\n Tables to load: {len(TABLE_MAPPING)}")
    for folder_name in TABLE_MAPPING.keys():
        print(f"   - {folder_name}")
    
    # Confirm
    confirm = input("\nProceed with loading? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return
    
    #load all tables
    total = 0
    for folder_name, config in TABLE_MAPPING.items():
        count = load_table(folder_name, config)
        total += count
    
   
    
    print("✅ DATA LOADING COMPLETE!")
  
    print(f"Total records loaded: {total}")
   

if __name__ == "__main__":
    main()