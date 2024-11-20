document.addEventListener('DOMContentLoaded', () => {
  initVectorGraph();
  initFileUpload();
  updateStats();
  initializeContent();
  initializeUser();
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

// New functionality for analytics page
let currentPage = 'overview'; // Initialize to track active page

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', (e) => {
    // Remove active class from all items
    document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
    
    // Add active class to clicked item
    item.classList.add('active');

    // Show appropriate content based on clicked item
    if (item.textContent.trim() === 'Analytics') {
      showAnalyticsPage();
    } else {
      document.getElementById('analyticsContent').style.display = 'none';
      document.querySelector('.kb-overview').style.display = 'block';
      currentPage = 'overview';
    }
  });
});

function showAnalyticsPage() {
  document.getElementById('analyticsContent').style.display = 'block';
  document.querySelector('.kb-overview').style.display = 'none';
  
  // Initialize charts after content is added
  initializeCharts();
  loadAIInsights();
}

async function loadAIInsights() {
  try {
    const response = await fetch('/api/ai_completion', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt: `Analyze the following metrics for GBP Automation Pro and provide 3-4 strategic insights and recommendations:
        - 1,247 Active Clients (+12.5% MoM)
        - 4.8 Average Rating (+0.3 MoM)
        - 89.3% Profile Optimization (+5.2% MoM)
        - 15,892 Reviews Managed (+18.7% MoM)

        Format the response as HTML with icons and styling classes.
        `,
        data: "Performance metrics analysis"
      })
    });

    const data = await response.json();
    document.getElementById('aiInsights').innerHTML = data.analysis;
  } catch (error) {
    console.error('Error fetching AI insights:', error);
    document.getElementById('aiInsights').innerHTML = 'Error loading insights';
  }
}

function initializeCharts() {
  // Client Growth Chart
  const clientGrowth = new Chart(document.getElementById('clientGrowthChart'), {
    type: 'line',
    data: {
      labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
      datasets: [{
        label: 'Active Clients',
        data: [850, 920, 1050, 1150, 1200, 1247],
        borderColor: '#4285f4',
        tension: 0.4
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: 'top',
        }
      }
    }
  });

  // Performance Radar Chart
  const performance = new Chart(document.getElementById('performanceRadarChart'), {
    type: 'radar',
    data: {
      labels: ['Profile Optimization', 'Response Rate', 'Review Score', 'Post Engagement', 'Client Retention'],
      datasets: [{
        label: 'Current Period',
        data: [89, 95, 96, 85, 92],
        borderColor: '#34a853',
        backgroundColor: 'rgba(52, 168, 83, 0.2)'
      }]
    }
  });

  // Add more charts as needed
}
