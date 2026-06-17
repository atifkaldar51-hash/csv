/* ============================================================
   CSV Analytics Dashboard - Front-end Controller
   ============================================================
   - Drag & drop upload with AJAX
   - Chart builder AJAX calls
   - Friendly toast-style error handling
   ============================================================ */

window.AppCSV = (function () {

  /* ---------- Small helpers ---------- */
  function $(id) { return document.getElementById(id); }

  function showStatus(id, message, isError) {
    var el = $(id);
    if (!el) return;
    el.classList.remove('d-none');
    var txt = el.querySelector('.status-text');
    if (txt) txt.textContent = message;
    el.style.color = isError ? '#ff3b30' : '#007aff';
    el.style.background = isError
      ? 'rgba(255, 59, 48, 0.10)'
      : 'rgba(0, 122, 255, 0.08)';
  }

  function hideStatus(id) {
    var el = $(id);
    if (el) el.classList.add('d-none');
  }

  /* ---------- Toast ---------- */
  function toast(message, kind) {
    kind = kind || 'info';
    var colors = {
      success: '#34c759',
      error:   '#ff3b30',
      info:    '#007aff'
    };
    var t = document.createElement('div');
    t.textContent = message;
    t.style.cssText =
      'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);' +
      'background:' + (colors[kind] || colors.info) + ';' +
      'color:#fff;padding:0.8rem 1.4rem;border-radius:12px;' +
      'box-shadow:0 8px 24px rgba(0,0,0,0.2);font-weight:500;' +
      'font-size:0.95rem;z-index:9999;opacity:0;transition:opacity .25s ease;' +
      'max-width:90vw;text-align:center;';
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.style.opacity = '1'; });
    setTimeout(function () {
      t.style.opacity = '0';
      setTimeout(function () { t.remove(); }, 300);
    }, 3200);
  }

  /* ---------- Drop zone init ---------- */
  function initDropZone(opts) {
    var input    = $(opts.inputId);
    var dropZone = $(opts.dropZoneId);
    var browse   = $(opts.browseBtnId);
    if (!input || !dropZone) return;

    function handleFile(file) {
      if (!file) return;
      var name = file.name.toLowerCase();
      if (!name.endsWith('.csv')) {
        toast('Please select a .csv file.', 'error');
        return;
      }
      // No size limit -- the backend streams large files in chunks.
      // We just warn the user for very large files so they know to wait.
      if (file.size > 200 * 1024 * 1024) {
        toast('Large file detected (' + Math.round(file.size / 1024 / 1024) + ' MB). Processing may take a moment...', 'info');
      }

      var fd = new FormData();
      fd.append('csv_file', file);

      showStatus(opts.statusId, 'Uploading & validating...', false);

      fetch(opts.endpoint, { method: 'POST', body: fd })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          hideStatus(opts.statusId);
          if (data.success) {
            toast(data.message || 'Upload successful!', 'success');
            if (data.redirect) {
              setTimeout(function () {
                window.location.href = data.redirect;
              }, 600);
            }
          } else {
            toast(data.message || 'Upload failed.', 'error');
          }
        })
        .catch(function (err) {
          hideStatus(opts.statusId);
          console.error(err);
          toast('Network error during upload.', 'error');
        });
    }

    // Click to browse
    dropZone.addEventListener('click', function () { input.click(); });
    if (browse) browse.addEventListener('click', function (e) {
      e.stopPropagation(); input.click();
    });

    input.addEventListener('change', function () {
      handleFile(input.files && input.files[0]);
    });

    // Drag events
    ['dragenter', 'dragover'].forEach(function (evt) {
      dropZone.addEventListener(evt, function (e) {
        e.preventDefault(); e.stopPropagation();
        dropZone.classList.add('dragover');
      });
    });
    ['dragleave', 'drop'].forEach(function (evt) {
      dropZone.addEventListener(evt, function (e) {
        e.preventDefault(); e.stopPropagation();
        dropZone.classList.remove('dragover');
      });
    });
    dropZone.addEventListener('drop', function (e) {
      var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      handleFile(f);
    });
  }

  /* ---------- Chart builder ---------- */
  function postJSON(url, payload) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json(); });
  }

  function showLatestLoading() {
    var empty = $('latestEmpty');
    var img   = $('latestImg');
    var load  = $('latestLoading');
    if (empty) empty.classList.add('d-none');
    if (img)   img.classList.add('d-none');
    if (load)  load.classList.remove('d-none');
  }

  function showLatestImage(url) {
    var empty = $('latestEmpty');
    var img   = $('latestImg');
    var load  = $('latestLoading');
    var dl    = $('latestDownload');
    if (load)  load.classList.add('d-none');
    if (empty) empty.classList.add('d-none');
    if (img) {
      img.src = url + (url.indexOf('?') >= 0 ? '&' : '?') + '_t=' + Date.now();
      img.classList.remove('d-none');
    }
    if (dl) {
      // Build a download URL by swapping /static/charts/ -> /download/chart/
      var fname = url.split('/').pop();
      dl.href = '/download/chart/' + fname;
      dl.classList.remove('d-none');
    }
  }

  /* ---------- Gallery refresh (no page reload) ---------- */
  function escapeHTML(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function renderGallery(charts) {
    var grid   = $('galleryGrid');
    var badge  = $('galleryCount');
    if (!grid) return;

    if (badge) badge.textContent = charts.length + ' chart(s)';

    if (!charts.length) {
      grid.innerHTML =
        '<div class="glass-card empty-state-card">' +
          '<i class="bi bi-images"></i>' +
          '<h5>No charts yet</h5>' +
          '<p>Use the builders above to generate your first chart. ' +
          'It will appear here automatically.</p>' +
        '</div>';
      return;
    }

    var html = '<div class="row g-4">';
    charts.forEach(function (c) {
      html +=
        '<div class="col-md-6 col-lg-4">' +
          '<div class="glass-card chart-card h-100">' +
            '<div class="chart-thumb">' +
              '<img src="' + c.url + '?_t=' + Date.now() + '" alt="' + escapeHTML(c.name) + '" />' +
            '</div>' +
            '<div class="chart-meta">' +
              '<div>' +
                '<div class="chart-name">' + escapeHTML(c.name) + '</div>' +
                '<div class="chart-info">' + escapeHTML(c.created) +
                  ' &middot; ' + c.size_kb + ' KB</div>' +
              '</div>' +
              '<a href="' + c.download_url + '" class="btn btn-sm btn-accent" title="Download">' +
                '<i class="bi bi-download"></i>' +
              '</a>' +
            '</div>' +
          '</div>' +
        '</div>';
    });
    html += '</div>';
    grid.innerHTML = html;
  }

  function refreshGallery() {
    fetch('/api/charts')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.success) renderGallery(data.charts || []);
      })
      .catch(function (err) { console.error('gallery refresh failed', err); });
  }

  function showLatestEmpty(message) {
    var empty = $('latestEmpty');
    var img   = $('latestImg');
    var load  = $('latestLoading');
    if (load) load.classList.add('d-none');
    if (img)  img.classList.add('d-none');
    if (empty) {
      empty.classList.remove('d-none');
      var p = empty.querySelector('p');
      if (p && message) p.textContent = message;
    }
  }

  function initChartBuilders(opts) {
    // Bar
    var barBtn = $(opts.barBtn);
    if (barBtn) barBtn.addEventListener('click', function () {
      var x = $(opts.barX).value;
      var y = $(opts.barY).value;
      if (!x || !y) { toast('Please select both X and Y columns.', 'error'); return; }
      barBtn.disabled = true;
      showLatestLoading();
      postJSON(opts.endpoint, { x_col: x, y_col: y })
        .then(function (data) {
          barBtn.disabled = false;
          if (data.success) {
            toast('Bar chart generated!', 'success');
            // Show the new chart in the Latest Chart panel -- it stays
            // visible until the next chart is generated (no page reload).
            showLatestImage(data.chart_url);
            // Refresh only the gallery section below via AJAX
            refreshGallery();
          } else {
            toast(data.message || 'Could not generate chart.', 'error');
            showLatestEmpty(data.message || 'Generation failed.');
          }
        })
        .catch(function (err) {
          barBtn.disabled = false;
          console.error(err);
          toast('Network error.', 'error');
          showLatestEmpty('Network error.');
        });
    });

    // Line
    var lineBtn = $(opts.lineBtn);
    if (lineBtn) lineBtn.addEventListener('click', function () {
      var x = $(opts.lineX).value;
      var y = $(opts.lineY).value;
      if (!x || !y) { toast('Please select both X and Y columns.', 'error'); return; }
      lineBtn.disabled = true;
      showLatestLoading();
      postJSON(opts.lineEndpoint, { x_col: x, y_col: y })
        .then(function (data) {
          lineBtn.disabled = false;
          if (data.success) {
            toast('Line chart generated!', 'success');
            showLatestImage(data.chart_url);
            // Latest chart stays visible -- only refresh the gallery
            refreshGallery();
          } else {
            toast(data.message || 'Could not generate chart.', 'error');
            showLatestEmpty(data.message || 'Generation failed.');
          }
        })
        .catch(function (err) {
          lineBtn.disabled = false;
          console.error(err);
          toast('Network error.', 'error');
          showLatestEmpty('Network error.');
        });
    });

    // Pie
    var pieBtn = $(opts.pieBtn);
    if (pieBtn) pieBtn.addEventListener('click', function () {
      var c = $(opts.pieCat).value;
      if (!c) { toast('Please select a category column.', 'error'); return; }
      pieBtn.disabled = true;
      showLatestLoading();
      postJSON(opts.pieEndpoint, { cat_col: c })
        .then(function (data) {
          pieBtn.disabled = false;
          if (data.success) {
            toast('Pie chart generated!', 'success');
            showLatestImage(data.chart_url);
            // Latest chart stays visible -- only refresh the gallery
            refreshGallery();
          } else {
            toast(data.message || 'Could not generate chart.', 'error');
            showLatestEmpty(data.message || 'Generation failed.');
          }
        })
        .catch(function (err) {
          pieBtn.disabled = false;
          console.error(err);
          toast('Network error.', 'error');
          showLatestEmpty('Network error.');
        });
    });
  }

  /* ---------- Public API ---------- */
  return {
    initDropZone: initDropZone,
    initChartBuilders: initChartBuilders,
    refreshGallery: refreshGallery,
    toast: toast
  };

})();
