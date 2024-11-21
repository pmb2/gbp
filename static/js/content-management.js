document.addEventListener('DOMContentLoaded', initializeApp);

async function initializeApp() {
  try {
    await fetchKnowledgeBaseContent();
    currentUser = await window.websim.getUser();
    updateUserProfile();
    initSidebar();
    initCalendar();
    initContentManagement();
  } catch (error) {
    console.error('Error initializing app:', error);
  }
}

// Fetch knowledge base content
async function fetchKnowledgeBaseContent() {
  try {
    // Simulated API call - replace with actual API endpoint
    const response = await fetch('/api/knowledge-base');
    const data = await response.json();
    knowledgeBaseContent = data;
  } catch (error) {
    console.error('Error fetching knowledge base content:', error);
  }
}

// Update user profile section
function updateUserProfile() {
  if (!currentUser) return;
  
  const userAvatar = document.getElementById('userAvatar');
  const userName = document.getElementById('userName');
  const userCredits = document.getElementById('userCredits');
  
  userAvatar.src = currentUser.avatar_url || 'https://images.websim.ai/avatar/' + currentUser.username;
  userName.textContent = '@' + currentUser.username;
  userCredits.textContent = 'Credits: 100'; // Replace with actual credits when available
}

// Initialize calendar
function initCalendar() {
  const calendarEl = document.getElementById('calendar');
  const calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: 'dayGridMonth',
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,dayGridWeek'
    },
    editable: true,
    droppable: true,
    events: [
      {
        title: 'Weekly Special Menu',
        start: '2023-07-15',
        backgroundColor: 'var(--primary)'
      },
      {
        title: 'Summer Sale Announcement',
        start: '2023-07-20',
        backgroundColor: 'var(--warning)'
      }
    ],
    eventClick: function(info) {
      loadContentToEditor(info.event);
    },
    dateClick: function(info) {
      clearEditor();
      document.querySelector('input[type="time"]').value = '12:00';
      selectScheduleOption('Schedule');
    }
  });
  
  calendar.render();
}

function initContentManagement() {
  // Handle content item selection
  document.querySelectorAll('.content-item').forEach(item => {
    item.addEventListener('click', () => {
      loadContentToEditor({
        title: item.querySelector('.item-title').textContent,
        status: item.classList.contains('draft') ? 'draft' : 
                item.classList.contains('scheduled') ? 'scheduled' : 'published'
      });
    });
  });
  
  // Handle filter pills
  document.querySelectorAll('.filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      filterContent(pill.textContent.toLowerCase());
    });
  });
  
  // Handle content type selection
  const contentTypeSelect = document.getElementById('contentTypeSelect');
  const templateSelect = document.getElementById('templateSelect');
  const allowedTypes = document.getElementById('allowedTypes');

  contentTypeSelect.addEventListener('change', () => {
    const selectedType = contentTypeSelect.value;
    updateContentTypeUI(selectedType);
  });

  // Initialize with default content type
  updateContentTypeUI('posts');

  // Add knowledge base search handler
  const searchInput = document.getElementById('knowledgeBaseSearch');
  const searchBtn = document.getElementById('searchKnowledgeBase');
  
  searchBtn.addEventListener('click', () => {
    searchKnowledgeBase(searchInput.value);
  });
  
  searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      searchKnowledgeBase(searchInput.value);
    }
  });
  
  // Initialize AI chat
  initAiChat();
}

// Search knowledge base
async function searchKnowledgeBase(query) {
  const searchResults = document.getElementById('searchResults');
  searchResults.style.display = 'block';
  
  try {
    const response = await fetch(`/api/knowledge-base/search?q=${encodeURIComponent(query)}`);
    const results = await response.json();
    
    searchResults.innerHTML = results.map(item => `
      <div class="search-result-item" data-id="${item.id}">
        <div class="item-title">${item.title}</div>
        <div class="item-preview">${item.preview}</div>
      </div>
    `).join('');
    
    // Add click handlers for search results
    document.querySelectorAll('.search-result-item').forEach(item => {
      item.addEventListener('click', () => selectKnowledgeBaseItem(item.dataset.id));
    });
  } catch (error) {
    console.error('Error searching knowledge base:', error);
    searchResults.innerHTML = '<div class="error-message">Error searching knowledge base</div>';
  }
}

function selectKnowledgeBaseItem(id) {
  // Handle selecting a knowledge base item
  console.log('Selected knowledge base item:', id);
  document.getElementById('searchResults').style.display = 'none';
}

