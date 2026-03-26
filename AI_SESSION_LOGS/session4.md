
# session 4

Give an example LLM configuration script. The data is loaded into the database , and it's format is in this script .

6:29 PM
I'll create an example LLM configuration script that connects to this MySQL database and enables natural language querying over the O2C (Order-to-Cash) data.


Viewed a file, created a file, read a file
Viewed a file, created a file, read a file
Here's a breakdown of the 9 sections in the script:

Configuration layers

DB_CONFIG — mirrors the exact same env-var pattern from your loader, so both scripts share a single .env file.
SCHEMA_CONTEXT — a precise description of every table, column, data type, and foreign key relationship, derived directly from your TABLE_MAPPING. This is what lets Claude write correct SQL without guessing.
SYSTEM_PROMPT — wraps the schema context with behavioral rules (no SELECT *, 20-row limits, currency formatting, etc.).
Execution engine

run_query() — executes any SQL and returns rows as a list of dicts (or an error string).
TOOLS — exposes an execute_sql tool so Claude can request DB calls mid-conversation rather than hallucinating results.
ask() — runs a tool-use loop: Claude writes SQL → your code executes it → results fed back → Claude interprets and responds.
Interface modes

Interactive CLI — conversational REPL with history, clear, and examples commands.
query_once() — single-call function for programmatic / API use: from llm_query_config import query_once.
To run it:

bash
pip install anthropic mysql-connector-python python-dotenv
Add ANTHROPIC_API_KEY to your .env file
python llm_query_config.py
Llm query config
PY 
what does this error means? Trace the full flow of a given billing document (Sales Order → Delivery → Billing → Journal Entry)
Query error: 1064 (42000): You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '[given_invoice_id]' at line 34

7:29 PM
This error means Claude generated literal placeholder text ([given_invoice_id]) in the SQL instead of a real value — it's a template substitution bug, not a database or schema error.

Here's the full flow of what happened:

The root cause: The system prompt says "Trace the full flow of a given billing document" but no actual invoice ID was provided. Claude tried to write the SQL anyway and used [given_invoice_id] as a placeholder, which is invalid MySQL syntax. MySQL saw the square bracket and threw a syntax error at line 34.

The fix is twofold — update the system prompt to handle ambiguous inputs, and add SQL validation before execution. Here's the patched section:


Read the current script
Read the current script
Now I'll apply all three fixes: SQL placeholder validation, a clearer clarification rule in the system prompt, and a "list available IDs" helper query.


Edited 2 files
Edited 2 files
Claude's response was interrupted
Nevermind i see it

7:30 PM
Got it! Let me know if you run into anything else or need further changes to the script. 😊

What can be possible reasons Trace the full flow of billing document, "90504298"(Sales Order → Delivery → Billing → Journal Entry)
No results found for your query.

7:31 PM
"No results found" means the query ran successfully (no syntax error this time!) but returned empty rows. Here are the likely reasons:

1. ID doesn't exist in the database The most common cause. The value 90504298 may simply not be present in billing_documents.invoice_id. Worth verifying with:

sql
SELECT invoice_id FROM billing_documents 
WHERE invoice_id = '90504298' OR invoice_id LIKE '%90504298%' LIMIT 5;
2. Data type mismatch Your loader stores invoice_id as it came from the JSONL (billingDocument key). If it was loaded as an integer but Claude is querying it as a string (or vice versa), the WHERE clause silently matches nothing.

3. The ID belongs to a different document type SAP often uses overlapping number ranges. 90504298 might be a sales order ID or delivery ID, not a billing document ID. Try checking across tables:

sql
SELECT 'sales_order'     AS found_in FROM sales_orders       WHERE order_id    = '90504298'
UNION ALL
SELECT 'delivery'        AS found_in FROM deliveries         WHERE delivery_id = '90504298'
UNION ALL
SELECT 'billing_doc'     AS found_in FROM billing_documents  WHERE invoice_id  = '90504298';
4. Data was never loaded If the loader hit errors or skipped records for billing_document_headers, that document may be missing entirely. Check your loader output for ⚠️ Skipped N records warnings for that folder.

