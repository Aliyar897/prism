// static/js/editor.js

async function saveChanges() {
  const data = {
    bio: document.getElementById('editor-bio').value,
    mode: currentMode,
    links: getLinksFromDOM()
  }
  
  const response = await fetch('/api/editor/save/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken')  // Django CSRF
    },
    body: JSON.stringify(data)
  })
  
  if (response.ok) {
    showToast('Saved successfully')
  }
}