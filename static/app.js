// SnapFetch front-end: mobile nav + the downloader tool.
(function () {
  var toggle = document.getElementById('navToggle');
  var nav = document.getElementById('mainNav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  var form = document.getElementById('fetchForm');
  if (!form) return; // only the home page has the tool

  var input = document.getElementById('urlInput');
  var btn = document.getElementById('fetchBtn');
  var statusBox = document.getElementById('statusBox');
  var statusText = document.getElementById('statusText');
  var errorBox = document.getElementById('errorBox');
  var card = document.getElementById('resultCard');

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove('hidden');
    statusBox.classList.add('hidden');
  }
  function clearError() { errorBox.classList.add('hidden'); }

  function fmtDuration(s) {
    if (!s && s !== 0) return '';
    s = Math.round(s);
    var m = Math.floor(s / 60), sec = s % 60;
    return m + ':' + (sec < 10 ? '0' : '') + sec;
  }

  function makeButton(f, sourceUrl, isAudio) {
    var a = document.createElement('a');
    a.className = 'fmt-btn' + (isAudio ? ' audio' : '');
    var href = '/download?url=' + encodeURIComponent(sourceUrl) +
               '&format_id=' + encodeURIComponent(f.format_id);
    a.href = href;
    var txt = f.label;
    if (f.filesize_label) txt += ' <small>(' + f.filesize_label + ')</small>';
    a.innerHTML = txt;
    return a;
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearError();
    card.classList.add('hidden');
    var url = input.value.trim();
    if (!url) { showError('Please paste a video link first.'); return; }
    btn.disabled = true;
    statusText.textContent = 'Fetching your video…';
    statusBox.classList.remove('hidden');

    fetch('/api/info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    })
      .then(function (r) {
        return r.json().then(function (data) {
          if (!r.ok) throw new Error(data.error || 'Something went wrong.');
          return data;
        });
      })
      .then(function (data) {
        document.getElementById('resTitle').textContent = data.title || '';
        document.getElementById('resPlatform').textContent = data.platform || '';
        var meta = fmtDuration(data.duration);
        document.getElementById('resMeta').textContent =
          meta ? 'Duration: ' + meta : '';
        var img = document.getElementById('resThumb');
        if (data.thumbnail) { img.src = data.thumbnail; img.style.display = 'block'; }
        else { img.style.display = 'none'; }

        var vWrap = document.getElementById('videoFormats');
        var aWrap = document.getElementById('audioFormats');
        vWrap.innerHTML = ''; aWrap.innerHTML = '';
        var sourceUrl = data.webpage_url || url;
        var hasVideo = false, hasAudio = false;
        (data.formats || []).forEach(function (f) {
          if (f.kind === 'video') {
            hasVideo = true;
            vWrap.appendChild(makeButton(f, sourceUrl, false));
            if (f.note) {
              var n = document.createElement('span');
              n.className = 'fmt-note';
              n.textContent = f.label + ': ' + f.note;
              vWrap.appendChild(n);
            }
          } else {
            hasAudio = true;
            aWrap.appendChild(makeButton(f, sourceUrl, true));
          }
        });
        if (!hasVideo) vWrap.innerHTML = '<span class="fmt-note">No separate video formats were offered for this link — try the audio option or another link.</span>';
        statusBox.classList.add('hidden');
        card.classList.remove('hidden');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      })
      .catch(function (err) {
        showError(err.message || 'Something went wrong. Please try again.');
      })
      .finally(function () { btn.disabled = false; });
  });
})();
