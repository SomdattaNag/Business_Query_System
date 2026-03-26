# session 2
This is an example of a json file I need to parse. Show me the most effective way to store it in an RDBMS database      

{"billingDocument": "90504274", "billingDocumentType": "F2", "creationDate": "2025-04-03T00:00:00.000Z", "creationTime": {"hours": 11, "minutes": 31, "seconds": 13}, "lastChangeDateTime": "2025-07-24T11:42:30.485Z", "billingDocumentDate": "2025-04-02T00:00:00.000Z", "billingDocumentIsCancelled": true, "cancelledBillingDocument": "", "totalNetAmount": "253.39", "transactionCurrency": "INR", "companyCode": "ABCD", "fiscalYear": "2025", "accountingDocument": "9400000275", "soldToParty": "320000083"}
Show less
8:57 AM
Here's the most effective approach to store this document in an RDBMS.

The key design decisions are: normalize the composite fields (split creationTime into columns or use a proper TIMESTAMP), type everything correctly (don't store money as VARCHAR), and keep the schema future-proof for multiple document types.

Here's the recommended schema:



Key decisions explained:

Flatten creationTime — your JSON separates creationDate and creationTime into two fields, but they describe a single moment. Merge them into one TIMESTAMPTZ column (created_at). This makes querying by time range trivial and avoids awkward creationDate + creationTime.hours arithmetic in SQL.

Use NUMERIC(15,2) for totalNetAmount — never VARCHAR or FLOAT for money. NUMERIC is exact; floats silently introduce rounding errors. The (15,2) precision handles amounts up to 13 digits with 2 decimal places.

Normalize lookup values — documentType, transactionCurrency, and companyCode are foreign keys into small reference tables (document_types, currencies, company_codes). This enforces referential integrity and lets you join to get human-readable names without bloating the main table.

billingDocument as a unique business key, not the PK — use a surrogate bigint id as the primary key. The billing document number is a unique business identifier (UNIQUE constraint), not a good PK because external systems can sometimes renumber or reuse them.

fiscalYear as SMALLINT — a 2-byte integer is sufficient for a year and is cheaper to index than VARCHAR.

Recommended DDL (PostgreSQL):

sql
CREATE TABLE billing_documents (
    id                    BIGSERIAL PRIMARY KEY,
    billing_document_no   VARCHAR(20)     NOT NULL UNIQUE,
    document_type         VARCHAR(4)      NOT NULL REFERENCES document_types(code),
    document_date         DATE            NOT NULL,
    created_at            TIMESTAMPTZ     NOT NULL,
    last_changed_at       TIMESTAMPTZ,
    is_cancelled          BOOLEAN         NOT NULL DEFAULT FALSE,
    cancelled_document_no VARCHAR(20),
    net_amount            NUMERIC(15, 2)  NOT NULL,
    currency_code         CHAR(3)         NOT NULL REFERENCES currencies(code),
    company_code          VARCHAR(10)     NOT NULL REFERENCES company_codes(code),
    fiscal_year           SMALLINT        NOT NULL,
    accounting_document_no VARCHAR(20),
    sold_to_party         VARCHAR(20)
);

-- Useful indexes
CREATE INDEX ON billing_documents (document_date);
CREATE INDEX ON billing_documents (sold_to_party);
CREATE INDEX ON billing_documents (company_code, fiscal_year);
Parsing note: when ingesting the JSON, combine the two time fields like this before inserting:

python
from datetime import datetime, timezone

created_at = datetime.fromisoformat(record["creationDate"].replace("Z", "+00:00")).replace(
    hour=record["creationTime"]["hours"],
    minute=record["creationTime"]["minutes"],
    second=record["creationTime"]["seconds"]
)
This gives you a single, timezone-aware timestamp ready for the TIMESTAMPTZ column.

no i just want to see a script that stores parsed documents with an existing schema in a DB.           Say this is the table schema

CREATE TABLE IF NOT EXISTS business_partners (
    id INT PRIMARY KEY AUTO_INCREMENT,
    partner_id VARCHAR(50) UNIQUE,
    partner_name VARCHAR(255),
    partner_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
Show more
9:00 AM
What language and database are you using?

What language and database should the script target?

Language: Python, Node.js, Java, or Go?
Database: MySQL, PostgreSQL, SQLite, or SQL Server?
Q: What language should the script be in?
A: Python

Q: What database?
A: MySQL

9:00 AM

Viewed a file, created a file, read a file
Viewed a file, created a file, read a file
Here's what the script does and how to use it:

Setup

bash
pip install mysql-connector-python
Fill in your credentials in the DB_CONFIG dict at the top, then run:

bash
python load_business_partners.py --file data.jsonl
How it works

FIELD_MAP is the central mapping between JSON keys and table columns — if your JSON uses different key names (e.g. "id" instead of "partner_id"), just update that dict. The SQL uses ON DUPLICATE KEY UPDATE so re-running the script on the same file is safe — it upserts rather than erroring on the UNIQUE constraint on partner_id.

Records are committed in configurable batches (default 500 rows), and each batch is individually rolled back on error so one bad batch doesn't abort the whole load. Any line with a missing partner_id is skipped with a warning rather than crashing.

Customising for your actual JSON

Your sample document has fields like billingDocument, soldToParty, etc. If you're mapping a different JSON shape to this table, just update FIELD_MAP — the rest of the script stays the same.

Load business partners
PY 
What if there is active relations between the tables? For example there is another table schema that references the previous one 

CREATE TABLE IF NOT EXISTS sales_orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id VARCHAR(50) UNIQUE,
    partner_id VARCHAR(50),
    order_date DATE,
    status VARCHAR(50),
    total_amount DECIMAL(15,2),
    FOREIGN KEY (partner_id) REFERENCES business_partners(partner_id)
);
Show more
11:11 AM
Good question — the key constraint here is that a sales_orders row cannot be inserted before its referenced business_partners row exists. The script needs to respect that insertion order.

Here's an updated script handling both tables with proper FK dependency management:


Created a file, read a file
Created a file, read a file
The core challenge with FK relations is insertion order and orphan prevention. Here's how the script handles it:

Three-phase load sequence

The script always runs in this order, and it matters:

Parse and split all records by type (record_type field in the JSON)
Commit all business_partners upserts first
Only then insert sales_orders
Partners must be committed — not just in the same transaction — before orders reference them, because MySQL checks FK constraints row-by-row on insert.

Pre-flight FK validation (validate_fk)

Before touching the DB, the script builds the full set of known partner_id values from two sources: what's already in the DB, and what's in the current file. Any order whose partner_id appears in neither is flagged as an orphan and skipped with a warning rather than crashing the whole batch.

Expected JSON shape

Records are routed by a record_type discriminator field:

jsonl
{"record_type": "partner", "partner_id": "320000083", "partner_name": "Acme", "partner_type": "Customer"}
{"record_type": "order", "order_id": "ORD-001", "partner_id": "320000083", "order_date": "2025-04-02", "status": "OPEN", "total_amount": "253.39"}
If your JSON has a different way of distinguishing record types, update the routing logic in parse_jsonl. If partners and orders come from separate files, you can call parse_jsonl twice and merge the results before passing to upsert_all.

Load orders
PY 