// Initialize AI chat functionality
function initAiChat() {
  const modal = document.getElementById('aiChatModal');
  const closeBtn = document.getElementById('closeAiChat');
  const sendBtn = document.getElementById('sendAiMessage');
  const confirmBtn = document.getElementById('confirmAiContent');
  const input = document.getElementById('aiChatInput');
  const messages = document.getElementById('aiChatMessages');
  
  document.getElementById('aiGenerateBtn').addEventListener('click', () => {
    modal.style.display = 'flex';
  });
  
  closeBtn.addEventListener('click', () => {
    modal.style.display = 'none';
  });
  
  // Close modal when clicking outside
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.style.display = 'none';
    }
  });
  
  sendBtn.addEventListener('click', async () => {
    if (!input.value.trim()) return;
    
    // Add user message
    const userMessage = document.createElement('div');
    userMessage.className = 'user-message';
    userMessage.textContent = input.value;
    messages.appendChild(userMessage);
    
    // Call AI API
    try {
      const response = await fetch('/api/ai_completion', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: `Generate content based on: ${input.value}`,
          data: { knowledgeBase: knowledgeBaseContent }
        })
      });
      
      const data = await response.json();
      
      // Add AI response
      const aiMessage = document.createElement('div');
      aiMessage.className = 'ai-message';
      aiMessage.textContent = data.content;
      messages.appendChild(aiMessage);
      
      // Enable confirm button
      confirmBtn.disabled = false;
      
      // Store generated content
      window.generatedContent = data.content;
    } catch (error) {
      console.error('Error generating content:', error);
    }
    
    input.value = '';
    messages.scrollTop = messages.scrollHeight;
  });
  
  confirmBtn.addEventListener('click', () => {
    if (window.generatedContent) {
      document.querySelector('.form-input[rows="10"]').value = window.generatedContent;
      modal.style.display = 'none';
      confirmBtn.disabled = true;
      window.generatedContent = null;
    }
  });
}

// Update initialization
function updateContentTypeUI(contentType) {
  const config = contentTypes[contentType];
  
  // Update templates
  const templateSelect = document.getElementById('templateSelect');
  templateSelect.innerHTML = '<option value="">Select a template...</option>';
  config.templates.forEach(template => {
    const option = document.createElement('option');
    option.value = template;
    option.textContent = template.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    templateSelect.appendChild(option);
  });

  // Update character limit
  const contentTextarea = document.querySelector('.form-input[rows="10"]');
  contentTextarea.maxLength = config.maxLength;
}

function loadContentToEditor(content) {
  const titleInput = document.querySelector('.form-input[type="text"]');
  const contentTextarea = document.querySelector('.form-input[rows="10"]');
  
  titleInput.value = content.title || '';
  contentTextarea.value = content.description || '';
  
  // Set appropriate schedule option
  selectScheduleOption(content.status === 'scheduled' ? 'Schedule' : 
                      content.status === 'draft' ? 'Post Now' : 'Schedule');
}

function clearEditor() {
  const titleInput = document.querySelector('.form-input[type="text"]');
  const contentTextarea = document.querySelector('.form-input[rows="10"]');
  
  titleInput.value = '';
  contentTextarea.value = '';
}

function selectScheduleOption(option) {
  const options = document.querySelectorAll('.schedule-option');
  options.forEach(o => {
    o.classList.toggle('selected', o.textContent === option);
  });
  
  const recurringOptions = document.querySelector('.recurring-options');
  recurringOptions.style.display = option === 'Recurring' ? 'block' : 'none';
}

function filterContent(filter) {
  const contentItems = document.querySelectorAll('.content-item');
  const contentTypeSelect = document.getElementById('contentTypeSelect');
  
  if (filter !== 'all') {
    contentTypeSelect.value = filter;
    updateContentTypeUI(filter);
  }

  contentItems.forEach(item => {
    if (filter === 'all' || item.dataset.type === filter) {
      item.style.display = 'block';
    } else {
      item.style.display = 'none';
    }
  });
}

async function handleAction(action) {
  const titleInput = document.querySelector('.form-input[type="text"]');
  const contentTextarea = document.querySelector('.form-input[rows="10"]');
  const contentType = document.getElementById('contentTypeSelect').value;
  
  const content = {
    title: titleInput.value,
    content: contentTextarea.value,
    type: contentType,
    status: action === 'save draft' ? 'draft' : 
            action === 'schedule' ? 'scheduled' : 'published'
  };
  
  try {
    // Here you would typically make an API call to save the content
    console.log('Saving content:', content);
    // Show success message
    alert(`${contentType.charAt(0).toUpperCase() + contentType.slice(1)} ${action} successfully!`);
    // Clear editor after successful save
    if (action !== 'save draft') {
      clearEditor();
    }
  } catch (error) {
    console.error('Error saving content:', error);
    alert('Error saving content. Please try again.');
  }
}
