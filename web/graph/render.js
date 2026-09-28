(function () {
  'use strict';
  var TYPE_COLORS = {
    concept: '#7aa2f7',
    project: '#9ece6a',
    task: '#e0af68',
    issue: '#f7768e',
    resource: '#bb9af7',
    person: '#7dcfff',
    decision: '#ff9e64'
  };
  var UNKNOWN_COLOR = '#8b93a4';
  var MISSING_COLOR = '#565f89';
  var EDGE_COLOR = '#333947';
  var EDGE_FOCUS_COLOR = '#7aa2f7';
  var EDGE_DIM_COLOR = '#1e222a';
  var NODE_DIM_COLOR = '#262b34';

  function colorOf(node) {
    if (!node.exists) return MISSING_COLOR;
    return TYPE_COLORS[node.type] || UNKNOWN_COLOR;
  }

  function sizeOf(node) {
    return Math.min(26, 4 + 2 * Math.sqrt(node.degree || 0));
  }

  function passesFilters(attrs, filters) {
    if (filters.type && attrs.nodeType !== filters.type) return false;
    if (filters.scope && attrs.scope !== filters.scope) return false;
    if (filters.stage && attrs.stage !== filters.stage) return false;
    if (filters.exists === 'notes' && !attrs.exists) return false;
    if (filters.exists === 'missing' && attrs.exists) return false;
    return true;
  }

  function neighborhood(graph, start, depth) {
    var seen = new Set([start]);
    var frontier = [start];
    for (var d = 0; d < depth; d += 1) {
      var next = [];
      frontier.forEach(function (current) {
        graph.forEachNeighbor(current, function (neighbor) {
          if (!seen.has(neighbor)) {
            seen.add(neighbor);
            next.push(neighbor);
          }
        });
      });
      frontier = next;
    }
    return seen;
  }

  function neighborsSorted(graph, node) {
    var out = [];
    graph.forEachNeighbor(node, function (neighbor) {
      out.push(neighbor);
    });
    out.sort(function (a, b) {
      var da = graph.getNodeAttribute(a, 'degree') || 0;
      var db = graph.getNodeAttribute(b, 'degree') || 0;
      return db - da || a.localeCompare(b);
    });
    return out;
  }

  var NOMA = (window.NOMA = window.NOMA || {});

  NOMA.render = {
    EDGE_COLOR: EDGE_COLOR,
    colorOf: colorOf,
    sizeOf: sizeOf,
    neighborhood: neighborhood,
    neighborsSorted: neighborsSorted,
    treeParent: function (graph, node) {
      var found = null;
      graph.forEachOutEdge(node, function (edge, attrs, source, target) {
        if (attrs.kind === 'tree' && !found) found = target;
      });
      return found;
    },
    treeChild: function (graph, node) {
      var found = null;
      graph.forEachInEdge(node, function (edge, attrs, source, target) {
        if (attrs.kind === 'tree' && !found) found = source;
      });
      return found;
    },
    create: function (graph, container, state, handlers) {
      var renderer = new Sigma(graph, container, {
        allowInvalidContainer: false,
        minCameraRatio: 0.02,
        maxCameraRatio: 30,
        labelDensity: 0.5,
        labelGridCellSize: 120,
        labelRenderedSizeThreshold: 6.5,
        labelFont: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        labelSize: 12,
        labelWeight: '500',
        labelColor: { color: '#c2c9d6' },
        stagePadding: 2,
        nodeReducer: function (node, attrs) {
          var res = Object.assign({}, attrs);
          if (state.visibleSet && !state.visibleSet.has(node)) {
            res.hidden = true;
            return res;
          }
          if (!passesFilters(attrs, state.filters)) {
            res.hidden = true;
            return res;
          }
          res.size = Math.max(0.6, attrs.size * NOMA.anim.scale(node));
          var focus = state.hover || state.selected;
          if (focus) {
            if (node === focus) {
              res.highlighted = true;
              res.forceLabel = true;
            } else if (graph.hasEdge(node, focus) || graph.hasEdge(focus, node)) {
              res.forceLabel = true;
            } else {
              res.color = NODE_DIM_COLOR;
              res.label = '';
            }
          } else if (node === state.selected) {
            res.highlighted = true;
          }
          if (state.hoverEdge) {
            var hoverSource = graph.source(state.hoverEdge);
            var hoverTarget = graph.target(state.hoverEdge);
            if (node === hoverSource || node === hoverTarget) {
              res.forceLabel = true;
              res.size = Math.max(res.size, attrs.size * 1.15);
            } else if (!focus) {
              res.color = NODE_DIM_COLOR;
              res.label = '';
            }
          }
          if (state.selected === node) {
            res.highlighted = true;
            res.forceLabel = true;
          }
          return res;
        },
        edgeReducer: function (edge, attrs) {
          var res = Object.assign({}, attrs);
          var source = graph.source(edge);
          var target = graph.target(edge);
          if (state.visibleSet && (!state.visibleSet.has(source) || !state.visibleSet.has(target))) {
            res.hidden = true;
            return res;
          }
          if (!passesFilters(graph.getNodeAttributes(source), state.filters) ||
              !passesFilters(graph.getNodeAttributes(target), state.filters)) {
            res.hidden = true;
            return res;
          }
          if (state.hoverEdge === edge) {
            res.color = EDGE_FOCUS_COLOR;
            res.size = 2.4;
            return res;
          }
          var focus = state.hover || state.selected;
          if (focus) {
            var touched = source === focus || target === focus;
            res.color = touched ? EDGE_FOCUS_COLOR : EDGE_DIM_COLOR;
            res.size = touched ? 1.6 : 0.5;
          }
          return res;
        }
      });
      NOMA.renderer = renderer;

      var hoverTween = function (node, on) {
        if (!node || node === state.selected) return;
        NOMA.anim.tweenScale(node, on ? 1.18 : 1, 200);
      };

      renderer.on('enterNode', function (event) {
        container.style.cursor = 'pointer';
        state.setHover(event.node);
        hoverTween(event.node, true);
      });
      renderer.on('leaveNode', function () {
        container.style.cursor = 'default';
        state.setHover(null);
      });
      renderer.on('enterEdge', function (event) {
        container.style.cursor = 'crosshair';
        state.setHoverEdge(event.edge);
      });
      renderer.on('leaveEdge', function () {
        container.style.cursor = 'default';
        state.setHoverEdge(null);
      });
      renderer.on('clickNode', function (event) {
        state.select(event.node);
      });
      renderer.on('clickStage', function () {
        if (performance.now() - (state.lastDragAt || 0) < 150) return;
        state.clearSelection();
      });
      renderer.on('doubleClickNode', function (event) {
        event.event.preventDefault();
        if (handlers.onDoubleClickNode) handlers.onDoubleClickNode(event.node);
      });
      renderer.on('doubleClickStage', function (event) {
        event.event.preventDefault();
        if (handlers.onDoubleClickStage) handlers.onDoubleClickStage();
      });
      renderer.on('rightClickNode', function (event) {
        event.event.preventDefault();
        state.select(event.node);
        if (handlers.onContextMenu) {
          handlers.onContextMenu(event.node, event.event);
        }
      });

      var dragNode = null;
      var dragMoved = false;
      renderer.on('downNode', function (event) {
        dragNode = event.node;
        dragMoved = false;
      });
      var mouseCaptor = renderer.getMouseCaptor();
      mouseCaptor.on('mousemovebody', function (event) {
        if (!dragNode) return;
        if (!dragMoved) {
          dragMoved = true;
          NOMA.layout.stop();
          if (state.physicsOn && handlers.onDragStartLive) {
            handlers.onDragStartLive(dragNode);
          }
        }
        var pos = renderer.viewportToGraph(event);
        graph.setNodeAttribute(dragNode, 'x', pos.x);
        graph.setNodeAttribute(dragNode, 'y', pos.y);
        renderer.refresh({ skipIndexation: true });
      });
      var finishDrag = function () {
        if (!dragNode) return;
        if (dragMoved) {
          NOMA.layout.stopLive();
          NOMA.layout.savePositions(graph);
          if (handlers.onDragEnd) handlers.onDragEnd(dragNode);
        }
        dragNode = null;
      };
      mouseCaptor.on('mouseup', finishDrag);
      window.addEventListener('mouseup', finishDrag);
      window.addEventListener('blur', finishDrag);

      if (handlers.onReady) handlers.onReady(renderer);
      return renderer;
    },
    focusNode: function (renderer, graph, node, ratioTarget) {
      var attrs = graph.getNodeAttributes(node);
      if (!isFinite(attrs.x)) return;
      var camera = renderer.getCamera();
      camera.animate(
        { x: attrs.x, y: attrs.y, ratio: Math.min(camera.ratio, ratioTarget || 0.12) },
        { duration: 380, easing: 'cubicInOut' }
      );
    },
    zoom: function (renderer, direction) {
      var camera = renderer.getCamera();
      if (direction > 0) {
        camera.animatedZoom({ duration: 260, factor: 1.25 });
      } else {
        camera.animatedUnzoom({ duration: 260, factor: 1.25 });
      }
    },
    resetView: function (renderer) {
      renderer.getCamera().animatedReset({ duration: 420 });
    }
  };
})();