5. JOIN chain breaks mid-flow Even if the billing document exists, if any link in the chain (billing_items → delivery_items → sales_order_items) has a missing foreign key row, the full-flow JOIN returns nothing. Querying each table in isolation would pinpoint exactly where the chain breaks.

Quick diagnostic — run this to find valid billing document IDs you can trace:

sql
SELECT bd.invoice_id, bd.invoice_date, bd.amount, bp.partner_name
FROM billing_documents bd
JOIN business_partners bp ON bd.partner_id = bp.partner_id
LIMIT 10;
Then retry the trace with one of those confirmed IDs.

what can be the possible problem here? It's showing 5-10 orders but why is the count only 3? Found 17 records. Showing first 5:
1. {'order_id': '740506'}
2. {'order_id': '740507'}
3. {'order_id': '740508'}
4. {'order_id': '740584'}
5. {'order_id': '740585'}
SHOW MORE
Please ask questions related to the business data: orders, deliveries, invoices, payments, products, or customers.
NO I MEANT YOU ONLY SHOWED THE 1ST 5 ORDERS THAT HAVE BROKEN OR INCOMPLETE FLOWS, SHOW MORE SAY 10
Found 10 results:
1. invoice_id: 90504248, invoice_date: 2025-04-02, invoice_amount: 216.10, delivery_id: 80738072, delivery_date: 2025-04-02, order_id: 740552, order_date: 2025-04-02, order_total: 216.10, customer_name: Torres-Williams, payment_id: None, payment_date: None, payment_amount: None
2. invoice_id: 90504248, invoice_date: 2025-04-02, invoice_amount: 216.10, delivery_id: 80738072, delivery_date: 2025-04-02, order_id: 740552, order_date: 2025-04-02, order_total: 216.10, customer_name: Torres-Williams, payment_id: None, payment_date: None, payment_amount: None
3. invoice_id: 90628265, invoice_date: 2025-04-30, invoice_amount: 245.90, delivery_id: 80754575, delivery_date: 2025-04-07, order_id: 740543, order_date: 2025-04-02, order_total: 245.90, customer_name: Nguyen-Davis, payment_id: None, payment_date: None, payment_amount: None
4. invoice_id: 90628265, invoice_date: 2025-04-30, invoice_amount: 245.90, delivery_id: 80754575, delivery_date: 2025-04-07, order_id: 740543, order_date: 2025-04-02, order_total: 245.90, customer_name: Nguyen-Davis, payment_id: None, payment_date: None, payment_amount: None
5. invoice_id: 90628266, invoice_date: 2025-04-30, invoice_amount: 287.90, delivery_id: 80754576, delivery_date: 2025-04-07, order_id: 740544, order_date: 2025-04-02, order_total: 287.90, customer_name: Nguyen-Davis, payment_id: None, payment_date: None, payment_amount: None
6. invoice_id: 90628266, invoice_date: 2025-04-30, invoice_amount: 287.90, delivery_id: 80754576, delivery_date: 2025-04-07, order_id: 740544, order_date: 2025-04-02, order_total: 287.90, customer_name: Nguyen-Davis, payment_id: None, payment_date: None, payment_amount: None
7. invoice_id: 90504274, invoice_date: 2025-04-02, invoice_amount: 253.39, delivery_id: 80738091, delivery_date: 2025-04-02, order_id: 740571, order_date: 2025-04-02, order_total: 253.39, customer_name: Torres-Williams, payment_id: None, payment_date: None, payment_amount: None
8. invoice_id: 90504274, invoice_date: 2025-04-02, invoice_amount: 253.39, delivery_id: 80738091, delivery_date: 2025-04-02, order_id: 740571, order_date: 2025-04-02, order_total: 253.39, customer_name: Torres-Williams, payment_id: None, payment_date: None, payment_amount: None
9. invoice_id: 90504242, invoice_date: 2025-04-02, invoice_amount: 151.69, delivery_id: 80738068, delivery_date: 2025-04-02, order_id: 740548, order_date: 2025-04-02, order_total: 151.69, customer_name: Torres-Williams, payment_id: None, payment_date: None, payment_amount: None
10. invoice_id: 90504242, invoice_date: 2025-04-02, invoice_amount: 151.69, delivery_id: 80738068, delivery_date: 2025-04-02, order_id: 740548, order_date: 2025-04-02, order_total: 151.69, customer_name: Torres-Williams, payment_id: None, payment_date: None, payment_amount: None
Total how many such orders are there?
The answer is: 3
Total how many orders that have broken flows are there?
The answer is: 3

