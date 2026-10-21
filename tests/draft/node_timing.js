// Functions for speed tests that run in Node. A test puts this text at the start of its driver script.
// A fixed limit in ms failed at random on slow CI runners (#83). A speed test now divides the time of the engine
// calls by the time of reference(), in the same Node process. A slow runner makes both times slower, so the ratio
// changes less than the time in ms.

// The least time of 5 calls of f, in ms. The least time leaves out most of the noise from other work on the machine.
function best(f) {
  let least = Infinity;
  for (let i = 0; i < 5; i++) {
    const start = performance.now();
    f();
    least = Math.min(least, performance.now() - start);
  }
  return least;
}

// Fixed work that does not use an engine: objects, Set lookups and small sorts. It takes about 10 ms on the
// owner's machine.
function reference() {
  const items = Array.from({ length: 500 }, (_, i) => ({ id: i, team: `T${(i * 7) % 30}`, value: (i * 37) % 101 }));
  const days = Array.from({ length: 21 }, (_, d) => new Set(items.filter(p => (p.id + d) % 3 === 0).map(p => p.team)));
  let n = 0;
  for (let round = 0; round < 10; round++) {
    for (const p of items) {
      days.forEach((teams, i) => {
        if (!teams.has(p.team)) return;
        const some = items.slice(i + round, i + round + 8).concat([p]);
        some.sort((a, b) => b.value - a.value);
        n += some[0].id;
      });
    }
  }
  return n;
}
