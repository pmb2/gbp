function switchTaskTab(tabName) {
    document.getElementById("tab-content-compliance").classList.add("hidden");
    document.getElementById("tab-content-agent-tasks").classList.add("hidden");
    if (tabName === "compliance") {
        document.getElementById("tab-content-compliance").classList.remove("hidden");
    } else {
        document.getElementById("tab-content-agent-tasks").classList.remove("hidden");
    }
}
window.switchTaskTab = switchTaskTab;
