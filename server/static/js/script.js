document.addEventListener("DOMContentLoaded", () => {
    const clientListDiv = document.getElementById("client-list")
    const fileGroupsDiv = document.getElementById("file-groups")
    const totalClientsSpan = document.getElementById("total-clients");
    const totalFilesSpan = document.getElementById("total-files");
    const totalStorageSpan = document.getElementById("total-storage"); // Assumes an element with this ID exists

    // --- Page Navigation ---
    const pages = {
        dashboard: document.getElementById('page-dashboard'),
        analytics: document.getElementById('page-analytics'),
        settings: document.getElementById('page-settings')
    };
    const navTabs = document.querySelectorAll('.nav-tab');

    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const pageName = tab.dataset.page;
            
            // Hide all pages
            for (const page in pages) {
                if (pages[page]) pages[page].style.display = 'none';
            }
            // Show the selected page
            if (pages[pageName]) pages[pageName].style.display = 'block';

            // Update active tab style
            navTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Load content for the new page
            if (pageName === 'analytics') loadAnalytics();
            if (pageName === 'settings') loadSettings();
        });
    });

    function fetchAndRender() {
        Promise.all([
            fetch("/admin/clients").then((res) => res.json()), 
            fetch("/files").then((res) => res.json()),
            fetch("/api/analytics").then((res) => res.json()) // Fetch analytics data as well
        ])
        .then(([clients, fileGroups, analytics]) => {
            // Store clients globally so other functions can access it without re-fetching
            window.clientsData = clients; 
            renderClients(clients);
            renderFileGroups(fileGroups);
            updateStats(clients, fileGroups, analytics);
        })
        .catch((error) => console.error("Error fetching data:", error));
    }
  
    function updateStats(clients, fileGroups, analytics) {
      const clientCount = Object.keys(clients).length
      let fileCount = 0
  
      for (const clientId in fileGroups) {
        fileCount += countFilesInTree(fileGroups[clientId].tree || {})
      }
  
      totalClientsSpan.textContent = clientCount
      totalFilesSpan.textContent = fileCount
      
      // Display storage usage with limit
      if (analytics) {
        const usedMB = analytics.total_size_mb.toFixed(2)
        const limitMB = analytics.storage_limit_mb.toFixed(0)
        const percent = analytics.storage_usage_percent.toFixed(1)
        totalStorageSpan.textContent = `${usedMB} MB / ${limitMB} MB (${percent}%)`
        
        // Add warning class if over 80%
        if (analytics.storage_usage_percent > 80) {
          totalStorageSpan.className = 'stat-value warning'
        } else {
          totalStorageSpan.className = 'stat-value'
        }
      } else {
        totalStorageSpan.textContent = '0.00 MB / 5120 MB (0.0%)'
        totalStorageSpan.className = 'stat-value'
      }
    }
  
    function countFilesInTree(tree) {
      let count = 0
      for (const name in tree) {
        const node = tree[name]
        if (node.type === "file") {
          count++
        } else if (node.type === "folder" && node.children) {
          count += countFilesInTree(node.children)
        }
      }
      return count
    }
  
    function renderClients(clients) {
        clientListDiv.innerHTML = "";
        for (const clientId in clients) {
            const client = clients[clientId];
            const clientCard = document.createElement("div");
            clientCard.className = "client-card";

            const hasLabel = client.label && client.label.trim() !== "";
            const label = hasLabel ? client.label : "(Unlabeled)";
            const type = client.type === "star_machine" ? "Star Machine" : "PC Client";

            // Conditional rendering for the form
            const formHtml = hasLabel ? '' : `
                <div class="label-form">
                    <input type="text" placeholder="Enter label..." value="" id="label-input-${clientId}">
                    <button class="action-btn save-btn" data-id="${clientId}">Save</button>
                </div>`;

            clientCard.innerHTML = `
                <h4>${label}</h4>
                <div class="client-info">
                    <p><strong>ID:</strong> ${clientId.substring(0, 8)}...</p>
                    <p><strong>Type:</strong> ${type}</p>
                    <p><strong>IP:</strong> ${client.ip_address}</p>
                    <p><strong>Last Seen:</strong> ${new Date(client.last_seen).toLocaleString()}</p>
                </div>
                ${formHtml}
            `;
            clientListDiv.appendChild(clientCard);
        }
    }

    function renderFileGroups(fileGroups) {
        fileGroupsDiv.innerHTML = "";
        for (const clientId in fileGroups) {
            const group = fileGroups[clientId];
            const groupContainer = document.createElement("div");
            groupContainer.className = "file-group";

            const label = group.label || `Client ${clientId.substring(0, 8)}`;
            
            const fileTreeContainer = document.createElement("div");
            fileTreeContainer.className = "file-tree";

            if (group.tree && Object.keys(group.tree).length > 0) {
                const sortedFolders = Object.keys(group.tree).sort().reverse(); // Sort dates descending
                
                sortedFolders.forEach((folderName, index) => {
                    const node = group.tree[folderName];
                    const treeNode = renderTreeNode(node, folderName, fileTreeContainer, 0);
                    if (index >= 5) {
                        treeNode.mainElement.style.display = 'none'; // Hide folders beyond the 5th
                        treeNode.childrenContainer.style.display = 'none';
                    }
                });

                if (sortedFolders.length > 5) {
                    const showMoreBtn = document.createElement('button');
                    showMoreBtn.textContent = 'Show More';
                    showMoreBtn.className = 'action-btn show-more-btn';
                    showMoreBtn.onclick = (e) => {
                        // Show all hidden nodes
                        const hiddenNodes = fileTreeContainer.querySelectorAll('.tree-node[style*="display: none"], .children[style*="display: none"]');
                        hiddenNodes.forEach(node => node.style.display = '');
                        e.target.remove(); // Remove the button after clicking
                    };
                    fileTreeContainer.appendChild(showMoreBtn);
                }

            } else {
                fileTreeContainer.innerHTML = '<p class="no-files">No files uploaded yet.</p>';
            }
            
            groupContainer.innerHTML = `<h3>${label}</h3>`;
            groupContainer.appendChild(fileTreeContainer);
            fileGroupsDiv.appendChild(groupContainer);
        }
    }

    function renderTreeNode(node, name, container, level) {
        const element = document.createElement("div");
        element.style.paddingLeft = `${level * 20 + 20}px`;
        let childrenContainer; // To be returned

        if (node.type === "folder") {
            element.className = "tree-node folder";
            element.innerHTML = `<span class="icon"></span><span class="name">${name}</span>`;

            childrenContainer = document.createElement("div");
            childrenContainer.className = "children hidden";

            const sortedChildren = Object.keys(node.children).sort();
            for (const childName of sortedChildren) {
                const childNode = node.children[childName];
                renderTreeNode(childNode, childName, childrenContainer, level + 1);
            }

            element.addEventListener("click", (e) => {
                e.stopPropagation();
                element.classList.toggle("expanded");
                childrenContainer.classList.toggle("hidden");
            });

            container.appendChild(element);
            container.appendChild(childrenContainer);
        } else if (node.type === "file") {
            element.className = "tree-node file";
            element.innerHTML = `
                <span class="icon"></span>
                <span class="name">${name}</span>
                <span class="actions">
                    <button class="action-btn view-btn" data-path="${node.path}">View</button>
                    <a href="/files/${node.path}" class="action-btn download-btn" download>Download</a>
                    <button class="action-btn delete-btn" data-path="${node.path}">Delete</button>
                </span>
            `;
            container.appendChild(element);
        }
        return { mainElement: element, childrenContainer: childrenContainer };
    }
  
    function setClientLabel(clientId, newLabel) {
      fetch(`/admin/clients/${clientId}/label`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: newLabel }),
      })
        .then((response) => {
          if (response.ok) {
            fetchAndRender()
          } else {
            alert("Failed to set label.")
          }
        })
        .catch((error) => console.error("Error setting label:", error))
    }
  
    function deleteFile(filePath) {
      if (!confirm(`Are you sure you want to delete ${filePath}?`)) {
        return
      }
  
      fetch(`/files/${filePath}`, { method: "DELETE" })
        .then((response) => {
          if (response.ok) {
            fetchAndRender()
          } else {
            alert("Failed to delete file.")
          }
        })
        .catch((error) => console.error("Error deleting file:", error))
    }
  
    const searchInput = document.getElementById("file-search");
    if (searchInput) {
        const revealParents = (element) => {
            let parent = element.closest('.children');
            while (parent) {
                const folderNode = parent.previousElementSibling;
                if (folderNode && folderNode.classList.contains('folder')) {
                    folderNode.style.display = 'flex';
                    folderNode.classList.add('expanded');
                    parent.classList.remove('hidden');
                }
                parent = parent.parentElement.closest('.children');
            }
        };

        searchInput.addEventListener("input", (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const fileGroups = document.querySelectorAll(".file-group");

            fileGroups.forEach(group => {
                const allNodes = group.querySelectorAll(".tree-node");
                const showMoreBtn = group.querySelector('.show-more-btn');

                if (showMoreBtn) {
                    showMoreBtn.style.display = searchTerm ? 'none' : 'block';
                }

                if (searchTerm === '') {
                    // Reset the view to its initial state
                    const topLevelFolders = group.querySelectorAll('.file-tree > .tree-node');
                    allNodes.forEach(n => {
                        n.style.display = 'flex'; // Make all nodes visible first
                        if (n.classList.contains('folder')) {
                            n.classList.remove('expanded');
                            const children = n.nextElementSibling;
                            if (children && children.classList.contains('children')) {
                                children.classList.add('hidden');
                            }
                        }
                    });
                    // Then re-apply the "show more" logic
                    topLevelFolders.forEach((folder, index) => {
                        if (index >= 5) {
                            folder.style.display = 'none';
                             const children = folder.nextElementSibling;
                            if (children && children.classList.contains('children')) {
                                children.style.display = 'none';
                            }
                        }
                    });
                    return;
                }

                // Hide all nodes to begin the search
                allNodes.forEach(node => node.style.display = 'none');

                allNodes.forEach(node => {
                    const nodeName = node.querySelector('.name').textContent.toLowerCase();
                    if (nodeName.includes(searchTerm)) {
                        // This is a match, show it and its parents
                        node.style.display = 'flex';
                        revealParents(node);

                        // If it's a folder, also show all its children recursively
                        if (node.classList.contains('folder')) {
                            const childrenContainer = node.nextElementSibling;
                            if (childrenContainer) {
                                childrenContainer.querySelectorAll('.tree-node').forEach(n => n.style.display = 'flex');
                            }
                        }
                    }
                });
            });
        });
    }

    // --- Analytics Page ---
    let analyticsChart = null;
    function loadAnalytics() {
        const analyticsPage = pages.analytics;
        if (!analyticsPage) return;
        analyticsPage.innerHTML = `<div class="analytics-grid">
            <div class="chart-container panel">
                <div class="panel-header"><h3>Uploads Over Time</h3></div>
                <div class="panel-content"><canvas id="uploads-chart"></canvas></div>
            </div>
            <div class="top-clients-container panel">
                <div class="panel-header"><h3>Top Clients</h3></div>
                <div class="panel-content" id="top-clients-list"></div>
            </div>
        </div>`;

        fetch('/api/analytics')
            .then(res => res.json())
            .then(data => {
                renderUploadsChart(data.uploads_by_day);
                renderTopClients(data.uploads_by_client);
            })
            .catch(error => console.error("Error fetching analytics:", error));
    }

    function renderUploadsChart(uploadsByDay) {
        const ctx = document.getElementById('uploads-chart').getContext('2d');
        if (analyticsChart) {
            analyticsChart.destroy();
        }
        analyticsChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: Object.keys(uploadsByDay),
                datasets: [{
                    label: 'Files Uploaded',
                    data: Object.values(uploadsByDay),
                    backgroundColor: 'rgba(0, 112, 243, 0.5)',
                    borderColor: 'rgba(0, 112, 243, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                scales: { y: { beginAtZero: true } },
                maintainAspectRatio: false
            }
        });
    }

    function renderTopClients(uploadsByClient) {
        const topClientsList = document.getElementById('top-clients-list');
        topClientsList.innerHTML = '';
        const sortedClients = Object.entries(uploadsByClient).sort((a, b) => b[1] - a[1]);
        
        // Use the globally stored clients data to get labels
        for (const [clientId, count] of sortedClients) {
            const clientName = window.clientsData[clientId]?.label || `Client ${clientId.substring(0,8)}`;
            const clientElement = document.createElement('div');
            clientElement.className = 'client-stat';
            clientElement.innerHTML = `<span class="name">${clientName}</span><span class="count">${count} files</span>`;
            topClientsList.appendChild(clientElement);
        }
    }

    // --- Settings Page ---
    function loadSettings() {
        const settingsPage = pages.settings;
        if (!settingsPage) return;
        
        Promise.all([
            fetch('/api/settings').then(res => res.json()),
            fetch('/admin/clients').then(res => res.json())
        ])
        .then(([settings, clientsData]) => {
            settingsPage.innerHTML = `
            <div class="settings-grid">
                <div class="settings-container panel">
                    <div class="panel-header"><h2>Global Settings</h2></div>
                    <div class="panel-content">
                        <form id="global-settings-form">
                            <div class="form-group">
                                <label for="default_retention_days">Default File Retention (days)</label>
                                <input type="number" id="default_retention_days" name="default_retention_days" value="${settings.default_retention_days}" min="1">
                                <p class="help-text">New clients will use this retention period by default.</p>
                            </div>
                            <button type="submit" class="action-btn save-btn">Save Defaults</button>
                        </form>
                        <div id="global-settings-status"></div>
                    </div>
                </div>
                <div class="client-management-container panel">
                    <div class="panel-header"><h2>Client-Specific Settings</h2></div>
                    <div class="panel-content" id="client-management-list">
                        <!-- Client settings forms will be here -->
                    </div>
                </div>
            </div>`;
            
            renderClientManagementList(clientsData);
        })
        .catch(error => console.error("Error fetching settings:", error));
    }

    function renderClientManagementList(clients) {
        const container = document.getElementById('client-management-list');
        container.innerHTML = '';
        for (const clientId in clients) {
            const client = clients[clientId];
            const item = document.createElement('div');
            item.className = 'client-management-item';
            // Each client gets its own form
            item.innerHTML = `
                <form class="client-settings-form" data-id="${clientId}">
                    <div class="client-name">${client.label || `(Unlabeled)`} <small>${clientId.substring(0,8)}...</small></div>
                    <div class="form-group">
                        <label for="mgmt-label-input-${clientId}">Label</label>
                        <input type="text" id="mgmt-label-input-${clientId}" value="${client.label || ''}">
                    </div>
                    <div class="form-group">
                        <label for="mgmt-retention-input-${clientId}">Retention (days)</label>
                        <input type="number" id="mgmt-retention-input-${clientId}" value="${client.retention_days || 30}" min="1">
                    </div>
                    <button type="submit" class="action-btn save-btn">Update Client</button>
                </form>
            `;
            container.appendChild(item);
        }
    }

    // --- Event Listeners ---
    document.body.addEventListener('submit', function(event) {
        // Handle client-specific settings form
        if (event.target.classList.contains('client-settings-form')) {
            event.preventDefault();
            const clientId = event.target.dataset.id;
            const newLabel = document.getElementById(`mgmt-label-input-${clientId}`).value;
            const newRetention = document.getElementById(`mgmt-retention-input-${clientId}`).value;

            fetch(`/admin/clients/${clientId}/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ label: newLabel, retention_days: newRetention })
            })
            .then(res => {
                if(res.ok) fetchAndRender(); // Refresh dashboard on success
            })
            .catch(error => console.error("Error updating client settings:", error));
        }

        // Handle global settings form
        if (event.target.id === 'global-settings-form') {
            event.preventDefault();
            const newDefaultRetention = document.getElementById('default_retention_days').value;
            const statusDiv = document.getElementById('global-settings-status');
            
            fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ default_retention_days: newDefaultRetention })
            })
            .then(res => res.json())
            .then(data => {
                statusDiv.textContent = data.message || 'Settings saved!';
                statusDiv.className = 'status-success';
            })
            .catch(error => {
                statusDiv.textContent = 'Error saving settings.';
                statusDiv.className = 'status-error';
                console.error('Error saving settings:', error)
            });
        }
    });

    // This is the existing click listener for dashboard buttons like delete/rename
    document.body.addEventListener("click", (event) => {
      if (event.target.classList.contains("save-btn")) {
        const clientId = event.target.dataset.id;
        // This part is for the main dashboard's initial labeling
        if(document.getElementById(`label-input-${clientId}`)){
            const input = document.getElementById(`label-input-${clientId}`);
            setClientLabel(clientId, input.value);
        }
      }
      if (event.target.classList.contains("delete-btn")) {
        const filePath = event.target.dataset.path;
        deleteFile(filePath);
      }
      if (event.target.classList.contains("view-btn")) {
        const filePath = event.target.dataset.path;
        openPdfModal(filePath);
      }
    });

    // --- PDF Modal ---
    const pdfModal = document.getElementById('pdf-modal');
    const pdfViewer = document.getElementById('pdf-viewer');
    const closeModalBtn = document.getElementById('close-modal');
    const modalFileName = document.getElementById('modal-file-name');

    function openPdfModal(filePath) {
        if (!pdfModal || !pdfViewer || !modalFileName) return;
        modalFileName.textContent = filePath.split('/').pop();
        pdfViewer.src = `/files/${filePath}?view=true`;
        pdfModal.style.display = 'flex';
    }

    function closePdfModal() {
        if (!pdfModal || !pdfViewer) return;
        pdfViewer.src = ''; // Clear the src to stop loading
        pdfModal.style.display = 'none';
    }

    if (closeModalBtn) closeModalBtn.addEventListener('click', closePdfModal);
    if (pdfModal) pdfModal.addEventListener('click', (e) => {
        if (e.target === pdfModal) { // Close if clicking on the backdrop
            closePdfModal();
        }
    });


    // Initial load
    fetchAndRender();
    setInterval(fetchAndRender, 30000); // Increased interval
  
    window.fetchAndRender = fetchAndRender
  })
  