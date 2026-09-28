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

  function neighborsPanel(id) {
    var neighbors = [];
    graphRef.forEachNeighbor(id, function (neighbor) {
      neighbors.push(neighbor);
    });
    neighbors.sort(function (a, b) {
      var da = graphRef.getNodeAttribute(a, 'degree') || 0;
      var db = graphRef.getNodeAttribute(b, 'degree') || 0;
      return db - da || a.localeCompare(b);
    });
    if (!neighbors.length) return '';
    var chips = neighbors.slice(0, 10).map(function (neighbor) {
      var attrs = graphRef.getNodeAttributes(neighbor);
      var color = attrs.color || '#8b93a4';
      return '<button class="neighbor-chip" type="button" data-node="' + esc(neighbor) + '">' +
        '<span class="dot" style="background:' + color + '"></span>' +
        '<span>' + esc(attrs.label || neighbor) + '</span></button>';
    }).join('');
    return '<div class="panel-section">Komşular (' + neighbors.length + ')</div>' +
      '<div class="neighbor-list">' + chips + '</div>';
  }

  var NOMA = (window.NOMA = window.NOMA || {});
  var stateRef = null;
  var apiRef = null;
  var graphRef = null;
  var dataRef = null;
  var nodeIndex = {};
  var tooltip = null;
  var menu = null;

  function place(element, x, y) {
    element.style.left = '0px';
    element.style.top = '0px';
    var box = element.getBoundingClientRect();
    var left = Math.min(x + 14, window.innerWidth - box.width - 8);
    var top = Math.min(y + 14, window.innerHeight - box.height - 8);
    element.style.left = Math.max(8, left) + 'px';
    element.style.top = Math.max(8, top) + 'px';
  }

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
      neighborsPanel(id) +
      '<div class="panel-actions">' +
      '<button class="btn" id="btn-local">Yerel graph</button>' +
      '<button class="btn" id="btn-focus">Odakla</button>' +
      (node.exists && node.url ? '<a class="btn" href="' + esc(node.url) + '" target="_blank" rel="noreferrer">URL</a>' : '') +
      '</div>' +
      '<div class="panel-hint">← → komşu · ↑ hub · Enter yerel/global · Esc temizle</div>';
    panel.hidden = false;
    panel.scrollTop = 0;
    document.getElementById('btn-local').addEventListener('click', function () {
      apiRef.setLocal(id, stateRef.depth);
    });
    document.getElementById('btn-focus').addEventListener('click', function () {
      apiRef.focusNode(id);
    });
    panel.querySelectorAll('.neighbor-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        apiRef.focusNode(chip.dataset.node);
      });
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
      tooltip = document.getElementById('tooltip');
      menu = document.getElementById('context-menu');

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
        if (!event.target.closest('#context-menu')) {
          NOMA.ui.hideMenu();
        }
      });
      document.addEventListener('keydown', function (event) {
        if (event.key === '/' && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) {
          event.preventDefault();
          search.focus();
        }
        if (event.key === 'Escape' && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) {
          NOMA.ui.hideMenu();
          NOMA.ui.hideTooltip();
          state.clearSelection();
          state.clearLocal();
        }
      });
      var stage = document.getElementById('graph-container');
      stage.addEventListener('mousemove', function (event) {
        if (!tooltip.hidden) place(tooltip, event.clientX, event.clientY);
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
      document.getElementById('btn-zoom-in').addEventListener('click', function () {
        api.zoom(1);
      });
      document.getElementById('btn-zoom-out').addEventListener('click', function () {
        api.zoom(-1);
      });
      document.getElementById('btn-reset-view').addEventListener('click', function () {
        api.resetView();
      });
      var physicsBtn = document.getElementById('btn-physics');
      physicsBtn.classList.toggle('active', state.physicsOn);
      physicsBtn.addEventListener('click', function () {
        state.setPhysics(!state.physicsOn);
        physicsBtn.classList.toggle('active', state.physicsOn);
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
    },
    showNodeTooltip: function (node) {
      if (!node || !nodeIndex[node]) {
        this.hideTooltip();
        return;
      }
      var item = nodeIndex[node];
      tooltip.innerHTML =
        '<div class="t-label">' + esc(item.label) + '</div>' +
        '<div class="t-meta">' + esc(item.type || '?') + ' · ' + esc(item.scope || '?') +
        ' · ' + esc(item.stage || '?') + ' · ' + item.degree + ' bağlantı</div>';
      tooltip.hidden = false;
    },
    showEdgeTooltip: function (edge) {
      if (!edge || !graphRef.hasEdge(edge)) {
        this.hideTooltip();
        return;
      }
      var source = graphRef.getNodeAttributes(graphRef.source(edge));
      var target = graphRef.getNodeAttributes(graphRef.target(edge));
      var kind = graphRef.getEdgeAttributes(edge).kind === 'tree' ? 'hub bağlantısı' : 'referans';
      tooltip.innerHTML =
        '<div class="t-label">' + esc(source.label) + ' → ' + esc(target.label) + '</div>' +
        '<div class="t-meta">' + kind + '</div>';
      tooltip.hidden = false;
    },
    hideTooltip: function () {
      tooltip.hidden = true;
    },
    showMenu: function (node, x, y) {
      if (!node || !nodeIndex[node]) return;
      var item = nodeIndex[node];
      menu.innerHTML =
        '<div class="menu-title">' + esc(item.label) + '</div>' +
        '<button class="menu-item" data-action="focus">Odakla</button>' +
        '<button class="menu-item" data-action="local">Yerel graph (derinlik ' + stateRef.depth + ')</button>' +
        '<button class="menu-item" data-action="global">Genel graph</button>' +
        '<button class="menu-item" data-action="relayout">Yerleşimi yeniden diz</button>';
      menu.hidden = false;
      place(menu, x, y);
      menu.querySelectorAll('.menu-item').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var action = btn.dataset.action;
          NOMA.ui.hideMenu();
          if (action === 'focus') apiRef.focusNode(node);
          if (action === 'local') apiRef.setLocal(node, stateRef.depth);
          if (action === 'global') stateRef.clearLocal();
          if (action === 'relayout') apiRef.relayout();
        });
      });
    },
    hideMenu: function () {
      if (menu) menu.hidden = true;
    }
  };
})();
