// Authentication State Management
document.addEventListener('DOMContentLoaded', () => {
    const authLinks = document.getElementById('auth-links');
    const profileSection = document.getElementById('profile-section');
    const profileIconBtn = document.getElementById('profile-icon-btn');
    const profileDropdown = document.getElementById('profile-dropdown');
    const dropdownUsername = document.getElementById('dropdown-username');
    const signoutBtn = document.getElementById('signout-btn');

    // Check if user is logged in
    function checkLoginState() { 
        const userData = localStorage.getItem('user');
        return userData ? JSON.parse(userData) : null;
    }

    // Update header based on login state
    function updateHeaderState() {
        const user = checkLoginState();

        if (user) {
            // User is logged in
            if (authLinks) authLinks.style.display = 'none';
            if (profileSection) {
                profileSection.style.display = 'flex';
                if (dropdownUsername) {
                    dropdownUsername.textContent = user.name || user.email;
                }
            }
        } else {
            // User is not logged in
            if (authLinks) authLinks.style.display = 'flex';
            if (profileSection) profileSection.style.display = 'none';
            if (profileDropdown) profileDropdown.classList.remove('active');
        }
    }

    // Handle profile icon click to toggle dropdown
    if (profileIconBtn) {
        profileIconBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (profileDropdown) {
                profileDropdown.classList.toggle('active');
            }
        });
    }

    // Close dropdown when clicking elsewhere
    document.addEventListener('click', (e) => {
        if (profileDropdown && profileSection) {
            if (!profileSection.contains(e.target)) {
                profileDropdown.classList.remove('active');
            }
        }
    });

    // Handle login (call this from your login page)
    window.setUserLogin = (userData) => {
        localStorage.setItem('user', JSON.stringify(userData));
        updateHeaderState();
    };

    // Handle logout
    if (signoutBtn) {
        signoutBtn.addEventListener('click', () => {
            localStorage.removeItem('user');
            updateHeaderState();
            // Redirect to home page
            window.location.href = 'index.html';
        });
    }

    // Initialize on page load
    updateHeaderState();
});
