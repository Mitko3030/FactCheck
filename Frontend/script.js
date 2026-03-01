// API base — relative path so it works anywhere
const API_BASE = 'factcheck-noit.up.railway.app';
//
document.addEventListener('DOMContentLoaded', () => {

    const modeSelect = document.getElementById('modeSelect');
    const textInput  = document.getElementById('inputText');
    const btn        = document.getElementById('checkBtn');
    const result     = document.getElementById('result');

    // Скрит input за изображения
    const fileInput = document.createElement('input');
    fileInput.type    = 'file';
    fileInput.accept  = 'image/*';
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);
 
    // ─────────────────────────────────────
    // Placeholder според режима
    // ─────────────────────────────────────
    function updatePlaceholder() {
        const mode = modeSelect.value;

        if (mode === 'image') {
            textInput.placeholder = 'Натисни „Провери" за да качиш изображение за AI детекция';
            textInput.disabled = true;

        } else if (mode === 'text') {
            textInput.placeholder = 'Постави текст за да провериш дали е написан от AI...';
            textInput.disabled = false;

        } else {
            textInput.placeholder = 'Въведи твърдение за проверка на факти...';
            textInput.disabled = false;
        }
    }

    modeSelect.addEventListener('change', () => {
        updatePlaceholder();
        result.textContent = '';
        textInput.value    = '';
    });

    // ─────────────────────────────────────
    // Бутон „Провери"
    // ─────────────────────────────────────
    btn.addEventListener('click', async () => {
        const mode = modeSelect.value;
        const text = textInput.value.trim();

        if (mode === 'image') {
            fileInput.click();
            return;
        }

        if (!text) {
            result.textContent = 'Моля, въведи текст.';
            return;
        }

        await processRequest(mode, text);
    });

    // ─────────────────────────────────────
    // Избор на изображение
    // ─────────────────────────────────────
    fileInput.onchange = async () => {
        if (fileInput.files.length > 0) {
            await processRequest('image', fileInput.files[0]);
        }
    };

    // ─────────────────────────────────────
    // Основна функция за заявки
    // ─────────────────────────────────────
    async function processRequest(mode, inputData) {

        result.textContent = '⏳ Анализирам...';
        btn.disabled = true;

        try {
            let response;

            // ДЕТЕКЦИЯ НА ИЗОБРАЖЕНИЕ
            if (mode === 'image') {
                const formData = new FormData();
                formData.append('file', inputData);

                response = await fetch(API_BASE + '/detect-image', {
                    method: 'POST',
                    body: formData
                });

            // ДЕТЕКЦИЯ НА AI ТЕКСТ
            } else if (mode === 'text') {
                response = await fetch(API_BASE + '/detect-text', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: inputData })
                });

            // ПРОВЕРКА НА ФАКТИ
            } else {
                response = await fetch(API_BASE + '/fact-check', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ claim: inputData })
                });
            }

            if (!response.ok) throw new Error(`Грешка от сървъра: ${response.status}`);

            const data = await response.json();

            // Резултат от класификация (изображение или текст)
            if (mode === 'image' || mode === 'text') {
                const label = data.result[0].label;
                const score = (data.result[0].score * 100).toFixed(2);
                result.textContent = `Резултат: ${label} (${score}% увереност)`;

            // Резултат от проверка на факти
            } else {
                result.textContent = data.result;
            }

        } catch (error) {
            console.error(error);
            result.textContent = `❌ Грешка: ${error.message}`;

        } finally {
            btn.disabled = false;
        }
    }

    // Инициализация
    updatePlaceholder();
});