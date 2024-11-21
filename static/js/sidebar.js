document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.getElementById('sidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  
  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('closed');
    const toggleArrow = document.getElementById('toggleArrow');
    toggleArrow.classList.toggle('fa-chevron-left');
    toggleArrow.classList.toggle('fa-chevron-right');
  });

  // Initialize user profile
  async function initUserProfile() {
    const user = await window.websim.getUser();
    if (user) {
      document.getElementById('userAvatar').src = user.avatar_url || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(user.username);
      document.getElementById('userName').textContent = user.username;
      document.getElementById('userCredits').textContent = 'Credits: 100';
    }
  }

  initUserProfile();
});
document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.getElementById('sidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  
  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('closed');
    const toggleArrow = document.getElementById('toggleArrow');
    toggleArrow.classList.toggle('fa-chevron-left');
    toggleArrow.classList.toggle('fa-chevron-right');
  });

  // Initialize user profile
  async function initUserProfile() {
    const user = await window.websim.getUser();
    if (user) {
      document.getElementById('userAvatar').src = user.avatar_url || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(user.username);
      document.getElementById('userName').textContent = user.username;
      document.getElementById('userCredits').textContent = 'Credits: 100';
    }
  }

  initUserProfile();
});
