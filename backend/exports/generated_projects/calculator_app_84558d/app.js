document.getElementById('actionBtn').addEventListener('click', () => {
  const val = document.getElementById('inputField').value.trim();
  const res = document.getElementById('resultBox');
  if (!val) {
    res.textContent = 'Please enter a value.';
    return;
  }
  res.textContent = `Executed successfully: ${val.toUpperCase()} at ${new Date().toLocaleTimeString()}`;
});
