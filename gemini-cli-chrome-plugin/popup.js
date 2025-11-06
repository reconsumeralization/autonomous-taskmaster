
const input = document.getElementById('input');
const output = document.getElementById('output');
const commandHistory = [];
let historyIndex = -1;

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const command = input.value;
    input.value = '';
    addToOutput(`> ${command}`);
    commandHistory.push(command);
    historyIndex = commandHistory.length;
    chrome.runtime.sendMessage({ command: command }, (response) => {
      addToOutput(response.result);
    });
  } else if (e.key === 'ArrowUp') {
    if (historyIndex > 0) {
      historyIndex--;
      input.value = commandHistory[historyIndex];
    }
  } else if (e.key === 'ArrowDown') {
    if (historyIndex < commandHistory.length - 1) {
      historyIndex++;
      input.value = commandHistory[historyIndex];
    } else {
      historyIndex = commandHistory.length;
      input.value = '';
    }
  }
});

function addToOutput(text) {
  const p = document.createElement('p');
  p.textContent = text;
  output.appendChild(p);
  output.scrollTop = output.scrollHeight;
}
