// Global variables
let network = null;
let physicsEnabled = true;
let allNodes = [];
let allEdges = [];

// Load graph data when page loads
document.addEventListener('DOMContentLoaded', function() {
    loadGraph();
});

async function loadGraph() {
    const container = document.getElementById('graph-container');
    
    // Show loading indicator
    container.innerHTML = '<div style="display: flex; justify-content: center; align-items: center; height: 100%;"><div class="loading"></div><span style="margin-left: 10px;">Loading graph...</span></div>';
    
    try {
        const response = await fetch('/api/graph-data');
        const data = await response.json();
        
        // Prepare nodes for vis.js
        const nodes = data.nodes.map(node => ({
            id: node.id,
            label: node.label.length > 20 ? node.label.substring(0, 17) + '...' : node.label,
            title: `${node.type}: ${node.label}`,
            group: node.type,
            color: getNodeColor(node.type),
            font: { size: 12 }
        }));
        
        // Prepare edges
        const edges = data.edges.map(edge => ({
            from: edge.from,
            to: edge.to,
            label: edge.label,
            arrows: 'to',
            font: { size: 10, align: 'middle' }
        }));
        
        allNodes = nodes;
        allEdges = edges;
        
        // Update node count display
        document.getElementById('node-count').textContent = `${nodes.length} nodes, ${edges.length} edges`;
        
        // Create network
        const networkData = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };
        const options = {
            nodes: {
                shape: 'dot',
                size: 20,
                borderWidth: 2,
                shadow: true,
                font: { size: 12 }
            },
            edges: {
                smooth: { type: 'cubicBezier', forceDirection: 'none' },
                arrows: 'to',
                font: { size: 10, align: 'middle' },
                color: { color: '#848484', highlight: '#667eea' }
            },
            physics: {
                enabled: true,
                stabilization: { iterations: 100 },
                solver: 'forceAtlas2Based',
                forceAtlas2Based: { gravitationalConstant: -50 }
            },
            interaction: {
                hover: true,
                tooltipDelay: 100,
                navigationButtons: true,
                zoomView: true,
                dragView: true
            },
            layout: {
                improvedLayout: true
            }
        };
        
        network = new vis.Network(container, networkData, options);
        
        // Wait for stabilization
        network.once('stabilizationIterationsDone', function() {
            network.fit();
        });
        
        // Add click handler
        network.on('click', function(params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const node = network.body.data.nodes.get(nodeId);
                fetchNodeDetails(nodeId, node);
            }
        });
        
        // Add double-click handler for expanding
        network.on('doubleClick', function(params) {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                expandNode(nodeId);
            }
        });
        
        console.log('✅ Graph loaded successfully');
        
    } catch (error) {
        console.error('Error loading graph:', error);
        container.innerHTML = '<div style="display: flex; justify-content: center; align-items: center; height: 100%; color: red;">❌ Error loading graph. Check console for details.</div>';
    }
}

function getNodeColor(type) {
    const colors = {
        'customer': '#4CAF50',
        'order': '#2196F3',
        'product': '#FF9800',
        'delivery': '#9C27B0',
        'invoice': '#E91E63',
        'payment': '#00BCD4'
    };
    return colors[type] || '#607D8B';
}

async function fetchNodeDetails(nodeId, node) {
    try {
        const response = await fetch(`/api/node/${nodeId}`);
        const data = await response.json();
        
        if (data.details) {
            // Format details nicely
            let detailsText = `📌 **${node.label}** (${node.group})\n\n`;
            for (const [key, value] of Object.entries(data.details)) {
                if (value && key !== 'id') {
                    detailsText += `• ${key}: ${value}\n`;
                }
            }
            
            if (window.addSystemMessage) {
                window.addSystemMessage(detailsText);
            }
        } else {
            if (window.addSystemMessage) {
                window.addSystemMessage(`📌 Selected: ${node.label}\nType: ${node.group}`);
            }
        }
    } catch (error) {
        console.error('Error fetching node details:', error);
        if (window.addSystemMessage) {
            window.addSystemMessage(`📌 Selected: ${node.label}\nType: ${node.group}`);
        }
    }
}

async function expandNode(nodeId) {
    // Future enhancement: load connected nodes dynamically
    if (window.addSystemMessage) {
        window.addSystemMessage(`🔍 Expanding node: ${nodeId} (feature coming soon)`);
    }
}

function resetGraph() {
    if (network) {
        network.fit();
        network.moveTo({ scale: 1 });
    }
}

function togglePhysics() {
    if (network) {
        physicsEnabled = !physicsEnabled;
        network.setOptions({ physics: { enabled: physicsEnabled } });
        const btn = document.querySelector('.graph-controls button:last-child');
        if (btn) btn.textContent = physicsEnabled ? 'Disable Physics' : 'Enable Physics';
    }
}

function highlightNodes(nodeIds) {
    if (!network) return;
    
    const allNodesData = network.body.data.nodes.get();
    const updates = {};
    
    allNodesData.forEach(node => {
        updates[node.id] = {
            color: nodeIds.includes(node.id) ? '#ff0000' : getNodeColor(node.group),
            borderWidth: nodeIds.includes(node.id) ? 3 : 2
        };
    });
    
    network.body.data.nodes.update(updates);
}

// Make functions available globally
window.resetGraph = resetGraph;
window.togglePhysics = togglePhysics;
window.highlightNodes = highlightNodes;