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

  var navIndex = -1;

  function cycleNeighbor(step) {
    var base = state.selected;
    var list = base
      ? NOMA.render.neighborsSorted(graph, base)
      : graph.nodes().sort(function (a, b) {
          return (graph.getNodeAttribute(b, 'degree') || 0) -
                 (graph.getNodeAttribute(a, 'degree') || 0);
        });
    if (!list.length) return;
    navIndex = (navIndex + step + list.length) % list.length;
    var next = list[navIndex];
    state.select(next);
    NOMA.render.focusNode(renderer, graph, next, 0.12);
  }

  function moveTree(direction) {
    if (!state.selected) return;
    var next = direction > 0
      ? NOMA.render.treeParent(graph, state.selected)
      : NOMA.render.treeChild(graph, state.selected);
    if (!next) return;
    state.select(next);
    NOMA.render.focusNode(renderer, graph, next, 0.12);
  }

  function toggleLocal() {
    if (state.visibleSet && state.localCenter) {
      state.clearLocal();
    } else if (state.selected) {
      api.setLocal(state.selected, state.depth);
    }
  }

  var state = {
    selected: null,
    hover: null,
    hoverEdge: null,
    visibleSet: null,
    localCenter: null,
    depth: 1,
    physicsOn: true,
    lastDragAt: 0,
    filters: { type: '', scope: '', stage: '', exists: 'all' },
    setHover: function (node) {
      if (state.hover === node) return;
      state.hover = node;
      renderer.refresh();
      NOMA.ui.showNodeTooltip(node);
    },
    setHoverEdge: function (edge) {
      if (state.hoverEdge === edge) return;
      state.hoverEdge = edge;
      renderer.refresh();
      NOMA.ui.showEdgeTooltip(edge);
    },
    select: function (node) {
      if (state.selected && state.selected !== node) NOMA.anim.stopPulse(state.selected);
      state.selected = node;
      navIndex = -1;
      if (node) NOMA.anim.pulse(node);
      renderer.refresh();
      NOMA.ui.onSelectionChange();
    },
    clearSelection: function () {
      if (!state.selected) return;
      NOMA.anim.stopPulse(state.selected);
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
    },
    setPhysics: function (on) {
      state.physicsOn = on;
      if (!on) NOMA.layout.stopLive();
    }
  };

  function applyLocal(center, depth) {
    state.visibleSet = NOMA.render.neighborhood(graph, center, depth);
    state.localCenter = center;
    state.selected = center;
    navIndex = -1;
    renderer.refresh();
    NOMA.anim.pop(Array.from(state.visibleSet));
    NOMA.ui.onModeChange();
    NOMA.ui.onSelectionChange();
    NOMA.render.focusNode(renderer, graph, center, 0.2);
  }

  NOMA.layout.seedPositions(graph);

  var renderer = NOMA.render.create(
    graph,
    document.getElementById('graph-container'),
    state,
    {
      onDragEnd: function () {
        state.lastDragAt = performance.now();
      },
      onDragStartLive: function (node) {
        NOMA.layout.startLive(graph, renderer, node);
      },
      onDoubleClickNode: function (node) {
        state.select(node);
        NOMA.render.focusNode(renderer, graph, node, 0.12);
      },
      onDoubleClickStage: function () {
        NOMA.render.resetView(renderer);
      },
      onContextMenu: function (node, event) {
        NOMA.ui.showMenu(node, event.clientX, event.clientY);
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
      NOMA.anim.removeLoops('intro');
      NOMA.layout.reset(graph, renderer);
    },
    zoom: function (direction) {
      NOMA.render.zoom(renderer, direction);
    },
    resetView: function () {
      NOMA.render.resetView(renderer);
    }
  };

  document.addEventListener('keydown', function (event) {
    var tag = document.activeElement ? document.activeElement.tagName : '';
    if (/INPUT|SELECT|TEXTAREA/.test(tag)) return;
    switch (event.key) {
      case 'ArrowRight':
      case 'Tab':
        event.preventDefault();
        cycleNeighbor(1);
        break;
      case 'ArrowLeft':
        event.preventDefault();
        cycleNeighbor(-1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        moveTree(1);
        break;
      case 'ArrowDown':
        event.preventDefault();
        moveTree(-1);
        break;
      case 'Enter':
        event.preventDefault();
        toggleLocal();
        break;
      case '+':
      case '=':
        api.zoom(1);
        break;
      case '-':
        api.zoom(-1);
        break;
      case '0':
      case 'r':
        api.resetView();
        break;
      default:
        break;
    }
  });

  NOMA.ui.init(data, graph, state, api);
  NOMA.layout.ensurePositions(graph, renderer);
  NOMA.anim.intro(graph.nodes(), 900);
})();
