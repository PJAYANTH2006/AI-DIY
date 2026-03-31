document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chatMessages');
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const typingIndicator = document.getElementById('typingIndicator');
    const promptChips = document.querySelectorAll('.prompt-chip');
    const clearChatBtn = document.getElementById('clearChatBtn');
    
    // Core state: conversational history required for stateless serverless backend
    let conversationHistory = [];

    // System/User svg icons
    const botIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>`;
    const userIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;

    // Formatting markdown-like text to basic HTML (bolding, lists)
    function formatMessage(text) {
        // Simple formatter since Gemini often returns markdown
        let formatted = text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n- /g, '<br>• ');
        
        // Wrap in p tags if entirely plain string originally
        if (!formatted.startsWith('<')) {
            formatted = `<p>${formatted}</p>`;
        }
        return formatted;
    }

    function addMessage(content, isUser) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'system-message'}`;
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = `avatar ${isUser ? 'user-avatar' : 'system-avatar'}`;
        avatarDiv.innerHTML = isUser ? userIcon : botIcon;
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'bubble';
        bubbleDiv.innerHTML = isUser ? `<p>${content}</p>` : formatMessage(content);
        
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(bubbleDiv);
        chatMessages.appendChild(messageDiv);
        
        // Scroll physics
        setTimeout(() => {
            chatMessages.scrollTo({
                top: chatMessages.scrollHeight,
                behavior: 'smooth'
            });
        }, 50);
    }
    
    function setTypingTarget(state) {
        typingIndicator.style.display = state ? 'flex' : 'none';
        if (state) {
            chatMessages.scrollTo({
                top: chatMessages.scrollHeight,
                behavior: 'smooth'
            });
        }
    }
    
    async function sendMessage(messageText) {
        setTypingTarget(true);
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    message: messageText,
                    history: conversationHistory 
                }),
            });
            
            if (!response.ok) throw new Error('API Sync Failed');
            
            const data = await response.json();
            setTypingTarget(false);
            
            // Render the response
            addMessage(data.response, false);
            
            // Mutate state with new exchanges
            conversationHistory.push(
                { role: 'user', content: messageText },
                { role: 'model', content: data.response }
            );

            // Optional: Cap history size to prevent massive payload issues (e.g. keep last 10 messages)
            if (conversationHistory.length > 20) {
                conversationHistory = conversationHistory.slice(conversationHistory.length - 20);
            }
            
        } catch (error) {
            setTypingTarget(false);
            addMessage("Subspace communication failure. Ensure backend services are online.", false);
            console.error(error);
        }
    }
    
    function handleTransaction(e) {
        e.preventDefault();
        const msg = userInput.value.trim();
        if (!msg) return;
        
        // Add to DOM
        addMessage(msg, true);
        
        // Clear input area
        userInput.value = '';
        
        // Trigger Async Request
        sendMessage(msg);
    }
    
    // Bindings
    chatForm.addEventListener('submit', handleTransaction);
    
    promptChips.forEach(chip => {
        chip.addEventListener('click', () => {
            const question = chip.getAttribute('data-question') || chip.textContent;
            addMessage(question, true);
            sendMessage(question);
        });
    });

    clearChatBtn.addEventListener('click', () => {
        // Clear state
        conversationHistory = [];
        
        // Clear DOM (keep intro message)
        const messages = chatMessages.querySelectorAll('.message');
        for (let i = 1; i < messages.length; i++) {
            messages[i].remove();
        }
        
        addMessage("Session memory flushed. Starting anew.", false);
    });
});
