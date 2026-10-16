// Loaded into every Node process of a perturbed run (NODE_OPTIONS=--require, or a runner's setup
// file). Inert unless a WIGGLE_ROOM_PERTURB_* variable turns a perturbation on.
'use strict';
const env = process.env;

if (env.WIGGLE_ROOM_PERTURB_CLOCK_OFFSET_MS || env.WIGGLE_ROOM_PERTURB_CLOCK_BACKWARDS_MS) {
  // Wall clock only. performance.now and hrtime are monotonic by contract, so they stay real.
  const RealDate = Date;
  const offset = Number(env.WIGGLE_ROOM_PERTURB_CLOCK_OFFSET_MS || 0);
  const window = Number(env.WIGGLE_ROOM_PERTURB_CLOCK_BACKWARDS_MS || 0);
  const t0 = RealDate.now();
  let reads = 0;
  // For the first `window` ms of the process, every read is earlier than the one before. After
  // that it snaps back to real time, so a loop waiting on a wall-clock deadline still ends.
  const now = () => {
    const real = RealDate.now();
    return offset + (real - t0 < window ? t0 - (real - t0) - ++reads : real);
  };
  function PerturbedDate(...args) {
    if (!new.target) return new RealDate(now()).toString();
    // Reflect.construct keeps `class X extends Date` working.
    return Reflect.construct(RealDate, args.length ? args : [now()], new.target);
  }
  PerturbedDate.prototype = RealDate.prototype;
  PerturbedDate.now = now;
  PerturbedDate.parse = RealDate.parse;
  PerturbedDate.UTC = RealDate.UTC;
  globalThis.Date = PerturbedDate;
}

if (env.WIGGLE_ROOM_PERTURB_RANDOM === 'extremes') {
  let i = 0;
  Math.random = () => (i++ % 2 ? 1 - 2 ** -53 : 0);
}

if (env.WIGGLE_ROOM_PERTURB_READDIR === 'reverse') {
  // readdir order is unspecified. Reversed is guaranteed to differ from whatever order code assumed.
  const fs = require('fs');
  const rev = (r) => (Array.isArray(r) ? r.slice().reverse() : r);
  const readdirSync = fs.readdirSync;
  fs.readdirSync = function (...a) { return rev(readdirSync.apply(this, a)); };
  const readdir = fs.readdir;
  fs.readdir = function (...a) {
    const cb = a.pop();
    return readdir.apply(this, [...a, (err, r) => cb(err, rev(r))]);
  };
  const promisesReaddir = fs.promises.readdir;
  fs.promises.readdir = async function (...a) { return rev(await promisesReaddir.apply(this, a)); };
  // ESM named imports of builtins are snapshots until this is called.
  require('module').syncBuiltinESMExports();
}

if (env.WIGGLE_ROOM_PERTURB_NETWORK === 'down') {
  // Refuse every non-loopback connection. Covers http, https, and fetch, which all connect
  // through net.Socket. A local test server or test database keeps working.
  const net = require('net');
  const connect = net.Socket.prototype.connect;
  const loopback = /^(localhost|127\.|::1$|::ffff:127\.|0\.0\.0\.0)/;
  net.Socket.prototype.connect = function (...args) {
    let opts = args[0];
    if (Array.isArray(opts)) opts = opts[0]; // net.connect passes pre-normalized args
    let host, path;
    if (opts && typeof opts === 'object') ({ host, path } = opts);
    else if (typeof opts === 'string' && Number.isNaN(Number(opts))) path = opts;
    else host = typeof args[1] === 'string' ? args[1] : undefined;
    if (path || !host || loopback.test(host)) return connect.apply(this, args);
    const err = Object.assign(new Error(`connect ECONNREFUSED ${host} (perturb: network down)`),
      { code: 'ECONNREFUSED', syscall: 'connect', address: host });
    process.nextTick(() => this.destroy(err));
    return this;
  };
}
