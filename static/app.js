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
        '<video class="clip-video" controls preload="metadata" playsinline src="' + escapeHtml(clip.preview_url) + '"></video>' +
        '<div class="clip-details"><span class="clip-number-inline">CLIP ' + String(index + 1).padStart(2, "0") + '</span>' +
        '<strong>' + escapeHtml(data.title) + ' · ' +
        escapeHtml(clip.start) + '–' + escapeHtml(clip.end) + '</strong>' +
        '<p>Portrait 9:16 · ' + escapeHtml(clip.size_mb) + ' MB</p>' +
        '<a class="download-link" href="' + escapeHtml(clip.url) + '">Download MP4 <span>↓</span></a>' +
        '</div></article>';
    }).join("");
    results.hidden = false;
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function pollJob(jobId) {
    for (;;) {
      await new Promise(function (resolve) { setTimeout(resolve, 2500); });
      const response = await fetch("/api/jobs/" + encodeURIComponent(jobId));
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "Could not check job status.");
      if (data.status === "error") throw new Error(data.error || data.message || "Clip creation failed.");
      if (data.status === "done") return data;
      showMessage(data.message || "Processing your clips…", "working");
    }
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
    showMessage("Starting clip job… keep this tab open while your video is processed.", "working");
    try {
      const response = await fetch("/api/create-clips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({url: url, count: Number(countSelect.value), clip_length: Number(lengthSelect.value)})
      });
      const started = await response.json();
      if (!response.ok || !started.ok) throw new Error(started.error || "Couldn't start clip creation.");
      const data = await pollJob(started.job_id);
      showMessage(data.message, "success");
      renderClips(data);
    } catch (error) {
      showMessage(error.message || "The request was interrupted. Try a shorter public video.", "error");
    } finally {
      button.disabled = false;
      button.querySelector("span:first-child").textContent = "Create clips";
    }
  });
})();