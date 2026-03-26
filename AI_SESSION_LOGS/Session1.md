

# Session 1
I need to build a graph-based data query system with LLM integration. What's the best architecture?
Mar 24
Graph-Based Data Query System with LLM Integration
Here's a battle-tested architecture for this kind of system:



Here's how the four layers break down and the key decisions in each:

Interface layer — a single entry point that accepts natural language queries. Keep this thin; all the heavy lifting happens downstream. REST or GraphQL works fine here.

LLM layer — this is where most of the design complexity lives. You need three roles: an intent classifier that categorizes the query (entity lookup, path query, aggregation, etc.), a query translator that converts natural language into your graph query language (Cypher for Neo4j, SPARQL for RDF graphs, Gremlin for property graphs), and an answer synthesizer that turns raw graph results back into natural language.

The translator is the trickiest piece. Few-shot prompting with schema context works well — you feed the LLM your node types, edge types, and a handful of example NL→Cypher pairs. Consider fine-tuning on your domain if query patterns are predictable.

Graph layer — the query engine executes the traversal, the subgraph extractor pulls only the relevant neighborhood (important for keeping results manageable), and the result ranker scores paths by relevance before handing off to the synthesizer. Without ranking, large graphs will flood the LLM context.

Storage layer — three components work together here. The graph database holds your topology. A vector store holds semantic embeddings of nodes so you can seed traversals with a similarity search (hybrid retrieval). A query cache memoizes frequently-hit subgraphs — the dashed feedback arrow in the diagram — so repeated queries skip the LLM translation step entirely.

Key architectural decisions to make early:

The biggest is whether to do query translation (LLM generates Cypher) or retrieval augmentation (LLM never touches the graph directly, only sees pre-fetched context). Translation gives more precise answers for structured questions; retrieval is more robust for fuzzy or open-ended queries. Many production systems do both and route based on intent.

Second is your embedding strategy — whether you embed at the node level, subgraph level, or both affects how good your vector-seeded traversals are.

Third is failure handling in the translation layer. LLMs will occasionally generate invalid queries. You need a validation + retry loop before the query hits the engine, ideally with schema-constrained generation or output validation.

No actually I am parsing the JSON files and storing the relations. I am thinking of using  MySQL to store the relations in RDBMS format and then us JS to visualize the graphs

Mar 24
Got it — that's a much more concrete setup. Let me make sure I understand what you're building before suggesting anything.

Q: What are you parsing from the JSON files?
A: Entity relationships (nodes + edges)

Q: What's the goal of the JS visualization?
A: Explore the graph interactively

Q: Do you have the MySQL schema in mind, or do you need help designing it?
A: I have a schema already

Mar 24
Perfect. So the core pipeline is: JSON → parse nodes/edges → MySQL → JS fetches and renders an interactive graph.

A few quick questions to give you the right recommendations:

[User denied question request]

Mar 24
No problem! Let me give you a solid end-to-end recommendation that works well across most setups.

MySQL schema — the standard adjacency pattern for nodes + edges:

sql
CREATE TABLE nodes (
  id VARCHAR(64) PRIMARY KEY,
  label VARCHAR(255),
  type  VARCHAR(64),
  properties JSON
);

CREATE TABLE edges (
  id        VARCHAR(64) PRIMARY KEY,
  source_id VARCHAR(64) NOT NULL REFERENCES nodes(id),
  target_id VARCHAR(64) NOT NULL REFERENCES nodes(id),
  relation  VARCHAR(64),
  weight    FLOAT DEFAULT 1.0,
  properties JSON
);

CREATE INDEX idx_edges_source ON edges(source_id);
CREATE INDEX idx_edges_target ON edges(target_id);
The properties JSON column keeps it flexible — you don't need to alter the table every time your JSON shape changes.

API endpoint — serve nodes + edges together for a given query:

js
// GET /api/graph?node=<id>&depth=2
app.get('/api/graph', async (req, res) => {
  const { node, depth = 2 } = req.query;

  // Fetch ego-graph up to N hops (recursive CTE — MySQL 8+)
  const [edges] = await db.query(`
    WITH RECURSIVE graph AS (
      SELECT source_id, target_id, relation, 0 AS depth
      FROM edges WHERE source_id = ? OR target_id = ?
      UNION
      SELECT e.source_id, e.target_id, e.relation, g.depth + 1
      FROM edges e JOIN graph g
        ON e.source_id = g.target_id
      WHERE g.depth < ?
    )
    SELECT DISTINCT * FROM graph
  `, [node, node, depth]);

  const nodeIds = [...new Set(edges.flatMap(e => [e.source_id, e.target_id]))];
  const [nodes] = await db.query(
    `SELECT * FROM nodes WHERE id IN (?)`, [nodeIds]
  );

  res.json({ nodes, edges });
});
This avoids fetching the entire graph — you only load the neighborhood around a node, which keeps the viz fast even at scale.

