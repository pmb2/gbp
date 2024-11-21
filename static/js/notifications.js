document.addEventListener('DOMContentLoaded', () => {
  initVectorGraph();
  initFileUpload();
  updateStats();
  initializeContent();
  initializeUser();
  initializeNotifications();
});

// Initialize vector graph visualization using D3.js
function initVectorGraph() {
  const width = document.getElementById('vectorGraph').clientWidth;
  const height = 400;
  
  // Create SVG
  const svg = d3.select('#vectorGraph')
    .append('svg')
    .attr('width', width)
    .attr('height', height);

  // Sample data - replace with real data from your vector database
  const data = {
    nodes: [
      {id: "doc1", type: "document", title: "Company Overview"},
      {id: "doc2", type: "document", title: "Marketing Strategy"},
      {id: "concept1", type: "concept", title: "Brand Identity"},
      {id: "concept2", type: "concept", title: "Customer Engagement"},
      {id: "concept3", type: "concept", title: "Market Analysis"},
      {id: "relation1", type: "relation", title: "Influences"},
      {id: "relation2", type: "relation", title: "Defines"}
    ],
    links: [
      {source: "doc1", target: "concept1"},
      {source: "doc1", target: "concept2"},
      {source: "doc2", target: "concept2"},
      {source: "doc2", target: "concept3"},
      {source: "concept1", target: "relation1"},
      {source: "concept2", target: "relation2"}
    ]
  };

  // Create force simulation
  const simulation = d3.forceSimulation(data.nodes)
    .force("link", d3.forceLink(data.links).id(d => d.id).distance(100))
    .force("charge", d3.forceManyBody().strength(-200))
    .force("center", d3.forceCenter(width / 2, height / 2));

  // Draw links
  const links = svg.append("g")
    .selectAll("line")
    .data(data.links)
    .join("line")
    .style("stroke", "#999")
    .style("stroke-width", 1);

  // Draw nodes
  const nodes = svg.append("g")
    .selectAll("circle")
    .data(data.nodes)
    .join("circle")
    .attr("r", 8)
    .style("fill", d => {
      switch(d.type) {
        case "document": return "#4285f4";
        case "concept": return "#34a853";
        case "relation": return "#fbbc05";
      }
    })
    .call(drag(simulation));

  // Add node titles
  nodes.append("title")
    .text(d => d.title);

  // Update positions
  simulation.on("tick", () => {
    links
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);

    nodes
      .attr("cx", d => d.x)
      .attr("cy", d => d.y);
  });

  // Drag functionality
  function drag(simulation) {
    function dragstarted(event) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }
    
    function dragged(event) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }
    
    function dragended(event) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }
    
    return d3.drag()
      .on("start", dragstarted)
      .on("drag", dragged)
      .on("end", dragended);
  }
}

// File upload handling
function initFileUpload() {
  const uploadZone = document.getElementById('uploadZone');
  const fileInput = document.getElementById('fileInput');
  
  uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
  });
  
  uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('drag-over');
  });
  
  uploadZone.addEventListener('drop', async (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    
    const files = e.dataTransfer.files;
    await handleFiles(files);
  });
  
  fileInput.addEventListener('change', async () => {
    await handleFiles(fileInput.files);
  });
}

async function handleFiles(files) {
  for (const file of files) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      // Upload file and generate embeddings
      const response = await fetch('/api/knowledge-base/upload', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) throw new Error('Upload failed');
      
      // Update UI
      updateFileGrid();
      updateStats();
    } catch (error) {
      console.error('Error uploading file:', error);
    }
  }
}

function updateFileGrid() {
  // Update file grid with newly uploaded files
}

function updateStats() {
  // Update knowledge base statistics
}

// Add this to your existing script
function initializeContent() {
  // Company Overview
  const companyOverview = document.getElementById('companyOverview');
  companyOverview.innerHTML = `
    <p style="margin-bottom: 1rem">
      GBP Automation Pro specializes in automating and optimizing Google Business Profile management 
      for businesses of all sizes. Our cutting-edge AI-powered platform streamlines content creation, 
      review management, and profile optimization.
    </p>
    <ul style="list-style: none; padding: 0">
      <li style="margin: 0.5rem 0">
        <i class="fas fa-check-circle" style="color: var(--primary); margin-right: 0.5rem"></i>
        Established: 2023
      </li>
      <li style="margin: 0.5rem 0">
        <i class="fas fa-check-circle" style="color: var(--primary); margin-right: 0.5rem"></i>
        Clients: 1000+
      </li>
      <li style="margin: 0.5rem 0">
        <i class="fas fa-check-circle" style="color: var(--primary); margin-right: 0.5rem"></i>
        Success Rate: 98%
      </li>
    </ul>
  `;

  // Operations News
  const operationsNews = document.getElementById('operationsNews');
  operationsNews.innerHTML = `
    <div class="news-item" style="border-bottom: 1px solid #eee; padding: 1rem 0;">
      <h4>New AI Model Integration</h4>
      <p>Enhanced content generation capabilities with latest LLM implementation.</p>
      <small style="color: var(--gray)">2 hours ago</small>
    </div>
    <div class="news-item" style="border-bottom: 1px solid #eee; padding: 1rem 0;">
      <h4>Vector Database Upgrade</h4>
      <p>Improved knowledge base search and retrieval performance.</p>
      <small style="color: var(--gray)">1 day ago</small>
    </div>
    <div class="news-item" style="padding: 1rem 0;">
      <h4>System Performance Update</h4>
      <p>30% faster response times for all API endpoints.</p>
      <small style="color: var(--gray)">2 days ago</small>
    </div>
  `;
}

