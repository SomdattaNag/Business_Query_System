// Chat functionality
document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('question-input');
    const sendButton = document.getElementById('send-button');
    
    sendButton.addEventListener('click', sendQuestion);
    input.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendQuestion();
        }
    });
});

async function sendQuestion() {
    const input = document.getElementById('question-input');
    const question = input.value.trim();
    
    if (!question) return;
    
    // Add user message
    addMessage('user', question);
    input.value = '';
    
    // Show typing indicator
    showTypingIndicator();
    
    try {
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question: question })
        });
        
        const data = await response.json();
        
        // Remove typing indicator
        removeTypingIndicator();
        
        // Add response
        if (data.answer) {
            addMessage('assistant', data.answer);
            
            // If SQL was executed and results exist, optionally highlight related nodes
            if (data.related_entities && window.highlightNodes) {
                window.highlightNodes(data.related_entities);
            }
        } else if (data.error) {
            addMessage('error', `❌ Error: ${data.error}`);
        } else {
            addMessage('error', 'Sorry, I could not process that question.');
        }
        
    } catch (error) {
        removeTypingIndicator();
        addMessage('error', `❌ Network error: ${error.message}`);
        console.error('Error:', error);
    }
}

function addMessage(role, content) {
    const messagesDiv = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    
    // Handle different message types
    let className = 'message';
    if (role === 'user') className += ' user';
    else if (role === 'assistant') className += ' assistant';
    else if (role === 'error') className += ' error';
    else className += ' system';
    
    messageDiv.className = className;
    
    // Format content with line breaks
    messageDiv.style.whiteSpace = 'pre-wrap';
    messageDiv.textContent = content;
    
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function showTypingIndicator() {
    const messagesDiv = document.getElementById('chat-messages');
    const indicator = document.createElement('div');
    indicator.className = 'message assistant';
    indicator.id = 'typing-indicator';
    indicator.innerHTML = '<div class="typing-indicator">🤔 Thinking<span>.</span><span>.</span><span>.</span></div>';
    messagesDiv.appendChild(indicator);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// Make this available to graph.js
window.addSystemMessage = function(content) {
    addMessage('system', content);
};

// Auto-resize input? Not needed but nice to have
document.getElementById('question-input')?.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 100) + 'px';
});