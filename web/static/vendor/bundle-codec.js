// Official fflate + MessagePack + ZIP bundle codec extracted verbatim from parsed_js/bundle.js
(function (global) {
  'use strict';
var Xi = Uint8Array,
      ji = Uint16Array,
      $i = Int32Array,
      Ki = new Xi([0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0, 0, 0, 0]),
      qi = new Xi([0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13, 0, 0]),
      Zi = new Xi([16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]),
      Qi = function(t, e) {
        for (var i = new ji(31), s = 0; s < 31; ++s) i[s] = e += 1 << t[s - 1];
        var n = new $i(i[30]);
        for (s = 1; s < 30; ++s)
          for (var r = i[s]; r < i[s + 1]; ++r) n[r] = r - i[s] << 5 | s;
        return {
          b: i,
          r: n
        }
      },
      Ji = Qi(Ki, 2),
      ts = Ji.b,
      es = Ji.r;
    ts[28] = 258, es[258] = 28;
    for (var is = Qi(qi, 0), ss = is.b, ns = (is.r, new ji(32768)), rs = 0; rs < 32768; ++rs) {
      var as = (43690 & rs) >> 1 | (21845 & rs) << 1;
      as = (61680 & (as = (52428 & as) >> 2 | (13107 & as) << 2)) >> 4 | (3855 & as) << 4, ns[rs] = ((65280 & as) >> 8 | (255 & as) << 8) >> 1
    }
    var os = function(t, e, i) {
        for (var s = t.length, n = 0, r = new ji(e); n < s; ++n) t[n] && ++r[t[n] - 1];
        var a, o = new ji(e);
        for (n = 1; n < e; ++n) o[n] = o[n - 1] + r[n - 1] << 1;
        if (i) {
          a = new ji(1 << e);
          var h = 15 - e;
          for (n = 0; n < s; ++n)
            if (t[n])
              for (var l = n << 4 | t[n], c = e - t[n], d = o[t[n] - 1]++ << c, u = d | (1 << c) - 1; d <= u; ++d) a[ns[d] >> h] = l
        } else
          for (a = new ji(s), n = 0; n < s; ++n) t[n] && (a[n] = ns[o[t[n] - 1]++] >> 15 - t[n]);
        return a
      },
      hs = new Xi(288);
    for (rs = 0; rs < 144; ++rs) hs[rs] = 8;
    for (rs = 144; rs < 256; ++rs) hs[rs] = 9;
    for (rs = 256; rs < 280; ++rs) hs[rs] = 7;
    for (rs = 280; rs < 288; ++rs) hs[rs] = 8;
    var ls = new Xi(32);
    for (rs = 0; rs < 32; ++rs) ls[rs] = 5;
    var cs = os(hs, 9, 1),
      ds = os(ls, 5, 1),
      us = function(t) {
        for (var e = t[0], i = 1; i < t.length; ++i) t[i] > e && (e = t[i]);
        return e
      },
      ps = function(t, e, i) {
        var s = e / 8 | 0;
        return (t[s] | t[s + 1] << 8) >> (7 & e) & i
      },
      gs = function(t, e) {
        var i = e / 8 | 0;
        return (t[i] | t[i + 1] << 8 | t[i + 2] << 16) >> (7 & e)
      },
      ms = function(t) {
        return (t + 7) / 8 | 0
      },
      fs = function(t, e, i) {
        return (null == e || e < 0) && (e = 0), (null == i || i > t.length) && (i = t.length), new Xi(t.subarray(e, i))
      },
      ys = ["unexpected EOF", "invalid block type", "invalid length/literal", "invalid distance", "stream finished", "no stream handler", , "no callback", "invalid UTF-8 data", "extra field too long", "date not in range 1980-2099", "filename too long", "stream finishing", "invalid zip data"],
      _s = function(t, e, i) {
        var s = new Error(e || ys[t]);
        if (s.code = t, Error.captureStackTrace && Error.captureStackTrace(s, _s), !i) throw s;
        return s
      },
      bs = function(t, e, i, s) {
        var n = t.length,
          r = s ? s.length : 0;
        if (!n || e.f && !e.l) return i || new Xi(0);
        var a = !i,
          o = a || 2 != e.i,
          h = e.i;
        a && (i = new Xi(3 * n));
        var l = function(t) {
            var e = i.length;
            if (t > e) {
              var s = new Xi(Math.max(2 * e, t));
              s.set(i), i = s
            }
          },
          c = e.f || 0,
          d = e.p || 0,
          u = e.b || 0,
          p = e.l,
          g = e.d,
          m = e.m,
          f = e.n,
          y = 8 * n;
        do {
          if (!p) {
            c = ps(t, d, 1);
            var _ = ps(t, d + 1, 3);
            if (d += 3, !_) {
              var b = t[(E = ms(d) + 4) - 4] | t[E - 3] << 8,
                v = E + b;
              if (v > n) {
                h && _s(0);
                break
              }
              o && l(u + b), i.set(t.subarray(E, v), u), e.b = u += b, e.p = d = 8 * v, e.f = c;
              continue
            }
            if (1 == _) p = cs, g = ds, m = 9, f = 5;
            else if (2 == _) {
              var x = ps(t, d, 31) + 257,
                w = ps(t, d + 10, 15) + 4,
                S = x + ps(t, d + 5, 31) + 1;
              d += 14;
              for (var T = new Xi(S), C = new Xi(19), k = 0; k < w; ++k) C[Zi[k]] = ps(t, d + 3 * k, 7);
              d += 3 * w;
              var P = us(C),
                A = (1 << P) - 1,
                I = os(C, P, 1);
              for (k = 0; k < S;) {
                var E, O = I[ps(t, d, A)];
                if (d += 15 & O, (E = O >> 4) < 16) T[k++] = E;
                else {
                  var M = 0,
                    B = 0;
                  for (16 == E ? (B = 3 + ps(t, d, 3), d += 2, M = T[k - 1]) : 17 == E ? (B = 3 + ps(t, d, 7), d += 3) : 18 == E && (B = 11 + ps(t, d, 127), d += 7); B--;) T[k++] = M
                }
              }
              var R = T.subarray(0, x),
                D = T.subarray(x);
              m = us(R), f = us(D), p = os(R, m, 1), g = os(D, f, 1)
            } else _s(1);
            if (d > y) {
              h && _s(0);
              break
            }
          }
          o && l(u + 131072);
          for (var L = (1 << m) - 1, F = (1 << f) - 1, N = d;; N = d) {
            var V = (M = p[gs(t, d) & L]) >> 4;
            if ((d += 15 & M) > y) {
              h && _s(0);
              break
            }
            if (M || _s(2), V < 256) i[u++] = V;
            else {
              if (256 == V) {
                N = d, p = null;
                break
              }
              var z = V - 254;
              if (V > 264) {
                var U = Ki[k = V - 257];
                z = ps(t, d, (1 << U) - 1) + ts[k], d += U
              }
              var H = g[gs(t, d) & F],
                W = H >> 4;
              H || _s(3), d += 15 & H;
              D = ss[W];
              if (W > 3) {
                U = qi[W];
                D += gs(t, d) & (1 << U) - 1, d += U
              }
              if (d > y) {
                h && _s(0);
                break
              }
              o && l(u + 131072);
              var Y = u + z;
              if (u < D) {
                var G = r - D,
                  X = Math.min(D, Y);
                for (G + u < 0 && _s(3); u < X; ++u) i[u] = s[G + u]
              }
              for (; u < Y; ++u) i[u] = i[u - D]
            }
          }
          e.l = p, e.p = N, e.b = u, e.f = c, p && (c = 1, e.m = m, e.d = g, e.n = f)
        } while (!c);
        return u != i.length && a ? fs(i, 0, u) : i.subarray(0, u)
      },
      vs = new Xi(0),
      xs = function(t, e) {
        return t[e] | t[e + 1] << 8
      },
      ws = function(t, e) {
        return (t[e] | t[e + 1] << 8 | t[e + 2] << 16 | t[e + 3] << 24) >>> 0
      },
      Ss = function(t, e) {
        return ws(t, e) + 4294967296 * ws(t, e + 4)
      };

    function Ts(t, e) {
      return bs(t, {
        i: 2
      }, e && e.out, e && e.dictionary)
    }
    var Cs = "undefined" != typeof TextDecoder && new TextDecoder;
    try {
      Cs.decode(vs, {
        stream: !0
      })
    } catch (t) {}
    var ks = function(t) {
      for (var e = "", i = 0;;) {
        var s = t[i++],
          n = (s > 127) + (s > 223) + (s > 239);
        if (i + n > t.length) return {
          s: e,
          r: fs(t, i - 1)
        };
        n ? 3 == n ? (s = ((15 & s) << 18 | (63 & t[i++]) << 12 | (63 & t[i++]) << 6 | 63 & t[i++]) - 65536, e += String.fromCharCode(55296 | s >> 10, 56320 | 1023 & s)) : e += 1 & n ? String.fromCharCode((31 & s) << 6 | 63 & t[i++]) : String.fromCharCode((15 & s) << 12 | (63 & t[i++]) << 6 | 63 & t[i++]) : e += String.fromCharCode(s)
      }
    };

    function Ps(t, e) {
      if (e) {
        for (var i = "", s = 0; s < t.length; s += 16384) i += String.fromCharCode.apply(null, t.subarray(s, s + 16384));
        return i
      }
      if (Cs) return Cs.decode(t);
      var n = ks(t),
        r = n.s;
      return (i = n.r).length && _s(8), r
    }
    var As = function(t, e) {
        return e + 30 + xs(t, e + 26) + xs(t, e + 28)
      },
      Is = function(t, e, i) {
        var s = xs(t, e + 28),
          n = xs(t, e + 30),
          r = Ps(t.subarray(e + 46, e + 46 + s), !(2048 & xs(t, e + 8))),
          a = e + 46 + s,
          o = Es(t, a, n, i, ws(t, e + 20), ws(t, e + 24), ws(t, e + 42)),
          h = o[0],
          l = o[1],
          c = o[2];
        return [xs(t, e + 10), h, l, r, a + n + xs(t, e + 32), c]
      },
      Es = function(t, e, i, s, n, r, a) {
        var o = 4294967295 == n,
          h = 4294967295 == r,
          l = 4294967295 == a,
          c = e + i;
        if (s && o + h + l) {
          for (; e + 4 < c; e += 4 + xs(t, e + 2))
            if (1 == xs(t, e)) return [o ? Ss(t, e + 4 + 8 * h) : n, h ? Ss(t, e + 4) : r, l ? Ss(t, e + 4 + 8 * (h + o)) : a, 1];
          s < 2 && _s(13)
        }
        return [n, r, a, 0]
      };
    "function" == typeof queueMicrotask ? queueMicrotask : "function" == typeof setTimeout && setTimeout;

    function Os(t) {
      return `${t<0?"-":""}0x${Math.abs(t).toString(16).padStart(2,"0")}`
    }
    class Ms {
      type;
      data;
      constructor(t, e) {
        this.type = t, this.data = e
      }
    }
    class Bs extends Error {
      constructor(t) {
        super(t);
        const e = Object.create(Bs.prototype);
        Object.setPrototypeOf(this, e), Object.defineProperty(this, "name", {
          configurable: !0,
          enumerable: !1,
          value: Bs.name
        })
      }
    }
    const Rs = 4294967295;

    function Ds(t, e) {
      return 4294967296 * t.getInt32(e) + t.getUint32(e + 4)
    }

    function Ls({
      sec: t,
      nsec: e
    }) {
      if (t >= 0 && e >= 0 && t <= 17179869183) {
        if (0 === e && t <= 4294967295) {
          const e = new Uint8Array(4);
          return new DataView(e.buffer).setUint32(0, t), e
        } {
          const i = t / 4294967296,
            s = 4294967295 & t,
            n = new Uint8Array(8),
            r = new DataView(n.buffer);
          return r.setUint32(0, e << 2 | 3 & i), r.setUint32(4, s), n
        }
      } {
        const i = new Uint8Array(12),
          s = new DataView(i.buffer);
        return s.setUint32(0, e),
          function(t, e, i) {
            const s = Math.floor(i / 4294967296),
              n = i;
            t.setUint32(e, s), t.setUint32(e + 4, n)
          }(s, 4, t), i
      }
    }
    const Fs = {
      type: -1,
      encode: function(t) {
        if (t instanceof Date) {
          return Ls(function(t) {
            const e = t.getTime(),
              i = Math.floor(e / 1e3),
              s = 1e6 * (e - 1e3 * i),
              n = Math.floor(s / 1e9);
            return {
              sec: i + n,
              nsec: s - 1e9 * n
            }
          }(t))
        }
        return null
      },
      decode: function(t) {
        const e = function(t) {
          const e = new DataView(t.buffer, t.byteOffset, t.byteLength);
          switch (t.byteLength) {
            case 4:
              return {
                sec: e.getUint32(0), nsec: 0
              };
            case 8: {
              const t = e.getUint32(0);
              return {
                sec: 4294967296 * (3 & t) + e.getUint32(4),
                nsec: t >>> 2
              }
            }
            case 12:
              return {
                sec: Ds(e, 4), nsec: e.getUint32(0)
              };
            default:
              throw new Bs(`Unrecognized data size for timestamp (expected 4, 8, or 12): ${t.length}`)
          }
        }(t);
        return new Date(1e3 * e.sec + e.nsec / 1e6)
      }
    };
    class Ns {
      static defaultCodec = new Ns;
      __brand;
      builtInEncoders = [];
      builtInDecoders = [];
      encoders = [];
      decoders = [];
      constructor() {
        this.register(Fs)
      }
      register({
        type: t,
        encode: e,
        decode: i
      }) {
        if (t >= 0) this.encoders[t] = e, this.decoders[t] = i;
        else {
          const s = -1 - t;
          this.builtInEncoders[s] = e, this.builtInDecoders[s] = i
        }
      }
      tryToEncode(t, e) {
        for (let i = 0; i < this.builtInEncoders.length; i++) {
          const s = this.builtInEncoders[i];
          if (null != s) {
            const n = s(t, e);
            if (null != n) {
              return new Ms(-1 - i, n)
            }
          }
        }
        for (let i = 0; i < this.encoders.length; i++) {
          const s = this.encoders[i];
          if (null != s) {
            const n = s(t, e);
            if (null != n) {
              return new Ms(i, n)
            }
          }
        }
        return t instanceof Ms ? t : null
      }
      decode(t, e, i) {
        const s = e < 0 ? this.builtInDecoders[-1 - e] : this.decoders[e];
        return s ? s(t, e, i) : new Ms(e, t)
      }
    }
    new TextEncoder;

    function Vs(t, e, i) {
      let s = e;
      const n = s + i,
        r = [];
      let a = "";
      for (; s < n;) {
        const e = t[s++];
        if (128 & e)
          if (192 == (224 & e)) {
            const i = 63 & t[s++];
            r.push((31 & e) << 6 | i)
          } else if (224 == (240 & e)) {
          const i = 63 & t[s++],
            n = 63 & t[s++];
          r.push((31 & e) << 12 | i << 6 | n)
        } else if (240 == (248 & e)) {
          let i = (7 & e) << 18 | (63 & t[s++]) << 12 | (63 & t[s++]) << 6 | 63 & t[s++];
          i > 65535 && (i -= 65536, r.push(i >>> 10 & 1023 | 55296), i = 56320 | 1023 & i), r.push(i)
        } else r.push(e);
        else r.push(e);
        r.length >= 4096 && (a += String.fromCharCode(...r), r.length = 0)
      }
      return r.length > 0 && (a += String.fromCharCode(...r)), a
    }
    const zs = new TextDecoder;

    function Us(t, e, i) {
      return i > 200 ? function(t, e, i) {
        const s = t.subarray(e, e + i);
        return zs.decode(s)
      }(t, e, i) : Vs(t, e, i)
    }

    function Hs(t) {
      return t instanceof Uint8Array ? t : ArrayBuffer.isView(t) ? new Uint8Array(t.buffer, t.byteOffset, t.byteLength) : function(t) {
        return t instanceof ArrayBuffer || "undefined" != typeof SharedArrayBuffer && t instanceof SharedArrayBuffer
      }(t) ? new Uint8Array(t) : Uint8Array.from(t)
    }
    const Ws = "array",
      Ys = "map_key",
      Gs = "map_value",
      Xs = t => {
        if ("string" == typeof t || "number" == typeof t) return t;
        throw new Bs("The type of key must be string or number but " + typeof t)
      };
    class js {
      stack = [];
      stackHeadPosition = -1;
      get length() {
        return this.stackHeadPosition + 1
      }
      top() {
        return this.stack[this.stackHeadPosition]
      }
      pushArrayState(t) {
        const e = this.getUninitializedStateFromPool();
        e.type = Ws, e.position = 0, e.size = t, e.array = new Array(t)
      }
      pushMapState(t) {
        const e = this.getUninitializedStateFromPool();
        e.type = Ys, e.readCount = 0, e.size = t, e.map = {}
      }
      getUninitializedStateFromPool() {
        if (this.stackHeadPosition++, this.stackHeadPosition === this.stack.length) {
          const t = {
            type: void 0,
            size: 0,
            array: void 0,
            position: 0,
            readCount: 0,
            map: void 0,
            key: null
          };
          this.stack.push(t)
        }
        return this.stack[this.stackHeadPosition]
      }
      release(t) {
        if (this.stack[this.stackHeadPosition] !== t) throw new Error("Invalid stack state. Released state is not on top of the stack.");
        if (t.type === Ws) {
          const e = t;
          e.size = 0, e.array = void 0, e.position = 0, e.type = void 0
        }
        if (t.type === Ys || t.type === Gs) {
          const e = t;
          e.size = 0, e.map = void 0, e.readCount = 0, e.type = void 0
        }
        this.stackHeadPosition--
      }
      reset() {
        this.stack.length = 0, this.stackHeadPosition = -1
      }
    }
    const $s = new DataView(new ArrayBuffer(0)),
      Ks = new Uint8Array($s.buffer);
    try {
      $s.getInt8(0)
    } catch (t) {
      if (!(t instanceof RangeError)) throw new Error("This module is not supported in the current JavaScript engine because DataView does not throw RangeError on out-of-bounds access")
    }
    const qs = new RangeError("Insufficient data"),
      Zs = new class {
        hit = 0;
        miss = 0;
        caches;
        maxKeyLength;
        maxLengthPerKey;
        constructor(t = 16, e = 16) {
          this.maxKeyLength = t, this.maxLengthPerKey = e, this.caches = [];
          for (let t = 0; t < this.maxKeyLength; t++) this.caches.push([])
        }
        canBeCached(t) {
          return t > 0 && t <= this.maxKeyLength
        }
        find(t, e, i) {
          const s = this.caches[i - 1];
          t: for (const n of s) {
            const s = n.bytes;
            for (let n = 0; n < i; n++)
              if (s[n] !== t[e + n]) continue t;
            return n.str
          }
          return null
        }
        store(t, e) {
          const i = this.caches[t.length - 1],
            s = {
              bytes: t,
              str: e
            };
          i.length >= this.maxLengthPerKey ? i[Math.random() * i.length | 0] = s : i.push(s)
        }
        decode(t, e, i) {
          const s = this.find(t, e, i);
          if (null != s) return this.hit++, s;
          this.miss++;
          const n = Vs(t, e, i),
            r = Uint8Array.prototype.slice.call(t, e, e + i);
          return this.store(r, n), n
        }
      };
    class Qs {
      extensionCodec;
      context;
      useBigInt64;
      rawStrings;
      maxStrLength;
      maxBinLength;
      maxArrayLength;
      maxMapLength;
      maxExtLength;
      keyDecoder;
      mapKeyConverter;
      totalPos = 0;
      pos = 0;
      view = $s;
      bytes = Ks;
      headByte = -1;
      stack = new js;
      entered = !1;
      constructor(t) {
        this.extensionCodec = t?.extensionCodec ?? Ns.defaultCodec, this.context = t?.context, this.useBigInt64 = t?.useBigInt64 ?? !1, this.rawStrings = t?.rawStrings ?? !1, this.maxStrLength = t?.maxStrLength ?? Rs, this.maxBinLength = t?.maxBinLength ?? Rs, this.maxArrayLength = t?.maxArrayLength ?? Rs, this.maxMapLength = t?.maxMapLength ?? Rs, this.maxExtLength = t?.maxExtLength ?? Rs, this.keyDecoder = void 0 !== t?.keyDecoder ? t.keyDecoder : Zs, this.mapKeyConverter = t?.mapKeyConverter ?? Xs
      }
      clone() {
        return new Qs({
          extensionCodec: this.extensionCodec,
          context: this.context,
          useBigInt64: this.useBigInt64,
          rawStrings: this.rawStrings,
          maxStrLength: this.maxStrLength,
          maxBinLength: this.maxBinLength,
          maxArrayLength: this.maxArrayLength,
          maxMapLength: this.maxMapLength,
          maxExtLength: this.maxExtLength,
          keyDecoder: this.keyDecoder
        })
      }
      reinitializeState() {
        this.totalPos = 0, this.headByte = -1, this.stack.reset()
      }
      setBuffer(t) {
        const e = Hs(t);
        this.bytes = e, this.view = new DataView(e.buffer, e.byteOffset, e.byteLength), this.pos = 0
      }
      appendBuffer(t) {
        if (-1 !== this.headByte || this.hasRemaining(1)) {
          const e = this.bytes.subarray(this.pos),
            i = Hs(t),
            s = new Uint8Array(e.length + i.length);
          s.set(e), s.set(i, e.length), this.setBuffer(s)
        } else this.setBuffer(t)
      }
      hasRemaining(t) {
        return this.view.byteLength - this.pos >= t
      }
      createExtraByteError(t) {
        const {
          view: e,
          pos: i
        } = this;
        return new RangeError(`Extra ${e.byteLength-i} of ${e.byteLength} byte(s) found at buffer[${t}]`)
      }
      decode(t) {
        if (this.entered) {
          return this.clone().decode(t)
        }
        try {
          this.entered = !0, this.reinitializeState(), this.setBuffer(t);
          const e = this.doDecodeSync();
          if (this.hasRemaining(1)) throw this.createExtraByteError(this.pos);
          return e
        } finally {
          this.entered = !1
        }
      }* decodeMulti(t) {
        if (this.entered) {
          const e = this.clone();
          return void(yield* e.decodeMulti(t))
        }
        try {
          for (this.entered = !0, this.reinitializeState(), this.setBuffer(t); this.hasRemaining(1);) yield this.doDecodeSync()
        } finally {
          this.entered = !1
        }
      }
      async decodeAsync(t) {
        if (this.entered) {
          return this.clone().decodeAsync(t)
        }
        try {
          this.entered = !0;
          let e, i = !1;
          for await (const s of t) {
            if (i) throw this.entered = !1, this.createExtraByteError(this.totalPos);
            this.appendBuffer(s);
            try {
              e = this.doDecodeSync(), i = !0
            } catch (t) {
              if (!(t instanceof RangeError)) throw t
            }
            this.totalPos += this.pos
          }
          if (i) {
            if (this.hasRemaining(1)) throw this.createExtraByteError(this.totalPos);
            return e
          }
          const {
            headByte: s,
            pos: n,
            totalPos: r
          } = this;
          throw new RangeError(`Insufficient data in parsing ${Os(s)} at ${r} (${n} in the current buffer)`)
        } finally {
          this.entered = !1
        }
      }
      decodeArrayStream(t) {
        return this.decodeMultiAsync(t, !0)
      }
      decodeStream(t) {
        return this.decodeMultiAsync(t, !1)
      }
      async * decodeMultiAsync(t, e) {
        if (this.entered) {
          const i = this.clone();
          return void(yield* i.decodeMultiAsync(t, e))
        }
        try {
          this.entered = !0;
          let i = e,
            s = -1;
          for await (const n of t) {
            if (e && 0 === s) throw this.createExtraByteError(this.totalPos);
            this.appendBuffer(n), i && (s = this.readArraySize(), i = !1, this.complete());
            try {
              for (; yield this.doDecodeSync(), 0 !== --s;);
            } catch (t) {
              if (!(t instanceof RangeError)) throw t
            }
            this.totalPos += this.pos
          }
        } finally {
          this.entered = !1
        }
      }
      doDecodeSync() {
        t: for (;;) {
          const t = this.readHeadByte();
          let e;
          if (t >= 224) e = t - 256;
          else if (t < 192)
            if (t < 128) e = t;
            else if (t < 144) {
            const i = t - 128;
            if (0 !== i) {
              this.pushMapState(i), this.complete();
              continue t
            }
            e = {}
          } else if (t < 160) {
            const i = t - 144;
            if (0 !== i) {
              this.pushArrayState(i), this.complete();
              continue t
            }
            e = []
          } else {
            const i = t - 160;
            e = this.decodeString(i, 0)
          } else if (192 === t) e = null;
          else if (194 === t) e = !1;
          else if (195 === t) e = !0;
          else if (202 === t) e = this.readF32();
          else if (203 === t) e = this.readF64();
          else if (204 === t) e = this.readU8();
          else if (205 === t) e = this.readU16();
          else if (206 === t) e = this.readU32();
          else if (207 === t) e = this.useBigInt64 ? this.readU64AsBigInt() : this.readU64();
          else if (208 === t) e = this.readI8();
          else if (209 === t) e = this.readI16();
          else if (210 === t) e = this.readI32();
          else if (211 === t) e = this.useBigInt64 ? this.readI64AsBigInt() : this.readI64();
          else if (217 === t) {
            const t = this.lookU8();
            e = this.decodeString(t, 1)
          } else if (218 === t) {
            const t = this.lookU16();
            e = this.decodeString(t, 2)
          } else if (219 === t) {
            const t = this.lookU32();
            e = this.decodeString(t, 4)
          } else if (220 === t) {
            const t = this.readU16();
            if (0 !== t) {
              this.pushArrayState(t), this.complete();
              continue t
            }
            e = []
          } else if (221 === t) {
            const t = this.readU32();
            if (0 !== t) {
              this.pushArrayState(t), this.complete();
              continue t
            }
            e = []
          } else if (222 === t) {
            const t = this.readU16();
            if (0 !== t) {
              this.pushMapState(t), this.complete();
              continue t
            }
            e = {}
          } else if (223 === t) {
            const t = this.readU32();
            if (0 !== t) {
              this.pushMapState(t), this.complete();
              continue t
            }
            e = {}
          } else if (196 === t) {
            const t = this.lookU8();
            e = this.decodeBinary(t, 1)
          } else if (197 === t) {
            const t = this.lookU16();
            e = this.decodeBinary(t, 2)
          } else if (198 === t) {
            const t = this.lookU32();
            e = this.decodeBinary(t, 4)
          } else if (212 === t) e = this.decodeExtension(1, 0);
          else if (213 === t) e = this.decodeExtension(2, 0);
          else if (214 === t) e = this.decodeExtension(4, 0);
          else if (215 === t) e = this.decodeExtension(8, 0);
          else if (216 === t) e = this.decodeExtension(16, 0);
          else if (199 === t) {
            const t = this.lookU8();
            e = this.decodeExtension(t, 1)
          } else if (200 === t) {
            const t = this.lookU16();
            e = this.decodeExtension(t, 2)
          } else {
            if (201 !== t) throw new Bs(`Unrecognized type byte: ${Os(t)}`);
            {
              const t = this.lookU32();
              e = this.decodeExtension(t, 4)
            }
          }
          this.complete();
          const i = this.stack;
          for (; i.length > 0;) {
            const t = i.top();
            if (t.type === Ws) {
              if (t.array[t.position] = e, t.position++, t.position !== t.size) continue t;
              e = t.array, i.release(t)
            } else {
              if (t.type === Ys) {
                if ("__proto__" === e) throw new Bs("The key __proto__ is not allowed");
                t.key = this.mapKeyConverter(e), t.type = Gs;
                continue t
              }
              if (t.map[t.key] = e, t.readCount++, t.readCount !== t.size) {
                t.key = null, t.type = Ys;
                continue t
              }
              e = t.map, i.release(t)
            }
          }
          return e
        }
      }
      readHeadByte() {
        return -1 === this.headByte && (this.headByte = this.readU8()), this.headByte
      }
      complete() {
        this.headByte = -1
      }
      readArraySize() {
        const t = this.readHeadByte();
        switch (t) {
          case 220:
            return this.readU16();
          case 221:
            return this.readU32();
          default:
            if (t < 160) return t - 144;
            throw new Bs(`Unrecognized array type byte: ${Os(t)}`)
        }
      }
      pushMapState(t) {
        if (t > this.maxMapLength) throw new Bs(`Max length exceeded: map length (${t}) > maxMapLengthLength (${this.maxMapLength})`);
        this.stack.pushMapState(t)
      }
      pushArrayState(t) {
        if (t > this.maxArrayLength) throw new Bs(`Max length exceeded: array length (${t}) > maxArrayLength (${this.maxArrayLength})`);
        this.stack.pushArrayState(t)
      }
      decodeString(t, e) {
        return !this.rawStrings || this.stateIsMapKey() ? this.decodeUtf8String(t, e) : this.decodeBinary(t, e)
      }
      decodeUtf8String(t, e) {
        if (t > this.maxStrLength) throw new Bs(`Max length exceeded: UTF-8 byte length (${t}) > maxStrLength (${this.maxStrLength})`);
        if (this.bytes.byteLength < this.pos + e + t) throw qs;
        const i = this.pos + e;
        let s;
        return s = this.stateIsMapKey() && this.keyDecoder?.canBeCached(t) ? this.keyDecoder.decode(this.bytes, i, t) : Us(this.bytes, i, t), this.pos += e + t, s
      }
      stateIsMapKey() {
        if (this.stack.length > 0) {
          return this.stack.top().type === Ys
        }
        return !1
      }
      decodeBinary(t, e) {
        if (t > this.maxBinLength) throw new Bs(`Max length exceeded: bin length (${t}) > maxBinLength (${this.maxBinLength})`);
        if (!this.hasRemaining(t + e)) throw qs;
        const i = this.pos + e,
          s = this.bytes.subarray(i, i + t);
        return this.pos += e + t, s
      }
      decodeExtension(t, e) {
        if (t > this.maxExtLength) throw new Bs(`Max length exceeded: ext length (${t}) > maxExtLength (${this.maxExtLength})`);
        const i = this.view.getInt8(this.pos + e),
          s = this.decodeBinary(t, e + 1);
        return this.extensionCodec.decode(s, i, this.context)
      }
      lookU8() {
        return this.view.getUint8(this.pos)
      }
      lookU16() {
        return this.view.getUint16(this.pos)
      }
      lookU32() {
        return this.view.getUint32(this.pos)
      }
      readU8() {
        const t = this.view.getUint8(this.pos);
        return this.pos++, t
      }
      readI8() {
        const t = this.view.getInt8(this.pos);
        return this.pos++, t
      }
      readU16() {
        const t = this.view.getUint16(this.pos);
        return this.pos += 2, t
      }
      readI16() {
        const t = this.view.getInt16(this.pos);
        return this.pos += 2, t
      }
      readU32() {
        const t = this.view.getUint32(this.pos);
        return this.pos += 4, t
      }
      readI32() {
        const t = this.view.getInt32(this.pos);
        return this.pos += 4, t
      }
      readU64() {
        const t = (e = this.view, i = this.pos, 4294967296 * e.getUint32(i) + e.getUint32(i + 4));
        var e, i;
        return this.pos += 8, t
      }
      readI64() {
        const t = Ds(this.view, this.pos);
        return this.pos += 8, t
      }
      readU64AsBigInt() {
        const t = this.view.getBigUint64(this.pos);
        return this.pos += 8, t
      }
      readI64AsBigInt() {
        const t = this.view.getBigInt64(this.pos);
        return this.pos += 8, t
      }
      readF32() {
        const t = this.view.getFloat32(this.pos);
        return this.pos += 4, t
      }
      readF64() {
        const t = this.view.getFloat64(this.pos);
        return this.pos += 8, t
      }
    }

    function Js(t, e) {
      return new Qs(e).decode(t)
    }
    const tn = 4294967295,
      en = "manifest.bin";

    function sn(t) {
      if (t.byteLength < 22) return null;
      const e = new DataView(t.buffer, t.byteOffset, t.byteLength),
        i = function(t) {
          const e = Math.min(t.byteLength, 65557);
          for (let i = t.byteLength - 22; i >= t.byteLength - e; i--)
            if (i >= 0 && 101010256 === t.getUint32(i, !0)) return i;
          return -1
        }(e);
      if (i < 0) return null;
      const s = e.getUint16(i + 10, !0),
        n = e.getUint32(i + 16, !0);
      if (65535 === s || n === tn) return null;
      const r = new TextDecoder,
        a = new Map;
      let o = n;
      for (let i = 0; i < s; i++) {
        if (o + 46 > t.byteLength) return null;
        if (33639248 !== e.getUint32(o, !0)) return null;
        const i = e.getUint16(o + 10, !0),
          s = e.getUint32(o + 20, !0),
          n = e.getUint32(o + 24, !0),
          h = e.getUint16(o + 28, !0),
          l = e.getUint16(o + 30, !0),
          c = e.getUint16(o + 32, !0),
          d = e.getUint32(o + 42, !0);
        if (0 !== i && 8 !== i) return null;
        if (s === tn || d === tn) return null;
        if (n === tn) return null;
        const u = o + 46,
          p = r.decode(t.subarray(u, u + h));
        if (d + 30 > t.byteLength) return null;
        if (67324752 !== e.getUint32(d, !0)) return null;
        const g = d + 30 + e.getUint16(d + 26, !0) + e.getUint16(d + 28, !0),
          m = g + s;
        if (m > t.byteLength) return null;
        const f = t.subarray(g, m);
        if (0 === i) a.set(p, f);
        else try {
          a.set(p, n > 0 ? Ts(f, {
            out: new Uint8Array(n)
          }) : Ts(f))
        } catch (t) {
          return null
        }
        o = u + h + l + c
      }
      return a
    }
  global.BundleCodec = {
    inflate: Ts,
    parseZip: function (bytes) {
      const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
      const m = sn(u8);
      if (!m) throw new Error('Invalid or unsupported room.bundle ZIP');
      return m;
    },
    decodeMsgpack: Js,
  };
})(typeof window !== 'undefined' ? window : globalThis);
