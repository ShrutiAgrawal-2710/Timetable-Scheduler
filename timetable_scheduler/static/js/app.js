// State variables
let activeRunData = null;
let selectedAltIndex = 0;

document.addEventListener("DOMContentLoaded", () => {
    // Navigation & Modal Elements
    const btnHowToSidebar = document.getElementById("btn-how-to");
    const btnHowToHeader = document.getElementById("btn-how-to-header");
    const welcomeGuideBtn = document.getElementById("welcome-guide-btn");
    const modalHow = document.getElementById("modal-how");
    const modalClose = document.getElementById("modal-close");
    const modalFooterClose = document.getElementById("modal-footer-close");
    
    // Sidebar toggle (Google Hamburger Menu)
    const ggMenuToggle = document.getElementById("gg-menu-toggle");
    const ggSidebarMenu = document.getElementById("gg-sidebar-menu");
    
    // Upload & Inputs
    const sidebarUploadBtn = document.getElementById("sidebar-upload-btn");
    const fileInput = document.getElementById("file-input");
    const dropzone = document.getElementById("dropzone");
    
    // Application state views
    const welcomeState = document.getElementById("welcome-state");
    const loaderState = document.getElementById("loader-state");
    const errorState = document.getElementById("error-state");
    const resultsState = document.getElementById("results-state");
    
    const errorTbody = document.getElementById("error-tbody");
    
    const statusBadge = document.getElementById("status-badge");
    const resultHorizon = document.getElementById("result-horizon");
    const resultResources = document.getElementById("result-resources");
    const resultDepartments = document.getElementById("result-departments");
    
    const alternateTabs = document.getElementById("alternate-tabs");
    const scheduleTbody = document.getElementById("schedule-tbody");
    
    const violationsContainer = document.getElementById("violations-container");
    const violationsList = document.getElementById("violations-list");
    
    const filterInput = document.getElementById("filter-input");
    const headerSearchInput = document.getElementById("header-search-input");
    const searchClearBtn = document.getElementById("search-clear-btn");

    // --- Modal Dialog Event Handlers ---
    const openModal = (e) => {
        if (e) e.preventDefault();
        modalHow.classList.add("active");
    };
    
    const closeModal = () => {
        modalHow.classList.remove("active");
    };

    if (btnHowToSidebar) btnHowToSidebar.addEventListener("click", openModal);
    if (btnHowToHeader) btnHowToHeader.addEventListener("click", openModal);
    if (welcomeGuideBtn) welcomeGuideBtn.addEventListener("click", openModal);
    
    if (modalClose) modalClose.addEventListener("click", closeModal);
    if (modalFooterClose) modalFooterClose.addEventListener("click", closeModal);
    
    window.addEventListener("click", (e) => {
        if (e.target === modalHow) {
            closeModal();
        }
    });

    // --- Sidebar Hamburger Toggle ---
    if (ggMenuToggle && ggSidebarMenu) {
        ggMenuToggle.addEventListener("click", () => {
            if (window.innerWidth <= 768) {
                ggSidebarMenu.classList.toggle("active-mobile");
            } else {
                ggSidebarMenu.classList.toggle("collapsed");
            }
        });
    }

    // --- Upload Trigger ---
    if (sidebarUploadBtn && fileInput) {
        sidebarUploadBtn.addEventListener("click", (e) => {
            // Only click if we didn't click the input itself
            if (e.target !== fileInput) {
                fileInput.click();
            }
        });
    }
    
    if (fileInput) {
        fileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                handleFileUpload(e.target.files[0]);
            }
        });
    }

    // --- Fullscreen Drag & Drop Handling (Google Drive style) ---
    window.addEventListener("dragenter", (e) => {
        e.preventDefault();
        if (dropzone) dropzone.classList.add("dragover");
    });
    
    if (dropzone) {
        dropzone.addEventListener("dragover", (e) => {
            e.preventDefault();
        });
        
        dropzone.addEventListener("dragleave", (e) => {
            // Only hide if we leave the window/overlay container
            if (e.relatedTarget === null || e.target === dropzone) {
                dropzone.classList.remove("dragover");
            }
        });
        
        dropzone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropzone.classList.remove("dragover");
            if (e.dataTransfer.files.length > 0) {
                handleFileUpload(e.dataTransfer.files[0]);
            }
        });
    }

    // --- API Upload Handler ---
    function handleFileUpload(file) {
        // Show loading state, hide other content areas
        welcomeState.classList.add("hidden");
        errorState.classList.add("hidden");
        resultsState.classList.add("hidden");
        loaderState.classList.remove("hidden");
        
        const formData = new FormData();
        formData.append("file", file);
        
        fetch("/api/schedule/upload", {
            method: "POST",
            body: formData
        })
        .then(async (response) => {
            const data = await response.json();
            if (!response.ok) {
                // Check if validation failure
                if (response.status === 400 && data.validation_errors) {
                    showValidationErrors(data.validation_errors);
                } else {
                    showGenericError(data.detail || "An unexpected error occurred during scheduling.");
                }
            } else {
                renderResults(data);
            }
        })
        .catch((error) => {
            showGenericError("Network communication error. Failed to reach the solver server.");
            console.error(error);
        })
        .finally(() => {
            loaderState.classList.add("hidden");
        });
    }

    // --- Render Validation Errors ---
    function showValidationErrors(errorsList) {
        errorTbody.innerHTML = "";
        errorsList.forEach(err => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td><strong>${escapeHtml(err.sheet)}</strong></td>
                <td>${escapeHtml(String(err.row))}</td>
                <td>${escapeHtml(err.column)}</td>
                <td class="error-msg">${escapeHtml(err.message)}</td>
            `;
            errorTbody.appendChild(row);
        });
        
        document.getElementById("error-summary-msg").textContent = `Spreadsheet parsing failed with ${errorsList.length} format violation(s).`;
        errorState.classList.remove("hidden");
        
        // Update sidebar status
        if (statusBadge) {
            statusBadge.textContent = "Error";
            statusBadge.className = "gg-status-badge badge-warning";
        }
    }

    function showGenericError(message) {
        errorTbody.innerHTML = `
            <tr>
                <td colspan="4" style="text-align: center; color: var(--gg-red); font-weight: 600; padding: 2rem;">
                    <i class="fa-solid fa-circle-xmark" style="font-size: 1.5rem; margin-bottom: 0.5rem; display: block;"></i>
                    ${escapeHtml(message)}
                </td>
            </tr>
        `;
        document.getElementById("error-summary-msg").textContent = "The server returned a processing error.";
        errorState.classList.remove("hidden");
        
        if (statusBadge) {
            statusBadge.textContent = "Error";
            statusBadge.className = "gg-status-badge badge-warning";
        }
    }

    // --- Render Solver Timetable Results ---
    function renderResults(runData) {
        activeRunData = runData;
        selectedAltIndex = 0;
        
        // 1. Setup Status Badge in sidebar
        if (statusBadge) {
            statusBadge.textContent = runData.status;
            statusBadge.className = "gg-status-badge " + (runData.status === "SUCCESS" ? "badge-success" : "badge-warning");
        }
        
        // 2. Scan assignments to get summary counts
        const allAssignments = runData.alternatives[0].assignments;
        const uniqueResources = new Set(allAssignments.map(a => a.resource_name));
        const uniqueDepts = new Set(allAssignments.map(a => a.dept_name));
        
        // Extract Horizon Bounds
        if (allAssignments.length > 0) {
            const datesSorted = allAssignments.map(a => new Date(a.date)).sort((a,b) => a-b);
            const startStr = datesSorted[0].toISOString().split('T')[0];
            const endStr = datesSorted[datesSorted.length - 1].toISOString().split('T')[0];
            resultHorizon.textContent = `${startStr} to ${endStr}`;
        } else {
            resultHorizon.textContent = "N/A";
        }
        
        resultResources.textContent = uniqueResources.size;
        resultDepartments.textContent = uniqueDepts.size;
        
        // 3. Render Tabs
        alternateTabs.innerHTML = "";
        runData.alternatives.forEach((alt, idx) => {
            const tab = document.createElement("div");
            tab.className = `gg-tab-item ${idx === 0 ? "active" : ""}`;
            tab.textContent = `Alternative ${idx + 1} ${idx === 0 ? "(Optimal)" : ""}`;
            tab.addEventListener("click", () => {
                // Switch tabs
                document.querySelectorAll(".gg-tab-item").forEach(t => t.classList.remove("active"));
                tab.classList.add("active");
                selectedAltIndex = idx;
                renderActiveAlternative();
            });
            alternateTabs.appendChild(tab);
        });
        
        // 4. Render Active Alternative Grid
        renderActiveAlternative();
        
        resultsState.classList.remove("hidden");
    }

    function renderActiveAlternative() {
        if (!activeRunData) return;
        const alternative = activeRunData.alternatives[selectedAltIndex];
        
        // Render Violations list
        violationsList.innerHTML = "";
        if (alternative.violations && alternative.violations.length > 0) {
            alternative.violations.forEach(v => {
                const li = document.createElement("li");
                li.textContent = v.description;
                violationsList.appendChild(li);
            });
            violationsContainer.classList.remove("hidden");
        } else {
            violationsContainer.classList.add("hidden");
        }
        
        // Render Grid Assignments
        renderAssignmentsTable(alternative.assignments);
    }

    function renderAssignmentsTable(assignments) {
        scheduleTbody.innerHTML = "";
        const sorted = [...assignments].sort((a, b) => {
            if (a.date !== b.date) return a.date.localeCompare(b.date);
            return a.resource_name.localeCompare(b.resource_name);
        });
        
        sorted.forEach(a => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td><strong>${escapeHtml(a.date)}</strong></td>
                <td>${escapeHtml(a.resource_name)}</td>
                <td><span class="gg-status-badge badge-idle" style="font-weight: 500;">${escapeHtml(a.dept_name)}</span></td>
                <td>${escapeHtml(String(a.hours))} hrs</td>
            `;
            scheduleTbody.appendChild(row);
        });
        
        // Re-apply filter if text in search box
        filterGrid();
    }

    // --- Search Synchronization & Filters ---
    if (filterInput) {
        filterInput.addEventListener("keyup", () => {
            if (headerSearchInput) {
                headerSearchInput.value = filterInput.value;
                toggleSearchClearBtn();
            }
            filterGrid();
        });
    }
    
    if (headerSearchInput) {
        headerSearchInput.addEventListener("keyup", () => {
            if (filterInput) {
                filterInput.value = headerSearchInput.value;
            }
            toggleSearchClearBtn();
            filterGrid();
        });
    }
    
    if (searchClearBtn) {
        searchClearBtn.addEventListener("click", () => {
            if (headerSearchInput) headerSearchInput.value = "";
            if (filterInput) filterInput.value = "";
            toggleSearchClearBtn();
            filterGrid();
        });
    }
    
    function toggleSearchClearBtn() {
        if (searchClearBtn && headerSearchInput) {
            if (headerSearchInput.value.length > 0) {
                searchClearBtn.style.display = "flex";
            } else {
                searchClearBtn.style.display = "none";
            }
        }
    }
    
    function filterGrid() {
        const query = (filterInput ? filterInput.value : "").toLowerCase().trim();
        const rows = scheduleTbody.getElementsByTagName("tr");
        
        for (let row of rows) {
            const cells = row.getElementsByTagName("td");
            if (cells.length >= 3) {
                const resourceText = cells[1].textContent.toLowerCase();
                const deptText = cells[2].textContent.toLowerCase();
                if (resourceText.includes(query) || deptText.includes(query)) {
                    row.style.display = "";
                } else {
                    row.style.display = "none";
                }
            }
        }
    }

    // --- HTML Sanitization Helper ---
    function escapeHtml(unsafe) {
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
});
