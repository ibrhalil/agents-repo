(function () {
  'use strict';
  var TYPE_ORDER = ['concept', 'project', 'task', 'issue', 'resource', 'person', 'decision'];
  var SCOPE_ORDER = ['work', 'personal', 'learning', 'systems', 'creator', 'media', 'common'];
  var STAGE_ORDER = ['inbox', 'next', 'in_progress', 'waiting', 'done', 'archived'];

  function fold(text) {
    return String(text || '').replace(/İ/g, 'i').toLowerCase();
  }

  function option(select, value, label) {
    var el = document.createElement('option');
    el.value = value;
    el.textContent = label;
    select.appendChild(el);
  }

  function buildSelect(id, values, order, allLabel) {
    var select = document.getElementById(id);
    var ordered = order.filter(function (value) {
      return values[value];
    });
    var rest = Object.keys(values)
      .filter(function (value) {
        return order.indexOf(value) === -1 && value;
      })
      .sort();
    option(select, '', allLabel + ' (' + Object.keys(values).reduce(function (sum, key) {
      return sum + values[key];
    }, 0) + ')');
    ordered.concat(rest).forEach(function (value) {
      option(select, value, value + ' (' + values[value] + ')');
    });
    return select;
  }

  function countBy(nodes, key) {
    var counts = {};
    nodes.forEach(function (node) {
      var value = node[key] || '';
      counts[value] = (counts[value] || 0) + 1;
    });
    return counts;
  }

  function searchNodes(nodes, rawQuery) {
    var query = fold(rawQuery.trim());
    if (!query) return [];
    var hits = [];
    nodes.forEach(function (node) {
      var label = fold(node.label);
      var slug = fold(node.id);
      var score = -1;
      if (slug === query || label === query) score = 100;
      else if (slug.indexOf(query) === 0 || label.indexOf(query) === 0) score = 60;
      else if (slug.indexOf(query) !== -1 || label.indexOf(query) !== -1) score = 30;
      if (score > 0) {
        hits.push({ node: node, score: score + Math.min(node.degree, 20) });
      }
    });
    hits.sort(function (a, b) {
      return b.score - a.score || a.node.id.localeCompare(b.node.id);
    });
    return hits.slice(0, 12).map(function (hit) {
      return hit.node;
    });
  }

  function badges(node) {
    var items = [
      { text: node.type || 'bilinmeyen', color: NOMA.render.colorOf(node) },
      node.scope,
      node.stage,
      node.status
    ].filter(Boolean);
    return items
      .map(function (item) {
        if (typeof item === 'string') {
          return '<span class="badge">' + item + '</span>';
        }
        return '<span class="badge"><span class="dot" style="background:' +
          item.color + '"></span>' + item.text + '</span>';
      })
      .join('');
  }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
    });
  }

  var NOMA = (window.NOMA = window.NOMA || {});
  var stateRef = null;
  var apiRef = null;
  var graphRef = null;
  var dataRef = null;
  var nodeIndex = {};

  function updateModeBar() {
    var bar = document.getElementById('mode-bar');
    if (!stateRef.visibleSet) {
      bar.hidden = true;
      return;
    }
    bar.hidden = false;
    var center = nodeIndex[stateRef.localCenter];
    document.getElementById('local-label').textContent =
      'Yerel: ' + (center ? center.label : stateRef.localCenter);
    document.querySelectorAll('.depth-btn').forEach(function (btn) {
      btn.classList.toggle('active', Number(btn.dataset.depth) === stateRef.depth);
    });
  }

  function updateMeta() {
    var counts = dataRef.meta.counts;
    var mode = stateRef.visibleSet ? ' · yerel graph' : '';
    document.getElementById('meta-bar').textContent =
      counts.nodes + ' not · ' + counts.edges + ' bağlantı · ' +
      counts.missing + ' eksik' + mode;
  }

  function updateSelection() {
    var panel = document.getElementById('panel');
    var id = stateRef.selected;
    if (!id || !nodeIndex[id]) {
      panel.hidden = true;
      return;
    }
    var node = nodeIndex[id];
    var tags = (node.tags || [])
      .map(function (tag) {
        return '<span class="tag">' + esc(tag) + '</span>';
      })
      .join('');
    panel.innerHTML =
      '<h2>' + esc(node.label) + '</h2>' +
      '<div class="panel-slug">' + esc(node.id) + '</div>' +
      '<div class="badges">' + badges(node) + '</div>' +
      (tags ? '<div class="tag-list">' + tags + '</div>' : '') +
      '<div class="panel-stats">' +
      '<div class="stat"><b>' + node.incoming + '</b><span>gelen</span></div>' +
      '<div class="stat"><b>' + node.outgoing + '</b><span>giden</span></div>' +
      '<div class="stat"><b>' + node.degree + '</b><span>toplam</span></div>' +
      '</div>' +
      '<div class="panel-path">' + esc(node.path || 'wiki/' + node.id + '.md yok') + '</div>' +
      (node.exists ? '' : '<div class="warn">Çözülmemiş bağlantı: hedef not bulunamadı</div>') +
      '<div class="panel-actions">' +
      '<button class="btn" id="btn-local">Yerel graph</button>' +
      (node.exists && node.url ? '<a class="btn" href="' + esc(node.url) + '" target="_blank" rel="noreferrer">URL</a>' : '') +
      '</div>';
    panel.hidden = false;
    document.getElementById('btn-local').addEventListener('click', function () {
      apiRef.setLocal(id, stateRef.depth);
    });
  }

  function renderSearch(rawQuery) {
    var box = document.getElementById('search-results');
    var query = rawQuery.trim();
    if (!query) {
      box.hidden = true;
      box.innerHTML = '';
      return;
    }
    var hits = searchNodes(dataRef.nodes, query);
    if (!hits.length) {
      box.innerHTML = '<button class="search-hit" disabled>Sonuç yok</button>';
      box.hidden = false;
      return;
    }
    box.innerHTML = '';
    hits.forEach(function (node) {
      var btn = document.createElement('button');
      btn.className = 'search-hit';
      btn.type = 'button';
      btn.innerHTML =
        '<span class="dot" style="background:' + NOMA.render.colorOf(node) + '"></span>' +
        '<span class="hit-label">' + esc(node.label) + '</span>' +
        '<span class="hit-meta">' + esc(node.type || '?') + ' · ' + node.degree + '</span>';
      btn.addEventListener('click', function () {
        apiRef.focusNode(node.id);
        box.hidden = true;
      });
      box.appendChild(btn);
    });
    box.hidden = false;
  }

  NOMA.ui = {
    init: function (data, graph, state, api) {
      stateRef = state;
      apiRef = api;
      graphRef = graph;
      dataRef = data;
      data.nodes.forEach(function (node) {
        nodeIndex[node.id] = node;
      });

      buildSelect('filter-type', countBy(data.nodes, 'type'), TYPE_ORDER, 'Tür');
      buildSelect('filter-scope', countBy(data.nodes, 'scope'), SCOPE_ORDER, 'Kapsam');
      buildSelect('filter-stage', countBy(data.nodes, 'stage'), STAGE_ORDER, 'Stage');
      var existsSelect = document.getElementById('filter-exists');
      option(existsSelect, 'all', 'Bağlantı durumu');
      option(existsSelect, 'notes', 'Notlar (' + (data.meta.counts.nodes - data.meta.counts.missing) + ')');
      option(existsSelect, 'missing', 'Eksik (' + data.meta.counts.missing + ')');

      ['filter-type', 'filter-scope', 'filter-stage', 'filter-exists'].forEach(function (id) {
        document.getElementById(id).addEventListener('change', function (event) {
          var key = id.replace('filter-', '');
          state.setFilter(key === 'exists' ? 'exists' : key, event.target.value);
        });
      });

      var search = document.getElementById('search');
      var timer = null;
      search.addEventListener('input', function () {
        clearTimeout(timer);
        timer = setTimeout(function () {
          renderSearch(search.value);
        }, 120);
      });
      search.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
          search.value = '';
          renderSearch('');
          search.blur();
        } else if (event.key === 'Enter') {
          var first = document.querySelector('#search-results .search-hit');
          if (first) first.click();
        }
      });
      document.addEventListener('click', function (event) {
        if (!event.target.closest('.search')) {
          document.getElementById('search-results').hidden = true;
        }
      });
      document.addEventListener('keydown', function (event) {
        if (event.key === '/' && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) {
          event.preventDefault();
          search.focus();
        }
        if (event.key === 'Escape' && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) {
          state.clearSelection();
          state.clearLocal();
        }
      });

      document.getElementById('btn-global').addEventListener('click', function () {
        state.clearLocal();
      });
      document.querySelectorAll('.depth-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
          state.setDepth(Number(btn.dataset.depth));
        });
      });
      document.getElementById('btn-relayout').addEventListener('click', function () {
        api.relayout();
      });

      this.updateAll();
    },
    updateAll: function () {
      updateModeBar();
      updateMeta();
      updateSelection();
    },
    onSelectionChange: function () {
      updateSelection();
      updateModeBar();
    },
    onModeChange: function () {
      updateModeBar();
      updateMeta();
    }
  };
})();
