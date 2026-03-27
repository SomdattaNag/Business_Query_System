# Business Graph Query System

A graph-based data modeling and query system that transforms fragmented business data — orders, deliveries, invoices, and payments — into an interactive graph visualization with natural language querying powered by an LLM.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [System Architecture](#system-architecture)
- [Query Processing Flow](#query-processing-flow)
- [Graph Visualization](#graph-visualization)   
- [Database Schema](#database-schema)
- [Data Loading](#data-loading)
- [LLM Prompting Strategy](#llm-prompting-strategy)
- [Guardrails Implementation](#guardrails-implementation)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Deployment](#deployment)

---

## Features

- **Graph Construction** — Converts relational business data into a graph of interconnected entities (customers, orders, deliveries, invoices, payments).
- **Interactive Graph Visualization** — Explore nodes and edges with click, drag, and zoom functionality via vis.js.
- **Natural Language Querying** — Ask questions about your business data in plain English; no SQL knowledge required.
- **LLM-Powered SQL Generation** — Uses the Groq API (Llama 3.3 70B) to translate natural language into executable MySQL queries.
- **Two-Layer Guardrails** — Automatically rejects off-topic questions and validates generated SQL before execution.
- **Broken Flow Detection** — Identifies incomplete business processes such as deliveries without invoices, or invoices without payments.

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Flask (Python) |
| Database | MySQL 8.0 |
| Graph Visualization | vis.js |
| LLM Integration | Groq API — Llama 3.3 70B |
| Frontend | HTML / CSS / JavaScript |
| Deployment | Railway |

---

## System Architecture

The system is composed of three primary layers: a data ingestion layer that loads JSONL files into MySQL, a graph construction layer that builds entity relationships from relational tables, and a query interface that combines vis.js visualization with LLM-powered natural language processing.

```
[ JSONL Data Files ]
        │
        ▼
[ Data Loader (TABLE_MAPPING) ]
        │
        ▼
[ MySQL Database ]
        │
        ├──────────────────────┐
        ▼                      ▼
[ Graph Builder ]       [ NL Query Engine ]
        │                      │
        ▼                      ▼
[ vis.js Frontend ] ←── [ Flask API (Python) ]
```

> For a detailed architecture diagram, see `assets/architecture.png`.

---

## Query Processing Flow

This is the end-to-end pipeline that runs every time a user submits a natural language question.

```
User Input (natural language)
        │
        ▼
┌───────────────────────────┐
│  Layer 1: Input Guardrail  │  ◄── Keyword filter: reject off-topic questions
└───────────────────────────┘
        │ (passes)
        ▼
┌───────────────────────────┐
│   LLM Prompt Builder       │  ◄── Injects schema + few-shot examples into prompt
└───────────────────────────┘
        │
        ▼
┌───────────────────────────┐
│   Groq API (Llama 3.3 70B) │  ◄── Returns raw SQL only — no explanations
└───────────────────────────┘
        │
        ▼
┌───────────────────────────┐
│  Layer 2: SQL Validator    │  ◄── Blocks DDL/DML; enforces schema constraints
└───────────────────────────┘
        │ (valid SELECT)
        ▼
┌───────────────────────────┐
│   MySQL Execution Engine   │
└───────────────────────────┘
        │
        ▼
┌───────────────────────────┐
│   Result Formatter         │  ◄── Formats rows as JSON for the frontend
└───────────────────────────┘
        │
        ▼
   Response to User
```

**Step-by-step breakdown:**

1. **Input Guardrail** — The raw question is checked against a set of business-domain keywords. Questions unrelated to orders, deliveries, invoices, payments, or customers are rejected immediately with a friendly error message, without ever reaching the LLM.

2. **Prompt Builder** — A structured prompt is assembled containing the database schema, table relationships, three to five few-shot examples mapping natural language to correct SQL, and the user's question. The LLM never sees actual data values, only the schema.

3. **LLM Inference (Groq API)** — The prompt is sent to Llama 3.3 70B via the Groq API. The model is instructed to return only a SQL `SELECT` statement — no preamble, no explanation.

4. **SQL Validator** — The returned SQL is checked to ensure it starts with `SELECT` or `WITH`, contains no data-modifying operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`), and references only tables and columns that exist in the schema.

5. **MySQL Execution** — The validated query is run against the MySQL database.

6. **Result Formatter** — Rows are serialized to JSON and returned to the frontend for display.

---
## Graph Visualization

The graph is rendered using **vis.js**, providing full interactivity for users to explore business relationships.

### Interactive Features

| Feature | Description |
|---------|-------------|
| **Pan & Zoom** | Drag to move around, scroll to zoom in/out |
| **Click to Inspect** | Click any node to view metadata in the chat panel |
| **Hover Tooltips** | Mouse over nodes or edges to see labels and relationship types |
| **Drag Nodes** | Reposition nodes manually; physics engine updates connected nodes |
| **Reset View** | Button to fit graph to screen and reset zoom |
| **Toggle Physics** | Enable/disable automatic node movement |

### Node Types & Colors

| Node Type | Color | Description |
|-----------|-------|-------------|
| Customer | Green | Business partner who placed orders |
| Order | Blue | Sales order header |
| Product | Orange | Items ordered |
| Delivery | Purple | Outbound delivery document |
| Invoice | Pink | Billing document |
| Payment | Cyan | Payment record |

### Edge Types & Relationships

| Edge Label | Source → Target | Meaning |
|------------|-----------------|---------|
| `placed_by` | Order → Customer | Customer placed this order |
| `contains` | Order → Product | Order includes this product |
| `fulfills` | Delivery → Order | Delivery fulfills this order |
| `bills` | Invoice → Delivery | Invoice bills this delivery |

### Visual Flow

The graph visually represents the complete business flow:

```
Customer → Order → Delivery → Invoice → Payment
                    ↓
                 Product
```

This visual representation helps users quickly identify:
- **Complete flows** — Full chain from customer to payment
- **Broken flows** — Orders with delivery but no invoice (missing pink node)
- **Product popularity** — Products with many connections to orders


## Database Schema
I chose MySQL for this project because it is a robust relational database that allows us to model graph-based relationships using foreign keys and joins. MySQL is the RDBMS I am most comfortable with, making it ideal for quickly building and iterating on the data model.
### Tables

| Table | Description |
|---|---|
| `business_partners` | Customer master data |
| `products` | Product catalogue |
| `sales_orders` | Order headers |
| `sales_order_items` | Order line items linked to products |
| `deliveries` | Delivery headers |
| `delivery_items` | Links deliveries to sales orders |
| `billing_documents` | Invoice headers |
| `billing_items` | Links invoices to deliveries |
| `payments` | Payment records linked to invoices |

### Entity Relationships

The core business flow runs left to right:

```
Customer → Sales Order → Delivery → Invoice → Payment
              │
              └──► Sales Order Items → Products
```

Broken flows occur when a node exists without its downstream counterpart — for example, a delivery that has no corresponding billing document, or a billing document that has no payment record.

---

## Data Loading

The system loads data from JSONL files into MySQL using a declarative `TABLE_MAPPING` configuration. Each entry maps a source JSON key to a target table column:

```python
TABLE_MAPPING = {
    'business_partners': {
        'table': 'business_partners',
        'columns': ['partner_id', 'partner_name', 'partner_type'],
        'json_keys': ['businessPartner', 'organizationBpName1', 'businessPartnerCategory']
    },
    # ... other tables
}
```

This approach keeps the loader logic generic. To add a new data source, you only need to add an entry to `TABLE_MAPPING` — no changes to the loader itself are required.

---

## LLM Prompting Strategy

### Core principle

The LLM acts solely as a SQL translator. It receives the database schema and a natural language question, and returns executable SQL. It never sees actual data values — only the schema and structural relationships.

### Prompt structure

```
[CRITICAL RULES]
- Return ONLY SQL
- No explanations or preamble
- Query must begin with SELECT, WITH, or SHOW
- Always use DISTINCT to avoid duplicates from many-to-many joins
- Use the explicit table mapping for business metrics

[Database Schema]
- Table name: columns, foreign keys, relationships

[Few-Shot Examples]
- Question → SQL  (3–5 examples)

[Current Question]
<user's question>
```

### Example

**Question:** "Which products have the most invoices?"

**Generated SQL:**
```sql
SELECT p.product_id, p.product_name, COUNT(DISTINCT bi.invoice_id) AS invoice_count
FROM products p
JOIN billing_items bi ON p.product_id = bi.product_id
GROUP BY p.product_id, p.product_name
ORDER BY invoice_count DESC
LIMIT 5;
```

### Key prompt engineering decisions

| Decision | Rationale |
|---|---|
| Return only SQL | Prevents explanatory text that breaks execution |
| Always use `DISTINCT` | Avoids duplicate rows from many-to-many joins |
| Explicit metric-to-table mapping | Pins ambiguous terms: "sales quantity" → `sales_order_items.quantity`, "revenue" → `billing_items.amount` |
| Include JOIN path examples | Shows the exact join chain required for complex cross-table queries |
| Always include `LIMIT` | Prevents runaway responses on large datasets |

---

## Guardrails Implementation

A two-layer system protects the pipeline from misuse and errors.

### Layer 1 — Input filter

Before the question reaches the LLM, it is checked against a whitelist of business-domain keywords (e.g., `order`, `invoice`, `payment`, `customer`, `delivery`, `product`). Questions that contain none of these keywords are rejected immediately with a user-facing message. This prevents the LLM from being used as a general-purpose chatbot and keeps response latency low for invalid queries.

### Layer 2 — SQL validator

After the LLM returns SQL, the validator checks:

- The statement begins with `SELECT`, `WITH`, or `SHOW` — no data-modifying statements are permitted.
- No dangerous keywords are present (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`).
- All referenced table names exist in the known schema.
- The query does not attempt to access system tables or internal metadata.

If either layer rejects the input, a structured error is returned to the frontend and the database is never touched.

---

## Prerequisites

- Python 3.8 or higher
- MySQL 8.0 or higher
- A Groq API key (free tier available at [console.groq.com](https://console.groq.com))

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-org/business-graph-query.git
cd business-graph-query
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=business_graph
```

### 4. Set up the database

```bash
mysql -u root -p < schema.sql
```

### 5. Load sample data

```bash
python load_data.py
```

### 6. Run the application

```bash
flask run
```

Open `http://localhost:5000` in your browser.

---

## Deployment

The application is configured for deployment on [Railway](https://railway.app). Ensure the following environment variables are set in your Railway project settings:

- `GROQ_API_KEY`
- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `FLASK_ENV=production`

A `Procfile` is included for Railway's build detection:

```
web: gunicorn app:app
```

# LIVE DEMO:
https://web-production-8e6a8.up.railway.app/
