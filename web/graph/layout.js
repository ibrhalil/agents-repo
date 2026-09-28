(function () {
  'use strict';
  var STORE_KEY = 'nomaGraph.positions.v1';
  var MAX_ITER = 200;
  var SLICE = 20;

  var running = false;
  var lastRestoredRatio = 1;

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
      if (graph.order < 2 || lastRestoredRatio >= 0.9) {
        renderer.refresh();
        if (onDone) onDone();
        return;
      }
      this.run(graph, renderer, onDone, MAX_ITER);
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