JS visualization — use Cytoscape.js (better for graph topology, filtering, layouts) or D3-force (more control, better for custom styling). Cytoscape is easier to get running:

js
import cytoscape from 'cytoscape';

const { nodes, edges } = await fetch('/api/graph?node=123&depth=2').then(r => r.json());

const cy = cytoscape({
  container: document.getElementById('graph'),
  elements: [
    ...nodes.map(n => ({ data: { id: n.id, label: n.label, type: n.type } })),
    ...edges.map(e => ({ data: { source: e.source_id, target: e.target_id, label: e.relation } }))
  ],
  style: [
    { selector: 'node', style: { label: 'data(label)', 'background-color': '#7F77DD' } },
    { selector: 'edge', style: { label: 'data(label)', 'curve-style': 'bezier', 'target-arrow-shape': 'triangle' } }
  ],
  layout: { name: 'cose' }  // force-directed, good default
});

// Click a node to re-center the graph around it
cy.on('tap', 'node', async evt => {
  const newData = await fetch(`/api/graph?node=${evt.target.id()}&depth=2`).then(r => r.json());
  cy.add([
    ...newData.nodes.map(n => ({ data: { id: n.id, label: n.label } })),
    ...newData.edges.map(e => ({ data: { source: e.source_id, target: e.target_id } }))
  ]);
  cy.layout({ name: 'cose', animate: true }).run();
});
The tap handler is key for large graphs — clicking a node expands its neighborhood lazily rather than loading everything upfront.

The one gotcha with MySQL for graphs — recursive CTEs (needed for multi-hop traversal) are only available in MySQL 8.0+. If you're on 5.7, you'd need to either do the traversal in application code with multiple queries, or store a materialized closure table for fast ancestor/descendant lookups. Worth checking your version early.

Ok, now the system uses an LLM powered chat interface. I am kinda confused regarding this. What will the LLM API actually do here?

Mar 24
Great question — this is the part that confuses most people. Let me break down exactly where the LLM sits in your pipeline.

Without the LLM, your flow is: User types a query → you write the SQL → MySQL returns data → Cytoscape renders it

The LLM's job is to replace you writing the SQL. That's it.

The concrete flow:

User: "Show me all people connected to Alice within 2 hops"
         ↓
LLM receives: [your schema] + [user message]
         ↓
LLM outputs: a SQL query
         ↓
Your backend runs that SQL on MySQL
         ↓
Cytoscape renders the result
So the LLM never touches your database directly. It's just a text-in, SQL-out translator.

What you actually send to the LLM API:

js
const response = await fetch('https://api.anthropic.com/v1/messages', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 1000,
    messages: [
      {
        role: 'user',
        content: `You are a SQL assistant. Given this schema:

nodes(id, label, type, properties)
edges(id, source_id, target_id, relation, weight)

Convert this question to a MySQL query that returns nodes and edges:
"${userQuestion}"

Return only the SQL, no explanation.`
      }
    ]
  })
});

const sql = response.content[0].text;  // e.g. SELECT * FROM edges WHERE ...
Then you run sql against MySQL and feed the result to Cytoscape.

Three things the LLM actually enables that you couldn't easily do otherwise:

Natural language filtering — "show only edges where relation is 'owns'" instead of building a filter UI for every possible relation type
Multi-hop reasoning — "find the shortest path between Alice and Bob" — the LLM can write the recursive CTE for you based on a plain English request
Summarizing what's on screen — after Cytoscape renders a subgraph, you can send the node/edge data back to the LLM and ask "what patterns do you see here?" — it reads the graph data and gives a written summary
The one thing to be careful about:

The LLM can hallucinate column names or table names it wasn't told about. Always validate the generated SQL against your schema before running it — at minimum check that every table/column name in the query actually exists. A simple allowlist check prevents most accidents.

Ok now I haven't worked with graph visualization before. Tell me which JS library shall I use for my work ( easiest). Also show examples of how it works

Mar 25
For your use case — interactive graph exploration fed from MySQL data — Cytoscape.js is the easiest pick. Here's why it beats the alternatives for your situation:

D3-force: very powerful but you hand-code everything — nodes, edges, forces, drag, zoom. 200+ lines for a basic graph.
Sigma.js: great for large graphs but more setup, less intuitive API.
Vis.js Network: close second, good defaults, but Cytoscape has better layout algorithms and a cleaner API for dynamic data loading (which you need for the click-to-expand pattern).
Cytoscape.js: works with plain arrays of nodes/edges (exactly what your MySQL API returns), built-in layouts, built-in interaction events, and minimal boilerplate.
Here's a live interactive demo showing how it works with data shaped exactly like your MySQL output would produce:



The demo above uses data structured exactly like your MySQL API would return. A few things to notice:

