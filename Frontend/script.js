// Simple frontend logic: update placeholder based on mode and show a basic result message.
document.addEventListener('DOMContentLoaded', ()=>{
  const modeSelect = document.getElementById('modeSelect');
  const input = document.getElementById('inputText');
  const btn = document.getElementById('checkBtn');
  const result = document.getElementById('result');

  function updatePlaceholder(){
    const mode = modeSelect.value;
    if(mode === 'image') input.placeholder = 'Enter an image URL or description';
    else if(mode === 'text') input.placeholder = 'Paste or type the text to analyze';
    else input.placeholder = 'Enter a statement';
  }

  modeSelect.addEventListener('change', ()=>{
    updatePlaceholder();
    result.textContent = '';
  });

  btn.addEventListener('click', ()=>{
    const mode = modeSelect.value;
    const text = input.value.trim();
    if(!text){ result.textContent = 'Please enter input to check.'; return; }
    result.textContent = `Checking (${mode}) — "${text}" ... (demo)`;
  });

  updatePlaceholder();
});
