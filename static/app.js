(() => {
  const form = document.getElementById("video-form");
  const input = document.getElementById("video-url");
  const button = document.getElementById("analyze-button");
  const countSelect = document.getElementById("clip-count");
  const lengthSelect = document.getElementById("clip-length");
  const message = document.getElementById("result-message");
  const results = document.getElementById("clip-results");
  const resultsGrid = document.getElementById("clips-grid");

  function showMessage(text, kind) {
    message.textContent = text;
    message.className = "result-message " + kind;
    message.hidden = false;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[character];
    });
  }

  function renderClips(data) {
    resultsGrid.innerHTML = data.clips.map(function (clip, index) {
      return '<article class="clip-result">' +
        '<div class="clip-preview"><span class="clip-preview-mark">▶</span>' +
        '<span class="clip-number">CLIP ' + String(index + 1).padStart(2, "0") + '</span>' +
        '<span class="clip-duration">' + escapeHtml(clip.duration) + 's</span></div>' +
        '<div class="clip-details"><strong>' + escapeHtml(data.title) + ' · ' +
        escapeHtml(clip.start) + '–' + escapeHtml(clip.end) + '</strong>' +
        '<p>Portrait 9:16 · ' + escapeHtml(clip.size_mb) + ' MB</p>' +
        '<a class="download-link" href="' + escapeHtml(clip.url) + '">Download MP4 <span>↓</span></a>' +
        '</div></article>';
    }).join("");
    results.hidden = false;
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const url = input.value.trim();
    if (!url) {
      showMessage("Paste a YouTube or Twitch link first.", "error");
      input.focus();
      return;
    }
    button.disabled = true;
    button.querySelector("span:first-child").textContent = "Creating clips…";
    message.hidden = true;
    results.hidden = true;
    resultsGrid.innerHTML = "";
    showMessage("Connecting to the video and analysing its audio. This can take a few minutes—keep this tab open.", "working");
    try {
      const response = await fetch("/api/create-clips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({url: url, count: Number(countSelect.value), clip_length: Number(lengthSelect.value)})
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        showMessage(data.error || "Couldn't create clips from that link.", "error");
      } else {
        showMessage(data.message, "success");
        renderClips(data);
      }
    } catch (_) {
      showMessage("The request was interrupted. The free server may have restarted or timed out. Try a shorter video.", "error");
    } finally {
      button.disabled = false;
      button.querySelector("span:first-child").textContent = "Create clips";
    }
  });
})();