Click any node — it lazily fetches and adds that node's neighborhood. This is exactly the pattern you'd use with your real API: GET /api/graph?node=alice&depth=1. Nodes and edges already on screen aren't duplicated.

Hover a node — everything not connected dims out. That's two lines of Cytoscape code using .addClass('dimmed').

Layout buttons — Cytoscape ships with 8+ layouts out of the box. cose (force-directed) is best for general graphs. breadthfirst works well if your data has a natural root/hierarchy.

The three core concepts you need to know:

1. Data goes in as plain arrays — nodes need an id, edges need source and target. Everything else is optional data you can style or display.

2. Styles are CSS-like selectors — node[type="person"] targets nodes where data.type === "person", same as CSS attribute selectors. Color-coding by node type is trivial.

3. Events are jQuery-like — cy.on('tap', 'node', fn) is all you need for interaction. Swap tap for mouseover, mouseout, select, etc.

To connect this to your real MySQL backend, the only change is replacing the getNeighborhood() function with an actual fetch('/api/graph?node='+id) call.

the vis.js seems easier, can I use that?

Mar 25
Absolutely, Vis.js Network is a solid choice too. It's arguably more beginner-friendly because the configuration is more declarative — you just describe what you want rather than building it up piece by piece.

Here's the same demo rebuilt in Vis.js:



The key reason Vis.js feels easier is the DataSet — it's a live data store that the network watches automatically. Adding nodes/edges is just:

js
nodes.add({ id: 'newNode', label: 'New' });
edges.add({ from: 'alice', to: 'newNode', label: 'knows' });
// network re-renders automatically, no manual refresh needed
Compare that to Cytoscape where you call cy.add(...) then manually re-run the layout. Vis.js handles it for you.

The three things you need to wire up for your MySQL backend:

js
// 1. On page load — fetch seed node
const res = await fetch('/api/graph?node=alice&depth=1');
const { nodes: n, edges: e } = await res.json();
buildNetwork(n, e);  // same function from the demo

// 2. On node click — fetch and expand
network.on('click', async (params) => {
  if (!params.nodes.length) return;
  const res = await fetch(`/api/graph?node=${params.nodes[0]}&depth=1`);
  const { nodes: n, edges: e } = await res.json();
  nodes.add(n.filter(...).map(toVisNode));   // skip already-loaded
  edges.add(e.filter(...).map(toVisEdge));
});

// 3. Your MySQL rows map directly to Vis format
// MySQL: { id, label, type }  →  Vis: { id, label, shape, color }
// MySQL: { source_id, target_id, relation }  →  Vis: { from, to, label }
The only real gotcha: Vis.js uses from/to for edges while your MySQL schema uses source_id/target_id — that's just a rename in your toVisEdge() mapping function, as shown in the demo.

ok now suppose this is an example json                                                                                                                            

{"billingDocument": "90504274", "billingDocumentType": "F2", "creationDate": "2025-04-03T00:00:00.000Z", "creationTime": {"hours": 11, "minutes": 31, "seconds": 13}, "lastChangeDateTime": "2025-07-24T11:42:30.485Z", "billingDocumentDate": "2025-04-02T00:00:00.000Z", "billingDocumentIsCancelled": true, "cancelledBillingDocument": "", "totalNetAmount": "253.39", "transactionCurrency": "INR", "companyCode": "ABCD", "fiscalYear": "2025", "accountingDocument": "9400000275", "soldToParty": "320000083"}
       How can I visualize this in vis?

Mar 25
Good example. This is a single billing document with relationships to other entities — soldToParty, companyCode, accountingDocument etc. The visualization strategy is to treat each field as either a node or a property of a node.

Here's how I'd model it:

Nodes: BillingDocument, Customer (soldToParty), CompanyCode, AccountingDocument
Properties: dates, amounts, currency — shown as node details, not separate nodes (otherwise the graph gets cluttered with leaf nodes that have no connections)
Here's a live demo parsing your exact JSON:



The key design decision here is the parser function — it's what converts your flat JSON into nodes + edges. Here's the logic explained:

js
// Your JSON has these "relational" fields → become nodes
soldToParty   → Customer node  (edge: "sold to")
companyCode   → Company node   (edge: "issued by")
accountingDocument → Acc. Doc node (edge: "posts to")

// These fields are just properties → stay as metadata on the billing node
totalNetAmount, creationDate, billingDocumentType, fiscalYear ...
The rule of thumb: if a field references another entity that could have its own connections, make it a node. If it's just a value describing the current entity, keep it as a property.

When you have multiple JSON records (e.g. 100 billing documents), the same parser runs on each — and nodes with the same companyCode or soldToParty automatically merge in the DataSet because they share the same id. That's how shared entities (one customer appearing across many invoices) naturally cluster in the graph.





