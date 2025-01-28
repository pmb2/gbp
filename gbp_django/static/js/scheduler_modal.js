function showSchedulerModal(businessId) {
    console.log('[INFO] showSchedulerModal called with businessId:', businessId);
    if (!businessId) {
        console.error('[ERROR] showSchedulerModal called without businessId');
        return;
    }

    const modal = document.getElementById('schedulerModal');
    if (!modal) {
        console.error('[ERROR] Modal element not found');
        return;
    }
    
    console.log('[INFO] Found schedulerModal element:', modal);
    
    // Close any existing modals first
    document.querySelectorAll('.modal-open').forEach(m => m.classList.add('hidden'));

    // Set business ID and show modal
    document.getElementById('businessIdInput').value = businessId;
    document.getElementById('taskForm').dataset.businessId = businessId;
    
    // Show modal with proper display and z-index
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    
    // Reset form
    document.getElementById('taskForm').reset();
    const contentContainer = document.getElementById('generatedContentContainer');
    if (contentContainer) {
        contentContainer.classList.add('hidden');
    }
    const generatedContent = document.getElementById('generatedContent');
    if (generatedContent) {
        generatedContent.value = '';
    }
}

// Make function globally available
window.showSchedulerModal = showSchedulerModal;

// Close modal when clicking outside
document.addEventListener('click', function(event) {
    const modal = document.getElementById('schedulerModal');
    if (modal && event.target === modal) {
        closeSchedulerModal();
    }
});

    // Content generation functions
    async function generateInitialContent() {
        const generateBtn = document.getElementById('generateButtonText');
        const loader = document.getElementById('generateLoader');
        const businessId = document.getElementById('businessIdInput').value;
        const taskType = document.querySelector('select[name="task_type"]').value; // Get selected task type

        generateBtn.textContent = 'Analyzing business profile...';
        loader.classList.remove('hidden');

        try {
            const response = await fetch(`/api/generate-content?business_id=${businessId}&task_type=${taskType}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({
                    sample_input: document.getElementById('sampleInput').value,
                    template: document.getElementById('templateSelect').value,
                    business_context: {
                        name: document.getElementById('businessNameInput').value,
                        category: document.getElementById('businessCategoryInput').value,
                        faqs: JSON.parse(document.getElementById('businessFaqsInput').textContent)
                    }
                })
            });

            const data = await response.json();
            if (data.content) {
                document.getElementById('generatedContent').value = data.content;
                document.getElementById('generatedContentContainer').classList.remove('hidden');
                generateBtn.textContent = 'Content generated!';
            } else {
                generateBtn.textContent = 'Error generating content - try again';
            }
        } catch (error) {
            console.error('Content generation error:', error);
            generateBtn.textContent = 'Generation failed - try again';
        }

        loader.classList.add('hidden');
        setTimeout(() => {
            generateBtn.textContent = '✨ Generate AI Content';
        }, 2000);
    }

    function regenerateContent() {
        document.getElementById('generatedContent').value = 'Regenerating content...';
        generateInitialContent();
    }

    function applyContent() {
        // TODO: Connect to actual content storage
        showAlertBanner('Content saved for task!', 'success');
    }

    function closeSchedulerModal() {
        const modal = document.getElementById('schedulerModal');
        if (modal) {
            modal.classList.add('hidden');
            document.getElementById('taskIdInput').value = '';
            document.getElementById('existingTasks').classList.add('hidden');
            document.getElementById('submitButtonText').textContent = 'Schedule Task';
        } else {
            console.error("Modal element not found");
        }
    }

    window.handleScheduleTask = (button) => {
        console.log('[INFO] handleScheduleTask called');
        const form = button.closest('form');
        const businessId = form.dataset.businessId;

        if (!businessId) {
            console.error('[ERROR] No businessId found in form');
            return;
        }

        const taskData = new FormData(form);
        const payload = {
            business_id: businessId,
            task_type: taskData.get('task_type'),
            frequency: taskData.get('frequency'),
            custom_time: taskData.get('custom_time') ? String(taskData.get('custom_time')) : null,
            csrfmiddlewaretoken: taskData.get('csrfmiddlewaretoken')
        };

        fetch(`/api/business/${businessId}/tasks/create/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': payload.csrfmiddlewaretoken
            },
            body: JSON.stringify(payload)
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    showAlertBanner('Task scheduled successfully', 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    showAlertBanner(data.message || 'Error creating task', 'error');
                }
                closeSchedulerModal();
            })
            .catch(error => {
                console.error('Error:', error);
                showAlertBanner('Error creating task', 'error');
                closeSchedulerModal();
            });
    };
    // Content generation functions
    async function generateInitialContent() {
        const generateBtn = document.getElementById('generateButtonText');
        const loader = document.getElementById('generateLoader');
        const businessId = document.getElementById('businessIdInput').value;
        const taskType = document.querySelector('select[name="task_type"]').value; // Get selected task type

        generateBtn.textContent = 'Analyzing business profile...';
        loader.classList.remove('hidden');

        try {
            const response = await fetch(`/api/generate-content?business_id=${businessId}&task_type=${taskType}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({
                    sample_input: document.getElementById('sampleInput').value,
                    template: document.getElementById('templateSelect').value,
                    business_context: {
                        name: "{{ business.business_name }}",
                        category: "{{ business.category }}",
                        faqs: JSON.parse(document.getElementById('businessFaqsInput').textContent)
                    }
                })
            });

            const data = await response.json();
            if (data.content) {
                document.getElementById('generatedContent').value = data.content;
                document.getElementById('generatedContentContainer').classList.remove('hidden');
                generateBtn.textContent = 'Content generated!';
            } else {
                generateBtn.textContent = 'Error generating content - try again';
            }
        } catch (error) {
            console.error('Content generation error:', error);
            generateBtn.textContent = 'Generation failed - try again';
        }

        loader.classList.add('hidden');
        setTimeout(() => {
            generateBtn.textContent = '✨ Generate AI Content';
        }, 2000);
    }

    function regenerateContent() {
        document.getElementById('generatedContent').value = 'Regenerating content...';
        generateInitialContent();
    }

    function applyContent() {
        // TODO: Connect to actual content storage
        showAlertBanner('Content saved for task!', 'success');
    }

    function closeSchedulerModal() {
        const modal = document.getElementById('schedulerModal');
        if (modal) {
            modal.classList.add('hidden');
            document.getElementById('taskIdInput').value = '';
            document.getElementById('existingTasks').classList.add('hidden');
            document.getElementById('submitButtonText').textContent = 'Schedule Task';
        } else {
            console.error("Modal element not found");
        }
    }

    window.handleScheduleTask = (button) => {
        console.log('[INFO] handleScheduleTask called');
        const form = button.closest('form');
        const businessId = form.dataset.businessId;

        if (!businessId) {
            console.error('[ERROR] No businessId found in form');
            return;
        }

        const taskData = new FormData(form);
        const payload = {
            business_id: businessId,
            task_type: taskData.get('task_type'),
            frequency: taskData.get('frequency'),
            custom_time: taskData.get('custom_time'),
            csrfmiddlewaretoken: taskData.get('csrfmiddlewaretoken')
        };

        fetch(`/api/business/${businessId}/tasks/create/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': payload.csrfmiddlewaretoken
            },
            body: JSON.stringify(payload)
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    showAlertBanner('Task scheduled successfully', 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    showAlertBanner(data.message || 'Error creating task', 'error');
                }
                closeSchedulerModal();
            })
            .catch(error => {
                console.error('Error:', error);
                showAlertBanner('Error creating task', 'error');
                closeSchedulerModal();
            });
    };
