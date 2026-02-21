// API base — change only if backend runs elsewhere
const API_BASE = 'http://127.0.0.1:8000';

document.addEventListener('DOMContentLoaded', () => {

    const modeSelect = document.getElementById('modeSelect');
    const textInput = document.getElementById('inputText');
    const btn = document.getElementById('checkBtn');
    const result = document.getElementById('result');

    // Hidden image file input
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);

    // -----------------------------
    // UI placeholder management
    // -----------------------------
    function updatePlaceholder() {

        const mode = modeSelect.value;

        if (mode === 'image') {
            textInput.placeholder =
                'Click Verify to upload an image for AI detection';
            textInput.disabled = true;

        } else if (mode === 'text') {
            textInput.placeholder =
                'Paste text to check if it was written by AI...';
            textInput.disabled = false;

        } else {
            textInput.placeholder =
                'Enter a claim to fact-check...';
            textInput.disabled = false;
        }
    }

    modeSelect.addEventListener('change', () => {
        updatePlaceholder();
        result.textContent = '';
        textInput.value = '';
    });

    // -----------------------------
    // Verify button click
    // -----------------------------
    btn.addEventListener('click', async () => {

        const mode = modeSelect.value;
        const text = textInput.value.trim();

        // Image mode
        if (mode === 'image') {
            fileInput.click();
            return;
        }

        if (!text) {
            result.textContent = 'Please enter text.';
            return;
        }

        await processRequest(mode, text);
    });

    // -----------------------------
    // Image selection handler
    // -----------------------------
    fileInput.onchange = async () => {

        if (fileInput.files.length > 0) {
            await processRequest('image', fileInput.files[0]);
        }
    };

    // -----------------------------
    // Main request handler
    // -----------------------------
    async function processRequest(mode, inputData) {

        result.textContent = '⏳ Analyzing...';

        try {

            let response;

            // IMAGE DETECTION
            if (mode === 'image') {

                const formData = new FormData();
                formData.append('file', inputData);

                response = await fetch(API_BASE + '/detect-image', {
                    method: 'POST',
                    body: formData
                });
            }

            // TEXT AI DETECTION
            else if (mode === 'text') {

                response = await fetch(API_BASE + '/detect-text', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: inputData })
                });
            }

            // FACT CHECK
            else {

                response = await fetch(API_BASE + '/fact-check', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ claim: inputData })
                });
            }

            if (!response.ok)
                throw new Error(`Server error ${response.status}`);

            const data = await response.json();

            // Classification result formatting
            if (mode === 'image' || mode === 'text') {

                const label = data.result[0].label;
                const score =
                    (data.result[0].score * 100).toFixed(2);

                result.textContent =
                    `Result: ${label} (${score}% confidence)`;

            }

            // LLM fact-check result
            else {

                result.textContent = data.result;
            }

        }

        catch (error) {

            console.error(error);

            result.textContent =
                `❌ Server error: ${error.message}`;
        }
    }

    // Initialize UI
    updatePlaceholder();

});