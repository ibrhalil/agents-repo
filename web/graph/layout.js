(function () {
  'use strict';
  var STORE_KEY = 'nomaGraph.positions.v1';
  var MAX_ITER = 200;
  var SLICE = 20;

  var running = false;
  var lastRestoredRatio = 1;
  var live = false;
  var liveRaf = null;
  var LIVE_MAX_ORDER = 3000;

  function load() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (err) {
      return {};
    }
  }

  function save(graph) {
    var data = {};
    graph.forEachNode(function (node, attrs) {
      if (typeof attrs.x === 'number' && isFinite(attrs.x)) {
        data[node] = { x: attrs.x, y: attrs.y };
      }
    });
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(data));
    } catch (err) {}
  }

  function seed(graph) {
    var positions = load();
    var restored = 0;
    graph.forEachNode(function (node) {
      var pos = positions[node];
      if (pos && isFinite(pos.x) && isFinite(pos.y)) {
        graph.setNodeAttribute(node, 'x', pos.x);
        graph.setNodeAttribute(node, 'y', pos.y);
        restored += 1;
      } else {
        var angle = 2 * Math.PI * Math.random();
        var radius = 10 * Math.sqrt(Math.random());
        graph.setNodeAttribute(node, 'x', radius * Math.cos(angle));
        graph.setNodeAttribute(node, 'y', radius * Math.sin(angle));
      }
    });
    return graph.order ? restored / graph.order : 1;
  }

  var NOMA = (window.NOMA = window.NOMA || {});

  NOMA.layout = {
    isRunning: function () {
      return running;
    },
    seedPositions: function (graph) {
      // Sigma kurulmadan ÇAĞRILMALI: renderer node'larda sayısal x/y ister.
      lastRestoredRatio = seed(graph);
    },
    ensurePositions: function (graph, renderer, onDone) {
      if (graph.order < 2 || lastRestoredRatio >= 0.995) {
        renderer.refresh();
        if (onDone) onDone();
        return;
      }
      this.run(graph, renderer, onDone, lastRestoredRatio >= 0.9 ? 60 : MAX_ITER);
    },
    run: function (graph, renderer, onDone, iterations) {
      var total = iterations || MAX_ITER;
      var fa2 = window.graphologyLayoutForceAtlas2;
      var settings = fa2.inferSettings(graph);
      var done = 0;
      running = true;

      function step() {
        if (!running) return;
        try {
          fa2.assign(graph, { iterations: SLICE, settings: settings });
        } catch (err) {
          running = false;
          return;
        }
        done += SLICE;
        renderer.refresh();
        if (done >= total) {
          running = false;
          save(graph);
          if (onDone) onDone();
        } else {
          requestAnimationFrame(step);
        }
      }

      requestAnimationFrame(step);
    },
    stop: function () {
      running = false;
    },
    startLive: function (graph, renderer, pinned) {
      // Sürükleme sırasında canlı FA2: pinned node her karede sabitlenir,
      // komşular yaylanır (Obsidian graph hissi). file:// worker yok → main thread.
      if (graph.order > LIVE_MAX_ORDER) return;
      this.stop();
      this.stopLive();
      var fa2 = window.graphologyLayoutForceAtlas2;
      var settings = fa2.inferSettings(graph);
      settings.slowDown = Math.max(2, (settings.slowDown || 1) * 2);
      settings.gravity = 0.08;
      live = true;
      var frame = function () {
        if (!live) return;
        var px = graph.getNodeAttribute(pinned, 'x');
        var py = graph.getNodeAttribute(pinned, 'y');
        try {
          fa2.assign(graph, { iterations: 2, settings: settings });
        } catch (err) {
          live = false;
          return;
        }
        graph.setNodeAttribute(pinned, 'x', px);
        graph.setNodeAttribute(pinned, 'y', py);
        renderer.refresh({ skipIndexation: true });
        liveRaf = requestAnimationFrame(frame);
      };
      liveRaf = requestAnimationFrame(frame);
    },
    stopLive: function () {
      live = false;
      if (liveRaf !== null) {
        cancelAnimationFrame(liveRaf);
        liveRaf = null;
      }
    },
    isLive: function () {
      return live;
    },
    savePositions: save,
    reset: function (graph, renderer, onDone) {
      this.stop();
      graph.forEachNode(function (node) {
        var angle = 2 * Math.PI * Math.random();
        var radius = 10 * Math.sqrt(Math.random());
        graph.setNodeAttribute(node, 'x', radius * Math.cos(angle));
        graph.setNodeAttribute(node, 'y', radius * Math.sin(angle));
      });
      this.run(graph, renderer, onDone, MAX_ITER);
    }
  };
})();
