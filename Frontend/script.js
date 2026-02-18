/*function GetText(){

    text = get_website_text("https://example.com", max_length=5000)
}


POST /fetch-website
{
    "url": "https://example.com"
}*/
//Base URL of your backend (adjust if needed)
const API_BASE_URL = 'http://localhost:8000';

// Function to fetch text from a website
async function fetchWebsiteText(url) {
    try {
        const response = await fetch(`${API_BASE_URL}/fetch-website`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: url })
        });
        
        const data = await response.json();
        console.log('Website text:', data.text);
        return data.text;
    } catch (error) {
        console.error('Error fetching website:', error);
    }
}

// Function to analyze text
async function analyzeText(text) {
    try {
        const response = await fetch(`${API_BASE_URL}/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: text })
        });
        
        const data = await response.json();
        console.log('Analysis result:', data.analysis);
        return data.analysis;
    } catch (error) {
        console.error('Error analyzing text:', error);
    }
}

// Example usage
document.getElementById('analyzeButton').addEventListener('click', async () => {
    const url = document.getElementById('urlInput').value;
    const text = await fetchWebsiteText(url);
    const analysis = await analyzeText(text);
    document.getElementById('result').textContent = JSON.stringify(analysis, null, 2);
});