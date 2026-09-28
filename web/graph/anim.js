(function () {
  'use strict';
  var scales = {};
  var tweenJobs = [];
  var loops = [];
  var raf = null;

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function tick(now) {
    var active = false;
    now = now || performance.now();
    tweenJobs = tweenJobs.filter(function (job) {
      var t = Math.min(1, (now - job.start) / job.dur);
      job.set(job.from + (job.to - job.from) * job.ease(t));
      return t < 1;
    });
    if (tweenJobs.length) active = true;
    loops = loops.filter(function (fn) {
      if (fn(now) !== false) {
        active = true;
        return true;
      }
      return false;
    });
    if (window.NOMA && window.NOMA.renderer) window.NOMA.renderer.refresh();
    if (active) {
      raf = requestAnimationFrame(tick);
    } else {
      raf = null;
    }
  }

  function kick() {
    if (raf === null) raf = requestAnimationFrame(tick);
  }

  var NOMA = (window.NOMA = window.NOMA || {});

  NOMA.anim = {
    scale: function (node) {
      var value = scales[node];
      return value == null ? 1 : value;
    },
    tweenScale: function (node, to, duration) {
      var from = scales[node] == null ? 1 : scales[node];
      var target = scales[node] = from;
      tweenJobs.push({
        from: target,
        to: to,
        start: performance.now(),
        dur: duration || 220,
        ease: easeOutCubic,
        set: (function (id) {
          return function (value) {
            scales[id] = value;
          };
        })(node)
      });
      kick();
    },
    addLoop: function (fn) {
      loops.push(fn);
      kick();
      return fn;
    },
    removeLoops: function (tag) {
      loops = loops.filter(function (fn) {
        return fn.tag !== tag;
      });
    },
    pulse: function (node) {
      this.removeLoops('pulse');
      if (!node) return;
      this.addLoop(
        (function (id) {
          fn.tag = 'pulse';
          return fn;
          function fn(now) {
            scales[id] = 1 + 0.09 * Math.sin(now / 180);
            return true;
          }
        })(node)
      );
    },
    stopPulse: function (node) {
      this.removeLoops('pulse');
      if (node) this.tweenScale(node, 1, 260);
    },
    intro: function (nodes, duration) {
      var phases = {};
      var staggered = nodes.length <= 2000;
      nodes.forEach(function (id, index) {
        phases[id] = staggered ? (index % 40) * 0.006 : 0;
      });
      var t0 = performance.now();
      this.addLoop(
        (function (t0, phases, duration) {
          fn.tag = 'intro';
          return fn;
          function fn(now) {
            var t = (now - t0) / duration;
            if (t >= 1.3) {
              Object.keys(phases).forEach(function (id) {
                scales[id] = 1;
              });
              return false;
            }
            Object.keys(phases).forEach(function (id) {
              var local = Math.max(0, Math.min(1, (t - phases[id]) / 0.75));
              scales[id] = easeOutCubic(local);
            });
            return true;
          }
        })(t0, phases, duration)
      );
    },
    pop: function (nodes) {
      var t0 = performance.now();
      var list = nodes.slice(0, 400);
      this.addLoop(
        (function (t0, list) {
          fn.tag = 'pop';
          return fn;
          function fn(now) {
            var t = (now - t0) / 320;
            if (t >= 1) {
              list.forEach(function (id) {
                scales[id] = 1;
              });
              return false;
            }
            list.forEach(function (id, index) {
              var delay = Math.min(index * 4, 120);
              var local = Math.max(0, Math.min(1, ((now - t0) - delay) / 220));
              scales[id] = 0.6 + 0.4 * easeOutCubic(local);
            });
            return true;
          }
        })(t0, list)
      );
    }
  };
})();
