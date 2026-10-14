(() => {
  const form = document.getElementById("video-form");
  const input = document.getElementById("video-url");
  const button = document.getElementById("analyze-button");
  const message = document.getElementById("result-message");

  function showMessage(text, kind) {
    message.textContent = text;
    message.className = "result-message " + kind;
    message.hidden = false;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const url = input.value.trim();
    if (!url) {
      showMessage("Paste a YouTube or Twitch link first.", "error");
      input.focus();
      return;
    }
    button.disabled = true;
    button.querySelector("span:first-child").textContent = "Checking…";
    message.hidden = true;
    try {
      const response = await fetch("/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        showMessage(data.error || "That link could not be verified. Check it and try again.", "error");
      } else {
        showMessage(data.platform + " link verified. " + data.message, "success");
      }
    } catch (_) {
      showMessage("Could not reach Clipz.me right now. Please try again.", "error");
    } finally {
      button.disabled = false;
      button.querySelector("span:first-child").textContent = "Check link";
    }
  });
})();