Show more
7:33 PM
You've actually spotted two separate bugs here. Let me break them down:

Bug 1 — Duplicate rows (every record appears twice)

Rows 1&2, 3&4, 5&6, 7&8, 9&10 are exact duplicates. This is a JOIN fan-out problem. When Claude joins billing_items to delivery_items, if either table has multiple line items for the same document, the JOIN multiplies the rows (a classic cartesian product side-effect). The query is missing a DISTINCT or GROUP BY, so each unique flow appears once per product line item combination.

Fix in the query:

sql
SELECT DISTINCT bd.invoice_id, bd.invoice_date ...
-- or GROUP BY bd.invoice_id
Bug 2 — Count says 3 but 10 rows shown (5 unique invoices)

This is directly caused by Bug 1. The COUNT(*) or COUNT(DISTINCT order_id) query Claude wrote is counting order IDs, not invoice IDs or full flow records. Since there are only 3 unique order_id values across those 10 rows (740552, 740543, 740544... etc.), it returns 3.

The count query and the listing query are measuring different things — one counts orders, the other lists invoices.

Fix: The count query should use COUNT(DISTINCT bd.invoice_id) to match what the listing query actually shows.

Bug 3 — The real business finding (worth noting)

All 10 rows have payment_id: None — meaning these are invoices with no payment received. That's the actual broken flow: the O2C chain completes through billing but never reaches payment/clearing. This is likely genuine outstanding AR (Accounts Receivable), not a data error.

Quick summary of what's actually happening:

Issue	Cause	Fix
Duplicate rows	Multi-item JOIN fan-out	Add DISTINCT or GROUP BY invoice_id
Count = 3 vs 5 shown	Counting order_id not invoice_id	Use COUNT(DISTINCT invoice_id)
payment = None	Real unpaid invoices in AR	Business issue, not a bug
Would you like me to update the script to add a DISTINCT guard and align the count query automatically?

yes

7:33 PM

Read current script to find the right sections to patch
Read current script to find the right sections to patch
Now I'll apply all three fixes in one go:


Edited 5 files, read a file
Edited 5 files, read a file
Three fixes applied:

Fix 1 — System prompt: DISTINCT rule Claude is now explicitly instructed to always use SELECT DISTINCT (or GROUP BY on the header key) on any query that joins through item-level tables. A canonical example pattern is included so it has a template to follow.

Fix 2 — System prompt: COUNT alignment rule Claude must now use COUNT(DISTINCT invoice_id) — matching whatever unit the listing query shows — and never use bare COUNT(*) on a JOIN result. This is what was causing the "10 rows shown but count = 3" mismatch.

Fix 3 — run_query(): automatic dedup safety net Even if Claude ever forgets the DISTINCT rule, the Python layer now catches exact duplicate dicts, silently removes them, and prints a console warning like:

⚠  [dedup] Removed 5 duplicate row(s) caused by JOIN fan-out. Add DISTINCT or GROUP BY to the query.
This acts as a backstop so users never see duplicate rows regardless.

Llm query config
PY 