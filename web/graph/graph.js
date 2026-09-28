(function () {
  'use strict';
  var data = window.NOMA_GRAPH;
  var notice = document.getElementById('notice');

  function fail(message) {
    notice.style.display = 'flex';
    notice.innerHTML = '<div>' + message + '</div>';
  }

  if (!window.graphology || !window.Sigma || !window.graphologyLayoutForceAtlas2) {
    fail('Vendor kütüphaneleri yüklenemedi (web/vendor/).');
    return;
  }
  if (!data || !data.nodes) {
    fail('Graph verisi yok.<br><code>python3 scripts/noma_build_graph.py</code>');
    return;
  }
  if (!data.nodes.length) {
    fail('Wiki boş — graph gösterilecek not bulamadı.');
    return;
  }

  var graph = new graphology.Graph({ type: 'directed', multi: false });
  data.nodes.forEach(function (node) {
    graph.addNode(node.id, {
      label: node.label,
      size: NOMA.render.sizeOf(node),
      color: NOMA.render.colorOf(node),
      nodeType: node.type,
      stage: node.stage,
      scope: node.scope,
      status: node.status,
      tags: node.tags || [],
      exists: node.exists,
      path: node.path,
      incoming: node.incoming,
      outgoing: node.outgoing,
      degree: node.degree
    });
  });
  data.edges.forEach(function (edge) {
    if (edge.source === edge.target || graph.hasEdge(edge.source, edge.target)) return;
    graph.addEdge(edge.source, edge.target, {
      size: 0.8,
      color: NOMA.render.EDGE_COLOR,
      kind: edge.kind
    });
  });

  var state = {
    selected: null,
    hover: null,
    visibleSet: null,
    localCenter: null,
    depth: 1,
    lastDragAt: 0,
    filters: { type: '', scope: '', stage: '', exists: 'all' },
    setHover: function (node) {
      if (state.hover === node) return;
      state.hover = node;
      renderer.refresh();
    },
    select: function (node) {
      state.selected = node;
      renderer.refresh();
      NOMA.ui.onSelectionChange();
    },
    clearSelection: function () {
      if (!state.selected) return;
      state.selected = null;
      renderer.refresh();
      NOMA.ui.onSelectionChange();
    },
    setFilter: function (key, value) {
      state.filters[key] = value;
      renderer.refresh();
    },
    setDepth: function (depth) {
      state.depth = depth;
      if (state.localCenter) {
        applyLocal(state.localCenter, depth);
      } else {
        NOMA.ui.onModeChange();
      }
    },
    clearLocal: function () {
      if (!state.visibleSet) return;
      state.visibleSet = null;
      state.localCenter = null;
      renderer.refresh();
      NOMA.ui.onModeChange();
    }
  };

  function applyLocal(center, depth) {
    state.visibleSet = NOMA.render.neighborhood(graph, center, depth);
    state.localCenter = center;
    state.selected = center;
    renderer.refresh();
    NOMA.ui.onModeChange();
    NOMA.ui.onSelectionChange();
  }

  NOMA.layout.seedPositions(graph);

  var renderer = NOMA.render.create(
    graph,
    document.getElementById('graph-container'),
    state,
    {
      onDragEnd: function () {
        state.lastDragAt = performance.now();
      }
    }
  );

  var api = {
    focusNode: function (node) {
      state.select(node);
      NOMA.render.focusNode(renderer, graph, node);
    },
    setLocal: applyLocal,
    relayout: function () {
      NOMA.layout.reset(graph, renderer);
    }
  };

  NOMA.ui.init(data, graph, state, api);
  NOMA.layout.ensurePositions(graph, renderer);
})();