// Add to your existing script
async function initializeUser() {
  try {
    const user = await window.websim.getUser();
    if (user) {
      document.getElementById('userAvatar').src = user.avatar_url || 'https://via.placeholder.com/40';
      document.getElementById('username').textContent = '@' + user.username;
      document.getElementById('userCredits').textContent = '500 credits'; // Replace with actual credits
    }
  } catch (error) {
    console.error('Error loading user data:', error);
  }
}

// Initialize knowledge base features
document.addEventListener('DOMContentLoaded', () => {
  initVectorGraph();
  initFileUpload();
  updateStats();
  initializeContent();
  initializeUser();
  initializeNotifications();
});

// Add click handler to nav items
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    item.classList.add('active');
    
    // Show corresponding content section
    const sections = ['overview', 'knowledge-base', 'content', 'analytics', 'notifications'];
    const index = Array.from(item.parentElement.children).indexOf(item);
    showSection(sections[index]);
  });
});

function showSection(section) {
  document.querySelectorAll('.main-content > div').forEach(div => div.style.display = 'none');
  document.querySelector(`.${section}-content`).style.display = 'block';
}

// Add to your existing script
function initializeNotifications() {
  // Sample notifications data - replace with actual data from your backend
  const notifications = [
    {
      id: 1,
      title: "GBP Profile Needs Immediate Update",
      content: "Critical information missing in business hours section",
      type: "urgent",
      time: "2 hours ago",
      deadline: new Date(Date.now() + 1000 * 60 * 60 * 4), // 4 hours from now
      solutions: ["Update business hours", "Verify information", "Set holiday hours"]
    },
    {
      id: 2,
      title: "Review Response Required",
      content: "3 new customer reviews pending response",
      type: "important",
      time: "1 day ago",
      deadline: new Date(Date.now() + 1000 * 60 * 60 * 24 * 2), // 2 days from now
      solutions: ["Generate AI response", "Mark as responded", "Flag for manual review"]
    },
    {
      id: 3,
      title: "Content Update Suggested",
      content: "New photos recommended for your business profile",
      type: "regular",
      time: "3 days ago",
      deadline: new Date(Date.now() + 1000 * 60 * 60 * 24 * 7), // 7 days from now
      solutions: ["Upload new photos", "Schedule photoshoot", "Skip update"]
    }
  ];

  // Render notifications by type
  renderNotifications('urgentNotifications', notifications.filter(n => n.type === 'urgent'));
  renderNotifications('importantNotifications', notifications.filter(n => n.type === 'important'));
  renderNotifications('regularNotifications', notifications.filter(n => n.type === 'regular'));
}

function renderNotifications(containerId, notifications) {
  const container = document.getElementById(containerId);
  container.innerHTML = notifications.map(notification => `
    <div class="notification-item" data-id="${notification.id}">
      <div class="notification-header">
        <div class="notification-title">${notification.title}</div>
        <div class="notification-time">${notification.time}</div>
      </div>
      <div class="notification-content">${notification.content}</div>
      <div class="notification-actions">
        <button class="notification-btn solve-btn" onclick="showSolutions(${notification.id})">
          <i class="fas fa-magic"></i> Solve
        </button>
        <button class="notification-btn archive-btn" onclick="archiveNotification(${notification.id})">
          <i class="fas fa-archive"></i> Archive
        </button>
        <button class="notification-btn delete-btn" onclick="deleteNotification(${notification.id})">
          <i class="fas fa-trash"></i> Delete
        </button>
      </div>
    </div>
  `).join('');
}

function showSolutions(notificationId) {
  // Implement solution modal or dropdown
  console.log(`Showing solutions for notification ${notificationId}`);
}

function archiveNotification(notificationId) {
  // Implement archive functionality
  console.log(`Archiving notification ${notificationId}`);
  document.querySelector(`[data-id="${notificationId}"]`).remove();
}

function deleteNotification(notificationId) {
  // Implement delete functionality
  console.log(`Deleting notification ${notificationId}`);
  document.querySelector(`[data-id="${notificationId}"]`).remove();
}

function markAllRead() {
  // Implement mark all as read functionality
  console.log('Marking all notifications as read');
  document.querySelectorAll('.notification-item').forEach(item => {
    item.style.opacity = '0.7';
  });
}

function archiveAll() {
  // Implement archive all functionality
  console.log('Archiving all notifications');
  document.querySelectorAll('.notification-item').forEach(item => {
    item.remove();
  });
}
