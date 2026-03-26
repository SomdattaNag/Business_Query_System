# session 5

THIS IS THE DUMMY README FILE I HAVE WRITTEN FOR THE PROJECT. WRITE IT PROPERLY, ALSO INCLUDE SOMETHHING TO INCLUDE THE QUERY PROCESSING FLOW 
```
# Business Graph Query System

A graph-based data modeling and query system that transforms fragmented business data (orders, deliveries, invoices, payments) into an interactive graph visualization with natural language querying powered by LLM.

## Features

- **Graph Construction**: Converts relational business data into a graph of interconnected entities
- **Interactive Graph Visualization**: Explore nodes and edges with click, drag, and zoom functionality
- **Natural Language Querying**: Ask questions about your business data in plain English
- **LLM-Powered SQL Generation**: Uses Groq API to convert natural language to MySQL queries
- **Guardrails**: Automatically rejects off-topic questions not related to business data
- **Broken Flow Detection**: Identifies incomplete processes (delivered but not billed, billed but not paid)

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Flask (Python) |
| Database | MySQL |
| Graph Visualization | vis.js |
| LLM Integration | Groq API (Llama 3.3 70B) |
| Frontend | HTML/CSS/JavaScript |
| Deployment | Railway |

## System Architecture

This diagram shows the flow from data ingestion to user interaction.

<p align="center">
  <img src="assets/architecture.png" width="800"/>
</p>


## Database Schema

### Tables

| Table | Description |
|-------|-------------|
| `business_partners` | Customer information |
| `products` | Product master data |
| `sales_orders` | Order headers |
| `sales_order_items` | Order line items |
| `deliveries` | Delivery headers |
| `delivery_items` | Links deliveries to orders |
| `billing_documents` | Invoice headers |
| `billing_items` | Links invoices to deliveries |
| `payments` | Payment records |

### Entity Relationships

Examples of relationships:
- Customer → Order → Product
- Customer → Order → Delivery → Invoice → Payment


## Prerequisites

- Python 3.8+
- MySQL 8.0+
- Groq API Key (free tier available)



# Data Loading
The system loads data from JSONL files into MySQL tables. The loader uses a declarative TABLE_MAPPING approach:
```
TABLE_MAPPING = {
    'business_partners': {
        'table': 'business_partners',
        'columns': ['partner_id', 'partner_name', 'partner_type'],
        'json_keys': ['businessPartner', 'organizationBpName1', 'businessPartnerCategory']
    },
    # ... other tables
}
```
# LLM Prompting Strategy
Core Principle: LLM as SQL Translator
The LLM's sole job is to convert natural language to SQL. It never sees the actual data, only the schema.

Prompt Structure

[CRITICAL RULES]
- Return ONLY SQL
- No explanations
- Must start with SELECT/WITH/SHOW
- Always use DISTINCT
- Use specific tables for specific metrics

[Database Schema]
- Table: columns, relationships

[Examples]
- Question → SQL (3-5 examples)

[Current Question]
Example Prompt Design
text
Question: "Which products have the most invoices?"
SQL: SELECT p.product_id, p.product_name, COUNT(DISTINCT bi.invoice_id) as invoice_count 
FROM products p JOIN billing_items bi ON p.product_id = bi.product_id 
GROUP BY p.product_id, p.product_name ORDER BY invoice_count DESC LIMIT 5;
Key Prompt Engineering Decisions
Decision    Rationale
Return ONLY SQL    Prevents explanatory text that breaks execution
Always use DISTINCT    Avoids duplicate rows from many-to-many joins
Explicit table mapping    Sales quantity → sales_order_items.quantity, Revenue → billing_items.amount
Include relationship paths    Shows exact JOIN patterns for complex flows
Limit results    Always include LIMIT to prevent large responses



# GUARDRAILS IMPLEMENTATION

A two-layer guardrail system ensures safe and relevant querying by first filtering user input using business-specific keywords and rejecting off-topic requests, then validating the generated SQL to block dangerous operations and enforce schema constraints before execution.
```
Show less

10:33 PM

Reading the frontend design skill for creating a polished README
Reading the frontend design skill for creating a polished README
Now let me write a proper, well-structured README with a query processing flow diagram:

Now I have what I need. Let me create a polished README with a proper query processing flow diagram.


Writing a well-structured README for the Business Graph Query System
Writing a well-structured README for the Business Graph Query System
Now let me also create the query processing flow as a proper visual diagram:


Presented file
Presented file


Here's your polished README, along with an interactive query processing flow diagram above (each node is clickable for deeper explanations).

The key improvements made over your draft:

Structure & completeness — Added a table of contents, a proper Getting Started section with numbered steps, and a Deployment section with the required env vars and Procfile example.

Query Processing Flow — Fleshed this out into a full 7-step pipeline with a visual diagram showing both rejection paths (off-topic input → Layer 1 reject, unsafe SQL → Layer 2 reject) and the happy path through to the frontend.

Guardrails — Expanded from a single vague paragraph into two clearly named layers with specific validation rules listed for each.

LLM Prompting — Reorganised the prompt engineering section with a consistent structure: core principle → prompt template → concrete example → rationale table.

Data loading — Added a note explaining the declarative benefit of TABLE_MAPPING (adding a new source only requires a config entry, not code changes).

Readme
Document · MD 