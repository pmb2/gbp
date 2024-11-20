document.addEventListener('DOMContentLoaded', () => {
  initDB();
  initDragAndDrop();
  initSidebar();
  initUserProfile();
  initBulkActions();
  initAccountManagement();

  // Event listener for user profile elements
  const userProfile = document.getElementById('userProfile');
  userProfile.addEventListener('click', () => {
    // Logic to bring up settings popup/modal
    console.log('Open settings');
  });

  // Event listener for sidebar toggle
  const sidebar = document.getElementById('sidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  
  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('closed');
    const toggleArrow = document.getElementById('toggleArrow');
    toggleArrow.classList.toggle('fa-chevron-left');
    toggleArrow.classList.toggle('fa-chevron-right');
  });

  // Add modal close handlers
  document.querySelector('.modal-close').addEventListener('click', hideLoginModal);
  document.querySelector('.modal-overlay').addEventListener('click', hideLoginModal);
});

// Initialize user profile
async function initUserProfile() {
  const user = await window.websim.getUser();
  if (user) {
    document.getElementById('userAvatar').src = user.avatar_url || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(user.username);
    document.getElementById('userName').textContent = user.username;
    // You would typically fetch credits from your backend
    document.getElementById('userCredits').textContent = 'Credits: 100';
  }
}

// Sidebar Interaction
function initSidebar() {
  const navItems = document.querySelectorAll('.nav-item');
  
  navItems.forEach(item => {
    const subNav = item.querySelector('.sub-nav');
    if (subNav) {
      item.addEventListener('click', (e) => {
        if (e.target === item) {
          item.classList.toggle('expanded');
        }
      });
    }
    
    item.addEventListener('click', (e) => {
      if (!e.target.closest('.sub-nav')) {
        navItems.forEach(navItem => navItem.classList.remove('active'));
        item.classList.add('active');
      }
    });
  });
}

// Navigation and Tab Handling
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const tabId = tab.dataset.tab;
    
    // Hide all filter rows
    document.querySelectorAll('.filter-row').forEach(row => {
      row.style.display = 'none';
    });
    
    // Show the corresponding filter row
    document.getElementById(`${tabId}-filters`).style.display = 'flex';
    
    // Remove active class from all tabs and content
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    // Add active class to clicked tab
    tab.classList.add('active');
    
    // Show corresponding content
    const contentElement = document.getElementById(`${tabId}-content`);
    contentElement.classList.add('active');

    // Reset checkboxes when switching tabs
    document.querySelectorAll('.item-checkbox:checked').forEach(checkbox => {
      checkbox.checked = false;
    });
    document.getElementById('bulkActions').classList.remove('visible');
  });
});

// Initialize filter functionality
document.querySelectorAll('.filter-select').forEach(select => {
  select.addEventListener('change', () => {
    // Add your filtering logic here
    console.log('Filter changed:', select.value);
  });
});

// Initialize action buttons
document.querySelectorAll('.action-btn, .action-btn-small').forEach(button => {
  button.addEventListener('click', () => {
    // Add your action handling logic here
    console.log('Action clicked:', button.textContent);
  });
});

// Request Reviews functionality
const requestReviewsBtn = document.getElementById('requestReviews');
const checkboxes = document.querySelectorAll('.review-checkbox');
let isRequestMode = true;

requestReviewsBtn.addEventListener('click', () => {
  if (isRequestMode) {
    checkboxes.forEach(cb => cb.style.display = 'inline');
    requestReviewsBtn.innerHTML = 'Use 0 Credits <span style="position: absolute; top: 2px; right: 5px; cursor: pointer;">×</span>';
    requestReviewsBtn.style.position = 'relative';

    const closeBtn = requestReviewsBtn.querySelector('span');
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      resetRequestButton();
    });

    isRequestMode = false;
  } else {
    // Handle credits processing
    const selectedCount = [...checkboxes].filter(cb => cb.checked).length;
    const creditsRequired = selectedCount * 10;
    // Here you would add logic to deduct credits
    console.log(`Processing request for ${creditsRequired} credits`);
  }
});

function resetRequestButton() {
  checkboxes.forEach(cb => {
    cb.style.display = 'none';
    cb.checked = false;
  });
  requestReviewsBtn.textContent = 'Request Reviews';
  isRequestMode = true;
  updateTotal();
}

function updateTotal() {
  const selectedCount = [...checkboxes].filter(cb => cb.checked).length;
  const totalCredits = selectedCount * 10;
  if (!isRequestMode) {
    requestReviewsBtn.innerHTML = `Use ${totalCredits} Credits <span style="position: absolute; top: 2px; right: 5px; cursor: pointer;">×</span>`;

    const closeBtn = requestReviewsBtn.querySelector('span');
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      resetRequestButton();
    });
  }
}

document.querySelectorAll('.quick-action').forEach(button => {
  button.addEventListener('click', () => {
    if (button.textContent !== 'Request Reviews' && button.textContent !== 'Write Reviews') {
      const action = button.textContent;
      switch(action) {
        case 'Generate Content':
          // Handle content generation
          break;
        case 'Upload Media':
          // Handle media upload
          break;
      }
    }
  });
});

// Initialize bulk actions
function initBulkActions() {
  const bulkActionsDiv = document.getElementById('bulkActions');

  // Watch for checkbox changes
  document.addEventListener('change', e => {
    if (e.target.matches('.item-checkbox')) {
      const checkedBoxes = document.querySelectorAll('.item-checkbox:checked');
      const count = checkedBoxes.length;
      bulkActionsDiv.classList.toggle('visible', count > 0);
      document.getElementById('selectedCount').textContent = `${count} selected`;
      document.getElementById('creditsRequired').textContent = count * 10;
    }
  });
}

// Add OAuth and account management
function initAccountManagement() {
  const loginModal = document.getElementById('loginModal');

  // You can add logic to show the modal if needed
}

// Account Actions
function importAccounts() {
  // Trigger file input for CSV upload
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.csv';
  input.onchange = e => {
    const file = e.target.files[0];
    // Handle CSV processing here
    console.log('Processing CSV:', file);
  };
  input.click();
}

function addNewAccount() {
  showLoginModal();
}

function handleOAuth(provider) {
  // Implement OAuth flow for the selected provider
  console.log('Authenticating with:', provider);
}

function showLoginModal() {
  document.getElementById('loginModal').style.display = 'block';
  document.querySelector('.modal-overlay').style.display = 'block';
}

function hideLoginModal() {
  document.getElementById('loginModal').style.display = 'none';
  document.querySelector('.modal-overlay').style.display = 'none';
}
