// Official @esotericsoftware/spine runtime extracted verbatim from parsed_js/bundle.js (module 979)
(function (global) {
  'use strict';
  const window = global;


  // Minimal Phaser API shim so @esotericsoftware/spine canvas/core runtime works standalone without full Phaser bundle
  const __PhaserShim = (typeof window !== "undefined" && window.Phaser) ? window.Phaser : {
    Class: { mixin: function () {} },
    Plugins: { ScenePlugin: class ScenePlugin {} },
    Loader: {
      MultiFile: class MultiFile {},
      FileTypes: {
        ImageFile: class ImageFile {},
        JSONFile: class JSONFile {},
        BinaryFile: class BinaryFile {},
        TextFile: class TextFile {},
      },
    },
    GameObjects: {
      GameObject: class GameObject {},
      BuildGameObject: function () {},
      Components: {
        ComputedSize: {}, Depth: {}, Flip: {}, ScrollFactor: {},
        Transform: {}, Visible: {}, Origin: {}, Alpha: {},
      },
    },
    Renderer: { WebGL: { WebGLRenderer: class WebGLRenderer {} } },
    Scale: { Events: { RESIZE: "resize" } },
  };
  const Phaser = __PhaserShim;

        var t, e = Object.create,
          i = Object.defineProperty,
          s = Object.getOwnPropertyDescriptor,
          n = Object.getOwnPropertyNames,
          r = Object.getPrototypeOf,
          a = Object.prototype.hasOwnProperty,
          o = (t = function(t) {
            if (typeof require < "u") return require.apply(this, arguments);
            throw Error('Dynamic require of "' + t + '" is not supported')
          }, typeof require < "u" ? require : typeof Proxy < "u" ? new Proxy(t, {
            get: (t, e) => (typeof require < "u" ? require : t)[e]
          }) : t),
          h = (t, e, r, o) => {
            if (e && "object" == typeof e || "function" == typeof e)
              for (let h of n(e)) !a.call(t, h) && h !== r && i(t, h, {
                get: () => e[h],
                enumerable: !(o = s(e, h)) || o.enumerable
              });
            return t
          },
          l = {};
        if (((t, e) => {
            for (var s in e) i(t, s, {
              get: e[s],
              enumerable: !0
            })
          })(l, {
            AABBRectangleBoundsProvider: () => Vs,
            Alpha: () => As,
            AlphaMixin: () => Fs,
            AlphaTimeline: () => K,
            Animation: () => A,
            AnimationState: () => yt,
            AnimationStateAdapter: () => xt,
            AnimationStateData: () => It,
            AssetCache: () => Zt,
            AssetManager: () => xi,
            AssetManagerBase: () => qt,
            AtlasAttachmentLoader: () => Gt,
            Attachment: () => S,
            AttachmentTimeline: () => Q,
            BinaryInput: () => xe,
            BlendMode: () => _e,
            Bone: () => $t,
            BoneData: () => Xt,
            BoundingBoxAttachment: () => Et,
            CURRENT: () => At,
            CameraController: () => Wi,
            ClippingAttachment: () => Ot,
            Color: () => u,
            Color2Attribute: () => Zi,
            ColorAttribute: () => qi,
            ComputedSize: () => xs,
            ComputedSizeMixin: () => Es,
            ConstraintData: () => Kt,
            CurveTimeline: () => B,
            CurveTimeline1: () => R,
            CurveTimeline2: () => D,
            DebugUtils: () => _,
            DeformTimeline: () => J,
            Depth: () => ws,
            DepthMixin: () => Os,
            Downloader: () => Qt,
            DrawOrderTimeline: () => et,
            Event: () => Jt,
            EventData: () => te,
            EventQueue: () => bt,
            EventTimeline: () => tt,
            EventType: () => vt,
            FIRST: () => St,
            FakeTexture: () => Lt,
            Flip: () => Ss,
            FlipMixin: () => Ms,
            GLTexture: () => vi,
            HOLD_FIRST: () => Ct,
            HOLD_MIX: () => kt,
            HOLD_SUBSEQUENT: () => Tt,
            IkConstraint: () => ee,
            IkConstraintData: () => ie,
            IkConstraintTimeline: () => it,
            Inherit: () => jt,
            InheritTimeline: () => X,
            Input: () => Ui,
            IntSet: () => c,
            Interpolation: () => g,
            LoadingScreen: () => gs,
            M00: () => Si,
            M01: () => Ti,
            M02: () => Ci,
            M03: () => ki,
            M10: () => Pi,
            M11: () => Ai,
            M12: () => Ii,
            M13: () => Ei,
            M20: () => Oi,
            M21: () => Mi,
            M22: () => Bi,
            M23: () => Ri,
            M30: () => Di,
            M31: () => Li,
            M32: () => Fi,
            M33: () => Ni,
            ManagedWebGLRenderingContext: () => bi,
            MathUtils: () => p,
            Matrix4: () => Vi,
            Mesh: () => Gi,
            MeshAttachment: () => Ut,
            MixBlend: () => I,
            MixDirection: () => E,
            Origin: () => Ps,
            OriginMixin: () => Ls,
            OrthoCamera: () => zi,
            PathAttachment: () => Ht,
            PathConstraint: () => oe,
            PathConstraintData: () => se,
            PathConstraintMixTimeline: () => at,
            PathConstraintPositionTimeline: () => nt,
            PathConstraintSpacingTimeline: () => rt,
            Physics: () => ue,
            PhysicsConstraintDampingTimeline: () => ct,
            PhysicsConstraintGravityTimeline: () => pt,
            PhysicsConstraintInertiaTimeline: () => ht,
            PhysicsConstraintMassTimeline: () => dt,
            PhysicsConstraintMixTimeline: () => gt,
            PhysicsConstraintResetTimeline: () => mt,
            PhysicsConstraintStrengthTimeline: () => lt,
            PhysicsConstraintTimeline: () => ot,
            PhysicsConstraintWindTimeline: () => ut,
            PointAttachment: () => Wt,
            PolygonBatcher: () => Ji,
            Pool: () => b,
            Position2Attribute: () => ji,
            Position3Attribute: () => $i,
            PositionMode: () => ne,
            Pow: () => m,
            PowOut: () => f,
            RGB2Timeline: () => Z,
            RGBA2Timeline: () => q,
            RGBATimeline: () => j,
            RGBTimeline: () => $,
            RegionAttachment: () => Yt,
            ResizeMode: () => ls,
            RotateMode: () => ae,
            RotateTimeline: () => L,
            SETUP: () => Pt,
            SUBSEQUENT: () => wt,
            ScaleTimeline: () => z,
            ScaleXTimeline: () => U,
            ScaleYTimeline: () => H,
            SceneRenderer: () => hs,
            ScrollFactor: () => Ts,
            ScrollFactorMixin: () => Bs,
            SequenceTimeline: () => ft,
            SetupPoseBoundsProvider: () => zs,
            Shader: () => Yi,
            ShapeRenderer: () => ts,
            ShapeType: () => es,
            ShearTimeline: () => W,
            ShearXTimeline: () => Y,
            ShearYTimeline: () => G,
            Skeleton: () => de,
            SkeletonBinary: () => ve,
            SkeletonBounds: () => ri,
            SkeletonClipping: () => oi,
            SkeletonData: () => ge,
            SkeletonDebugRenderer: () => is,
            SkeletonJson: () => hi,
            SkeletonRenderer: () => ns,
            Skin: () => fe,
            SkinEntry: () => me,
            SkinsAndAnimationBoundsProvider: () => Us,
            Slot: () => le,
            SlotData: () => ye,
            SpacingMode: () => re,
            SpineCanvas: () => ys,
            SpineGameObject: () => Hs,
            SpinePlugin: () => Ws,
            StringSet: () => d,
            TexCoordAttribute: () => Ki,
            Texture: () => Mt,
            TextureAtlas: () => Ft,
            TextureAtlasPage: () => Vt,
            TextureAtlasRegion: () => zt,
            TextureFilter: () => Bt,
            TextureRegion: () => Dt,
            TextureWrap: () => Rt,
            TimeKeeper: () => x,
            Timeline: () => M,
            Touch: () => Hi,
            TrackEntry: () => _t,
            Transform: () => Cs,
            TransformConstraint: () => ce,
            TransformConstraintData: () => be,
            TransformConstraintTimeline: () => st,
            TransformMixin: () => Rs,
            TranslateTimeline: () => F,
            TranslateXTimeline: () => N,
            TranslateYTimeline: () => V,
            Triangulator: () => ai,
            Utils: () => y,
            Vector2: () => v,
            Vector3: () => wi,
            VertexAttachment: () => T,
            VertexAttribute: () => Xi,
            VertexAttributeType: () => Qi,
            Visible: () => ks,
            VisibleMixin: () => Ds,
            WindowedMean: () => w,
            createMixin: () => Is
          }), typeof window < "u" && window.Phaser) {
          let t = window.require;
          window.require = e => t ? t(e) : "Phaser" === e ? window.Phaser : void 0
        }
        var c = class {
            array = new Array;
            add(t) {
              let e = this.contains(t);
              return this.array[0 | t] = 0 | t, !e
            }
            contains(t) {
              return null != this.array[0 | t]
            }
            remove(t) {
              this.array[0 | t] = void 0
            }
            clear() {
              this.array.length = 0
            }
          },
          d = class {
            entries = {};
            size = 0;
            add(t) {
              let e = this.entries[t];
              return this.entries[t] = !0, !e && (this.size++, !0)
            }
            addAll(t) {
              let e = this.size;
              for (var i = 0, s = t.length; i < s; i++) this.add(t[i]);
              return e != this.size
            }
            contains(t) {
              return this.entries[t]
            }
            clear() {
              this.entries = {}, this.size = 0
            }
          },
          u = class t {
            constructor(t = 0, e = 0, i = 0, s = 0) {
              this.r = t, this.g = e, this.b = i, this.a = s
            }
            static WHITE = new t(1, 1, 1, 1);
            static RED = new t(1, 0, 0, 1);
            static GREEN = new t(0, 1, 0, 1);
            static BLUE = new t(0, 0, 1, 1);
            static MAGENTA = new t(1, 0, 1, 1);
            set(t, e, i, s) {
              return this.r = t, this.g = e, this.b = i, this.a = s, this.clamp()
            }
            setFromColor(t) {
              return this.r = t.r, this.g = t.g, this.b = t.b, this.a = t.a, this
            }
            setFromString(t) {
              return t = "#" == t.charAt(0) ? t.substr(1) : t, this.r = parseInt(t.substr(0, 2), 16) / 255, this.g = parseInt(t.substr(2, 2), 16) / 255, this.b = parseInt(t.substr(4, 2), 16) / 255, this.a = 8 != t.length ? 1 : parseInt(t.substr(6, 2), 16) / 255, this
            }
            add(t, e, i, s) {
              return this.r += t, this.g += e, this.b += i, this.a += s, this.clamp()
            }
            clamp() {
              return this.r < 0 ? this.r = 0 : this.r > 1 && (this.r = 1), this.g < 0 ? this.g = 0 : this.g > 1 && (this.g = 1), this.b < 0 ? this.b = 0 : this.b > 1 && (this.b = 1), this.a < 0 ? this.a = 0 : this.a > 1 && (this.a = 1), this
            }
            static rgba8888ToColor(t, e) {
              t.r = ((4278190080 & e) >>> 24) / 255, t.g = ((16711680 & e) >>> 16) / 255, t.b = ((65280 & e) >>> 8) / 255, t.a = (255 & e) / 255
            }
            static rgb888ToColor(t, e) {
              t.r = ((16711680 & e) >>> 16) / 255, t.g = ((65280 & e) >>> 8) / 255, t.b = (255 & e) / 255
            }
            toRgb888() {
              const t = t => ("0" + (255 * t).toString(16)).slice(-2);
              return +("0x" + t(this.r) + t(this.g) + t(this.b))
            }
            static fromString(e, i = new t) {
              return i.setFromString(e)
            }
          },
          p = class t {
            static PI = 3.1415927;
            static PI2 = 2 * t.PI;
            static invPI2 = 1 / t.PI2;
            static radiansToDegrees = 180 / t.PI;
            static radDeg = t.radiansToDegrees;
            static degreesToRadians = t.PI / 180;
            static degRad = t.degreesToRadians;
            static clamp(t, e, i) {
              return t < e ? e : t > i ? i : t
            }
            static cosDeg(e) {
              return Math.cos(e * t.degRad)
            }
            static sinDeg(e) {
              return Math.sin(e * t.degRad)
            }
            static atan2Deg(e, i) {
              return Math.atan2(e, i) * t.degRad
            }
            static signum(t) {
              return t > 0 ? 1 : t < 0 ? -1 : 0
            }
            static toInt(t) {
              return t > 0 ? Math.floor(t) : Math.ceil(t)
            }
            static cbrt(t) {
              let e = Math.pow(Math.abs(t), .3333333333333333);
              return t < 0 ? -e : e
            }
            static randomTriangular(e, i) {
              return t.randomTriangularWith(e, i, .5 * (e + i))
            }
            static randomTriangularWith(t, e, i) {
              let s = Math.random(),
                n = e - t;
              return s <= (i - t) / n ? t + Math.sqrt(s * n * (i - t)) : e - Math.sqrt((1 - s) * n * (e - i))
            }
            static isPowerOfTwo(t) {
              return t && !(t & t - 1)
            }
          },
          g = class {
            apply(t, e, i) {
              return t + (e - t) * this.applyInternal(i)
            }
          },
          m = class extends g {
            power = 2;
            constructor(t) {
              super(), this.power = t
            }
            applyInternal(t) {
              return t <= .5 ? Math.pow(2 * t, this.power) / 2 : Math.pow(2 * (t - 1), this.power) / (this.power % 2 == 0 ? -2 : 2) + 1
            }
          },
          f = class extends m {
            constructor(t) {
              super(t)
            }
            applyInternal(t) {
              return Math.pow(t - 1, this.power) * (this.power % 2 == 0 ? -1 : 1) + 1
            }
          },
          y = class t {
            static SUPPORTS_TYPED_ARRAYS = typeof Float32Array < "u";
            static arrayCopy(t, e, i, s, n) {
              for (let r = e, a = s; r < e + n; r++, a++) i[a] = t[r]
            }
            static arrayFill(t, e, i, s) {
              for (let n = e; n < i; n++) t[n] = s
            }
            static setArraySize(t, e, i = 0) {
              let s = t.length;
              if (s == e) return t;
              if (t.length = e, s < e)
                for (let n = s; n < e; n++) t[n] = i;
              return t
            }
            static ensureArrayCapacity(e, i, s = 0) {
              return e.length >= i ? e : t.setArraySize(e, i, s)
            }
            static newArray(t, e) {
              let i = new Array(t);
              for (let s = 0; s < t; s++) i[s] = e;
              return i
            }
            static newFloatArray(e) {
              if (t.SUPPORTS_TYPED_ARRAYS) return new Float32Array(e);
              {
                let t = new Array(e);
                for (let e = 0; e < t.length; e++) t[e] = 0;
                return t
              }
            }
            static newShortArray(e) {
              if (t.SUPPORTS_TYPED_ARRAYS) return new Int16Array(e);
              {
                let t = new Array(e);
                for (let e = 0; e < t.length; e++) t[e] = 0;
                return t
              }
            }
            static toFloatArray(e) {
              return t.SUPPORTS_TYPED_ARRAYS ? new Float32Array(e) : e
            }
            static toSinglePrecision(e) {
              return t.SUPPORTS_TYPED_ARRAYS ? Math.fround(e) : e
            }
            static webkit602BugfixHelper(t, e) {}
            static contains(t, e, i = !0) {
              for (var s = 0; s < t.length; s++)
                if (t[s] == e) return !0;
              return !1
            }
            static enumValue(t, e) {
              return t[e[0].toUpperCase() + e.slice(1)]
            }
          },
          _ = class {
            static logBones(t) {
              for (let e = 0; e < t.bones.length; e++) {
                let i = t.bones[e];
                console.log(i.data.name + ", " + i.a + ", " + i.b + ", " + i.c + ", " + i.d + ", " + i.worldX + ", " + i.worldY)
              }
            }
          },
          b = class {
            items = new Array;
            instantiator;
            constructor(t) {
              this.instantiator = t
            }
            obtain() {
              return this.items.length > 0 ? this.items.pop() : this.instantiator()
            }
            free(t) {
              t.reset && t.reset(), this.items.push(t)
            }
            freeAll(t) {
              for (let e = 0; e < t.length; e++) this.free(t[e])
            }
            clear() {
              this.items.length = 0
            }
          },
          v = class {
            constructor(t = 0, e = 0) {
              this.x = t, this.y = e
            }
            set(t, e) {
              return this.x = t, this.y = e, this
            }
            length() {
              let t = this.x,
                e = this.y;
              return Math.sqrt(t * t + e * e)
            }
            normalize() {
              let t = this.length();
              return 0 != t && (this.x /= t, this.y /= t), this
            }
          },
          x = class {
            maxDelta = .064;
            framesPerSecond = 0;
            delta = 0;
            totalTime = 0;
            lastTime = Date.now() / 1e3;
            frameCount = 0;
            frameTime = 0;
            update() {
              let t = Date.now() / 1e3;
              this.delta = t - this.lastTime, this.frameTime += this.delta, this.totalTime += this.delta, this.delta > this.maxDelta && (this.delta = this.maxDelta), this.lastTime = t, this.frameCount++, this.frameTime > 1 && (this.framesPerSecond = this.frameCount / this.frameTime, this.frameTime = 0, this.frameCount = 0)
            }
          },
          w = class {
            values;
            addedValues = 0;
            lastValue = 0;
            mean = 0;
            dirty = !0;
            constructor(t = 32) {
              this.values = new Array(t)
            }
            hasEnoughData() {
              return this.addedValues >= this.values.length
            }
            addValue(t) {
              this.addedValues < this.values.length && this.addedValues++, this.values[this.lastValue++] = t, this.lastValue > this.values.length - 1 && (this.lastValue = 0), this.dirty = !0
            }
            getMean() {
              if (this.hasEnoughData()) {
                if (this.dirty) {
                  let t = 0;
                  for (let e = 0; e < this.values.length; e++) t += this.values[e];
                  this.mean = t / this.values.length, this.dirty = !1
                }
                return this.mean
              }
              return 0
            }
          },
          S = class {
            name;
            constructor(t) {
              if (!t) throw new Error("name cannot be null.");
              this.name = t
            }
          },
          T = class t extends S {
            static nextID = 0;
            id = t.nextID++;
            bones = null;
            vertices = [];
            worldVerticesLength = 0;
            timelineAttachment = this;
            constructor(t) {
              super(t)
            }
            computeWorldVertices(t, e, i, s, n, r) {
              i = n + (i >> 1) * r;
              let a = t.bone.skeleton,
                o = t.deform,
                h = this.vertices,
                l = this.bones;
              if (!l) {
                o.length > 0 && (h = o);
                let a = t.bone,
                  l = a.worldX,
                  c = a.worldY,
                  d = a.a,
                  u = a.b,
                  p = a.c,
                  g = a.d;
                for (let t = e, a = n; a < i; t += 2, a += r) {
                  let e = h[t],
                    i = h[t + 1];
                  s[a] = e * d + i * u + l, s[a + 1] = e * p + i * g + c
                }
                return
              }
              let c = 0,
                d = 0;
              for (let t = 0; t < e; t += 2) {
                let t = l[c];
                c += t + 1, d += t
              }
              let u = a.bones;
              if (0 == o.length)
                for (let t = n, e = 3 * d; t < i; t += r) {
                  let i = 0,
                    n = 0,
                    r = l[c++];
                  for (r += c; c < r; c++, e += 3) {
                    let t = u[l[c]],
                      s = h[e],
                      r = h[e + 1],
                      a = h[e + 2];
                    i += (s * t.a + r * t.b + t.worldX) * a, n += (s * t.c + r * t.d + t.worldY) * a
                  }
                  s[t] = i, s[t + 1] = n
                } else {
                  let t = o;
                  for (let e = n, a = 3 * d, o = d << 1; e < i; e += r) {
                    let i = 0,
                      n = 0,
                      r = l[c++];
                    for (r += c; c < r; c++, a += 3, o += 2) {
                      let e = u[l[c]],
                        s = h[a] + t[o],
                        r = h[a + 1] + t[o + 1],
                        d = h[a + 2];
                      i += (s * e.a + r * e.b + e.worldX) * d, n += (s * e.c + r * e.d + e.worldY) * d
                    }
                    s[e] = i, s[e + 1] = n
                  }
                }
            }
            copyTo(t) {
              this.bones ? (t.bones = new Array(this.bones.length), y.arrayCopy(this.bones, 0, t.bones, 0, this.bones.length)) : t.bones = null, this.vertices && (t.vertices = y.newFloatArray(this.vertices.length), y.arrayCopy(this.vertices, 0, t.vertices, 0, this.vertices.length)), t.worldVerticesLength = this.worldVerticesLength, t.timelineAttachment = this.timelineAttachment
            }
          },
          C = class t {
            static _nextID = 0;
            id = t.nextID();
            regions;
            start = 0;
            digits = 0;
            setupIndex = 0;
            constructor(t) {
              this.regions = new Array(t)
            }
            copy() {
              let e = new t(this.regions.length);
              return y.arrayCopy(this.regions, 0, e.regions, 0, this.regions.length), e.start = this.start, e.digits = this.digits, e.setupIndex = this.setupIndex, e
            }
            apply(t, e) {
              let i = t.sequenceIndex; - 1 == i && (i = this.setupIndex), i >= this.regions.length && (i = this.regions.length - 1);
              let s = this.regions[i];
              e.region != s && (e.region = s, e.updateRegion())
            }
            getPath(t, e) {
              let i = t,
                s = (this.start + e).toString();
              for (let t = this.digits - s.length; t > 0; t--) i += "0";
              return i += s, i
            }
            static nextID() {
              return t._nextID++
            }
          },
          k = (t => (t[t.hold = 0] = "hold", t[t.once = 1] = "once", t[t.loop = 2] = "loop", t[t.pingpong = 3] = "pingpong", t[t.onceReverse = 4] = "onceReverse", t[t.loopReverse = 5] = "loopReverse", t[t.pingpongReverse = 6] = "pingpongReverse", t))(k || {}),
          P = [0, 1, 2, 3, 4, 5, 6],
          A = class {
            name;
            timelines = [];
            timelineIds = new d;
            duration;
            constructor(t, e, i) {
              if (!t) throw new Error("name cannot be null.");
              this.name = t, this.setTimelines(e), this.duration = i
            }
            setTimelines(t) {
              if (!t) throw new Error("timelines cannot be null.");
              this.timelines = t, this.timelineIds.clear();
              for (var e = 0; e < t.length; e++) this.timelineIds.addAll(t[e].getPropertyIds())
            }
            hasTimeline(t) {
              for (let e = 0; e < t.length; e++)
                if (this.timelineIds.contains(t[e])) return !0;
              return !1
            }
            apply(t, e, i, s, n, r, a, o) {
              if (!t) throw new Error("skeleton cannot be null.");
              s && 0 != this.duration && (i %= this.duration, e > 0 && (e %= this.duration));
              let h = this.timelines;
              for (let s = 0, l = h.length; s < l; s++) h[s].apply(t, e, i, n, r, a, o)
            }
          },
          I = (t => (t[t.setup = 0] = "setup", t[t.first = 1] = "first", t[t.replace = 2] = "replace", t[t.add = 3] = "add", t))(I || {}),
          E = (t => (t[t.mixIn = 0] = "mixIn", t[t.mixOut = 1] = "mixOut", t))(E || {}),
          O = {
            rotate: 0,
            x: 1,
            y: 2,
            scaleX: 3,
            scaleY: 4,
            shearX: 5,
            shearY: 6,
            inherit: 7,
            rgb: 8,
            alpha: 9,
            rgb2: 10,
            attachment: 11,
            deform: 12,
            event: 13,
            drawOrder: 14,
            ikConstraint: 15,
            transformConstraint: 16,
            pathConstraintPosition: 17,
            pathConstraintSpacing: 18,
            pathConstraintMix: 19,
            physicsConstraintInertia: 20,
            physicsConstraintStrength: 21,
            physicsConstraintDamping: 22,
            physicsConstraintMass: 23,
            physicsConstraintWind: 24,
            physicsConstraintGravity: 25,
            physicsConstraintMix: 26,
            physicsConstraintReset: 27,
            sequence: 28
          },
          M = class {
            propertyIds;
            frames;
            constructor(t, e) {
              this.propertyIds = e, this.frames = y.newFloatArray(t * this.getFrameEntries())
            }
            getPropertyIds() {
              return this.propertyIds
            }
            getFrameEntries() {
              return 1
            }
            getFrameCount() {
              return this.frames.length / this.getFrameEntries()
            }
            getDuration() {
              return this.frames[this.frames.length - this.getFrameEntries()]
            }
            static search1(t, e) {
              let i = t.length;
              for (let s = 1; s < i; s++)
                if (t[s] > e) return s - 1;
              return i - 1
            }
            static search(t, e, i) {
              let s = t.length;
              for (let n = i; n < s; n += i)
                if (t[n] > e) return n - i;
              return s - i
            }
          },
          B = class extends M {
            curves;
            constructor(t, e, i) {
              super(t, i), this.curves = y.newFloatArray(t + 18 * e), this.curves[t - 1] = 1
            }
            setLinear(t) {
              this.curves[t] = 0
            }
            setStepped(t) {
              this.curves[t] = 1
            }
            shrink(t) {
              let e = this.getFrameCount() + 18 * t;
              if (this.curves.length > e) {
                let t = y.newFloatArray(e);
                y.arrayCopy(this.curves, 0, t, 0, e), this.curves = t
              }
            }
            setBezier(t, e, i, s, n, r, a, o, h, l, c) {
              let d = this.curves,
                u = this.getFrameCount() + 18 * t;
              0 == i && (d[e] = 2 + u);
              let p = .03 * (s - 2 * r + o),
                g = .03 * (n - 2 * a + h),
                m = .006 * (3 * (r - o) - s + l),
                f = .006 * (3 * (a - h) - n + c),
                y = 2 * p + m,
                _ = 2 * g + f,
                b = .3 * (r - s) + p + .16666667 * m,
                v = .3 * (a - n) + g + .16666667 * f,
                x = s + b,
                w = n + v;
              for (let t = u + 18; u < t; u += 2) d[u] = x, d[u + 1] = w, b += y, v += _, y += m, _ += f, x += b, w += v
            }
            getBezierValue(t, e, i, s) {
              let n = this.curves;
              if (n[s] > t) {
                let r = this.frames[e],
                  a = this.frames[e + i];
                return a + (t - r) / (n[s] - r) * (n[s + 1] - a)
              }
              let r = s + 18;
              for (s += 2; s < r; s += 2)
                if (n[s] >= t) {
                  let e = n[s - 2],
                    i = n[s - 1];
                  return i + (t - e) / (n[s] - e) * (n[s + 1] - i)
                } e += this.getFrameEntries();
              let a = n[r - 2],
                o = n[r - 1];
              return o + (t - a) / (this.frames[e] - a) * (this.frames[e + i] - o)
            }
          },
          R = class extends B {
            constructor(t, e, i) {
              super(t, e, [i])
            }
            getFrameEntries() {
              return 2
            }
            setFrame(t, e, i) {
              t <<= 1, this.frames[t] = e, this.frames[t + 1] = i
            }
            getCurveValue(t) {
              let e = this.frames,
                i = e.length - 2;
              for (let s = 2; s <= i; s += 2)
                if (e[s] > t) {
                  i = s - 2;
                  break
                } let s = this.curves[i >> 1];
              switch (s) {
                case 0:
                  let s = e[i],
                    n = e[i + 1];
                  return n + (t - s) / (e[i + 2] - s) * (e[i + 2 + 1] - n);
                case 1:
                  return e[i + 1]
              }
              return this.getBezierValue(t, i, 1, s - 2)
            }
            getRelativeValue(t, e, i, s, n) {
              if (t < this.frames[0]) {
                switch (i) {
                  case 0:
                    return n;
                  case 1:
                    return s + (n - s) * e
                }
                return s
              }
              let r = this.getCurveValue(t);
              switch (i) {
                case 0:
                  return n + r * e;
                case 1:
                case 2:
                  r += n - s
              }
              return s + r * e
            }
            getAbsoluteValue(t, e, i, s, n) {
              if (t < this.frames[0]) {
                switch (i) {
                  case 0:
                    return n;
                  case 1:
                    return s + (n - s) * e
                }
                return s
              }
              let r = this.getCurveValue(t);
              return 0 == i ? n + (r - n) * e : s + (r - s) * e
            }
            getAbsoluteValue2(t, e, i, s, n, r) {
              if (t < this.frames[0]) {
                switch (i) {
                  case 0:
                    return n;
                  case 1:
                    return s + (n - s) * e
                }
                return s
              }
              return 0 == i ? n + (r - n) * e : s + (r - s) * e
            }
            getScaleValue(t, e, i, s, n, r) {
              if (t < this.frames[0]) {
                switch (i) {
                  case 0:
                    return r;
                  case 1:
                    return n + (r - n) * e
                }
                return n
              }
              let a = this.getCurveValue(t) * r;
              if (1 == e) return 3 == i ? n + a - r : a;
              if (1 == s) switch (i) {
                case 0:
                  return r + (Math.abs(a) * p.signum(r) - r) * e;
                case 1:
                case 2:
                  return n + (Math.abs(a) * p.signum(n) - n) * e
              } else {
                let t = 0;
                switch (i) {
                  case 0:
                    return t = Math.abs(r) * p.signum(a), t + (a - t) * e;
                  case 1:
                  case 2:
                    return t = Math.abs(n) * p.signum(a), t + (a - t) * e
                }
              }
              return n + (a - r) * e
            }
          },
          D = class extends B {
            constructor(t, e, i, s) {
              super(t, e, [i, s])
            }
            getFrameEntries() {
              return 3
            }
            setFrame(t, e, i, s) {
              t *= 3, this.frames[t] = e, this.frames[t + 1] = i, this.frames[t + 2] = s
            }
          },
          L = class extends R {
            boneIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.rotate + "|" + i), this.boneIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.bones[this.boneIndex];
              o.active && (o.rotation = this.getRelativeValue(i, n, r, o.rotation, o.data.rotation))
            }
          },
          F = class extends D {
            boneIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.x + "|" + i, O.y + "|" + i), this.boneIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.bones[this.boneIndex];
              if (!o.active) return;
              let h = this.frames;
              if (i < h[0]) {
                switch (r) {
                  case 0:
                    return o.x = o.data.x, void(o.y = o.data.y);
                  case 1:
                    o.x += (o.data.x - o.x) * n, o.y += (o.data.y - o.y) * n
                }
                return
              }
              let l = 0,
                c = 0,
                d = M.search(h, i, 3),
                u = this.curves[d / 3];
              switch (u) {
                case 0:
                  let t = h[d];
                  l = h[d + 1], c = h[d + 2];
                  let e = (i - t) / (h[d + 3] - t);
                  l += (h[d + 3 + 1] - l) * e, c += (h[d + 3 + 2] - c) * e;
                  break;
                case 1:
                  l = h[d + 1], c = h[d + 2];
                  break;
                default:
                  l = this.getBezierValue(i, d, 1, u - 2), c = this.getBezierValue(i, d, 2, u + 18 - 2)
              }
              switch (r) {
                case 0:
                  o.x = o.data.x + l * n, o.y = o.data.y + c * n;
                  break;
                case 1:
                case 2:
                  o.x += (o.data.x + l - o.x) * n, o.y += (o.data.y + c - o.y) * n;
                  break;
                case 3:
                  o.x += l * n, o.y += c * n
              }
            }
          },
          N = class extends R {
            boneIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.x + "|" + i), this.boneIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.bones[this.boneIndex];
              o.active && (o.x = this.getRelativeValue(i, n, r, o.x, o.data.x))
            }
          },
          V = class extends R {
            boneIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.y + "|" + i), this.boneIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.bones[this.boneIndex];
              o.active && (o.y = this.getRelativeValue(i, n, r, o.y, o.data.y))
            }
          },
          z = class extends D {
            boneIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.scaleX + "|" + i, O.scaleY + "|" + i), this.boneIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.bones[this.boneIndex];
              if (!o.active) return;
              let h = this.frames;
              if (i < h[0]) {
                switch (r) {
                  case 0:
                    return o.scaleX = o.data.scaleX, void(o.scaleY = o.data.scaleY);
                  case 1:
                    o.scaleX += (o.data.scaleX - o.scaleX) * n, o.scaleY += (o.data.scaleY - o.scaleY) * n
                }
                return
              }
              let l, c, d = M.search(h, i, 3),
                u = this.curves[d / 3];
              switch (u) {
                case 0:
                  let t = h[d];
                  l = h[d + 1], c = h[d + 2];
                  let e = (i - t) / (h[d + 3] - t);
                  l += (h[d + 3 + 1] - l) * e, c += (h[d + 3 + 2] - c) * e;
                  break;
                case 1:
                  l = h[d + 1], c = h[d + 2];
                  break;
                default:
                  l = this.getBezierValue(i, d, 1, u - 2), c = this.getBezierValue(i, d, 2, u + 18 - 2)
              }
              if (l *= o.data.scaleX, c *= o.data.scaleY, 1 == n) 3 == r ? (o.scaleX += l - o.data.scaleX, o.scaleY += c - o.data.scaleY) : (o.scaleX = l, o.scaleY = c);
              else {
                let t = 0,
                  e = 0;
                if (1 == a) switch (r) {
                  case 0:
                    t = o.data.scaleX, e = o.data.scaleY, o.scaleX = t + (Math.abs(l) * p.signum(t) - t) * n, o.scaleY = e + (Math.abs(c) * p.signum(e) - e) * n;
                    break;
                  case 1:
                  case 2:
                    t = o.scaleX, e = o.scaleY, o.scaleX = t + (Math.abs(l) * p.signum(t) - t) * n, o.scaleY = e + (Math.abs(c) * p.signum(e) - e) * n;
                    break;
                  case 3:
                    o.scaleX += (l - o.data.scaleX) * n, o.scaleY += (c - o.data.scaleY) * n
                } else switch (r) {
                  case 0:
                    t = Math.abs(o.data.scaleX) * p.signum(l), e = Math.abs(o.data.scaleY) * p.signum(c), o.scaleX = t + (l - t) * n, o.scaleY = e + (c - e) * n;
                    break;
                  case 1:
                  case 2:
                    t = Math.abs(o.scaleX) * p.signum(l), e = Math.abs(o.scaleY) * p.signum(c), o.scaleX = t + (l - t) * n, o.scaleY = e + (c - e) * n;
                    break;
                  case 3:
                    o.scaleX += (l - o.data.scaleX) * n, o.scaleY += (c - o.data.scaleY) * n
                }
              }
            }
          },
          U = class extends R {
            boneIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.scaleX + "|" + i), this.boneIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.bones[this.boneIndex];
              o.active && (o.scaleX = this.getScaleValue(i, n, r, a, o.scaleX, o.data.scaleX))
            }
          },
          H = class extends R {
            boneIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.scaleY + "|" + i), this.boneIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.bones[this.boneIndex];
              o.active && (o.scaleY = this.getScaleValue(i, n, r, a, o.scaleY, o.data.scaleY))
            }
          },
          W = class extends D {
            boneIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.shearX + "|" + i, O.shearY + "|" + i), this.boneIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.bones[this.boneIndex];
              if (!o.active) return;
              let h = this.frames;
              if (i < h[0]) {
                switch (r) {
                  case 0:
                    return o.shearX = o.data.shearX, void(o.shearY = o.data.shearY);
                  case 1:
                    o.shearX += (o.data.shearX - o.shearX) * n, o.shearY += (o.data.shearY - o.shearY) * n
                }
                return
              }
              let l = 0,
                c = 0,
                d = M.search(h, i, 3),
                u = this.curves[d / 3];
              switch (u) {
                case 0:
                  let t = h[d];
                  l = h[d + 1], c = h[d + 2];
                  let e = (i - t) / (h[d + 3] - t);
                  l += (h[d + 3 + 1] - l) * e, c += (h[d + 3 + 2] - c) * e;
                  break;
                case 1:
                  l = h[d + 1], c = h[d + 2];
                  break;
                default:
                  l = this.getBezierValue(i, d, 1, u - 2), c = this.getBezierValue(i, d, 2, u + 18 - 2)
              }
              switch (r) {
                case 0:
                  o.shearX = o.data.shearX + l * n, o.shearY = o.data.shearY + c * n;
                  break;
                case 1:
                case 2:
                  o.shearX += (o.data.shearX + l - o.shearX) * n, o.shearY += (o.data.shearY + c - o.shearY) * n;
                  break;
                case 3:
                  o.shearX += l * n, o.shearY += c * n
              }
            }
          },
          Y = class extends R {
            boneIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.shearX + "|" + i), this.boneIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.bones[this.boneIndex];
              o.active && (o.shearX = this.getRelativeValue(i, n, r, o.shearX, o.data.shearX))
            }
          },
          G = class extends R {
            boneIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.shearY + "|" + i), this.boneIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.bones[this.boneIndex];
              o.active && (o.shearY = this.getRelativeValue(i, n, r, o.shearY, o.data.shearY))
            }
          },
          X = class extends M {
            boneIndex = 0;
            constructor(t, e) {
              super(t, [O.inherit + "|" + e]), this.boneIndex = e
            }
            getFrameEntries() {
              return 2
            }
            setFrame(t, e, i) {
              t *= 2, this.frames[t] = e, this.frames[t + 1] = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.bones[this.boneIndex];
              if (!o.active) return;
              if (1 == a) return void(0 == r && (o.inherit = o.data.inherit));
              let h = this.frames;
              i < h[0] ? (0 == r || 1 == r) && (o.inherit = o.data.inherit) : o.inherit = this.frames[M.search(h, i, 2) + 1]
            }
          },
          j = class extends B {
            slotIndex = 0;
            constructor(t, e, i) {
              super(t, e, [O.rgb + "|" + i, O.alpha + "|" + i]), this.slotIndex = i
            }
            getFrameEntries() {
              return 5
            }
            setFrame(t, e, i, s, n, r) {
              t *= 5, this.frames[t] = e, this.frames[t + 1] = i, this.frames[t + 2] = s, this.frames[t + 3] = n, this.frames[t + 4] = r
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.slots[this.slotIndex];
              if (!o.bone.active) return;
              let h = this.frames,
                l = o.color;
              if (i < h[0]) {
                let t = o.data.color;
                switch (r) {
                  case 0:
                    return void l.setFromColor(t);
                  case 1:
                    l.add((t.r - l.r) * n, (t.g - l.g) * n, (t.b - l.b) * n, (t.a - l.a) * n)
                }
                return
              }
              let c = 0,
                d = 0,
                u = 0,
                p = 0,
                g = M.search(h, i, 5),
                m = this.curves[g / 5];
              switch (m) {
                case 0:
                  let t = h[g];
                  c = h[g + 1], d = h[g + 2], u = h[g + 3], p = h[g + 4];
                  let e = (i - t) / (h[g + 5] - t);
                  c += (h[g + 5 + 1] - c) * e, d += (h[g + 5 + 2] - d) * e, u += (h[g + 5 + 3] - u) * e, p += (h[g + 5 + 4] - p) * e;
                  break;
                case 1:
                  c = h[g + 1], d = h[g + 2], u = h[g + 3], p = h[g + 4];
                  break;
                default:
                  c = this.getBezierValue(i, g, 1, m - 2), d = this.getBezierValue(i, g, 2, m + 18 - 2), u = this.getBezierValue(i, g, 3, m + 36 - 2), p = this.getBezierValue(i, g, 4, m + 54 - 2)
              }
              1 == n ? l.set(c, d, u, p) : (0 == r && l.setFromColor(o.data.color), l.add((c - l.r) * n, (d - l.g) * n, (u - l.b) * n, (p - l.a) * n))
            }
          },
          $ = class extends B {
            slotIndex = 0;
            constructor(t, e, i) {
              super(t, e, [O.rgb + "|" + i]), this.slotIndex = i
            }
            getFrameEntries() {
              return 4
            }
            setFrame(t, e, i, s, n) {
              t <<= 2, this.frames[t] = e, this.frames[t + 1] = i, this.frames[t + 2] = s, this.frames[t + 3] = n
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.slots[this.slotIndex];
              if (!o.bone.active) return;
              let h = this.frames,
                l = o.color;
              if (i < h[0]) {
                let t = o.data.color;
                switch (r) {
                  case 0:
                    return l.r = t.r, l.g = t.g, void(l.b = t.b);
                  case 1:
                    l.r += (t.r - l.r) * n, l.g += (t.g - l.g) * n, l.b += (t.b - l.b) * n
                }
                return
              }
              let c = 0,
                d = 0,
                u = 0,
                p = M.search(h, i, 4),
                g = this.curves[p >> 2];
              switch (g) {
                case 0:
                  let t = h[p];
                  c = h[p + 1], d = h[p + 2], u = h[p + 3];
                  let e = (i - t) / (h[p + 4] - t);
                  c += (h[p + 4 + 1] - c) * e, d += (h[p + 4 + 2] - d) * e, u += (h[p + 4 + 3] - u) * e;
                  break;
                case 1:
                  c = h[p + 1], d = h[p + 2], u = h[p + 3];
                  break;
                default:
                  c = this.getBezierValue(i, p, 1, g - 2), d = this.getBezierValue(i, p, 2, g + 18 - 2), u = this.getBezierValue(i, p, 3, g + 36 - 2)
              }
              if (1 == n) l.r = c, l.g = d, l.b = u;
              else {
                if (0 == r) {
                  let t = o.data.color;
                  l.r = t.r, l.g = t.g, l.b = t.b
                }
                l.r += (c - l.r) * n, l.g += (d - l.g) * n, l.b += (u - l.b) * n
              }
            }
          },
          K = class extends R {
            slotIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.alpha + "|" + i), this.slotIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.slots[this.slotIndex];
              if (!o.bone.active) return;
              let h = o.color;
              if (i < this.frames[0]) {
                let t = o.data.color;
                switch (r) {
                  case 0:
                    return void(h.a = t.a);
                  case 1:
                    h.a += (t.a - h.a) * n
                }
                return
              }
              let l = this.getCurveValue(i);
              1 == n ? h.a = l : (0 == r && (h.a = o.data.color.a), h.a += (l - h.a) * n)
            }
          },
          q = class extends B {
            slotIndex = 0;
            constructor(t, e, i) {
              super(t, e, [O.rgb + "|" + i, O.alpha + "|" + i, O.rgb2 + "|" + i]), this.slotIndex = i
            }
            getFrameEntries() {
              return 8
            }
            setFrame(t, e, i, s, n, r, a, o, h) {
              t <<= 3, this.frames[t] = e, this.frames[t + 1] = i, this.frames[t + 2] = s, this.frames[t + 3] = n, this.frames[t + 4] = r, this.frames[t + 5] = a, this.frames[t + 6] = o, this.frames[t + 7] = h
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.slots[this.slotIndex];
              if (!o.bone.active) return;
              let h = this.frames,
                l = o.color,
                c = o.darkColor;
              if (i < h[0]) {
                let t = o.data.color,
                  e = o.data.darkColor;
                switch (r) {
                  case 0:
                    return l.setFromColor(t), c.r = e.r, c.g = e.g, void(c.b = e.b);
                  case 1:
                    l.add((t.r - l.r) * n, (t.g - l.g) * n, (t.b - l.b) * n, (t.a - l.a) * n), c.r += (e.r - c.r) * n, c.g += (e.g - c.g) * n, c.b += (e.b - c.b) * n
                }
                return
              }
              let d = 0,
                u = 0,
                p = 0,
                g = 0,
                m = 0,
                f = 0,
                y = 0,
                _ = M.search(h, i, 8),
                b = this.curves[_ >> 3];
              switch (b) {
                case 0:
                  let t = h[_];
                  d = h[_ + 1], u = h[_ + 2], p = h[_ + 3], g = h[_ + 4], m = h[_ + 5], f = h[_ + 6], y = h[_ + 7];
                  let e = (i - t) / (h[_ + 8] - t);
                  d += (h[_ + 8 + 1] - d) * e, u += (h[_ + 8 + 2] - u) * e, p += (h[_ + 8 + 3] - p) * e, g += (h[_ + 8 + 4] - g) * e, m += (h[_ + 8 + 5] - m) * e, f += (h[_ + 8 + 6] - f) * e, y += (h[_ + 8 + 7] - y) * e;
                  break;
                case 1:
                  d = h[_ + 1], u = h[_ + 2], p = h[_ + 3], g = h[_ + 4], m = h[_ + 5], f = h[_ + 6], y = h[_ + 7];
                  break;
                default:
                  d = this.getBezierValue(i, _, 1, b - 2), u = this.getBezierValue(i, _, 2, b + 18 - 2), p = this.getBezierValue(i, _, 3, b + 36 - 2), g = this.getBezierValue(i, _, 4, b + 54 - 2), m = this.getBezierValue(i, _, 5, b + 72 - 2), f = this.getBezierValue(i, _, 6, b + 90 - 2), y = this.getBezierValue(i, _, 7, b + 108 - 2)
              }
              if (1 == n) l.set(d, u, p, g), c.r = m, c.g = f, c.b = y;
              else {
                if (0 == r) {
                  l.setFromColor(o.data.color);
                  let t = o.data.darkColor;
                  c.r = t.r, c.g = t.g, c.b = t.b
                }
                l.add((d - l.r) * n, (u - l.g) * n, (p - l.b) * n, (g - l.a) * n), c.r += (m - c.r) * n, c.g += (f - c.g) * n, c.b += (y - c.b) * n
              }
            }
          },
          Z = class extends B {
            slotIndex = 0;
            constructor(t, e, i) {
              super(t, e, [O.rgb + "|" + i, O.rgb2 + "|" + i]), this.slotIndex = i
            }
            getFrameEntries() {
              return 7
            }
            setFrame(t, e, i, s, n, r, a, o) {
              t *= 7, this.frames[t] = e, this.frames[t + 1] = i, this.frames[t + 2] = s, this.frames[t + 3] = n, this.frames[t + 4] = r, this.frames[t + 5] = a, this.frames[t + 6] = o
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.slots[this.slotIndex];
              if (!o.bone.active) return;
              let h = this.frames,
                l = o.color,
                c = o.darkColor;
              if (i < h[0]) {
                let t = o.data.color,
                  e = o.data.darkColor;
                switch (r) {
                  case 0:
                    return l.r = t.r, l.g = t.g, l.b = t.b, c.r = e.r, c.g = e.g, void(c.b = e.b);
                  case 1:
                    l.r += (t.r - l.r) * n, l.g += (t.g - l.g) * n, l.b += (t.b - l.b) * n, c.r += (e.r - c.r) * n, c.g += (e.g - c.g) * n, c.b += (e.b - c.b) * n
                }
                return
              }
              let d = 0,
                u = 0,
                p = 0,
                g = 0,
                m = 0,
                f = 0,
                y = M.search(h, i, 7),
                _ = this.curves[y / 7];
              switch (_) {
                case 0:
                  let t = h[y];
                  d = h[y + 1], u = h[y + 2], p = h[y + 3], g = h[y + 4], m = h[y + 5], f = h[y + 6];
                  let e = (i - t) / (h[y + 7] - t);
                  d += (h[y + 7 + 1] - d) * e, u += (h[y + 7 + 2] - u) * e, p += (h[y + 7 + 3] - p) * e, g += (h[y + 7 + 4] - g) * e, m += (h[y + 7 + 5] - m) * e, f += (h[y + 7 + 6] - f) * e;
                  break;
                case 1:
                  d = h[y + 1], u = h[y + 2], p = h[y + 3], g = h[y + 4], m = h[y + 5], f = h[y + 6];
                  break;
                default:
                  d = this.getBezierValue(i, y, 1, _ - 2), u = this.getBezierValue(i, y, 2, _ + 18 - 2), p = this.getBezierValue(i, y, 3, _ + 36 - 2), g = this.getBezierValue(i, y, 4, _ + 54 - 2), m = this.getBezierValue(i, y, 5, _ + 72 - 2), f = this.getBezierValue(i, y, 6, _ + 90 - 2)
              }
              if (1 == n) l.r = d, l.g = u, l.b = p, c.r = g, c.g = m, c.b = f;
              else {
                if (0 == r) {
                  let t = o.data.color,
                    e = o.data.darkColor;
                  l.r = t.r, l.g = t.g, l.b = t.b, c.r = e.r, c.g = e.g, c.b = e.b
                }
                l.r += (d - l.r) * n, l.g += (u - l.g) * n, l.b += (p - l.b) * n, c.r += (g - c.r) * n, c.g += (m - c.g) * n, c.b += (f - c.b) * n
              }
            }
          },
          Q = class extends M {
            slotIndex = 0;
            attachmentNames;
            constructor(t, e) {
              super(t, [O.attachment + "|" + e]), this.slotIndex = e, this.attachmentNames = new Array(t)
            }
            getFrameCount() {
              return this.frames.length
            }
            setFrame(t, e, i) {
              this.frames[t] = e, this.attachmentNames[t] = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.slots[this.slotIndex];
              if (o.bone.active) {
                if (1 == a) return void(0 == r && this.setAttachment(t, o, o.data.attachmentName));
                if (i < this.frames[0]) return void((0 == r || 1 == r) && this.setAttachment(t, o, o.data.attachmentName));
                this.setAttachment(t, o, this.attachmentNames[M.search1(this.frames, i)])
              }
            }
            setAttachment(t, e, i) {
              e.setAttachment(i ? t.getAttachment(this.slotIndex, i) : null)
            }
          },
          J = class extends B {
            slotIndex = 0;
            attachment;
            vertices;
            constructor(t, e, i, s) {
              super(t, e, [O.deform + "|" + i + "|" + s.id]), this.slotIndex = i, this.attachment = s, this.vertices = new Array(t)
            }
            getFrameCount() {
              return this.frames.length
            }
            setFrame(t, e, i) {
              this.frames[t] = e, this.vertices[t] = i
            }
            setBezier(t, e, i, s, n, r, a, o, h, l, c) {
              let d = this.curves,
                u = this.getFrameCount() + 18 * t;
              0 == i && (d[e] = 2 + u);
              let p = .03 * (s - 2 * r + o),
                g = .03 * h - .06 * a,
                m = .006 * (3 * (r - o) - s + l),
                f = .018 * (a - h + .33333333),
                y = 2 * p + m,
                _ = 2 * g + f,
                b = .3 * (r - s) + p + .16666667 * m,
                v = .3 * a + g + .16666667 * f,
                x = s + b,
                w = v;
              for (let t = u + 18; u < t; u += 2) d[u] = x, d[u + 1] = w, b += y, v += _, y += m, _ += f, x += b, w += v
            }
            getCurvePercent(t, e) {
              let i = this.curves,
                s = i[e];
              switch (s) {
                case 0:
                  let i = this.frames[e];
                  return (t - i) / (this.frames[e + this.getFrameEntries()] - i);
                case 1:
                  return 0
              }
              if (s -= 2, i[s] > t) {
                let n = this.frames[e];
                return i[s + 1] * (t - n) / (i[s] - n)
              }
              let n = s + 18;
              for (s += 2; s < n; s += 2)
                if (i[s] >= t) {
                  let e = i[s - 2],
                    n = i[s - 1];
                  return n + (t - e) / (i[s] - e) * (i[s + 1] - n)
                } let r = i[n - 2],
                a = i[n - 1];
              return a + (1 - a) * (t - r) / (this.frames[e + this.getFrameEntries()] - r)
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.slots[this.slotIndex];
              if (!o.bone.active) return;
              let h = o.getAttachment();
              if (!(h && h instanceof T && h.timelineAttachment == this.attachment)) return;
              let l = o.deform;
              0 == l.length && (r = 0);
              let c = this.vertices,
                d = c[0].length,
                u = this.frames;
              if (i < u[0]) {
                switch (r) {
                  case 0:
                    return void(l.length = 0);
                  case 1:
                    if (1 == n) return void(l.length = 0);
                    l.length = d;
                    let t = h;
                    if (t.bones) {
                      n = 1 - n;
                      for (var p = 0; p < d; p++) l[p] *= n
                    } else {
                      let e = t.vertices;
                      for (p = 0; p < d; p++) l[p] += (e[p] - l[p]) * n
                    }
                }
                return
              }
              if (l.length = d, i >= u[u.length - 1]) {
                let t = c[u.length - 1];
                if (1 == n)
                  if (3 == r) {
                    let e = h;
                    if (e.bones)
                      for (let e = 0; e < d; e++) l[e] += t[e];
                    else {
                      let i = e.vertices;
                      for (let e = 0; e < d; e++) l[e] += t[e] - i[e]
                    }
                  } else y.arrayCopy(t, 0, l, 0, d);
                else switch (r) {
                  case 0: {
                    let e = h;
                    if (e.bones)
                      for (let e = 0; e < d; e++) l[e] = t[e] * n;
                    else {
                      let i = e.vertices;
                      for (let e = 0; e < d; e++) {
                        let s = i[e];
                        l[e] = s + (t[e] - s) * n
                      }
                    }
                    break
                  }
                  case 1:
                  case 2:
                    for (let e = 0; e < d; e++) l[e] += (t[e] - l[e]) * n;
                    break;
                  case 3:
                    let e = h;
                    if (e.bones)
                      for (let e = 0; e < d; e++) l[e] += t[e] * n;
                    else {
                      let i = e.vertices;
                      for (let e = 0; e < d; e++) l[e] += (t[e] - i[e]) * n
                    }
                }
                return
              }
              let g = M.search1(u, i),
                m = this.getCurvePercent(i, g),
                f = c[g],
                _ = c[g + 1];
              if (1 == n)
                if (3 == r) {
                  let t = h;
                  if (t.bones)
                    for (let t = 0; t < d; t++) {
                      let e = f[t];
                      l[t] += e + (_[t] - e) * m
                    } else {
                      let e = t.vertices;
                      for (let t = 0; t < d; t++) {
                        let i = f[t];
                        l[t] += i + (_[t] - i) * m - e[t]
                      }
                    }
                } else
                  for (let t = 0; t < d; t++) {
                    let e = f[t];
                    l[t] = e + (_[t] - e) * m
                  } else switch (r) {
                    case 0: {
                      let t = h;
                      if (t.bones)
                        for (let t = 0; t < d; t++) {
                          let e = f[t];
                          l[t] = (e + (_[t] - e) * m) * n
                        } else {
                          let e = t.vertices;
                          for (let t = 0; t < d; t++) {
                            let i = f[t],
                              s = e[t];
                            l[t] = s + (i + (_[t] - i) * m - s) * n
                          }
                        }
                      break
                    }
                    case 1:
                    case 2:
                      for (let t = 0; t < d; t++) {
                        let e = f[t];
                        l[t] += (e + (_[t] - e) * m - l[t]) * n
                      }
                      break;
                    case 3:
                      let t = h;
                      if (t.bones)
                        for (let t = 0; t < d; t++) {
                          let e = f[t];
                          l[t] += (e + (_[t] - e) * m) * n
                        } else {
                          let e = t.vertices;
                          for (let t = 0; t < d; t++) {
                            let i = f[t];
                            l[t] += (i + (_[t] - i) * m - e[t]) * n
                          }
                        }
                  }
            }
          },
          tt = class t extends M {
            static propertyIds = ["" + O.event];
            events;
            constructor(e) {
              super(e, t.propertyIds), this.events = new Array(e)
            }
            getFrameCount() {
              return this.frames.length
            }
            setFrame(t, e) {
              this.frames[t] = e.time, this.events[t] = e
            }
            apply(t, e, i, s, n, r, a) {
              if (!s) return;
              let o = this.frames,
                h = this.frames.length;
              if (e > i) this.apply(t, e, Number.MAX_VALUE, s, n, r, a), e = -1;
              else if (e >= o[h - 1]) return;
              if (i < o[0]) return;
              let l = 0;
              if (e < o[0]) l = 0;
              else {
                l = M.search1(o, e) + 1;
                let t = o[l];
                for (; l > 0 && o[l - 1] == t;) l--
              }
              for (; l < h && i >= o[l]; l++) s.push(this.events[l])
            }
          },
          et = class t extends M {
            static propertyIds = ["" + O.drawOrder];
            drawOrders;
            constructor(e) {
              super(e, t.propertyIds), this.drawOrders = new Array(e)
            }
            getFrameCount() {
              return this.frames.length
            }
            setFrame(t, e, i) {
              this.frames[t] = e, this.drawOrders[t] = i
            }
            apply(t, e, i, s, n, r, a) {
              if (1 == a) return void(0 == r && y.arrayCopy(t.slots, 0, t.drawOrder, 0, t.slots.length));
              if (i < this.frames[0]) return void((0 == r || 1 == r) && y.arrayCopy(t.slots, 0, t.drawOrder, 0, t.slots.length));
              let o = M.search1(this.frames, i),
                h = this.drawOrders[o];
              if (h) {
                let e = t.drawOrder,
                  i = t.slots;
                for (let t = 0, s = h.length; t < s; t++) e[t] = i[h[t]]
              } else y.arrayCopy(t.slots, 0, t.drawOrder, 0, t.slots.length)
            }
          },
          it = class extends B {
            constraintIndex = 0;
            constructor(t, e, i) {
              super(t, e, [O.ikConstraint + "|" + i]), this.constraintIndex = i
            }
            getFrameEntries() {
              return 6
            }
            setFrame(t, e, i, s, n, r, a) {
              t *= 6, this.frames[t] = e, this.frames[t + 1] = i, this.frames[t + 2] = s, this.frames[t + 3] = n, this.frames[t + 4] = r ? 1 : 0, this.frames[t + 5] = a ? 1 : 0
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.ikConstraints[this.constraintIndex];
              if (!o.active) return;
              let h = this.frames;
              if (i < h[0]) {
                switch (r) {
                  case 0:
                    return o.mix = o.data.mix, o.softness = o.data.softness, o.bendDirection = o.data.bendDirection, o.compress = o.data.compress, void(o.stretch = o.data.stretch);
                  case 1:
                    o.mix += (o.data.mix - o.mix) * n, o.softness += (o.data.softness - o.softness) * n, o.bendDirection = o.data.bendDirection, o.compress = o.data.compress, o.stretch = o.data.stretch
                }
                return
              }
              let l = 0,
                c = 0,
                d = M.search(h, i, 6),
                u = this.curves[d / 6];
              switch (u) {
                case 0:
                  let t = h[d];
                  l = h[d + 1], c = h[d + 2];
                  let e = (i - t) / (h[d + 6] - t);
                  l += (h[d + 6 + 1] - l) * e, c += (h[d + 6 + 2] - c) * e;
                  break;
                case 1:
                  l = h[d + 1], c = h[d + 2];
                  break;
                default:
                  l = this.getBezierValue(i, d, 1, u - 2), c = this.getBezierValue(i, d, 2, u + 18 - 2)
              }
              0 == r ? (o.mix = o.data.mix + (l - o.data.mix) * n, o.softness = o.data.softness + (c - o.data.softness) * n, 1 == a ? (o.bendDirection = o.data.bendDirection, o.compress = o.data.compress, o.stretch = o.data.stretch) : (o.bendDirection = h[d + 3], o.compress = 0 != h[d + 4], o.stretch = 0 != h[d + 5])) : (o.mix += (l - o.mix) * n, o.softness += (c - o.softness) * n, 0 == a && (o.bendDirection = h[d + 3], o.compress = 0 != h[d + 4], o.stretch = 0 != h[d + 5]))
            }
          },
          st = class extends B {
            constraintIndex = 0;
            constructor(t, e, i) {
              super(t, e, [O.transformConstraint + "|" + i]), this.constraintIndex = i
            }
            getFrameEntries() {
              return 7
            }
            setFrame(t, e, i, s, n, r, a, o) {
              let h = this.frames;
              h[t *= 7] = e, h[t + 1] = i, h[t + 2] = s, h[t + 3] = n, h[t + 4] = r, h[t + 5] = a, h[t + 6] = o
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.transformConstraints[this.constraintIndex];
              if (!o.active) return;
              let h = this.frames;
              if (i < h[0]) {
                let t = o.data;
                switch (r) {
                  case 0:
                    return o.mixRotate = t.mixRotate, o.mixX = t.mixX, o.mixY = t.mixY, o.mixScaleX = t.mixScaleX, o.mixScaleY = t.mixScaleY, void(o.mixShearY = t.mixShearY);
                  case 1:
                    o.mixRotate += (t.mixRotate - o.mixRotate) * n, o.mixX += (t.mixX - o.mixX) * n, o.mixY += (t.mixY - o.mixY) * n, o.mixScaleX += (t.mixScaleX - o.mixScaleX) * n, o.mixScaleY += (t.mixScaleY - o.mixScaleY) * n, o.mixShearY += (t.mixShearY - o.mixShearY) * n
                }
                return
              }
              let l, c, d, u, p, g, m = M.search(h, i, 7),
                f = this.curves[m / 7];
              switch (f) {
                case 0:
                  let t = h[m];
                  l = h[m + 1], c = h[m + 2], d = h[m + 3], u = h[m + 4], p = h[m + 5], g = h[m + 6];
                  let e = (i - t) / (h[m + 7] - t);
                  l += (h[m + 7 + 1] - l) * e, c += (h[m + 7 + 2] - c) * e, d += (h[m + 7 + 3] - d) * e, u += (h[m + 7 + 4] - u) * e, p += (h[m + 7 + 5] - p) * e, g += (h[m + 7 + 6] - g) * e;
                  break;
                case 1:
                  l = h[m + 1], c = h[m + 2], d = h[m + 3], u = h[m + 4], p = h[m + 5], g = h[m + 6];
                  break;
                default:
                  l = this.getBezierValue(i, m, 1, f - 2), c = this.getBezierValue(i, m, 2, f + 18 - 2), d = this.getBezierValue(i, m, 3, f + 36 - 2), u = this.getBezierValue(i, m, 4, f + 54 - 2), p = this.getBezierValue(i, m, 5, f + 72 - 2), g = this.getBezierValue(i, m, 6, f + 90 - 2)
              }
              if (0 == r) {
                let t = o.data;
                o.mixRotate = t.mixRotate + (l - t.mixRotate) * n, o.mixX = t.mixX + (c - t.mixX) * n, o.mixY = t.mixY + (d - t.mixY) * n, o.mixScaleX = t.mixScaleX + (u - t.mixScaleX) * n, o.mixScaleY = t.mixScaleY + (p - t.mixScaleY) * n, o.mixShearY = t.mixShearY + (g - t.mixShearY) * n
              } else o.mixRotate += (l - o.mixRotate) * n, o.mixX += (c - o.mixX) * n, o.mixY += (d - o.mixY) * n, o.mixScaleX += (u - o.mixScaleX) * n, o.mixScaleY += (p - o.mixScaleY) * n, o.mixShearY += (g - o.mixShearY) * n
            }
          },
          nt = class extends R {
            constraintIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.pathConstraintPosition + "|" + i), this.constraintIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.pathConstraints[this.constraintIndex];
              o.active && (o.position = this.getAbsoluteValue(i, n, r, o.position, o.data.position))
            }
          },
          rt = class extends R {
            constraintIndex = 0;
            constructor(t, e, i) {
              super(t, e, O.pathConstraintSpacing + "|" + i), this.constraintIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.pathConstraints[this.constraintIndex];
              o.active && (o.spacing = this.getAbsoluteValue(i, n, r, o.spacing, o.data.spacing))
            }
          },
          at = class extends B {
            constraintIndex = 0;
            constructor(t, e, i) {
              super(t, e, [O.pathConstraintMix + "|" + i]), this.constraintIndex = i
            }
            getFrameEntries() {
              return 4
            }
            setFrame(t, e, i, s, n) {
              let r = this.frames;
              r[t <<= 2] = e, r[t + 1] = i, r[t + 2] = s, r[t + 3] = n
            }
            apply(t, e, i, s, n, r, a) {
              let o = t.pathConstraints[this.constraintIndex];
              if (!o.active) return;
              let h = this.frames;
              if (i < h[0]) {
                switch (r) {
                  case 0:
                    return o.mixRotate = o.data.mixRotate, o.mixX = o.data.mixX, void(o.mixY = o.data.mixY);
                  case 1:
                    o.mixRotate += (o.data.mixRotate - o.mixRotate) * n, o.mixX += (o.data.mixX - o.mixX) * n, o.mixY += (o.data.mixY - o.mixY) * n
                }
                return
              }
              let l, c, d, u = M.search(h, i, 4),
                p = this.curves[u >> 2];
              switch (p) {
                case 0:
                  let t = h[u];
                  l = h[u + 1], c = h[u + 2], d = h[u + 3];
                  let e = (i - t) / (h[u + 4] - t);
                  l += (h[u + 4 + 1] - l) * e, c += (h[u + 4 + 2] - c) * e, d += (h[u + 4 + 3] - d) * e;
                  break;
                case 1:
                  l = h[u + 1], c = h[u + 2], d = h[u + 3];
                  break;
                default:
                  l = this.getBezierValue(i, u, 1, p - 2), c = this.getBezierValue(i, u, 2, p + 18 - 2), d = this.getBezierValue(i, u, 3, p + 36 - 2)
              }
              if (0 == r) {
                let t = o.data;
                o.mixRotate = t.mixRotate + (l - t.mixRotate) * n, o.mixX = t.mixX + (c - t.mixX) * n, o.mixY = t.mixY + (d - t.mixY) * n
              } else o.mixRotate += (l - o.mixRotate) * n, o.mixX += (c - o.mixX) * n, o.mixY += (d - o.mixY) * n
            }
          },
          ot = class extends R {
            constraintIndex = 0;
            constructor(t, e, i, s) {
              super(t, e, s + "|" + i), this.constraintIndex = i
            }
            apply(t, e, i, s, n, r, a) {
              let o;
              if (-1 == this.constraintIndex) {
                const e = i >= this.frames[0] ? this.getCurveValue(i) : 0;
                for (const s of t.physicsConstraints) s.active && this.global(s.data) && this.set(s, this.getAbsoluteValue2(i, n, r, this.get(s), this.setup(s), e))
              } else o = t.physicsConstraints[this.constraintIndex], o.active && this.set(o, this.getAbsoluteValue(i, n, r, this.get(o), this.setup(o)))
            }
          },
          ht = class extends ot {
            constructor(t, e, i) {
              super(t, e, i, O.physicsConstraintInertia)
            }
            setup(t) {
              return t.data.inertia
            }
            get(t) {
              return t.inertia
            }
            set(t, e) {
              t.inertia = e
            }
            global(t) {
              return t.inertiaGlobal
            }
          },
          lt = class extends ot {
            constructor(t, e, i) {
              super(t, e, i, O.physicsConstraintStrength)
            }
            setup(t) {
              return t.data.strength
            }
            get(t) {
              return t.strength
            }
            set(t, e) {
              t.strength = e
            }
            global(t) {
              return t.strengthGlobal
            }
          },
          ct = class extends ot {
            constructor(t, e, i) {
              super(t, e, i, O.physicsConstraintDamping)
            }
            setup(t) {
              return t.data.damping
            }
            get(t) {
              return t.damping
            }
            set(t, e) {
              t.damping = e
            }
            global(t) {
              return t.dampingGlobal
            }
          },
          dt = class extends ot {
            constructor(t, e, i) {
              super(t, e, i, O.physicsConstraintMass)
            }
            setup(t) {
              return 1 / t.data.massInverse
            }
            get(t) {
              return 1 / t.massInverse
            }
            set(t, e) {
              t.massInverse = 1 / e
            }
            global(t) {
              return t.massGlobal
            }
          },
          ut = class extends ot {
            constructor(t, e, i) {
              super(t, e, i, O.physicsConstraintWind)
            }
            setup(t) {
              return t.data.wind
            }
            get(t) {
              return t.wind
            }
            set(t, e) {
              t.wind = e
            }
            global(t) {
              return t.windGlobal
            }
          },
          pt = class extends ot {
            constructor(t, e, i) {
              super(t, e, i, O.physicsConstraintGravity)
            }
            setup(t) {
              return t.data.gravity
            }
            get(t) {
              return t.gravity
            }
            set(t, e) {
              t.gravity = e
            }
            global(t) {
              return t.gravityGlobal
            }
          },
          gt = class extends ot {
            constructor(t, e, i) {
              super(t, e, i, O.physicsConstraintMix)
            }
            setup(t) {
              return t.data.mix
            }
            get(t) {
              return t.mix
            }
            set(t, e) {
              t.mix = e
            }
            global(t) {
              return t.mixGlobal
            }
          },
          mt = class t extends M {
            static propertyIds = [O.physicsConstraintReset.toString()];
            constraintIndex;
            constructor(e, i) {
              super(e, t.propertyIds), this.constraintIndex = i
            }
            getFrameCount() {
              return this.frames.length
            }
            setFrame(t, e) {
              this.frames[t] = e
            }
            apply(t, e, i, s, n, r, a) {
              let o;
              if (-1 != this.constraintIndex && (o = t.physicsConstraints[this.constraintIndex], !o.active)) return;
              const h = this.frames;
              if (e > i) this.apply(t, e, Number.MAX_VALUE, [], n, r, a), e = -1;
              else if (e >= h[h.length - 1]) return;
              if (!(i < h[0]) && (e < h[0] || i >= h[M.search1(h, e) + 1]))
                if (null != o) o.reset();
                else
                  for (const e of t.physicsConstraints) e.active && e.reset()
            }
          },
          ft = class t extends M {
            static ENTRIES = 3;
            static MODE = 1;
            static DELAY = 2;
            slotIndex;
            attachment;
            constructor(t, e, i) {
              super(t, [O.sequence + "|" + e + "|" + i.sequence.id]), this.slotIndex = e, this.attachment = i
            }
            getFrameEntries() {
              return t.ENTRIES
            }
            getSlotIndex() {
              return this.slotIndex
            }
            getAttachment() {
              return this.attachment
            }
            setFrame(e, i, s, n, r) {
              let a = this.frames;
              a[e *= t.ENTRIES] = i, a[e + t.MODE] = s | n << 4, a[e + t.DELAY] = r
            }
            apply(e, i, s, n, r, a, o) {
              let h = e.slots[this.slotIndex];
              if (!h.bone.active) return;
              let l = h.attachment,
                c = this.attachment;
              if (!(l == c || l instanceof T && l.timelineAttachment == c)) return;
              if (1 == o) return void(0 == a && (h.sequenceIndex = -1));
              let d = this.frames;
              if (s < d[0]) return void((0 == a || 1 == a) && (h.sequenceIndex = -1));
              let u = M.search(d, s, t.ENTRIES),
                p = d[u],
                g = d[u + t.MODE],
                m = d[u + t.DELAY];
              if (!this.attachment.sequence) return;
              let f = g >> 4,
                y = this.attachment.sequence.regions.length,
                _ = P[15 & g];
              if (0 != _) switch (f += (s - p) / m + 1e-5 | 0, _) {
                case 1:
                  f = Math.min(y - 1, f);
                  break;
                case 2:
                  f %= y;
                  break;
                case 3: {
                  let t = (y << 1) - 2;
                  f = 0 == t ? 0 : f % t, f >= y && (f = t - f);
                  break
                }
                case 4:
                  f = Math.max(y - 1 - f, 0);
                  break;
                case 5:
                  f = y - 1 - f % y;
                  break;
                case 6: {
                  let t = (y << 1) - 2;
                  f = 0 == t ? 0 : (f + y - 1) % t, f >= y && (f = t - f)
                }
              }
              h.sequenceIndex = f
            }
          },
          yt = class t {
            static _emptyAnimation = new A("<empty>", [], 0);
            static emptyAnimation() {
              return t._emptyAnimation
            }
            data;
            tracks = new Array;
            timeScale = 1;
            unkeyedState = 0;
            events = new Array;
            listeners = new Array;
            queue = new bt(this);
            propertyIDs = new d;
            animationsChanged = !1;
            trackEntryPool = new b(() => new _t);
            constructor(t) {
              this.data = t
            }
            update(t) {
              t *= this.timeScale;
              let e = this.tracks;
              for (let i = 0, s = e.length; i < s; i++) {
                let s = e[i];
                if (!s) continue;
                s.animationLast = s.nextAnimationLast, s.trackLast = s.nextTrackLast;
                let n = t * s.timeScale;
                if (s.delay > 0) {
                  if (s.delay -= n, s.delay > 0) continue;
                  n = -s.delay, s.delay = 0
                }
                let r = s.next;
                if (r) {
                  let e = s.trackLast - r.delay;
                  if (e >= 0) {
                    for (r.delay = 0, r.trackTime += 0 == s.timeScale ? 0 : (e / s.timeScale + t) * r.timeScale, s.trackTime += n, this.setCurrent(i, r, !0); r.mixingFrom;) r.mixTime += t, r = r.mixingFrom;
                    continue
                  }
                } else if (s.trackLast >= s.trackEnd && !s.mixingFrom) {
                  e[i] = null, this.queue.end(s), this.clearNext(s);
                  continue
                }
                if (s.mixingFrom && this.updateMixingFrom(s, t)) {
                  let t = s.mixingFrom;
                  for (s.mixingFrom = null, t && (t.mixingTo = null); t;) this.queue.end(t), t = t.mixingFrom
                }
                s.trackTime += n
              }
              this.queue.drain()
            }
            updateMixingFrom(t, e) {
              let i = t.mixingFrom;
              if (!i) return !0;
              let s = this.updateMixingFrom(i, e);
              return i.animationLast = i.nextAnimationLast, i.trackLast = i.nextTrackLast, -1 != t.nextTrackLast && t.mixTime >= t.mixDuration ? ((0 == i.totalAlpha || 0 == t.mixDuration) && (t.mixingFrom = i.mixingFrom, null != i.mixingFrom && (i.mixingFrom.mixingTo = t), t.interruptAlpha = i.interruptAlpha, this.queue.end(i)), s) : (i.trackTime += e * i.timeScale, t.mixTime += e, !1)
            }
            apply(t) {
              if (!t) throw new Error("skeleton cannot be null.");
              this.animationsChanged && this._animationsChanged();
              let e = this.events,
                i = this.tracks,
                s = !1;
              for (let r = 0, a = i.length; r < a; r++) {
                let a = i[r];
                if (!a || a.delay > 0) continue;
                s = !0;
                let o = 0 == r ? 1 : a.mixBlend,
                  h = a.alpha;
                a.mixingFrom ? h *= this.applyMixingFrom(a, t, o) : a.trackTime >= a.trackEnd && !a.next && (h = 0);
                let l = h >= a.alphaAttachmentThreshold,
                  c = a.animationLast,
                  d = a.getAnimationTime(),
                  u = d,
                  p = e;
                a.reverse && (u = a.animation.duration - u, p = null);
                let g = a.animation.timelines,
                  m = g.length;
                if (0 == r && 1 == h || 3 == o) {
                  0 == r && (l = !0);
                  for (let e = 0; e < m; e++) {
                    y.webkit602BugfixHelper(h, o);
                    var n = g[e];
                    n instanceof Q ? this.applyAttachmentTimeline(n, t, u, o, l) : n.apply(t, c, u, p, h, o, 0)
                  }
                } else {
                  let e = a.timelineMode,
                    i = a.shortestRotation,
                    s = !i && a.timelinesRotation.length != m << 1;
                  s && (a.timelinesRotation.length = m << 1);
                  for (let n = 0; n < m; n++) {
                    let r = g[n],
                      d = e[n] == wt ? o : 0;
                    !i && r instanceof L ? this.applyRotateTimeline(r, t, u, h, d, a.timelinesRotation, n << 1, s) : r instanceof Q ? this.applyAttachmentTimeline(r, t, u, o, l) : (y.webkit602BugfixHelper(h, o), r.apply(t, c, u, p, h, d, 0))
                  }
                }
                this.queueEvents(a, d), e.length = 0, a.nextAnimationLast = d, a.nextTrackLast = a.trackTime
              }
              for (var r = this.unkeyedState + Pt, a = t.slots, o = 0, h = t.slots.length; o < h; o++) {
                var l = a[o];
                if (l.attachmentState == r) {
                  var c = l.data.attachmentName;
                  l.setAttachment(c ? t.getAttachment(l.data.index, c) : null)
                }
              }
              return this.unkeyedState += 2, this.queue.drain(), s
            }
            applyMixingFrom(t, e, i) {
              let s = t.mixingFrom;
              s.mixingFrom && this.applyMixingFrom(s, e, i);
              let n = 0;
              0 == t.mixDuration ? (n = 1, 1 == i && (i = 0)) : (n = t.mixTime / t.mixDuration, n > 1 && (n = 1), 1 != i && (i = s.mixBlend));
              let r = n < s.mixAttachmentThreshold,
                a = n < s.mixDrawOrderThreshold,
                o = s.animation.timelines,
                h = o.length,
                l = s.alpha * t.interruptAlpha,
                c = l * (1 - n),
                d = s.animationLast,
                u = s.getAnimationTime(),
                p = u,
                g = null;
              if (s.reverse ? p = s.animation.duration - p : n < s.eventThreshold && (g = this.events), 3 == i)
                for (let t = 0; t < h; t++) o[t].apply(e, d, p, g, c, i, 1);
              else {
                let t = s.timelineMode,
                  n = s.timelineHoldMix,
                  u = s.shortestRotation,
                  m = !u && s.timelinesRotation.length != h << 1;
                m && (s.timelinesRotation.length = h << 1), s.totalAlpha = 0;
                for (let f = 0; f < h; f++) {
                  let h, _ = o[f],
                    b = 1,
                    v = 0;
                  switch (t[f]) {
                    case wt:
                      if (!a && _ instanceof et) continue;
                      h = i, v = c;
                      break;
                    case St:
                      h = 0, v = c;
                      break;
                    case Tt:
                      h = i, v = l;
                      break;
                    case Ct:
                      h = 0, v = l;
                      break;
                    default:
                      h = 0;
                      let t = n[f];
                      v = l * Math.max(0, 1 - t.mixTime / t.mixDuration)
                  }
                  s.totalAlpha += v, !u && _ instanceof L ? this.applyRotateTimeline(_, e, p, v, h, s.timelinesRotation, f << 1, m) : _ instanceof Q ? this.applyAttachmentTimeline(_, e, p, h, r && v >= s.alphaAttachmentThreshold) : (y.webkit602BugfixHelper(v, i), a && _ instanceof et && 0 == h && (b = 0), _.apply(e, d, p, g, v, h, b))
                }
              }
              return t.mixDuration > 0 && this.queueEvents(s, u), this.events.length = 0, s.nextAnimationLast = u, s.nextTrackLast = s.trackTime, n
            }
            applyAttachmentTimeline(t, e, i, s, n) {
              var r = e.slots[t.slotIndex];
              r.bone.active && (i < t.frames[0] ? (0 == s || 1 == s) && this.setAttachment(e, r, r.data.attachmentName, n) : this.setAttachment(e, r, t.attachmentNames[M.search1(t.frames, i)], n), r.attachmentState <= this.unkeyedState && (r.attachmentState = this.unkeyedState + Pt))
            }
            setAttachment(t, e, i, s) {
              e.setAttachment(i ? t.getAttachment(e.data.index, i) : null), s && (e.attachmentState = this.unkeyedState + At)
            }
            applyRotateTimeline(t, e, i, s, n, r, a, o) {
              if (o && (r[a] = 0), 1 == s) return void t.apply(e, 0, i, null, 1, n, 0);
              let h = e.bones[t.boneIndex];
              if (!h.active) return;
              let l = 0,
                c = 0;
              if (i < t.frames[0]) switch (n) {
                case 0:
                  h.rotation = h.data.rotation;
                default:
                  return;
                case 1:
                  l = h.rotation, c = h.data.rotation
              } else l = 0 == n ? h.data.rotation : h.rotation, c = h.data.rotation + t.getCurveValue(i);
              let d = 0,
                u = c - l;
              if (u -= 360 * Math.ceil(u / 360 - .5), 0 == u) d = r[a];
              else {
                let t = 0,
                  e = 0;
                o ? (t = 0, e = u) : (t = r[a], e = r[a + 1]);
                let i = t - t % 360;
                d = u + i;
                let s = u >= 0,
                  n = t >= 0;
                Math.abs(e) <= 90 && p.signum(e) != p.signum(u) && (Math.abs(t - i) > 180 ? (d += 360 * p.signum(t), n = s) : 0 != i ? d -= 360 * p.signum(t) : n = s), n != s && (d += 360 * p.signum(t)), r[a] = d
              }
              r[a + 1] = u, h.rotation = l + d * s
            }
            queueEvents(t, e) {
              let i = t.animationStart,
                s = t.animationEnd,
                n = s - i,
                r = t.trackLast % n,
                a = this.events,
                o = 0,
                h = a.length;
              for (; o < h; o++) {
                let e = a[o];
                if (e.time < r) break;
                e.time > s || this.queue.event(t, e)
              }
              let l = !1;
              if (t.loop)
                if (0 == n) l = !0;
                else {
                  const e = Math.floor(t.trackTime / n);
                  l = e > 0 && e > Math.floor(t.trackLast / n)
                }
              else l = e >= s && t.animationLast < s;
              for (l && this.queue.complete(t); o < h; o++) {
                let e = a[o];
                e.time < i || this.queue.event(t, e)
              }
            }
            clearTracks() {
              let t = this.queue.drainDisabled;
              this.queue.drainDisabled = !0;
              for (let t = 0, e = this.tracks.length; t < e; t++) this.clearTrack(t);
              this.tracks.length = 0, this.queue.drainDisabled = t, this.queue.drain()
            }
            clearTrack(t) {
              if (t >= this.tracks.length) return;
              let e = this.tracks[t];
              if (!e) return;
              this.queue.end(e), this.clearNext(e);
              let i = e;
              for (;;) {
                let t = i.mixingFrom;
                if (!t) break;
                this.queue.end(t), i.mixingFrom = null, i.mixingTo = null, i = t
              }
              this.tracks[e.trackIndex] = null, this.queue.drain()
            }
            setCurrent(t, e, i) {
              let s = this.expandToIndex(t);
              this.tracks[t] = e, e.previous = null, s && (i && this.queue.interrupt(s), e.mixingFrom = s, s.mixingTo = e, e.mixTime = 0, s.mixingFrom && s.mixDuration > 0 && (e.interruptAlpha *= Math.min(1, s.mixTime / s.mixDuration)), s.timelinesRotation.length = 0), this.queue.start(e)
            }
            setAnimation(t, e, i = !1) {
              let s = this.data.skeletonData.findAnimation(e);
              if (!s) throw new Error("Animation not found: " + e);
              return this.setAnimationWith(t, s, i)
            }
            setAnimationWith(t, e, i = !1) {
              if (!e) throw new Error("animation cannot be null.");
              let s = !0,
                n = this.expandToIndex(t);
              n && (-1 == n.nextTrackLast ? (this.tracks[t] = n.mixingFrom, this.queue.interrupt(n), this.queue.end(n), this.clearNext(n), n = n.mixingFrom, s = !1) : this.clearNext(n));
              let r = this.trackEntry(t, e, i, n);
              return this.setCurrent(t, r, s), this.queue.drain(), r
            }
            addAnimation(t, e, i = !1, s = 0) {
              let n = this.data.skeletonData.findAnimation(e);
              if (!n) throw new Error("Animation not found: " + e);
              return this.addAnimationWith(t, n, i, s)
            }
            addAnimationWith(t, e, i = !1, s = 0) {
              if (!e) throw new Error("animation cannot be null.");
              let n = this.expandToIndex(t);
              if (n)
                for (; n.next;) n = n.next;
              let r = this.trackEntry(t, e, i, n);
              return n ? (n.next = r, r.previous = n, s <= 0 && (s = Math.max(s + n.getTrackComplete() - r.mixDuration, 0))) : (this.setCurrent(t, r, !0), this.queue.drain(), s < 0 && (s = 0)), r.delay = s, r
            }
            setEmptyAnimation(e, i = 0) {
              let s = this.setAnimationWith(e, t.emptyAnimation(), !1);
              return s.mixDuration = i, s.trackEnd = i, s
            }
            addEmptyAnimation(e, i = 0, s = 0) {
              let n = this.addAnimationWith(e, t.emptyAnimation(), !1, s);
              return s <= 0 && (n.delay = Math.max(n.delay + n.mixDuration - i, 0)), n.mixDuration = i, n.trackEnd = i, n
            }
            setEmptyAnimations(t = 0) {
              let e = this.queue.drainDisabled;
              this.queue.drainDisabled = !0;
              for (let e = 0, i = this.tracks.length; e < i; e++) {
                let i = this.tracks[e];
                i && this.setEmptyAnimation(i.trackIndex, t)
              }
              this.queue.drainDisabled = e, this.queue.drain()
            }
            expandToIndex(t) {
              return t < this.tracks.length ? this.tracks[t] : (y.ensureArrayCapacity(this.tracks, t + 1, null), this.tracks.length = t + 1, null)
            }
            trackEntry(t, e, i, s) {
              let n = this.trackEntryPool.obtain();
              return n.reset(), n.trackIndex = t, n.animation = e, n.loop = i, n.holdPrevious = !1, n.reverse = !1, n.shortestRotation = !1, n.eventThreshold = 0, n.alphaAttachmentThreshold = 0, n.mixAttachmentThreshold = 0, n.mixDrawOrderThreshold = 0, n.animationStart = 0, n.animationEnd = e.duration, n.animationLast = -1, n.nextAnimationLast = -1, n.delay = 0, n.trackTime = 0, n.trackLast = -1, n.nextTrackLast = -1, n.trackEnd = Number.MAX_VALUE, n.timeScale = 1, n.alpha = 1, n.mixTime = 0, n.mixDuration = s ? this.data.getMix(s.animation, e) : 0, n.interruptAlpha = 1, n.totalAlpha = 0, n.mixBlend = 2, n
            }
            clearNext(t) {
              let e = t.next;
              for (; e;) this.queue.dispose(e), e = e.next;
              t.next = null
            }
            _animationsChanged() {
              this.animationsChanged = !1, this.propertyIDs.clear();
              let t = this.tracks;
              for (let e = 0, i = t.length; e < i; e++) {
                let i = t[e];
                if (i) {
                  for (; i.mixingFrom;) i = i.mixingFrom;
                  do {
                    (!i.mixingTo || 3 != i.mixBlend) && this.computeHold(i), i = i.mixingTo
                  } while (i)
                }
              }
            }
            computeHold(t) {
              let e = t.mixingTo,
                i = t.animation.timelines,
                s = t.animation.timelines.length,
                n = t.timelineMode;
              n.length = s;
              let r = t.timelineHoldMix;
              r.length = 0;
              let a = this.propertyIDs;
              if (e && e.holdPrevious)
                for (let t = 0; t < s; t++) n[t] = a.addAll(i[t].getPropertyIds()) ? Ct : Tt;
              else t: for (let o = 0; o < s; o++) {
                let s = i[o],
                  h = s.getPropertyIds();
                if (a.addAll(h))
                  if (!e || s instanceof Q || s instanceof et || s instanceof tt || !e.animation.hasTimeline(h)) n[o] = St;
                  else {
                    for (let i = e.mixingTo; i; i = i.mixingTo)
                      if (!i.animation.hasTimeline(h)) {
                        if (t.mixDuration > 0) {
                          n[o] = kt, r[o] = i;
                          continue t
                        }
                        break
                      } n[o] = Ct
                  }
                else n[o] = wt
              }
            }
            getCurrent(t) {
              return t >= this.tracks.length ? null : this.tracks[t]
            }
            addListener(t) {
              if (!t) throw new Error("listener cannot be null.");
              this.listeners.push(t)
            }
            removeListener(t) {
              let e = this.listeners.indexOf(t);
              e >= 0 && this.listeners.splice(e, 1)
            }
            clearListeners() {
              this.listeners.length = 0
            }
            clearListenerNotifications() {
              this.queue.clear()
            }
          },
          _t = class {
            animation = null;
            previous = null;
            next = null;
            mixingFrom = null;
            mixingTo = null;
            listener = null;
            trackIndex = 0;
            loop = !1;
            holdPrevious = !1;
            reverse = !1;
            shortestRotation = !1;
            eventThreshold = 0;
            mixAttachmentThreshold = 0;
            alphaAttachmentThreshold = 0;
            mixDrawOrderThreshold = 0;
            animationStart = 0;
            animationEnd = 0;
            animationLast = 0;
            nextAnimationLast = 0;
            delay = 0;
            trackTime = 0;
            trackLast = 0;
            nextTrackLast = 0;
            trackEnd = 0;
            timeScale = 0;
            alpha = 0;
            mixTime = 0;
            _mixDuration = 0;
            interruptAlpha = 0;
            totalAlpha = 0;
            get mixDuration() {
              return this._mixDuration
            }
            set mixDuration(t) {
              this._mixDuration = t
            }
            setMixDurationWithDelay(t, e) {
              this._mixDuration = t, e <= 0 && (e = null != this.previous ? Math.max(e + this.previous.getTrackComplete() - t, 0) : 0), this.delay = e
            }
            mixBlend = 2;
            timelineMode = new Array;
            timelineHoldMix = new Array;
            timelinesRotation = new Array;
            reset() {
              this.next = null, this.previous = null, this.mixingFrom = null, this.mixingTo = null, this.animation = null, this.listener = null, this.timelineMode.length = 0, this.timelineHoldMix.length = 0, this.timelinesRotation.length = 0
            }
            getAnimationTime() {
              if (this.loop) {
                let t = this.animationEnd - this.animationStart;
                return 0 == t ? this.animationStart : this.trackTime % t + this.animationStart
              }
              return Math.min(this.trackTime + this.animationStart, this.animationEnd)
            }
            setAnimationLast(t) {
              this.animationLast = t, this.nextAnimationLast = t
            }
            isComplete() {
              return this.trackTime >= this.animationEnd - this.animationStart
            }
            resetRotationDirections() {
              this.timelinesRotation.length = 0
            }
            getTrackComplete() {
              let t = this.animationEnd - this.animationStart;
              if (0 != t) {
                if (this.loop) return t * (1 + (this.trackTime / t | 0));
                if (this.trackTime < t) return t
              }
              return this.trackTime
            }
            wasApplied() {
              return -1 != this.nextTrackLast
            }
            isNextReady() {
              return null != this.next && this.nextTrackLast - this.next.delay >= 0
            }
          },
          bt = class {
            objects = [];
            drainDisabled = !1;
            animState;
            constructor(t) {
              this.animState = t
            }
            start(t) {
              this.objects.push(0), this.objects.push(t), this.animState.animationsChanged = !0
            }
            interrupt(t) {
              this.objects.push(1), this.objects.push(t)
            }
            end(t) {
              this.objects.push(2), this.objects.push(t), this.animState.animationsChanged = !0
            }
            dispose(t) {
              this.objects.push(3), this.objects.push(t)
            }
            complete(t) {
              this.objects.push(4), this.objects.push(t)
            }
            event(t, e) {
              this.objects.push(5), this.objects.push(t), this.objects.push(e)
            }
            drain() {
              if (this.drainDisabled) return;
              this.drainDisabled = !0;
              let t = this.objects,
                e = this.animState.listeners;
              for (let i = 0; i < t.length; i += 2) {
                let s = t[i],
                  n = t[i + 1];
                switch (s) {
                  case 0:
                    n.listener && n.listener.start && n.listener.start(n);
                    for (let t = 0; t < e.length; t++) {
                      let i = e[t];
                      i.start && i.start(n)
                    }
                    break;
                  case 1:
                    n.listener && n.listener.interrupt && n.listener.interrupt(n);
                    for (let t = 0; t < e.length; t++) {
                      let i = e[t];
                      i.interrupt && i.interrupt(n)
                    }
                    break;
                  case 2:
                    n.listener && n.listener.end && n.listener.end(n);
                    for (let t = 0; t < e.length; t++) {
                      let i = e[t];
                      i.end && i.end(n)
                    }
                  case 3:
                    n.listener && n.listener.dispose && n.listener.dispose(n);
                    for (let t = 0; t < e.length; t++) {
                      let i = e[t];
                      i.dispose && i.dispose(n)
                    }
                    this.animState.trackEntryPool.free(n);
                    break;
                  case 4:
                    n.listener && n.listener.complete && n.listener.complete(n);
                    for (let t = 0; t < e.length; t++) {
                      let i = e[t];
                      i.complete && i.complete(n)
                    }
                    break;
                  case 5:
                    let s = t[2 + i++];
                    n.listener && n.listener.event && n.listener.event(n, s);
                    for (let t = 0; t < e.length; t++) {
                      let i = e[t];
                      i.event && i.event(n, s)
                    }
                }
              }
              this.clear(), this.drainDisabled = !1
            }
            clear() {
              this.objects.length = 0
            }
          },
          vt = (t => (t[t.start = 0] = "start", t[t.interrupt = 1] = "interrupt", t[t.end = 2] = "end", t[t.dispose = 3] = "dispose", t[t.complete = 4] = "complete", t[t.event = 5] = "event", t))(vt || {}),
          xt = class {
            start(t) {}
            interrupt(t) {}
            end(t) {}
            dispose(t) {}
            complete(t) {}
            event(t, e) {}
          },
          wt = 0,
          St = 1,
          Tt = 2,
          Ct = 3,
          kt = 4,
          Pt = 1,
          At = 2,
          It = class {
            skeletonData;
            animationToMixTime = {};
            defaultMix = 0;
            constructor(t) {
              if (!t) throw new Error("skeletonData cannot be null.");
              this.skeletonData = t
            }
            setMix(t, e, i) {
              let s = this.skeletonData.findAnimation(t);
              if (!s) throw new Error("Animation not found: " + t);
              let n = this.skeletonData.findAnimation(e);
              if (!n) throw new Error("Animation not found: " + e);
              this.setMixWith(s, n, i)
            }
            setMixWith(t, e, i) {
              if (!t) throw new Error("from cannot be null.");
              if (!e) throw new Error("to cannot be null.");
              let s = t.name + "." + e.name;
              this.animationToMixTime[s] = i
            }
            getMix(t, e) {
              let i = t.name + "." + e.name,
                s = this.animationToMixTime[i];
              return void 0 === s ? this.defaultMix : s
            }
          },
          Et = class t extends T {
            color = new u(1, 1, 1, 1);
            constructor(t) {
              super(t)
            }
            copy() {
              let e = new t(this.name);
              return this.copyTo(e), e.color.setFromColor(this.color), e
            }
          },
          Ot = class t extends T {
            endSlot = null;
            color = new u(.2275, .2275, .8078, 1);
            constructor(t) {
              super(t)
            }
            copy() {
              let e = new t(this.name);
              return this.copyTo(e), e.endSlot = this.endSlot, e.color.setFromColor(this.color), e
            }
          },
          Mt = class {
            _image;
            constructor(t) {
              this._image = t
            }
            getImage() {
              return this._image
            }
          },
          Bt = (t => (t[t.Nearest = 9728] = "Nearest", t[t.Linear = 9729] = "Linear", t[t.MipMap = 9987] = "MipMap", t[t.MipMapNearestNearest = 9984] = "MipMapNearestNearest", t[t.MipMapLinearNearest = 9985] = "MipMapLinearNearest", t[t.MipMapNearestLinear = 9986] = "MipMapNearestLinear", t[t.MipMapLinearLinear = 9987] = "MipMapLinearLinear", t))(Bt || {}),
          Rt = (t => (t[t.MirroredRepeat = 33648] = "MirroredRepeat", t[t.ClampToEdge = 33071] = "ClampToEdge", t[t.Repeat = 10497] = "Repeat", t))(Rt || {}),
          Dt = class {
            texture;
            u = 0;
            v = 0;
            u2 = 0;
            v2 = 0;
            width = 0;
            height = 0;
            degrees = 0;
            offsetX = 0;
            offsetY = 0;
            originalWidth = 0;
            originalHeight = 0
          },
          Lt = class extends Mt {
            setFilters(t, e) {}
            setWraps(t, e) {}
            dispose() {}
          },
          Ft = class {
            pages = new Array;
            regions = new Array;
            constructor(t) {
              let e = new Nt(t),
                i = new Array(4),
                s = {
                  size: t => {
                    t.width = parseInt(i[1]), t.height = parseInt(i[2])
                  },
                  format: () => {},
                  filter: t => {
                    t.minFilter = y.enumValue(Bt, i[1]), t.magFilter = y.enumValue(Bt, i[2])
                  },
                  repeat: t => {
                    -1 != i[1].indexOf("x") && (t.uWrap = 10497), -1 != i[1].indexOf("y") && (t.vWrap = 10497)
                  },
                  pma: t => {
                    t.pma = "true" == i[1]
                  }
                };
              var n = {
                xy: t => {
                  t.x = parseInt(i[1]), t.y = parseInt(i[2])
                },
                size: t => {
                  t.width = parseInt(i[1]), t.height = parseInt(i[2])
                },
                bounds: t => {
                  t.x = parseInt(i[1]), t.y = parseInt(i[2]), t.width = parseInt(i[3]), t.height = parseInt(i[4])
                },
                offset: t => {
                  t.offsetX = parseInt(i[1]), t.offsetY = parseInt(i[2])
                },
                orig: t => {
                  t.originalWidth = parseInt(i[1]), t.originalHeight = parseInt(i[2])
                },
                offsets: t => {
                  t.offsetX = parseInt(i[1]), t.offsetY = parseInt(i[2]), t.originalWidth = parseInt(i[3]), t.originalHeight = parseInt(i[4])
                },
                rotate: t => {
                  let e = i[1];
                  "true" == e ? t.degrees = 90 : "false" != e && (t.degrees = parseInt(e))
                },
                index: t => {
                  t.index = parseInt(i[1])
                }
              };
              let r = e.readLine();
              for (; r && 0 == r.trim().length;) r = e.readLine();
              for (; r && 0 != r.trim().length && 0 != e.readEntry(i, r);) r = e.readLine();
              let a = null,
                o = null,
                h = null;
              for (; null !== r;)
                if (0 == r.trim().length) a = null, r = e.readLine();
                else if (a) {
                let t = new zt(a, r);
                for (;;) {
                  let s = e.readEntry(i, r = e.readLine());
                  if (0 == s) break;
                  let a = n[i[0]];
                  if (a) a(t);
                  else {
                    o || (o = []), h || (h = []), o.push(i[0]);
                    let t = [];
                    for (let e = 0; e < s; e++) t.push(parseInt(i[e + 1]));
                    h.push(t)
                  }
                }
                0 == t.originalWidth && 0 == t.originalHeight && (t.originalWidth = t.width, t.originalHeight = t.height), o && o.length > 0 && h && h.length > 0 && (t.names = o, t.values = h, o = null, h = null), t.u = t.x / a.width, t.v = t.y / a.height, 90 == t.degrees ? (t.u2 = (t.x + t.height) / a.width, t.v2 = (t.y + t.width) / a.height) : (t.u2 = (t.x + t.width) / a.width, t.v2 = (t.y + t.height) / a.height), this.regions.push(t)
              } else {
                for (a = new Vt(r.trim()); 0 != e.readEntry(i, r = e.readLine());) {
                  let t = s[i[0]];
                  t && t(a)
                }
                this.pages.push(a)
              }
            }
            findRegion(t) {
              for (let e = 0; e < this.regions.length; e++)
                if (this.regions[e].name == t) return this.regions[e];
              return null
            }
            setTextures(t, e = "") {
              for (let i of this.pages) i.setTexture(t.get(e + i.name))
            }
            dispose() {
              for (let t = 0; t < this.pages.length; t++) this.pages[t].texture?.dispose()
            }
          },
          Nt = class {
            lines;
            index = 0;
            constructor(t) {
              this.lines = t.split(/\r\n|\r|\n/)
            }
            readLine() {
              return this.index >= this.lines.length ? null : this.lines[this.index++]
            }
            readEntry(t, e) {
              if (!e || 0 == (e = e.trim()).length) return 0;
              let i = e.indexOf(":");
              if (-1 == i) return 0;
              t[0] = e.substr(0, i).trim();
              for (let s = 1, n = i + 1;; s++) {
                let i = e.indexOf(",", n);
                if (-1 == i) return t[s] = e.substr(n).trim(), s;
                if (t[s] = e.substr(n, i - n).trim(), n = i + 1, 4 == s) return 4
              }
            }
          },
          Vt = class {
            name;
            minFilter = 9728;
            magFilter = 9728;
            uWrap = 33071;
            vWrap = 33071;
            texture = null;
            width = 0;
            height = 0;
            pma = !1;
            regions = new Array;
            constructor(t) {
              this.name = t
            }
            setTexture(t) {
              this.texture = t, t.setFilters(this.minFilter, this.magFilter), t.setWraps(this.uWrap, this.vWrap);
              for (let e of this.regions) e.texture = t
            }
          },
          zt = class extends Dt {
            page;
            name;
            x = 0;
            y = 0;
            offsetX = 0;
            offsetY = 0;
            originalWidth = 0;
            originalHeight = 0;
            index = 0;
            degrees = 0;
            names = null;
            values = null;
            constructor(t, e) {
              super(), this.page = t, this.name = e, t.regions.push(this)
            }
          },
          Ut = class t extends T {
            region = null;
            path;
            regionUVs = [];
            uvs = [];
            triangles = [];
            color = new u(1, 1, 1, 1);
            width = 0;
            height = 0;
            hullLength = 0;
            edges = [];
            parentMesh = null;
            sequence = null;
            tempColor = new u(0, 0, 0, 0);
            constructor(t, e) {
              super(t), this.path = e
            }
            updateRegion() {
              if (!this.region) throw new Error("Region not set.");
              let t = this.regionUVs;
              (!this.uvs || this.uvs.length != t.length) && (this.uvs = y.newFloatArray(t.length));
              let e = this.uvs,
                i = this.uvs.length,
                s = this.region.u,
                n = this.region.v,
                r = 0,
                a = 0;
              if (this.region instanceof zt) {
                let o = this.region,
                  h = o.page,
                  l = h.width,
                  c = h.height;
                switch (o.degrees) {
                  case 90:
                    s -= (o.originalHeight - o.offsetY - o.height) / l, n -= (o.originalWidth - o.offsetX - o.width) / c, r = o.originalHeight / l, a = o.originalWidth / c;
                    for (let o = 0; o < i; o += 2) e[o] = s + t[o + 1] * r, e[o + 1] = n + (1 - t[o]) * a;
                    return;
                  case 180:
                    s -= (o.originalWidth - o.offsetX - o.width) / l, n -= o.offsetY / c, r = o.originalWidth / l, a = o.originalHeight / c;
                    for (let o = 0; o < i; o += 2) e[o] = s + (1 - t[o]) * r, e[o + 1] = n + (1 - t[o + 1]) * a;
                    return;
                  case 270:
                    s -= o.offsetY / l, n -= o.offsetX / c, r = o.originalHeight / l, a = o.originalWidth / c;
                    for (let o = 0; o < i; o += 2) e[o] = s + (1 - t[o + 1]) * r, e[o + 1] = n + t[o] * a;
                    return
                }
                s -= o.offsetX / l, n -= (o.originalHeight - o.offsetY - o.height) / c, r = o.originalWidth / l, a = o.originalHeight / c
              } else this.region ? (r = this.region.u2 - s, a = this.region.v2 - n) : (s = n = 0, r = a = 1);
              for (let o = 0; o < i; o += 2) e[o] = s + t[o] * r, e[o + 1] = n + t[o + 1] * a
            }
            getParentMesh() {
              return this.parentMesh
            }
            setParentMesh(t) {
              this.parentMesh = t, t && (this.bones = t.bones, this.vertices = t.vertices, this.worldVerticesLength = t.worldVerticesLength, this.regionUVs = t.regionUVs, this.triangles = t.triangles, this.hullLength = t.hullLength, this.worldVerticesLength = t.worldVerticesLength)
            }
            copy() {
              if (this.parentMesh) return this.newLinkedMesh();
              let e = new t(this.name, this.path);
              return e.region = this.region, e.color.setFromColor(this.color), this.copyTo(e), e.regionUVs = new Array(this.regionUVs.length), y.arrayCopy(this.regionUVs, 0, e.regionUVs, 0, this.regionUVs.length), e.uvs = this.uvs instanceof Float32Array ? y.newFloatArray(this.uvs.length) : new Array(this.uvs.length), y.arrayCopy(this.uvs, 0, e.uvs, 0, this.uvs.length), e.triangles = new Array(this.triangles.length), y.arrayCopy(this.triangles, 0, e.triangles, 0, this.triangles.length), e.hullLength = this.hullLength, e.sequence = null != this.sequence ? this.sequence.copy() : null, this.edges && (e.edges = new Array(this.edges.length), y.arrayCopy(this.edges, 0, e.edges, 0, this.edges.length)), e.width = this.width, e.height = this.height, e
            }
            computeWorldVertices(t, e, i, s, n, r) {
              null != this.sequence && this.sequence.apply(t, this), super.computeWorldVertices(t, e, i, s, n, r)
            }
            newLinkedMesh() {
              let e = new t(this.name, this.path);
              return e.region = this.region, e.color.setFromColor(this.color), e.timelineAttachment = this.timelineAttachment, e.setParentMesh(this.parentMesh ? this.parentMesh : this), null != e.region && e.updateRegion(), e
            }
          },
          Ht = class t extends T {
            lengths = [];
            closed = !1;
            constantSpeed = !1;
            color = new u(1, 1, 1, 1);
            constructor(t) {
              super(t)
            }
            copy() {
              let e = new t(this.name);
              return this.copyTo(e), e.lengths = new Array(this.lengths.length), y.arrayCopy(this.lengths, 0, e.lengths, 0, this.lengths.length), e.closed = closed, e.constantSpeed = this.constantSpeed, e.color.setFromColor(this.color), e
            }
          },
          Wt = class t extends T {
            x = 0;
            y = 0;
            rotation = 0;
            color = new u(.38, .94, 0, 1);
            constructor(t) {
              super(t)
            }
            computeWorldPosition(t, e) {
              return e.x = this.x * t.a + this.y * t.b + t.worldX, e.y = this.x * t.c + this.y * t.d + t.worldY, e
            }
            computeWorldRotation(t) {
              const e = this.rotation * p.degRad,
                i = Math.cos(e),
                s = Math.sin(e),
                n = i * t.a + s * t.b,
                r = i * t.c + s * t.d;
              return p.atan2Deg(r, n)
            }
            copy() {
              let e = new t(this.name);
              return e.x = this.x, e.y = this.y, e.rotation = this.rotation, e.color.setFromColor(this.color), e
            }
          },
          Yt = class t extends S {
            x = 0;
            y = 0;
            scaleX = 1;
            scaleY = 1;
            rotation = 0;
            width = 0;
            height = 0;
            color = new u(1, 1, 1, 1);
            path;
            region = null;
            sequence = null;
            offset = y.newFloatArray(8);
            uvs = y.newFloatArray(8);
            tempColor = new u(1, 1, 1, 1);
            constructor(t, e) {
              super(t), this.path = e
            }
            updateRegion() {
              if (!this.region) throw new Error("Region not set.");
              let t = this.region,
                e = this.uvs;
              if (null == t) return e[0] = 0, e[1] = 0, e[2] = 0, e[3] = 1, e[4] = 1, e[5] = 1, e[6] = 1, void(e[7] = 0);
              let i = this.width / this.region.originalWidth * this.scaleX,
                s = this.height / this.region.originalHeight * this.scaleY,
                n = -this.width / 2 * this.scaleX + this.region.offsetX * i,
                r = -this.height / 2 * this.scaleY + this.region.offsetY * s,
                a = n + this.region.width * i,
                o = r + this.region.height * s,
                h = this.rotation * p.degRad,
                l = Math.cos(h),
                c = Math.sin(h),
                d = this.x,
                u = this.y,
                g = n * l + d,
                m = n * c,
                f = r * l + u,
                y = r * c,
                _ = a * l + d,
                b = a * c,
                v = o * l + u,
                x = o * c,
                w = this.offset;
              w[0] = g - y, w[1] = f + m, w[2] = g - x, w[3] = v + m, w[4] = _ - x, w[5] = v + b, w[6] = _ - y, w[7] = f + b, 90 == t.degrees ? (e[0] = t.u2, e[1] = t.v2, e[2] = t.u, e[3] = t.v2, e[4] = t.u, e[5] = t.v, e[6] = t.u2, e[7] = t.v) : (e[0] = t.u, e[1] = t.v2, e[2] = t.u, e[3] = t.v, e[4] = t.u2, e[5] = t.v, e[6] = t.u2, e[7] = t.v2)
            }
            computeWorldVertices(t, e, i, s) {
              null != this.sequence && this.sequence.apply(t, this);
              let n = t.bone,
                r = this.offset,
                a = n.worldX,
                o = n.worldY,
                h = n.a,
                l = n.b,
                c = n.c,
                d = n.d,
                u = 0,
                p = 0;
              u = r[0], p = r[1], e[i] = u * h + p * l + a, e[i + 1] = u * c + p * d + o, i += s, u = r[2], p = r[3], e[i] = u * h + p * l + a, e[i + 1] = u * c + p * d + o, i += s, u = r[4], p = r[5], e[i] = u * h + p * l + a, e[i + 1] = u * c + p * d + o, i += s, u = r[6], p = r[7], e[i] = u * h + p * l + a, e[i + 1] = u * c + p * d + o
            }
            copy() {
              let e = new t(this.name, this.path);
              return e.region = this.region, e.x = this.x, e.y = this.y, e.scaleX = this.scaleX, e.scaleY = this.scaleY, e.rotation = this.rotation, e.width = this.width, e.height = this.height, y.arrayCopy(this.uvs, 0, e.uvs, 0, 8), y.arrayCopy(this.offset, 0, e.offset, 0, 8), e.color.setFromColor(this.color), e.sequence = null != this.sequence ? this.sequence.copy() : null, e
            }
            static X1 = 0;
            static Y1 = 1;
            static C1R = 2;
            static C1G = 3;
            static C1B = 4;
            static C1A = 5;
            static U1 = 6;
            static V1 = 7;
            static X2 = 8;
            static Y2 = 9;
            static C2R = 10;
            static C2G = 11;
            static C2B = 12;
            static C2A = 13;
            static U2 = 14;
            static V2 = 15;
            static X3 = 16;
            static Y3 = 17;
            static C3R = 18;
            static C3G = 19;
            static C3B = 20;
            static C3A = 21;
            static U3 = 22;
            static V3 = 23;
            static X4 = 24;
            static Y4 = 25;
            static C4R = 26;
            static C4G = 27;
            static C4B = 28;
            static C4A = 29;
            static U4 = 30;
            static V4 = 31
          },
          Gt = class {
            atlas;
            constructor(t) {
              this.atlas = t
            }
            loadSequence(t, e, i) {
              let s = i.regions;
              for (let n = 0, r = s.length; n < r; n++) {
                let r = i.getPath(e, n),
                  a = this.atlas.findRegion(r);
                if (null == a) throw new Error("Region not found in atlas: " + r + " (sequence: " + t + ")");
                s[n] = a
              }
            }
            newRegionAttachment(t, e, i, s) {
              let n = new Yt(e, i);
              if (null != s) this.loadSequence(e, i, s);
              else {
                let t = this.atlas.findRegion(i);
                if (!t) throw new Error("Region not found in atlas: " + i + " (region attachment: " + e + ")");
                n.region = t
              }
              return n
            }
            newMeshAttachment(t, e, i, s) {
              let n = new Ut(e, i);
              if (null != s) this.loadSequence(e, i, s);
              else {
                let t = this.atlas.findRegion(i);
                if (!t) throw new Error("Region not found in atlas: " + i + " (mesh attachment: " + e + ")");
                n.region = t
              }
              return n
            }
            newBoundingBoxAttachment(t, e) {
              return new Et(e)
            }
            newPathAttachment(t, e) {
              return new Ht(e)
            }
            newPointAttachment(t, e) {
              return new Wt(e)
            }
            newClippingAttachment(t, e) {
              return new Ot(e)
            }
          },
          Xt = class {
            index = 0;
            name;
            parent = null;
            length = 0;
            x = 0;
            y = 0;
            rotation = 0;
            scaleX = 1;
            scaleY = 1;
            shearX = 0;
            shearY = 0;
            inherit = 0;
            skinRequired = !1;
            color = new u;
            icon;
            visible = !1;
            constructor(t, e, i) {
              if (t < 0) throw new Error("index must be >= 0.");
              if (!e) throw new Error("name cannot be null.");
              this.index = t, this.name = e, this.parent = i
            }
          },
          jt = (t => (t[t.Normal = 0] = "Normal", t[t.OnlyTranslation = 1] = "OnlyTranslation", t[t.NoRotationOrReflection = 2] = "NoRotationOrReflection", t[t.NoScale = 3] = "NoScale", t[t.NoScaleOrReflection = 4] = "NoScaleOrReflection", t))(jt || {}),
          $t = class {
            data;
            skeleton;
            parent = null;
            children = new Array;
            x = 0;
            y = 0;
            rotation = 0;
            scaleX = 0;
            scaleY = 0;
            shearX = 0;
            shearY = 0;
            ax = 0;
            ay = 0;
            arotation = 0;
            ascaleX = 0;
            ascaleY = 0;
            ashearX = 0;
            ashearY = 0;
            a = 0;
            b = 0;
            c = 0;
            d = 0;
            worldY = 0;
            worldX = 0;
            inherit = 0;
            sorted = !1;
            active = !1;
            constructor(t, e, i) {
              if (!t) throw new Error("data cannot be null.");
              if (!e) throw new Error("skeleton cannot be null.");
              this.data = t, this.skeleton = e, this.parent = i, this.setToSetupPose()
            }
            isActive() {
              return this.active
            }
            update(t) {
              this.updateWorldTransformWith(this.ax, this.ay, this.arotation, this.ascaleX, this.ascaleY, this.ashearX, this.ashearY)
            }
            updateWorldTransform() {
              this.updateWorldTransformWith(this.x, this.y, this.rotation, this.scaleX, this.scaleY, this.shearX, this.shearY)
            }
            updateWorldTransformWith(t, e, i, s, n, r, a) {
              this.ax = t, this.ay = e, this.arotation = i, this.ascaleX = s, this.ascaleY = n, this.ashearX = r, this.ashearY = a;
              let o = this.parent;
              if (!o) {
                let o = this.skeleton;
                const h = o.scaleX,
                  l = o.scaleY,
                  c = (i + r) * p.degRad,
                  d = (i + 90 + a) * p.degRad;
                return this.a = Math.cos(c) * s * h, this.b = Math.cos(d) * n * h, this.c = Math.sin(c) * s * l, this.d = Math.sin(d) * n * l, this.worldX = t * h + o.x, void(this.worldY = e * l + o.y)
              }
              let h = o.a,
                l = o.b,
                c = o.c,
                d = o.d;
              switch (this.worldX = h * t + l * e + o.worldX, this.worldY = c * t + d * e + o.worldY, this.inherit) {
                case 0: {
                  const t = (i + r) * p.degRad,
                    e = (i + 90 + a) * p.degRad,
                    o = Math.cos(t) * s,
                    u = Math.cos(e) * n,
                    g = Math.sin(t) * s,
                    m = Math.sin(e) * n;
                  return this.a = h * o + l * g, this.b = h * u + l * m, this.c = c * o + d * g, void(this.d = c * u + d * m)
                }
                case 1: {
                  const t = (i + r) * p.degRad,
                    e = (i + 90 + a) * p.degRad;
                  this.a = Math.cos(t) * s, this.b = Math.cos(e) * n, this.c = Math.sin(t) * s, this.d = Math.sin(e) * n;
                  break
                }
                case 2: {
                  let t = 1 / this.skeleton.scaleX,
                    e = 1 / this.skeleton.scaleY;
                  h *= t, c *= e;
                  let o = h * h + c * c,
                    u = 0;
                  o > 1e-4 ? (o = Math.abs(h * d * e - l * t * c) / o, l = c * o, d = h * o, u = Math.atan2(c, h) * p.radDeg) : (h = 0, c = 0, u = 90 - Math.atan2(d, l) * p.radDeg);
                  const g = (i + r - u) * p.degRad,
                    m = (i + a - u + 90) * p.degRad,
                    f = Math.cos(g) * s,
                    y = Math.cos(m) * n,
                    _ = Math.sin(g) * s,
                    b = Math.sin(m) * n;
                  this.a = h * f - l * _, this.b = h * y - l * b, this.c = c * f + d * _, this.d = c * y + d * b;
                  break
                }
                case 3:
                case 4: {
                  i *= p.degRad;
                  const t = Math.cos(i),
                    e = Math.sin(i);
                  let o = (h * t + l * e) / this.skeleton.scaleX,
                    u = (c * t + d * e) / this.skeleton.scaleY,
                    g = Math.sqrt(o * o + u * u);
                  g > 1e-5 && (g = 1 / g), o *= g, u *= g, g = Math.sqrt(o * o + u * u), 3 == this.inherit && h * d - l * c < 0 != (this.skeleton.scaleX < 0 != this.skeleton.scaleY < 0) && (g = -g), i = Math.PI / 2 + Math.atan2(u, o);
                  const m = Math.cos(i) * g,
                    f = Math.sin(i) * g;
                  r *= p.degRad, a = (90 + a) * p.degRad;
                  const y = Math.cos(r) * s,
                    _ = Math.cos(a) * n,
                    b = Math.sin(r) * s,
                    v = Math.sin(a) * n;
                  this.a = o * y + m * b, this.b = o * _ + m * v, this.c = u * y + f * b, this.d = u * _ + f * v;
                  break
                }
              }
              this.a *= this.skeleton.scaleX, this.b *= this.skeleton.scaleX, this.c *= this.skeleton.scaleY, this.d *= this.skeleton.scaleY
            }
            setToSetupPose() {
              let t = this.data;
              this.x = t.x, this.y = t.y, this.rotation = t.rotation, this.scaleX = t.scaleX, this.scaleY = t.scaleY, this.shearX = t.shearX, this.shearY = t.shearY, this.inherit = t.inherit
            }
            updateAppliedTransform() {
              let t = this.parent;
              if (!t) return this.ax = this.worldX - this.skeleton.x, this.ay = this.worldY - this.skeleton.y, this.arotation = Math.atan2(this.c, this.a) * p.radDeg, this.ascaleX = Math.sqrt(this.a * this.a + this.c * this.c), this.ascaleY = Math.sqrt(this.b * this.b + this.d * this.d), this.ashearX = 0, void(this.ashearY = Math.atan2(this.a * this.b + this.c * this.d, this.a * this.d - this.b * this.c) * p.radDeg);
              let e, i, s, n, r = t.a,
                a = t.b,
                o = t.c,
                h = t.d,
                l = 1 / (r * h - a * o),
                c = h * l,
                d = a * l,
                u = o * l,
                g = r * l,
                m = this.worldX - t.worldX,
                f = this.worldY - t.worldY;
              if (this.ax = m * c - f * d, this.ay = f * g - m * u, 1 == this.inherit) e = this.a, i = this.b, s = this.c, n = this.d;
              else {
                switch (this.inherit) {
                  case 2: {
                    let t = Math.abs(r * h - a * o) / (r * r + o * o);
                    a = -o * this.skeleton.scaleX * t / this.skeleton.scaleY, h = r * this.skeleton.scaleY * t / this.skeleton.scaleX, l = 1 / (r * h - a * o), c = h * l, d = a * l;
                    break
                  }
                  case 3:
                  case 4:
                    let t = p.cosDeg(this.rotation),
                      e = p.sinDeg(this.rotation);
                    r = (r * t + a * e) / this.skeleton.scaleX, o = (o * t + h * e) / this.skeleton.scaleY;
                    let i = Math.sqrt(r * r + o * o);
                    i > 1e-5 && (i = 1 / i), r *= i, o *= i, i = Math.sqrt(r * r + o * o), 3 == this.inherit && l < 0 != (this.skeleton.scaleX < 0 != this.skeleton.scaleY < 0) && (i = -i);
                    let s = p.PI / 2 + Math.atan2(o, r);
                    a = Math.cos(s) * i, h = Math.sin(s) * i, l = 1 / (r * h - a * o), c = h * l, d = a * l, u = o * l, g = r * l
                }
                e = c * this.a - d * this.c, i = c * this.b - d * this.d, s = g * this.c - u * this.a, n = g * this.d - u * this.b
              }
              if (this.ashearX = 0, this.ascaleX = Math.sqrt(e * e + s * s), this.ascaleX > 1e-4) {
                let t = e * n - i * s;
                this.ascaleY = t / this.ascaleX, this.ashearY = -Math.atan2(e * i + s * n, t) * p.radDeg, this.arotation = Math.atan2(s, e) * p.radDeg
              } else this.ascaleX = 0, this.ascaleY = Math.sqrt(i * i + n * n), this.ashearY = 0, this.arotation = 90 - Math.atan2(n, i) * p.radDeg
            }
            getWorldRotationX() {
              return Math.atan2(this.c, this.a) * p.radDeg
            }
            getWorldRotationY() {
              return Math.atan2(this.d, this.b) * p.radDeg
            }
            getWorldScaleX() {
              return Math.sqrt(this.a * this.a + this.c * this.c)
            }
            getWorldScaleY() {
              return Math.sqrt(this.b * this.b + this.d * this.d)
            }
            worldToLocal(t) {
              let e = 1 / (this.a * this.d - this.b * this.c),
                i = t.x - this.worldX,
                s = t.y - this.worldY;
              return t.x = i * this.d * e - s * this.b * e, t.y = s * this.a * e - i * this.c * e, t
            }
            localToWorld(t) {
              let e = t.x,
                i = t.y;
              return t.x = e * this.a + i * this.b + this.worldX, t.y = e * this.c + i * this.d + this.worldY, t
            }
            worldToParent(t) {
              if (null == t) throw new Error("world cannot be null.");
              return null == this.parent ? t : this.parent.worldToLocal(t)
            }
            parentToWorld(t) {
              if (null == t) throw new Error("world cannot be null.");
              return null == this.parent ? t : this.parent.localToWorld(t)
            }
            worldToLocalRotation(t) {
              let e = p.sinDeg(t),
                i = p.cosDeg(t);
              return Math.atan2(this.a * e - this.c * i, this.d * i - this.b * e) * p.radDeg + this.rotation - this.shearX
            }
            localToWorldRotation(t) {
              t -= this.rotation - this.shearX;
              let e = p.sinDeg(t),
                i = p.cosDeg(t);
              return Math.atan2(i * this.c + e * this.d, i * this.a + e * this.b) * p.radDeg
            }
            rotateWorld(t) {
              t *= p.degRad;
              const e = Math.sin(t),
                i = Math.cos(t),
                s = this.a,
                n = this.b;
              this.a = i * s - e * this.c, this.b = i * n - e * this.d, this.c = e * s + i * this.c, this.d = e * n + i * this.d
            }
          },
          Kt = class {
            constructor(t, e, i) {
              this.name = t, this.order = e, this.skinRequired = i
            }
          },
          qt = class {
            pathPrefix = "";
            textureLoader;
            downloader;
            cache;
            errors = {};
            toLoad = 0;
            loaded = 0;
            constructor(t, e = "", i = new Qt, s = new Zt) {
              this.textureLoader = t, this.pathPrefix = e, this.downloader = i, this.cache = s
            }
            start(t) {
              return this.toLoad++, this.pathPrefix + t
            }
            success(t, e, i) {
              this.toLoad--, this.loaded++, this.cache.assets[e] = i, this.cache.assetsRefCount[e] = (this.cache.assetsRefCount[e] || 0) + 1, t && t(e, i)
            }
            error(t, e, i) {
              this.toLoad--, this.loaded++, this.errors[e] = i, t && t(e, i)
            }
            loadAll() {
              return new Promise((t, e) => {
                let i = () => {
                  this.isLoadingComplete() ? this.hasErrors() ? e(this.errors) : t(this) : requestAnimationFrame(i)
                };
                requestAnimationFrame(i)
              })
            }
            setRawDataURI(t, e) {
              this.downloader.rawDataUris[this.pathPrefix + t] = e
            }
            loadBinary(t, e = () => {}, i = () => {}) {
              t = this.start(t), !this.reuseAssets(t, e, i) && (this.cache.assetsLoaded[t] = new Promise((s, n) => {
                this.downloader.downloadBinary(t, i => {
                  this.success(e, t, i), s(i)
                }, (e, s) => {
                  const r = `Couldn't load binary ${t}: status ${e}, ${s}`;
                  this.error(i, t, r), n(r)
                })
              }))
            }
            loadText(t, e = () => {}, i = () => {}) {
              t = this.start(t), this.downloader.downloadText(t, i => {
                this.success(e, t, i)
              }, (e, s) => {
                this.error(i, t, `Couldn't load text ${t}: status ${e}, ${s}`)
              })
            }
            loadJson(t, e = () => {}, i = () => {}) {
              t = this.start(t), !this.reuseAssets(t, e, i) && (this.cache.assetsLoaded[t] = new Promise((s, n) => {
                this.downloader.downloadJson(t, i => {
                  this.success(e, t, i), s(i)
                }, (e, s) => {
                  const r = `Couldn't load JSON ${t}: status ${e}, ${s}`;
                  this.error(i, t, r), n(r)
                })
              }))
            }
            reuseAssets(t, e = () => {}, i = () => {}) {
              const s = this.cache.assetsLoaded[t],
                n = void 0 !== s;
              return n && (this.cache.assetsLoaded[t] = s.then(i => (i = i instanceof Image || i instanceof ImageBitmap ? this.textureLoader(i) : i, this.success(e, t, i), i)).catch(e => this.error(i, t, e))), n
            }
            loadTexture(t, e = () => {}, i = () => {}) {
              t = this.start(t), !this.reuseAssets(t, e, i) && (this.cache.assetsLoaded[t] = new Promise((s, n) => {
                if (typeof window < "u" && typeof navigator < "u" && window.document) {
                  let r = new Image;
                  r.crossOrigin = "anonymous", r.onload = () => {
                    const i = this.textureLoader(r);
                    this.success(e, t, i), s(i)
                  }, r.onerror = () => {
                    const e = `Couldn't load image: ${t}`;
                    this.error(i, t, e), n(e)
                  }, this.downloader.rawDataUris[t] && (t = this.downloader.rawDataUris[t]), r.src = t
                } else fetch(t, {
                  mode: "cors"
                }).then(e => {
                  if (e.ok) return e.blob();
                  const s = `Couldn't load image: ${t}`;
                  this.error(i, t, `Couldn't load image: ${t}`), n(s)
                }).then(t => t ? createImageBitmap(t, {
                  premultiplyAlpha: "none",
                  colorSpaceConversion: "none"
                }) : null).then(i => {
                  if (i) {
                    const n = this.textureLoader(i);
                    this.success(e, t, n), s(n)
                  }
                })
              }))
            }
            loadTextureAtlas(t, e = () => {}, i = () => {}, s) {
              let n = t.lastIndexOf("/"),
                r = n >= 0 ? t.substring(0, n + 1) : "";
              t = this.start(t), !this.reuseAssets(t, e, i) && (this.cache.assetsLoaded[t] = new Promise((n, a) => {
                this.downloader.downloadText(t, o => {
                  try {
                    let h = new Ft(o),
                      l = h.pages.length,
                      c = !1;
                    for (let o of h.pages) this.loadTexture(s ? s[o.name] : r + o.name, (i, s) => {
                      c || (o.setTexture(s), 0 == --l && (this.success(e, t, h), n(h)))
                    }, (e, s) => {
                      if (!c) {
                        const s = `Couldn't load texture ${t} page image: ${e}`;
                        this.error(i, t, s), a(s)
                      }
                      c = !0
                    })
                  } catch (e) {
                    const s = `Couldn't parse texture atlas ${t}: ${e.message}`;
                    this.error(i, t, s), a(s)
                  }
                }, (e, s) => {
                  const n = `Couldn't load texture atlas ${t}: status ${e}, ${s}`;
                  this.error(i, t, n), a(n)
                })
              }))
            }
            loadTextureAtlasButNoTextures(t, e = () => {}, i = () => {}, s) {
              t = this.start(t), !this.reuseAssets(t, e, i) && (this.cache.assetsLoaded[t] = new Promise((s, n) => {
                this.downloader.downloadText(t, r => {
                  try {
                    const i = new Ft(r);
                    this.success(e, t, i), s(i)
                  } catch (e) {
                    const s = `Couldn't parse texture atlas ${t}: ${e.message}`;
                    this.error(i, t, s), n(s)
                  }
                }, (e, s) => {
                  const r = `Couldn't load texture atlas ${t}: status ${e}, ${s}`;
                  this.error(i, t, r), n(r)
                })
              }))
            }
            async loadBinaryAsync(t) {
              return new Promise((e, i) => {
                this.loadBinary(t, (t, i) => e(i), (t, e) => i(e))
              })
            }
            async loadJsonAsync(t) {
              return new Promise((e, i) => {
                this.loadJson(t, (t, i) => e(i), (t, e) => i(e))
              })
            }
            async loadTextureAsync(t) {
              return new Promise((e, i) => {
                this.loadTexture(t, (t, i) => e(i), (t, e) => i(e))
              })
            }
            async loadTextureAtlasAsync(t) {
              return new Promise((e, i) => {
                this.loadTextureAtlas(t, (t, i) => e(i), (t, e) => i(e))
              })
            }
            async loadTextureAtlasButNoTexturesAsync(t) {
              return new Promise((e, i) => {
                this.loadTextureAtlasButNoTextures(t, (t, i) => e(i), (t, e) => i(e))
              })
            }
            setCache(t) {
              this.cache = t
            }
            get(t) {
              return this.cache.assets[this.pathPrefix + t]
            }
            require(t) {
              t = this.pathPrefix + t;
              let e = this.cache.assets[t];
              if (e) return e;
              let i = this.errors[t];
              throw Error("Asset not found: " + t + (i ? "\n" + i : ""))
            }
            remove(t) {
              t = this.pathPrefix + t;
              let e = this.cache.assets[t];
              return e.dispose && e.dispose(), delete this.cache.assets[t], delete this.cache.assetsRefCount[t], delete this.cache.assetsLoaded[t], e
            }
            removeAll() {
              for (let t in this.cache.assets) {
                let e = this.cache.assets[t];
                e.dispose && e.dispose()
              }
              this.cache.assets = {}, this.cache.assetsLoaded = {}, this.cache.assetsRefCount = {}
            }
            isLoadingComplete() {
              return 0 == this.toLoad
            }
            getToLoad() {
              return this.toLoad
            }
            getLoaded() {
              return this.loaded
            }
            dispose() {
              this.removeAll()
            }
            disposeAsset(t) {
              0 === --this.cache.assetsRefCount[t] && this.remove(t)
            }
            hasErrors() {
              return Object.keys(this.errors).length > 0
            }
            getErrors() {
              return this.errors
            }
          },
          Zt = class t {
            assets = {};
            assetsRefCount = {};
            assetsLoaded = {};
            static AVAILABLE_CACHES = new Map;
            static getCache(e) {
              const i = t.AVAILABLE_CACHES.get(e);
              if (i) return i;
              const s = new t;
              return t.AVAILABLE_CACHES.set(e, s), s
            }
            async addAsset(t, e) {
              this.assetsLoaded[t] = Promise.resolve(e), this.assets[t] = await e
            }
          },
          Qt = class {
            callbacks = {};
            rawDataUris = {};
            dataUriToString(t) {
              if (!t.startsWith("data:")) throw new Error("Not a data URI.");
              let e = t.indexOf("base64,");
              return -1 != e ? (e += 7, atob(t.substr(e))) : t.substr(t.indexOf(",") + 1)
            }
            base64ToUint8Array(t) {
              for (var e = window.atob(t), i = e.length, s = new Uint8Array(i), n = 0; n < i; n++) s[n] = e.charCodeAt(n);
              return s
            }
            dataUriToUint8Array(t) {
              if (!t.startsWith("data:")) throw new Error("Not a data URI.");
              let e = t.indexOf("base64,");
              if (-1 == e) throw new Error("Not a binary data URI.");
              return e += 7, this.base64ToUint8Array(t.substr(e))
            }
            downloadText(t, e, i) {
              if (this.start(t, e, i)) return;
              const s = this.rawDataUris[t];
              if (s && !s.includes(".")) {
                try {
                  this.finish(t, 200, this.dataUriToString(s))
                } catch (e) {
                  this.finish(t, 400, JSON.stringify(e))
                }
                return
              }
              let n = new XMLHttpRequest;
              n.overrideMimeType("text/html"), n.open("GET", s || t, !0);
              let r = () => {
                this.finish(t, n.status, n.responseText)
              };
              n.onload = r, n.onerror = r, n.send()
            }
            downloadJson(t, e, i) {
              this.downloadText(t, t => {
                e(JSON.parse(t))
              }, i)
            }
            downloadBinary(t, e, i) {
              if (this.start(t, e, i)) return;
              const s = this.rawDataUris[t];
              if (s && !s.includes(".")) {
                try {
                  this.finish(t, 200, this.dataUriToUint8Array(s))
                } catch (e) {
                  this.finish(t, 400, JSON.stringify(e))
                }
                return
              }
              let n = new XMLHttpRequest;
              n.open("GET", s || t, !0), n.responseType = "arraybuffer";
              let r = () => {
                this.finish(t, n.status, n.response)
              };
              n.onload = () => {
                200 == n.status || 0 == n.status ? this.finish(t, 200, new Uint8Array(n.response)) : r()
              }, n.onerror = r, n.send()
            }
            start(t, e, i) {
              let s = this.callbacks[t];
              try {
                if (s) return !0;
                this.callbacks[t] = s = []
              } finally {
                s.push(e, i)
              }
            }
            finish(t, e, i) {
              let s = this.callbacks[t];
              delete this.callbacks[t];
              let n = 200 == e || 0 == e ? [i] : [e, i];
              for (let t = n.length - 1, e = s.length; t < e; t += 2) s[t].apply(null, n)
            }
          },
          Jt = class {
            data;
            intValue = 0;
            floatValue = 0;
            stringValue = null;
            time = 0;
            volume = 0;
            balance = 0;
            constructor(t, e) {
              if (!e) throw new Error("data cannot be null.");
              this.time = t, this.data = e
            }
          },
          te = class {
            name;
            intValue = 0;
            floatValue = 0;
            stringValue = null;
            audioPath = null;
            volume = 0;
            balance = 0;
            constructor(t) {
              this.name = t
            }
          },
          ee = class {
            data;
            bones;
            target;
            bendDirection = 0;
            compress = !1;
            stretch = !1;
            mix = 1;
            softness = 0;
            active = !1;
            constructor(t, e) {
              if (!t) throw new Error("data cannot be null.");
              if (!e) throw new Error("skeleton cannot be null.");
              this.data = t, this.bones = new Array;
              for (let i = 0; i < t.bones.length; i++) {
                let s = e.findBone(t.bones[i].name);
                if (!s) throw new Error(`Couldn't find bone ${t.bones[i].name}`);
                this.bones.push(s)
              }
              let i = e.findBone(t.target.name);
              if (!i) throw new Error(`Couldn't find bone ${t.target.name}`);
              this.target = i, this.mix = t.mix, this.softness = t.softness, this.bendDirection = t.bendDirection, this.compress = t.compress, this.stretch = t.stretch
            }
            isActive() {
              return this.active
            }
            setToSetupPose() {
              const t = this.data;
              this.mix = t.mix, this.softness = t.softness, this.bendDirection = t.bendDirection, this.compress = t.compress, this.stretch = t.stretch
            }
            update(t) {
              if (0 == this.mix) return;
              let e = this.target,
                i = this.bones;
              switch (i.length) {
                case 1:
                  this.apply1(i[0], e.worldX, e.worldY, this.compress, this.stretch, this.data.uniform, this.mix);
                  break;
                case 2:
                  this.apply2(i[0], i[1], e.worldX, e.worldY, this.bendDirection, this.stretch, this.data.uniform, this.softness, this.mix)
              }
            }
            apply1(t, e, i, s, n, r, a) {
              let o = t.parent;
              if (!o) throw new Error("IK bone must have parent.");
              let h = o.a,
                l = o.b,
                c = o.c,
                d = o.d,
                u = -t.ashearX - t.arotation,
                g = 0,
                m = 0;
              switch (t.inherit) {
                case 1:
                  g = (e - t.worldX) * p.signum(t.skeleton.scaleX), m = (i - t.worldY) * p.signum(t.skeleton.scaleY);
                  break;
                case 2:
                  let s = Math.abs(h * d - l * c) / Math.max(1e-4, h * h + c * c),
                    n = h / t.skeleton.scaleX,
                    r = c / t.skeleton.scaleY;
                  l = -r * s * t.skeleton.scaleX, d = n * s * t.skeleton.scaleY, u += Math.atan2(r, n) * p.radDeg;
                default:
                  let a = e - o.worldX,
                    f = i - o.worldY,
                    y = h * d - l * c;
                  Math.abs(y) <= 1e-4 ? (g = 0, m = 0) : (g = (a * d - f * l) / y - t.ax, m = (f * h - a * c) / y - t.ay)
              }
              u += Math.atan2(m, g) * p.radDeg, t.ascaleX < 0 && (u += 180), u > 180 ? u -= 360 : u < -180 && (u += 360);
              let f = t.ascaleX,
                y = t.ascaleY;
              if (s || n) {
                switch (t.inherit) {
                  case 3:
                  case 4:
                    g = e - t.worldX, m = i - t.worldY
                }
                const o = t.data.length * f;
                if (o > 1e-4) {
                  const t = g * g + m * m;
                  if (s && t < o * o || n && t > o * o) {
                    const e = (Math.sqrt(t) / o - 1) * a + 1;
                    f *= e, r && (y *= e)
                  }
                }
              }
              t.updateWorldTransformWith(t.ax, t.ay, t.arotation + u * a, f, y, t.ashearX, t.ashearY)
            }
            apply2(t, e, i, s, n, r, a, o, h) {
              if (0 != t.inherit || 0 != e.inherit) return;
              let l = t.ax,
                c = t.ay,
                d = t.ascaleX,
                u = t.ascaleY,
                g = d,
                m = u,
                f = e.ascaleX,
                y = 0,
                _ = 0,
                b = 0;
              d < 0 ? (d = -d, y = 180, b = -1) : (y = 0, b = 1), u < 0 && (u = -u, b = -b), f < 0 ? (f = -f, _ = 180) : _ = 0;
              let v = e.ax,
                x = 0,
                w = 0,
                S = 0,
                T = t.a,
                C = t.b,
                k = t.c,
                P = t.d,
                A = Math.abs(d - u) <= 1e-4;
              !A || r ? (x = 0, w = T * v + t.worldX, S = k * v + t.worldY) : (x = e.ay, w = T * v + C * x + t.worldX, S = k * v + P * x + t.worldY);
              let I = t.parent;
              if (!I) throw new Error("IK parent must itself have a parent.");
              T = I.a, C = I.b, k = I.c, P = I.d;
              let E = T * P - C * k,
                O = w - I.worldX,
                M = S - I.worldY;
              E = Math.abs(E) <= 1e-4 ? 0 : 1 / E;
              let B, R, D = (O * P - M * C) * E - l,
                L = (M * T - O * k) * E - c,
                F = Math.sqrt(D * D + L * L),
                N = e.data.length * f;
              if (F < 1e-4) return this.apply1(t, i, s, !1, r, !1, h), void e.updateWorldTransformWith(v, x, 0, e.ascaleX, e.ascaleY, e.ashearX, e.ashearY);
              O = i - I.worldX, M = s - I.worldY;
              let V = (O * P - M * C) * E - l,
                z = (M * T - O * k) * E - c,
                U = V * V + z * z;
              if (0 != o) {
                o *= d * (f + 1) * .5;
                let t = Math.sqrt(U),
                  e = t - F - N * d + o;
                if (e > 0) {
                  let i = Math.min(1, e / (2 * o)) - 1;
                  i = (e - o * (1 - i * i)) / t, V -= i * V, z -= i * z, U = V * V + z * z
                }
              }
              t: if (A) {
                N *= d;
                let t = (U - F * F - N * N) / (2 * F * N);
                t < -1 ? (t = -1, R = Math.PI * n) : t > 1 ? (t = 1, R = 0, r && (T = (Math.sqrt(U) / (F + N) - 1) * h + 1, g *= T, a && (m *= T))) : R = Math.acos(t) * n, T = F + N * t, C = N * Math.sin(R), B = Math.atan2(z * T - V * C, V * T + z * C)
              } else {
                T = d * N, C = u * N;
                let t = T * T,
                  e = C * C,
                  i = Math.atan2(z, V);
                k = e * F * F + t * U - t * e;
                let s = -2 * e * F,
                  r = e - t;
                if (P = s * s - 4 * r * k, P >= 0) {
                  let t = Math.sqrt(P);
                  s < 0 && (t = -t), t = .5 * -(s + t);
                  let e = t / r,
                    a = k / t,
                    o = Math.abs(e) < Math.abs(a) ? e : a;
                  if (e = U - o * o, e >= 0) {
                    M = Math.sqrt(e) * n, B = i - Math.atan2(M, o), R = Math.atan2(M / u, (o - F) / d);
                    break t
                  }
                }
                let a = p.PI,
                  o = F - T,
                  h = o * o,
                  l = 0,
                  c = 0,
                  g = F + T,
                  m = g * g,
                  f = 0;
                k = -T * F / (t - e), k >= -1 && k <= 1 && (k = Math.acos(k), O = T * Math.cos(k) + F, M = C * Math.sin(k), P = O * O + M * M, P < h && (a = k, h = P, o = O, l = M), P > m && (c = k, m = P, g = O, f = M)), U <= .5 * (h + m) ? (B = i - Math.atan2(l * n, o), R = a * n) : (B = i - Math.atan2(f * n, g), R = c * n)
              }
              let H = Math.atan2(x, v) * b,
                W = t.arotation;
              B = (B - H) * p.radDeg + y - W, B > 180 ? B -= 360 : B < -180 && (B += 360), t.updateWorldTransformWith(l, c, W + B * h, g, m, 0, 0), W = e.arotation, R = ((R + H) * p.radDeg - e.ashearX) * b + _ - W, R > 180 ? R -= 360 : R < -180 && (R += 360), e.updateWorldTransformWith(v, x, W + R * h, e.ascaleX, e.ascaleY, e.ashearX, e.ashearY)
            }
          },
          ie = class extends Kt {
            bones = new Array;
            _target = null;
            set target(t) {
              this._target = t
            }
            get target() {
              if (this._target) return this._target;
              throw new Error("BoneData not set.")
            }
            bendDirection = 0;
            compress = !1;
            stretch = !1;
            uniform = !1;
            mix = 0;
            softness = 0;
            constructor(t) {
              super(t, 0, !1)
            }
          },
          se = class extends Kt {
            bones = new Array;
            _target = null;
            set target(t) {
              this._target = t
            }
            get target() {
              if (this._target) return this._target;
              throw new Error("SlotData not set.")
            }
            positionMode = 0;
            spacingMode = 1;
            rotateMode = 1;
            offsetRotation = 0;
            position = 0;
            spacing = 0;
            mixRotate = 0;
            mixX = 0;
            mixY = 0;
            constructor(t) {
              super(t, 0, !1)
            }
          },
          ne = (t => (t[t.Fixed = 0] = "Fixed", t[t.Percent = 1] = "Percent", t))(ne || {}),
          re = (t => (t[t.Length = 0] = "Length", t[t.Fixed = 1] = "Fixed", t[t.Percent = 2] = "Percent", t[t.Proportional = 3] = "Proportional", t))(re || {}),
          ae = (t => (t[t.Tangent = 0] = "Tangent", t[t.Chain = 1] = "Chain", t[t.ChainScale = 2] = "ChainScale", t))(ae || {}),
          oe = class t {
            static NONE = -1;
            static BEFORE = -2;
            static AFTER = -3;
            static epsilon = 1e-5;
            data;
            bones;
            target;
            position = 0;
            spacing = 0;
            mixRotate = 0;
            mixX = 0;
            mixY = 0;
            spaces = new Array;
            positions = new Array;
            world = new Array;
            curves = new Array;
            lengths = new Array;
            segments = new Array;
            active = !1;
            constructor(t, e) {
              if (!t) throw new Error("data cannot be null.");
              if (!e) throw new Error("skeleton cannot be null.");
              this.data = t, this.bones = new Array;
              for (let i = 0, s = t.bones.length; i < s; i++) {
                let s = e.findBone(t.bones[i].name);
                if (!s) throw new Error(`Couldn't find bone ${t.bones[i].name}.`);
                this.bones.push(s)
              }
              let i = e.findSlot(t.target.name);
              if (!i) throw new Error(`Couldn't find target bone ${t.target.name}`);
              this.target = i, this.position = t.position, this.spacing = t.spacing, this.mixRotate = t.mixRotate, this.mixX = t.mixX, this.mixY = t.mixY
            }
            isActive() {
              return this.active
            }
            setToSetupPose() {
              const t = this.data;
              this.position = t.position, this.spacing = t.spacing, this.mixRotate = t.mixRotate, this.mixX = t.mixX, this.mixY = t.mixY
            }
            update(e) {
              let i = this.target.getAttachment();
              if (!(i instanceof Ht)) return;
              let s = this.mixRotate,
                n = this.mixX,
                r = this.mixY;
              if (0 == s && 0 == n && 0 == r) return;
              let a = this.data,
                o = 0 == a.rotateMode,
                h = 2 == a.rotateMode,
                l = this.bones,
                c = l.length,
                d = o ? c : c + 1,
                u = y.setArraySize(this.spaces, d),
                g = h ? this.lengths = y.setArraySize(this.lengths, c) : [],
                m = this.spacing;
              switch (a.spacingMode) {
                case 2:
                  if (h)
                    for (let t = 0, e = d - 1; t < e; t++) {
                      let e = l[t],
                        i = e.data.length,
                        s = i * e.a,
                        n = i * e.c;
                      g[t] = Math.sqrt(s * s + n * n)
                    }
                  y.arrayFill(u, 1, d, m);
                  break;
                case 3:
                  let e = 0;
                  for (let i = 0, s = d - 1; i < s;) {
                    let s = l[i],
                      n = s.data.length;
                    if (n < t.epsilon) h && (g[i] = 0), u[++i] = m;
                    else {
                      let t = n * s.a,
                        r = n * s.c,
                        a = Math.sqrt(t * t + r * r);
                      h && (g[i] = a), u[++i] = a, e += a
                    }
                  }
                  if (e > 0) {
                    e = d / e * m;
                    for (let t = 1; t < d; t++) u[t] *= e
                  }
                  break;
                default:
                  let i = 0 == a.spacingMode;
                  for (let e = 0, s = d - 1; e < s;) {
                    let s = l[e],
                      n = s.data.length;
                    if (n < t.epsilon) h && (g[e] = 0), u[++e] = m;
                    else {
                      let t = n * s.a,
                        r = n * s.c,
                        a = Math.sqrt(t * t + r * r);
                      h && (g[e] = a), u[++e] = (i ? n + m : m) * a / n
                    }
                  }
              }
              let f = this.computeWorldPositions(i, d, o),
                _ = f[0],
                b = f[1],
                v = a.offsetRotation,
                x = !1;
              if (0 == v) x = 1 == a.rotateMode;
              else {
                x = !1;
                let t = this.target.bone;
                v *= t.a * t.d - t.b * t.c > 0 ? p.degRad : -p.degRad
              }
              for (let t = 0, e = 3; t < c; t++, e += 3) {
                let i = l[t];
                i.worldX += (_ - i.worldX) * n, i.worldY += (b - i.worldY) * r;
                let a = f[e],
                  c = f[e + 1],
                  d = a - _,
                  m = c - b;
                if (h) {
                  let e = g[t];
                  if (0 != e) {
                    let t = (Math.sqrt(d * d + m * m) / e - 1) * s + 1;
                    i.a *= t, i.c *= t
                  }
                }
                if (_ = a, b = c, s > 0) {
                  let n = i.a,
                    r = i.b,
                    a = i.c,
                    h = i.d,
                    l = 0,
                    c = 0,
                    g = 0;
                  if (l = o ? f[e - 1] : 0 == u[t + 1] ? f[e + 2] : Math.atan2(m, d), l -= Math.atan2(a, n), x) {
                    c = Math.cos(l), g = Math.sin(l);
                    let t = i.data.length;
                    _ += (t * (c * n - g * a) - d) * s, b += (t * (g * n + c * a) - m) * s
                  } else l += v;
                  l > p.PI ? l -= p.PI2 : l < -p.PI && (l += p.PI2), l *= s, c = Math.cos(l), g = Math.sin(l), i.a = c * n - g * a, i.b = c * r - g * h, i.c = g * n + c * a, i.d = g * r + c * h
                }
                i.updateAppliedTransform()
              }
            }
            computeWorldPositions(e, i, s) {
              let n = this.target,
                r = this.position,
                a = this.spaces,
                o = y.setArraySize(this.positions, 3 * i + 2),
                h = this.world,
                l = e.closed,
                c = e.worldVerticesLength,
                d = c / 6,
                u = t.NONE;
              if (!e.constantSpeed) {
                let p = e.lengths;
                d -= l ? 1 : 2;
                let g, m = p[d];
                switch (1 == this.data.positionMode && (r *= m), this.data.spacingMode) {
                  case 2:
                    g = m;
                    break;
                  case 3:
                    g = m / i;
                    break;
                  default:
                    g = 1
                }
                h = y.setArraySize(this.world, 8);
                for (let f = 0, y = 0, _ = 0; f < i; f++, y += 3) {
                  let i = a[f] * g;
                  r += i;
                  let b = r;
                  if (l) b %= m, b < 0 && (b += m), _ = 0;
                  else {
                    if (b < 0) {
                      u != t.BEFORE && (u = t.BEFORE, e.computeWorldVertices(n, 2, 4, h, 0, 2)), this.addBeforePosition(b, h, 0, o, y);
                      continue
                    }
                    if (b > m) {
                      u != t.AFTER && (u = t.AFTER, e.computeWorldVertices(n, c - 6, 4, h, 0, 2)), this.addAfterPosition(b - m, h, 0, o, y);
                      continue
                    }
                  }
                  for (;; _++) {
                    let t = p[_];
                    if (!(b > t)) {
                      if (0 == _) b /= t;
                      else {
                        let e = p[_ - 1];
                        b = (b - e) / (t - e)
                      }
                      break
                    }
                  }
                  _ != u && (u = _, l && _ == d ? (e.computeWorldVertices(n, c - 4, 4, h, 0, 2), e.computeWorldVertices(n, 0, 4, h, 4, 2)) : e.computeWorldVertices(n, 6 * _ + 2, 8, h, 0, 2)), this.addCurvePosition(b, h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7], o, y, s || f > 0 && 0 == i)
                }
                return o
              }
              l ? (c += 2, h = y.setArraySize(this.world, c), e.computeWorldVertices(n, 2, c - 4, h, 0, 2), e.computeWorldVertices(n, 0, 2, h, c - 4, 2), h[c - 2] = h[0], h[c - 1] = h[1]) : (d--, c -= 4, h = y.setArraySize(this.world, c), e.computeWorldVertices(n, 2, c, h, 0, 2));
              let p, g = y.setArraySize(this.curves, d),
                m = 0,
                f = h[0],
                _ = h[1],
                b = 0,
                v = 0,
                x = 0,
                w = 0,
                S = 0,
                T = 0,
                C = 0,
                k = 0,
                P = 0,
                A = 0,
                I = 0,
                E = 0,
                O = 0,
                M = 0;
              for (let t = 0, e = 2; t < d; t++, e += 6) b = h[e], v = h[e + 1], x = h[e + 2], w = h[e + 3], S = h[e + 4], T = h[e + 5], C = .1875 * (f - 2 * b + x), k = .1875 * (_ - 2 * v + w), P = .09375 * (3 * (b - x) - f + S), A = .09375 * (3 * (v - w) - _ + T), I = 2 * C + P, E = 2 * k + A, O = .75 * (b - f) + C + .16666667 * P, M = .75 * (v - _) + k + .16666667 * A, m += Math.sqrt(O * O + M * M), O += I, M += E, I += P, E += A, m += Math.sqrt(O * O + M * M), O += I, M += E, m += Math.sqrt(O * O + M * M), O += I + P, M += E + A, m += Math.sqrt(O * O + M * M), g[t] = m, f = S, _ = T;
              switch (1 == this.data.positionMode && (r *= m), this.data.spacingMode) {
                case 2:
                  p = m;
                  break;
                case 3:
                  p = m / i;
                  break;
                default:
                  p = 1
              }
              let B = this.segments,
                R = 0;
              for (let t = 0, e = 0, n = 0, d = 0; t < i; t++, e += 3) {
                let i = a[t] * p;
                r += i;
                let y = r;
                if (l) y %= m, y < 0 && (y += m), n = 0;
                else {
                  if (y < 0) {
                    this.addBeforePosition(y, h, 0, o, e);
                    continue
                  }
                  if (y > m) {
                    this.addAfterPosition(y - m, h, c - 4, o, e);
                    continue
                  }
                }
                for (;; n++) {
                  let t = g[n];
                  if (!(y > t)) {
                    if (0 == n) y /= t;
                    else {
                      let e = g[n - 1];
                      y = (y - e) / (t - e)
                    }
                    break
                  }
                }
                if (n != u) {
                  u = n;
                  let t = 6 * n;
                  for (f = h[t], _ = h[t + 1], b = h[t + 2], v = h[t + 3], x = h[t + 4], w = h[t + 5], S = h[t + 6], T = h[t + 7], C = .03 * (f - 2 * b + x), k = .03 * (_ - 2 * v + w), P = .006 * (3 * (b - x) - f + S), A = .006 * (3 * (v - w) - _ + T), I = 2 * C + P, E = 2 * k + A, O = .3 * (b - f) + C + .16666667 * P, M = .3 * (v - _) + k + .16666667 * A, R = Math.sqrt(O * O + M * M), B[0] = R, t = 1; t < 8; t++) O += I, M += E, I += P, E += A, R += Math.sqrt(O * O + M * M), B[t] = R;
                  O += I, M += E, R += Math.sqrt(O * O + M * M), B[8] = R, O += I + P, M += E + A, R += Math.sqrt(O * O + M * M), B[9] = R, d = 0
                }
                for (y *= R;; d++) {
                  let t = B[d];
                  if (!(y > t)) {
                    if (0 == d) y /= t;
                    else {
                      let e = B[d - 1];
                      y = d + (y - e) / (t - e)
                    }
                    break
                  }
                }
                this.addCurvePosition(.1 * y, f, _, b, v, x, w, S, T, o, e, s || t > 0 && 0 == i)
              }
              return o
            }
            addBeforePosition(t, e, i, s, n) {
              let r = e[i],
                a = e[i + 1],
                o = e[i + 2] - r,
                h = e[i + 3] - a,
                l = Math.atan2(h, o);
              s[n] = r + t * Math.cos(l), s[n + 1] = a + t * Math.sin(l), s[n + 2] = l
            }
            addAfterPosition(t, e, i, s, n) {
              let r = e[i + 2],
                a = e[i + 3],
                o = r - e[i],
                h = a - e[i + 1],
                l = Math.atan2(h, o);
              s[n] = r + t * Math.cos(l), s[n + 1] = a + t * Math.sin(l), s[n + 2] = l
            }
            addCurvePosition(t, e, i, s, n, r, a, o, h, l, c, d) {
              if (0 == t || isNaN(t)) return l[c] = e, l[c + 1] = i, void(l[c + 2] = Math.atan2(n - i, s - e));
              let u = t * t,
                p = u * t,
                g = 1 - t,
                m = g * g,
                f = m * g,
                y = g * t,
                _ = 3 * y,
                b = g * _,
                v = _ * t,
                x = e * f + s * b + r * v + o * p,
                w = i * f + n * b + a * v + h * p;
              l[c] = x, l[c + 1] = w, d && (l[c + 2] = t < .001 ? Math.atan2(n - i, s - e) : Math.atan2(w - (i * m + n * y * 2 + a * u), x - (e * m + s * y * 2 + r * u)))
            }
          },
          he = class {
            data;
            _bone = null;
            set bone(t) {
              this._bone = t
            }
            get bone() {
              if (this._bone) return this._bone;
              throw new Error("Bone not set.")
            }
            inertia = 0;
            strength = 0;
            damping = 0;
            massInverse = 0;
            wind = 0;
            gravity = 0;
            mix = 0;
            _reset = !0;
            ux = 0;
            uy = 0;
            cx = 0;
            cy = 0;
            tx = 0;
            ty = 0;
            xOffset = 0;
            xVelocity = 0;
            yOffset = 0;
            yVelocity = 0;
            rotateOffset = 0;
            rotateVelocity = 0;
            scaleOffset = 0;
            scaleVelocity = 0;
            active = !1;
            skeleton;
            remaining = 0;
            lastTime = 0;
            constructor(t, e) {
              this.data = t, this.skeleton = e, this.bone = e.bones[t.bone.index], this.inertia = t.inertia, this.strength = t.strength, this.damping = t.damping, this.massInverse = t.massInverse, this.wind = t.wind, this.gravity = t.gravity, this.mix = t.mix
            }
            reset() {
              this.remaining = 0, this.lastTime = this.skeleton.time, this._reset = !0, this.xOffset = 0, this.xVelocity = 0, this.yOffset = 0, this.yVelocity = 0, this.rotateOffset = 0, this.rotateVelocity = 0, this.scaleOffset = 0, this.scaleVelocity = 0
            }
            setToSetupPose() {
              const t = this.data;
              this.inertia = t.inertia, this.strength = t.strength, this.damping = t.damping, this.massInverse = t.massInverse, this.wind = t.wind, this.gravity = t.gravity, this.mix = t.mix
            }
            isActive() {
              return this.active
            }
            update(t) {
              const e = this.mix;
              if (0 == e) return;
              const i = this.data.x > 0,
                s = this.data.y > 0,
                n = this.data.rotate > 0 || this.data.shearX > 0,
                r = this.data.scaleX > 0,
                a = this.bone,
                o = a.data.length;
              switch (t) {
                case 0:
                  return;
                case 1:
                  this.reset();
                case 2:
                  const t = this.skeleton,
                    h = Math.max(this.skeleton.time - this.lastTime, 0);
                  this.remaining += h, this.lastTime = t.time;
                  const l = a.worldX,
                    c = a.worldY;
                  if (this._reset) this._reset = !1, this.ux = l, this.uy = c;
                  else {
                    let d = this.remaining,
                      u = this.inertia,
                      g = this.data.step,
                      m = this.skeleton.data.referenceScale,
                      f = -1,
                      y = this.data.limit * h,
                      _ = y * Math.abs(t.scaleY);
                    if (y *= Math.abs(t.scaleX), i || s) {
                      if (i) {
                        const t = (this.ux - l) * u;
                        this.xOffset += t > y ? y : t < -y ? -y : t, this.ux = l
                      }
                      if (s) {
                        const t = (this.uy - c) * u;
                        this.yOffset += t > _ ? _ : t < -_ ? -_ : t, this.uy = c
                      }
                      if (d >= g) {
                        f = Math.pow(this.damping, 60 * g);
                        const e = this.massInverse * g,
                          n = this.strength,
                          r = this.wind * m * t.scaleX,
                          a = this.gravity * m * t.scaleY;
                        do {
                          i && (this.xVelocity += (r - this.xOffset * n) * e, this.xOffset += this.xVelocity * g, this.xVelocity *= f), s && (this.yVelocity -= (a + this.yOffset * n) * e, this.yOffset += this.yVelocity * g, this.yVelocity *= f), d -= g
                        } while (d >= g)
                      }
                      i && (a.worldX += this.xOffset * e * this.data.x), s && (a.worldY += this.yOffset * e * this.data.y)
                    }
                    if (n || r) {
                      let t = Math.atan2(a.c, a.a),
                        i = 0,
                        s = 0,
                        h = 0,
                        l = this.cx - a.worldX,
                        c = this.cy - a.worldY;
                      if (l > y ? l = y : l < -y && (l = -y), c > _ ? c = _ : c < -_ && (c = -_), n) {
                        h = (this.data.rotate + this.data.shearX) * e;
                        let n = Math.atan2(c + this.ty, l + this.tx) - t - this.rotateOffset * h;
                        this.rotateOffset += (n - Math.ceil(n * p.invPI2 - .5) * p.PI2) * u, n = this.rotateOffset * h + t, i = Math.cos(n), s = Math.sin(n), r && (n = o * a.getWorldScaleX(), n > 0 && (this.scaleOffset += (l * i + c * s) * u / n))
                      } else {
                        i = Math.cos(t), s = Math.sin(t);
                        const e = o * a.getWorldScaleX();
                        e > 0 && (this.scaleOffset += (l * i + c * s) * u / e)
                      }
                      if (d = this.remaining, d >= g) {
                        -1 == f && (f = Math.pow(this.damping, 60 * g));
                        const e = this.massInverse * g,
                          a = this.strength,
                          l = this.wind,
                          c = de.yDown ? -this.gravity : this.gravity,
                          u = o / m;
                        for (;;)
                          if (d -= g, r && (this.scaleVelocity += (l * i - c * s - this.scaleOffset * a) * e, this.scaleOffset += this.scaleVelocity * g, this.scaleVelocity *= f), n) {
                            if (this.rotateVelocity -= ((l * s + c * i) * u + this.rotateOffset * a) * e, this.rotateOffset += this.rotateVelocity * g, this.rotateVelocity *= f, d < g) break;
                            const n = this.rotateOffset * h + t;
                            i = Math.cos(n), s = Math.sin(n)
                          } else if (d < g) break
                      }
                    }
                    this.remaining = d
                  }
                  this.cx = a.worldX, this.cy = a.worldY;
                  break;
                case 3:
                  i && (a.worldX += this.xOffset * e * this.data.x), s && (a.worldY += this.yOffset * e * this.data.y)
              }
              if (n) {
                let t = this.rotateOffset * e,
                  i = 0,
                  s = 0,
                  n = 0;
                if (this.data.shearX > 0) {
                  let e = 0;
                  this.data.rotate > 0 && (e = t * this.data.rotate, i = Math.sin(e), s = Math.cos(e), n = a.b, a.b = s * n - i * a.d, a.d = i * n + s * a.d), e += t * this.data.shearX, i = Math.sin(e), s = Math.cos(e), n = a.a, a.a = s * n - i * a.c, a.c = i * n + s * a.c
                } else t *= this.data.rotate, i = Math.sin(t), s = Math.cos(t), n = a.a, a.a = s * n - i * a.c, a.c = i * n + s * a.c, n = a.b, a.b = s * n - i * a.d, a.d = i * n + s * a.d
              }
              if (r) {
                const t = 1 + this.scaleOffset * e * this.data.scaleX;
                a.a *= t, a.c *= t
              }
              3 != t && (this.tx = o * a.a, this.ty = o * a.c), a.updateAppliedTransform()
            }
            translate(t, e) {
              this.ux -= t, this.uy -= e, this.cx -= t, this.cy -= e
            }
            rotate(t, e, i) {
              const s = i * p.degRad,
                n = Math.cos(s),
                r = Math.sin(s),
                a = this.cx - t,
                o = this.cy - e;
              this.translate(a * n - o * r - a, a * r + o * n - o)
            }
          },
          le = class {
            data;
            bone;
            color;
            darkColor = null;
            attachment = null;
            attachmentState = 0;
            sequenceIndex = -1;
            deform = new Array;
            constructor(t, e) {
              if (!t) throw new Error("data cannot be null.");
              if (!e) throw new Error("bone cannot be null.");
              this.data = t, this.bone = e, this.color = new u, this.darkColor = t.darkColor ? new u : null, this.setToSetupPose()
            }
            getSkeleton() {
              return this.bone.skeleton
            }
            getAttachment() {
              return this.attachment
            }
            setAttachment(t) {
              this.attachment != t && ((!(t instanceof T) || !(this.attachment instanceof T) || t.timelineAttachment != this.attachment.timelineAttachment) && (this.deform.length = 0), this.attachment = t, this.sequenceIndex = -1)
            }
            setToSetupPose() {
              this.color.setFromColor(this.data.color), this.darkColor && this.darkColor.setFromColor(this.data.darkColor), this.data.attachmentName ? (this.attachment = null, this.setAttachment(this.bone.skeleton.getAttachment(this.data.index, this.data.attachmentName))) : this.attachment = null
            }
          },
          ce = class {
            data;
            bones;
            target;
            mixRotate = 0;
            mixX = 0;
            mixY = 0;
            mixScaleX = 0;
            mixScaleY = 0;
            mixShearY = 0;
            temp = new v;
            active = !1;
            constructor(t, e) {
              if (!t) throw new Error("data cannot be null.");
              if (!e) throw new Error("skeleton cannot be null.");
              this.data = t, this.bones = new Array;
              for (let i = 0; i < t.bones.length; i++) {
                let s = e.findBone(t.bones[i].name);
                if (!s) throw new Error(`Couldn't find bone ${t.bones[i].name}.`);
                this.bones.push(s)
              }
              let i = e.findBone(t.target.name);
              if (!i) throw new Error(`Couldn't find target bone ${t.target.name}.`);
              this.target = i, this.mixRotate = t.mixRotate, this.mixX = t.mixX, this.mixY = t.mixY, this.mixScaleX = t.mixScaleX, this.mixScaleY = t.mixScaleY, this.mixShearY = t.mixShearY
            }
            isActive() {
              return this.active
            }
            setToSetupPose() {
              const t = this.data;
              this.mixRotate = t.mixRotate, this.mixX = t.mixX, this.mixY = t.mixY, this.mixScaleX = t.mixScaleX, this.mixScaleY = t.mixScaleY, this.mixShearY = t.mixShearY
            }
            update(t) {
              0 == this.mixRotate && 0 == this.mixX && 0 == this.mixY && 0 == this.mixScaleX && 0 == this.mixScaleY && 0 == this.mixShearY || (this.data.local ? this.data.relative ? this.applyRelativeLocal() : this.applyAbsoluteLocal() : this.data.relative ? this.applyRelativeWorld() : this.applyAbsoluteWorld())
            }
            applyAbsoluteWorld() {
              let t = this.mixRotate,
                e = this.mixX,
                i = this.mixY,
                s = this.mixScaleX,
                n = this.mixScaleY,
                r = this.mixShearY,
                a = 0 != e || 0 != i,
                o = this.target,
                h = o.a,
                l = o.b,
                c = o.c,
                d = o.d,
                u = h * d - l * c > 0 ? p.degRad : -p.degRad,
                g = this.data.offsetRotation * u,
                m = this.data.offsetShearY * u,
                f = this.bones;
              for (let u = 0, y = f.length; u < y; u++) {
                let y = f[u];
                if (0 != t) {
                  let e = y.a,
                    i = y.b,
                    s = y.c,
                    n = y.d,
                    r = Math.atan2(c, h) - Math.atan2(s, e) + g;
                  r > p.PI ? r -= p.PI2 : r < -p.PI && (r += p.PI2), r *= t;
                  let a = Math.cos(r),
                    o = Math.sin(r);
                  y.a = a * e - o * s, y.b = a * i - o * n, y.c = o * e + a * s, y.d = o * i + a * n
                }
                if (a) {
                  let t = this.temp;
                  o.localToWorld(t.set(this.data.offsetX, this.data.offsetY)), y.worldX += (t.x - y.worldX) * e, y.worldY += (t.y - y.worldY) * i
                }
                if (0 != s) {
                  let t = Math.sqrt(y.a * y.a + y.c * y.c);
                  0 != t && (t = (t + (Math.sqrt(h * h + c * c) - t + this.data.offsetScaleX) * s) / t), y.a *= t, y.c *= t
                }
                if (0 != n) {
                  let t = Math.sqrt(y.b * y.b + y.d * y.d);
                  0 != t && (t = (t + (Math.sqrt(l * l + d * d) - t + this.data.offsetScaleY) * n) / t), y.b *= t, y.d *= t
                }
                if (r > 0) {
                  let t = y.b,
                    e = y.d,
                    i = Math.atan2(e, t),
                    s = Math.atan2(d, l) - Math.atan2(c, h) - (i - Math.atan2(y.c, y.a));
                  s > p.PI ? s -= p.PI2 : s < -p.PI && (s += p.PI2), s = i + (s + m) * r;
                  let n = Math.sqrt(t * t + e * e);
                  y.b = Math.cos(s) * n, y.d = Math.sin(s) * n
                }
                y.updateAppliedTransform()
              }
            }
            applyRelativeWorld() {
              let t = this.mixRotate,
                e = this.mixX,
                i = this.mixY,
                s = this.mixScaleX,
                n = this.mixScaleY,
                r = this.mixShearY,
                a = 0 != e || 0 != i,
                o = this.target,
                h = o.a,
                l = o.b,
                c = o.c,
                d = o.d,
                u = h * d - l * c > 0 ? p.degRad : -p.degRad,
                g = this.data.offsetRotation * u,
                m = this.data.offsetShearY * u,
                f = this.bones;
              for (let u = 0, y = f.length; u < y; u++) {
                let y = f[u];
                if (0 != t) {
                  let e = y.a,
                    i = y.b,
                    s = y.c,
                    n = y.d,
                    r = Math.atan2(c, h) + g;
                  r > p.PI ? r -= p.PI2 : r < -p.PI && (r += p.PI2), r *= t;
                  let a = Math.cos(r),
                    o = Math.sin(r);
                  y.a = a * e - o * s, y.b = a * i - o * n, y.c = o * e + a * s, y.d = o * i + a * n
                }
                if (a) {
                  let t = this.temp;
                  o.localToWorld(t.set(this.data.offsetX, this.data.offsetY)), y.worldX += t.x * e, y.worldY += t.y * i
                }
                if (0 != s) {
                  let t = (Math.sqrt(h * h + c * c) - 1 + this.data.offsetScaleX) * s + 1;
                  y.a *= t, y.c *= t
                }
                if (0 != n) {
                  let t = (Math.sqrt(l * l + d * d) - 1 + this.data.offsetScaleY) * n + 1;
                  y.b *= t, y.d *= t
                }
                if (r > 0) {
                  let t = Math.atan2(d, l) - Math.atan2(c, h);
                  t > p.PI ? t -= p.PI2 : t < -p.PI && (t += p.PI2);
                  let e = y.b,
                    i = y.d;
                  t = Math.atan2(i, e) + (t - p.PI / 2 + m) * r;
                  let s = Math.sqrt(e * e + i * i);
                  y.b = Math.cos(t) * s, y.d = Math.sin(t) * s
                }
                y.updateAppliedTransform()
              }
            }
            applyAbsoluteLocal() {
              let t = this.mixRotate,
                e = this.mixX,
                i = this.mixY,
                s = this.mixScaleX,
                n = this.mixScaleY,
                r = this.mixShearY,
                a = this.target,
                o = this.bones;
              for (let h = 0, l = o.length; h < l; h++) {
                let l = o[h],
                  c = l.arotation;
                0 != t && (c += (a.arotation - c + this.data.offsetRotation) * t);
                let d = l.ax,
                  u = l.ay;
                d += (a.ax - d + this.data.offsetX) * e, u += (a.ay - u + this.data.offsetY) * i;
                let p = l.ascaleX,
                  g = l.ascaleY;
                0 != s && 0 != p && (p = (p + (a.ascaleX - p + this.data.offsetScaleX) * s) / p), 0 != n && 0 != g && (g = (g + (a.ascaleY - g + this.data.offsetScaleY) * n) / g);
                let m = l.ashearY;
                0 != r && (m += (a.ashearY - m + this.data.offsetShearY) * r), l.updateWorldTransformWith(d, u, c, p, g, l.ashearX, m)
              }
            }
            applyRelativeLocal() {
              let t = this.mixRotate,
                e = this.mixX,
                i = this.mixY,
                s = this.mixScaleX,
                n = this.mixScaleY,
                r = this.mixShearY,
                a = this.target,
                o = this.bones;
              for (let h = 0, l = o.length; h < l; h++) {
                let l = o[h],
                  c = l.arotation + (a.arotation + this.data.offsetRotation) * t,
                  d = l.ax + (a.ax + this.data.offsetX) * e,
                  u = l.ay + (a.ay + this.data.offsetY) * i,
                  p = l.ascaleX * ((a.ascaleX - 1 + this.data.offsetScaleX) * s + 1),
                  g = l.ascaleY * ((a.ascaleY - 1 + this.data.offsetScaleY) * n + 1),
                  m = l.ashearY + (a.ashearY + this.data.offsetShearY) * r;
                l.updateWorldTransformWith(d, u, c, p, g, l.ashearX, m)
              }
            }
          },
          de = class t {
            static quadTriangles = [0, 1, 2, 2, 3, 0];
            static yDown = !1;
            data;
            bones;
            slots;
            drawOrder;
            ikConstraints;
            transformConstraints;
            pathConstraints;
            physicsConstraints;
            _updateCache = new Array;
            skin = null;
            color;
            scaleX = 1;
            _scaleY = 1;
            get scaleY() {
              return t.yDown ? -this._scaleY : this._scaleY
            }
            set scaleY(t) {
              this._scaleY = t
            }
            x = 0;
            y = 0;
            time = 0;
            constructor(t) {
              if (!t) throw new Error("data cannot be null.");
              this.data = t, this.bones = new Array;
              for (let e = 0; e < t.bones.length; e++) {
                let i, s = t.bones[e];
                if (s.parent) {
                  let t = this.bones[s.parent.index];
                  i = new $t(s, this, t), t.children.push(i)
                } else i = new $t(s, this, null);
                this.bones.push(i)
              }
              this.slots = new Array, this.drawOrder = new Array;
              for (let e = 0; e < t.slots.length; e++) {
                let i = t.slots[e],
                  s = this.bones[i.boneData.index],
                  n = new le(i, s);
                this.slots.push(n), this.drawOrder.push(n)
              }
              this.ikConstraints = new Array;
              for (let e = 0; e < t.ikConstraints.length; e++) {
                let i = t.ikConstraints[e];
                this.ikConstraints.push(new ee(i, this))
              }
              this.transformConstraints = new Array;
              for (let e = 0; e < t.transformConstraints.length; e++) {
                let i = t.transformConstraints[e];
                this.transformConstraints.push(new ce(i, this))
              }
              this.pathConstraints = new Array;
              for (let e = 0; e < t.pathConstraints.length; e++) {
                let i = t.pathConstraints[e];
                this.pathConstraints.push(new oe(i, this))
              }
              this.physicsConstraints = new Array;
              for (let e = 0; e < t.physicsConstraints.length; e++) {
                let i = t.physicsConstraints[e];
                this.physicsConstraints.push(new he(i, this))
              }
              this.color = new u(1, 1, 1, 1), this.updateCache()
            }
            updateCache() {
              this._updateCache.length = 0;
              let t = this.bones;
              for (let e = 0, i = t.length; e < i; e++) {
                let i = t[e];
                i.sorted = i.data.skinRequired, i.active = !i.sorted
              }
              if (this.skin) {
                let t = this.skin.bones;
                for (let e = 0, i = this.skin.bones.length; e < i; e++) {
                  let i = this.bones[t[e].index];
                  do {
                    i.sorted = !1, i.active = !0, i = i.parent
                  } while (i)
                }
              }
              let e = this.ikConstraints,
                i = this.transformConstraints,
                s = this.pathConstraints,
                n = this.physicsConstraints,
                r = e.length,
                a = i.length,
                o = s.length,
                h = this.physicsConstraints.length,
                l = r + a + o + h;
              t: for (let t = 0; t < l; t++) {
                for (let i = 0; i < r; i++) {
                  let s = e[i];
                  if (s.data.order == t) {
                    this.sortIkConstraint(s);
                    continue t
                  }
                }
                for (let e = 0; e < a; e++) {
                  let s = i[e];
                  if (s.data.order == t) {
                    this.sortTransformConstraint(s);
                    continue t
                  }
                }
                for (let e = 0; e < o; e++) {
                  let i = s[e];
                  if (i.data.order == t) {
                    this.sortPathConstraint(i);
                    continue t
                  }
                }
                for (let e = 0; e < h; e++) {
                  const i = n[e];
                  if (i.data.order == t) {
                    this.sortPhysicsConstraint(i);
                    continue t
                  }
                }
              }
              for (let e = 0, i = t.length; e < i; e++) this.sortBone(t[e])
            }
            sortIkConstraint(t) {
              if (t.active = t.target.isActive() && (!t.data.skinRequired || this.skin && y.contains(this.skin.constraints, t.data, !0)), !t.active) return;
              let e = t.target;
              this.sortBone(e);
              let i = t.bones,
                s = i[0];
              if (this.sortBone(s), 1 == i.length) this._updateCache.push(t), this.sortReset(s.children);
              else {
                let e = i[i.length - 1];
                this.sortBone(e), this._updateCache.push(t), this.sortReset(s.children), e.sorted = !0
              }
            }
            sortPathConstraint(t) {
              if (t.active = t.target.bone.isActive() && (!t.data.skinRequired || this.skin && y.contains(this.skin.constraints, t.data, !0)), !t.active) return;
              let e = t.target,
                i = e.data.index,
                s = e.bone;
              this.skin && this.sortPathConstraintAttachment(this.skin, i, s), this.data.defaultSkin && this.data.defaultSkin != this.skin && this.sortPathConstraintAttachment(this.data.defaultSkin, i, s);
              for (let t = 0, e = this.data.skins.length; t < e; t++) this.sortPathConstraintAttachment(this.data.skins[t], i, s);
              let n = e.getAttachment();
              n instanceof Ht && this.sortPathConstraintAttachmentWith(n, s);
              let r = t.bones,
                a = r.length;
              for (let t = 0; t < a; t++) this.sortBone(r[t]);
              this._updateCache.push(t);
              for (let t = 0; t < a; t++) this.sortReset(r[t].children);
              for (let t = 0; t < a; t++) r[t].sorted = !0
            }
            sortTransformConstraint(t) {
              if (t.active = t.target.isActive() && (!t.data.skinRequired || this.skin && y.contains(this.skin.constraints, t.data, !0)), !t.active) return;
              this.sortBone(t.target);
              let e = t.bones,
                i = e.length;
              if (t.data.local)
                for (let t = 0; t < i; t++) {
                  let i = e[t];
                  this.sortBone(i.parent), this.sortBone(i)
                } else
                  for (let t = 0; t < i; t++) this.sortBone(e[t]);
              this._updateCache.push(t);
              for (let t = 0; t < i; t++) this.sortReset(e[t].children);
              for (let t = 0; t < i; t++) e[t].sorted = !0
            }
            sortPathConstraintAttachment(t, e, i) {
              let s = t.attachments[e];
              if (s)
                for (let t in s) this.sortPathConstraintAttachmentWith(s[t], i)
            }
            sortPathConstraintAttachmentWith(t, e) {
              if (!(t instanceof Ht)) return;
              let i = t.bones;
              if (i) {
                let t = this.bones;
                for (let e = 0, s = i.length; e < s;) {
                  let s = i[e++];
                  for (s += e; e < s;) this.sortBone(t[i[e++]])
                }
              } else this.sortBone(e)
            }
            sortPhysicsConstraint(t) {
              const e = t.bone;
              t.active = e.active && (!t.data.skinRequired || null != this.skin && y.contains(this.skin.constraints, t.data, !0)), t.active && (this.sortBone(e), this._updateCache.push(t), this.sortReset(e.children), e.sorted = !0)
            }
            sortBone(t) {
              if (!t || t.sorted) return;
              let e = t.parent;
              e && this.sortBone(e), t.sorted = !0, this._updateCache.push(t)
            }
            sortReset(t) {
              for (let e = 0, i = t.length; e < i; e++) {
                let i = t[e];
                i.active && (i.sorted && this.sortReset(i.children), i.sorted = !1)
              }
            }
            updateWorldTransform(t) {
              if (null == t) throw new Error("physics is undefined");
              let e = this.bones;
              for (let t = 0, i = e.length; t < i; t++) {
                let i = e[t];
                i.ax = i.x, i.ay = i.y, i.arotation = i.rotation, i.ascaleX = i.scaleX, i.ascaleY = i.scaleY, i.ashearX = i.shearX, i.ashearY = i.shearY
              }
              let i = this._updateCache;
              for (let e = 0, s = i.length; e < s; e++) i[e].update(t)
            }
            updateWorldTransformWith(t, e) {
              if (!e) throw new Error("parent cannot be null.");
              let i = this.bones;
              for (let t = 1, e = i.length; t < e; t++) {
                let e = i[t];
                e.ax = e.x, e.ay = e.y, e.arotation = e.rotation, e.ascaleX = e.scaleX, e.ascaleY = e.scaleY, e.ashearX = e.shearX, e.ashearY = e.shearY
              }
              let s = this.getRootBone();
              if (!s) throw new Error("Root bone must not be null.");
              let n = e.a,
                r = e.b,
                a = e.c,
                o = e.d;
              s.worldX = n * this.x + r * this.y + e.worldX, s.worldY = a * this.x + o * this.y + e.worldY;
              const h = (s.rotation + s.shearX) * p.degRad,
                l = (s.rotation + 90 + s.shearY) * p.degRad,
                c = Math.cos(h) * s.scaleX,
                d = Math.cos(l) * s.scaleY,
                u = Math.sin(h) * s.scaleX,
                g = Math.sin(l) * s.scaleY;
              s.a = (n * c + r * u) * this.scaleX, s.b = (n * d + r * g) * this.scaleX, s.c = (a * c + o * u) * this.scaleY, s.d = (a * d + o * g) * this.scaleY;
              let m = this._updateCache;
              for (let e = 0, i = m.length; e < i; e++) {
                let i = m[e];
                i != s && i.update(t)
              }
            }
            setToSetupPose() {
              this.setBonesToSetupPose(), this.setSlotsToSetupPose()
            }
            setBonesToSetupPose() {
              for (const t of this.bones) t.setToSetupPose();
              for (const t of this.ikConstraints) t.setToSetupPose();
              for (const t of this.transformConstraints) t.setToSetupPose();
              for (const t of this.pathConstraints) t.setToSetupPose();
              for (const t of this.physicsConstraints) t.setToSetupPose()
            }
            setSlotsToSetupPose() {
              let t = this.slots;
              y.arrayCopy(t, 0, this.drawOrder, 0, t.length);
              for (let e = 0, i = t.length; e < i; e++) t[e].setToSetupPose()
            }
            getRootBone() {
              return 0 == this.bones.length ? null : this.bones[0]
            }
            findBone(t) {
              if (!t) throw new Error("boneName cannot be null.");
              let e = this.bones;
              for (let i = 0, s = e.length; i < s; i++) {
                let s = e[i];
                if (s.data.name == t) return s
              }
              return null
            }
            findSlot(t) {
              if (!t) throw new Error("slotName cannot be null.");
              let e = this.slots;
              for (let i = 0, s = e.length; i < s; i++) {
                let s = e[i];
                if (s.data.name == t) return s
              }
              return null
            }
            setSkinByName(t) {
              let e = this.data.findSkin(t);
              if (!e) throw new Error("Skin not found: " + t);
              this.setSkin(e)
            }
            setSkin(t) {
              if (t != this.skin) {
                if (t)
                  if (this.skin) t.attachAll(this, this.skin);
                  else {
                    let e = this.slots;
                    for (let i = 0, s = e.length; i < s; i++) {
                      let s = e[i],
                        n = s.data.attachmentName;
                      if (n) {
                        let e = t.getAttachment(i, n);
                        e && s.setAttachment(e)
                      }
                    }
                  } this.skin = t, this.updateCache()
              }
            }
            getAttachmentByName(t, e) {
              let i = this.data.findSlot(t);
              if (!i) throw new Error(`Can't find slot with name ${t}`);
              return this.getAttachment(i.index, e)
            }
            getAttachment(t, e) {
              if (!e) throw new Error("attachmentName cannot be null.");
              if (this.skin) {
                let i = this.skin.getAttachment(t, e);
                if (i) return i
              }
              return this.data.defaultSkin ? this.data.defaultSkin.getAttachment(t, e) : null
            }
            setAttachment(t, e) {
              if (!t) throw new Error("slotName cannot be null.");
              let i = this.slots;
              for (let s = 0, n = i.length; s < n; s++) {
                let n = i[s];
                if (n.data.name == t) {
                  let i = null;
                  if (e && (i = this.getAttachment(s, e), !i)) throw new Error("Attachment not found: " + e + ", for slot: " + t);
                  return void n.setAttachment(i)
                }
              }
              throw new Error("Slot not found: " + t)
            }
            findIkConstraint(t) {
              if (!t) throw new Error("constraintName cannot be null.");
              return this.ikConstraints.find(e => e.data.name == t) ?? null
            }
            findTransformConstraint(t) {
              if (!t) throw new Error("constraintName cannot be null.");
              return this.transformConstraints.find(e => e.data.name == t) ?? null
            }
            findPathConstraint(t) {
              if (!t) throw new Error("constraintName cannot be null.");
              return this.pathConstraints.find(e => e.data.name == t) ?? null
            }
            findPhysicsConstraint(t) {
              if (null == t) throw new Error("constraintName cannot be null.");
              return this.physicsConstraints.find(e => e.data.name == t) ?? null
            }
            getBoundsRect(t) {
              let e = new v,
                i = new v;
              return this.getBounds(e, i, void 0, t), {
                x: e.x,
                y: e.y,
                width: i.x,
                height: i.y
              }
            }
            getBounds(e, i, s = new Array(2), n = null) {
              if (!e) throw new Error("offset cannot be null.");
              if (!i) throw new Error("size cannot be null.");
              let r = this.drawOrder,
                a = Number.POSITIVE_INFINITY,
                o = Number.POSITIVE_INFINITY,
                h = Number.NEGATIVE_INFINITY,
                l = Number.NEGATIVE_INFINITY;
              for (let e = 0, i = r.length; e < i; e++) {
                let i = r[e];
                if (!i.bone.active) continue;
                let c = 0,
                  d = null,
                  u = null,
                  p = i.getAttachment();
                if (p instanceof Yt) c = 8, d = y.setArraySize(s, c, 0), p.computeWorldVertices(i, d, 0, 2), u = t.quadTriangles;
                else if (p instanceof Ut) {
                  let t = p;
                  c = t.worldVerticesLength, d = y.setArraySize(s, c, 0), t.computeWorldVertices(i, 0, c, d, 0, 2), u = t.triangles
                } else if (p instanceof Ot && null != n) {
                  n.clipStart(i, p);
                  continue
                }
                if (d && u) {
                  null != n && n.isClipping() && (n.clipTriangles(d, u, u.length), d = n.clippedVertices, c = n.clippedVertices.length);
                  for (let t = 0, e = d.length; t < e; t += 2) {
                    let e = d[t],
                      i = d[t + 1];
                    a = Math.min(a, e), o = Math.min(o, i), h = Math.max(h, e), l = Math.max(l, i)
                  }
                }
                n?.clipEndWithSlot(i)
              }
              n?.clipEnd(), e.set(a, o), i.set(h - a, l - o)
            }
            update(t) {
              this.time += t
            }
            physicsTranslate(t, e) {
              const i = this.physicsConstraints;
              for (let s = 0, n = i.length; s < n; s++) i[s].translate(t, e)
            }
            physicsRotate(t, e, i) {
              const s = this.physicsConstraints;
              for (let n = 0, r = s.length; n < r; n++) s[n].rotate(t, e, i)
            }
          },
          ue = (t => (t[t.none = 0] = "none", t[t.reset = 1] = "reset", t[t.update = 2] = "update", t[t.pose = 3] = "pose", t))(ue || {}),
          pe = class extends Kt {
            _bone = null;
            set bone(t) {
              this._bone = t
            }
            get bone() {
              if (this._bone) return this._bone;
              throw new Error("BoneData not set.")
            }
            x = 0;
            y = 0;
            rotate = 0;
            scaleX = 0;
            shearX = 0;
            limit = 0;
            step = 0;
            inertia = 0;
            strength = 0;
            damping = 0;
            massInverse = 0;
            wind = 0;
            gravity = 0;
            mix = 0;
            inertiaGlobal = !1;
            strengthGlobal = !1;
            dampingGlobal = !1;
            massGlobal = !1;
            windGlobal = !1;
            gravityGlobal = !1;
            mixGlobal = !1;
            constructor(t) {
              super(t, 0, !1)
            }
          },
          ge = class {
            name = null;
            bones = new Array;
            slots = new Array;
            skins = new Array;
            defaultSkin = null;
            events = new Array;
            animations = new Array;
            ikConstraints = new Array;
            transformConstraints = new Array;
            pathConstraints = new Array;
            physicsConstraints = new Array;
            x = 0;
            y = 0;
            width = 0;
            height = 0;
            referenceScale = 100;
            version = null;
            hash = null;
            fps = 0;
            imagesPath = null;
            audioPath = null;
            findBone(t) {
              if (!t) throw new Error("boneName cannot be null.");
              let e = this.bones;
              for (let i = 0, s = e.length; i < s; i++) {
                let s = e[i];
                if (s.name == t) return s
              }
              return null
            }
            findSlot(t) {
              if (!t) throw new Error("slotName cannot be null.");
              let e = this.slots;
              for (let i = 0, s = e.length; i < s; i++) {
                let s = e[i];
                if (s.name == t) return s
              }
              return null
            }
            findSkin(t) {
              if (!t) throw new Error("skinName cannot be null.");
              let e = this.skins;
              for (let i = 0, s = e.length; i < s; i++) {
                let s = e[i];
                if (s.name == t) return s
              }
              return null
            }
            findEvent(t) {
              if (!t) throw new Error("eventDataName cannot be null.");
              let e = this.events;
              for (let i = 0, s = e.length; i < s; i++) {
                let s = e[i];
                if (s.name == t) return s
              }
              return null
            }
            findAnimation(t) {
              if (!t) throw new Error("animationName cannot be null.");
              let e = this.animations;
              for (let i = 0, s = e.length; i < s; i++) {
                let s = e[i];
                if (s.name == t) return s
              }
              return null
            }
            findIkConstraint(t) {
              if (!t) throw new Error("constraintName cannot be null.");
              const e = this.ikConstraints;
              for (let i = 0, s = e.length; i < s; i++) {
                const s = e[i];
                if (s.name == t) return s
              }
              return null
            }
            findTransformConstraint(t) {
              if (!t) throw new Error("constraintName cannot be null.");
              const e = this.transformConstraints;
              for (let i = 0, s = e.length; i < s; i++) {
                const s = e[i];
                if (s.name == t) return s
              }
              return null
            }
            findPathConstraint(t) {
              if (!t) throw new Error("constraintName cannot be null.");
              const e = this.pathConstraints;
              for (let i = 0, s = e.length; i < s; i++) {
                const s = e[i];
                if (s.name == t) return s
              }
              return null
            }
            findPhysicsConstraint(t) {
              if (!t) throw new Error("constraintName cannot be null.");
              const e = this.physicsConstraints;
              for (let i = 0, s = e.length; i < s; i++) {
                const s = e[i];
                if (s.name == t) return s
              }
              return null
            }
          },
          me = class {
            constructor(t = 0, e, i) {
              this.slotIndex = t, this.name = e, this.attachment = i
            }
          },
          fe = class {
            name;
            attachments = new Array;
            bones = Array();
            constraints = new Array;
            color = new u(.99607843, .61960787, .30980393, 1);
            constructor(t) {
              if (!t) throw new Error("name cannot be null.");
              this.name = t
            }
            setAttachment(t, e, i) {
              if (!i) throw new Error("attachment cannot be null.");
              let s = this.attachments;
              t >= s.length && (s.length = t + 1), s[t] || (s[t] = {}), s[t][e] = i
            }
            addSkin(t) {
              for (let e = 0; e < t.bones.length; e++) {
                let i = t.bones[e],
                  s = !1;
                for (let t = 0; t < this.bones.length; t++)
                  if (this.bones[t] == i) {
                    s = !0;
                    break
                  } s || this.bones.push(i)
              }
              for (let e = 0; e < t.constraints.length; e++) {
                let i = t.constraints[e],
                  s = !1;
                for (let t = 0; t < this.constraints.length; t++)
                  if (this.constraints[t] == i) {
                    s = !0;
                    break
                  } s || this.constraints.push(i)
              }
              let e = t.getAttachments();
              for (let t = 0; t < e.length; t++) {
                var i = e[t];
                this.setAttachment(i.slotIndex, i.name, i.attachment)
              }
            }
            copySkin(t) {
              for (let e = 0; e < t.bones.length; e++) {
                let i = t.bones[e],
                  s = !1;
                for (let t = 0; t < this.bones.length; t++)
                  if (this.bones[t] == i) {
                    s = !0;
                    break
                  } s || this.bones.push(i)
              }
              for (let e = 0; e < t.constraints.length; e++) {
                let i = t.constraints[e],
                  s = !1;
                for (let t = 0; t < this.constraints.length; t++)
                  if (this.constraints[t] == i) {
                    s = !0;
                    break
                  } s || this.constraints.push(i)
              }
              let e = t.getAttachments();
              for (let t = 0; t < e.length; t++) {
                var i = e[t];
                i.attachment && (i.attachment instanceof Ut ? (i.attachment = i.attachment.newLinkedMesh(), this.setAttachment(i.slotIndex, i.name, i.attachment)) : (i.attachment = i.attachment.copy(), this.setAttachment(i.slotIndex, i.name, i.attachment)))
              }
            }
            getAttachment(t, e) {
              let i = this.attachments[t];
              return i ? i[e] : null
            }
            removeAttachment(t, e) {
              let i = this.attachments[t];
              i && delete i[e]
            }
            getAttachments() {
              let t = new Array;
              for (var e = 0; e < this.attachments.length; e++) {
                let i = this.attachments[e];
                if (i)
                  for (let s in i) {
                    let n = i[s];
                    n && t.push(new me(e, s, n))
                  }
              }
              return t
            }
            getAttachmentsForSlot(t, e) {
              let i = this.attachments[t];
              if (i)
                for (let s in i) {
                  let n = i[s];
                  n && e.push(new me(t, s, n))
                }
            }
            clear() {
              this.attachments.length = 0, this.bones.length = 0, this.constraints.length = 0
            }
            attachAll(t, e) {
              let i = 0;
              for (let s = 0; s < t.slots.length; s++) {
                let n = t.slots[s],
                  r = n.getAttachment();
                if (r && i < e.attachments.length) {
                  let t = e.attachments[i];
                  for (let e in t) {
                    if (r == t[e]) {
                      let t = this.getAttachment(i, e);
                      t && n.setAttachment(t);
                      break
                    }
                  }
                }
                i++
              }
            }
          },
          ye = class {
            index = 0;
            name;
            boneData;
            color = new u(1, 1, 1, 1);
            darkColor = null;
            attachmentName = null;
            blendMode = 0;
            visible = !0;
            constructor(t, e, i) {
              if (t < 0) throw new Error("index must be >= 0.");
              if (!e) throw new Error("name cannot be null.");
              if (!i) throw new Error("boneData cannot be null.");
              this.index = t, this.name = e, this.boneData = i
            }
          },
          _e = (t => (t[t.Normal = 0] = "Normal", t[t.Additive = 1] = "Additive", t[t.Multiply = 2] = "Multiply", t[t.Screen = 3] = "Screen", t))(_e || {}),
          be = class extends Kt {
            bones = new Array;
            _target = null;
            set target(t) {
              this._target = t
            }
            get target() {
              if (this._target) return this._target;
              throw new Error("BoneData not set.")
            }
            mixRotate = 0;
            mixX = 0;
            mixY = 0;
            mixScaleX = 0;
            mixScaleY = 0;
            mixShearY = 0;
            offsetRotation = 0;
            offsetX = 0;
            offsetY = 0;
            offsetScaleX = 0;
            offsetScaleY = 0;
            offsetShearY = 0;
            relative = !1;
            local = !1;
            constructor(t) {
              super(t, 0, !1)
            }
          },
          ve = class {
            scale = 1;
            attachmentLoader;
            linkedMeshes = new Array;
            constructor(t) {
              this.attachmentLoader = t
            }
            readSkeletonData(t) {
              let e = this.scale,
                i = new ge;
              i.name = "";
              let s = new xe(t),
                n = s.readInt32(),
                r = s.readInt32();
              i.hash = 0 == r && 0 == n ? null : r.toString(16) + n.toString(16), i.version = s.readString(), i.x = s.readFloat(), i.y = s.readFloat(), i.width = s.readFloat(), i.height = s.readFloat(), i.referenceScale = s.readFloat() * e;
              let a = s.readBoolean();
              a && (i.fps = s.readFloat(), i.imagesPath = s.readString(), i.audioPath = s.readString());
              let o = 0;
              o = s.readInt(!0);
              for (let t = 0; t < o; t++) {
                let t = s.readString();
                if (!t) throw new Error("String in string table must not be null.");
                s.strings.push(t)
              }
              o = s.readInt(!0);
              for (let t = 0; t < o; t++) {
                let n = s.readString();
                if (!n) throw new Error("Bone name must not be null.");
                let r = 0 == t ? null : i.bones[s.readInt(!0)],
                  o = new Xt(t, n, r);
                o.rotation = s.readFloat(), o.x = s.readFloat() * e, o.y = s.readFloat() * e, o.scaleX = s.readFloat(), o.scaleY = s.readFloat(), o.shearX = s.readFloat(), o.shearY = s.readFloat(), o.length = s.readFloat() * e, o.inherit = s.readByte(), o.skinRequired = s.readBoolean(), a && (u.rgba8888ToColor(o.color, s.readInt32()), o.icon = s.readString() ?? void 0, o.visible = s.readBoolean()), i.bones.push(o)
              }
              o = s.readInt(!0);
              for (let t = 0; t < o; t++) {
                let e = s.readString();
                if (!e) throw new Error("Slot name must not be null.");
                let n = i.bones[s.readInt(!0)],
                  r = new ye(t, e, n);
                u.rgba8888ToColor(r.color, s.readInt32());
                let o = s.readInt32(); - 1 != o && u.rgb888ToColor(r.darkColor = new u, o), r.attachmentName = s.readStringRef(), r.blendMode = s.readInt(!0), a && (r.visible = s.readBoolean()), i.slots.push(r)
              }
              o = s.readInt(!0);
              for (let t, n = 0; n < o; n++) {
                let n = s.readString();
                if (!n) throw new Error("IK constraint data name must not be null.");
                let r = new ie(n);
                r.order = s.readInt(!0), t = s.readInt(!0);
                for (let e = 0; e < t; e++) r.bones.push(i.bones[s.readInt(!0)]);
                r.target = i.bones[s.readInt(!0)];
                let a = s.readByte();
                r.skinRequired = !!(1 & a), r.bendDirection = 2 & a ? 1 : -1, r.compress = !!(4 & a), r.stretch = !!(8 & a), r.uniform = !!(16 & a), !!(32 & a) && (r.mix = 64 & a ? s.readFloat() : 1), !!(128 & a) && (r.softness = s.readFloat() * e), i.ikConstraints.push(r)
              }
              o = s.readInt(!0);
              for (let t, n = 0; n < o; n++) {
                let n = s.readString();
                if (!n) throw new Error("Transform constraint data name must not be null.");
                let r = new be(n);
                r.order = s.readInt(!0), t = s.readInt(!0);
                for (let e = 0; e < t; e++) r.bones.push(i.bones[s.readInt(!0)]);
                r.target = i.bones[s.readInt(!0)];
                let a = s.readByte();
                r.skinRequired = !!(1 & a), r.local = !!(2 & a), r.relative = !!(4 & a), !!(8 & a) && (r.offsetRotation = s.readFloat()), !!(16 & a) && (r.offsetX = s.readFloat() * e), !!(32 & a) && (r.offsetY = s.readFloat() * e), !!(64 & a) && (r.offsetScaleX = s.readFloat()), !!(128 & a) && (r.offsetScaleY = s.readFloat()), a = s.readByte(), !!(1 & a) && (r.offsetShearY = s.readFloat()), !!(2 & a) && (r.mixRotate = s.readFloat()), !!(4 & a) && (r.mixX = s.readFloat()), !!(8 & a) && (r.mixY = s.readFloat()), !!(16 & a) && (r.mixScaleX = s.readFloat()), !!(32 & a) && (r.mixScaleY = s.readFloat()), !!(64 & a) && (r.mixShearY = s.readFloat()), i.transformConstraints.push(r)
              }
              o = s.readInt(!0);
              for (let t, n = 0; n < o; n++) {
                let n = s.readString();
                if (!n) throw new Error("Path constraint data name must not be null.");
                let r = new se(n);
                r.order = s.readInt(!0), r.skinRequired = s.readBoolean(), t = s.readInt(!0);
                for (let e = 0; e < t; e++) r.bones.push(i.bones[s.readInt(!0)]);
                r.target = i.slots[s.readInt(!0)];
                const a = s.readByte();
                r.positionMode = 1 & a, r.spacingMode = a >> 1 & 3, r.rotateMode = a >> 3 & 3, !!(128 & a) && (r.offsetRotation = s.readFloat()), r.position = s.readFloat(), 0 == r.positionMode && (r.position *= e), r.spacing = s.readFloat(), (0 == r.spacingMode || 1 == r.spacingMode) && (r.spacing *= e), r.mixRotate = s.readFloat(), r.mixX = s.readFloat(), r.mixY = s.readFloat(), i.pathConstraints.push(r)
              }
              o = s.readInt(!0);
              for (let t = 0; t < o; t++) {
                const t = s.readString();
                if (!t) throw new Error("Physics constraint data name must not be null.");
                const n = new pe(t);
                n.order = s.readInt(!0), n.bone = i.bones[s.readInt(!0)];
                let r = s.readByte();
                n.skinRequired = !!(1 & r), !!(2 & r) && (n.x = s.readFloat()), !!(4 & r) && (n.y = s.readFloat()), !!(8 & r) && (n.rotate = s.readFloat()), !!(16 & r) && (n.scaleX = s.readFloat()), !!(32 & r) && (n.shearX = s.readFloat()), n.limit = (64 & r ? s.readFloat() : 5e3) * e, n.step = 1 / s.readUnsignedByte(), n.inertia = s.readFloat(), n.strength = s.readFloat(), n.damping = s.readFloat(), n.massInverse = 128 & r ? s.readFloat() : 1, n.wind = s.readFloat(), n.gravity = s.readFloat(), r = s.readByte(), !!(1 & r) && (n.inertiaGlobal = !0), !!(2 & r) && (n.strengthGlobal = !0), !!(4 & r) && (n.dampingGlobal = !0), !!(8 & r) && (n.massGlobal = !0), !!(16 & r) && (n.windGlobal = !0), !!(32 & r) && (n.gravityGlobal = !0), !!(64 & r) && (n.mixGlobal = !0), n.mix = 128 & r ? s.readFloat() : 1, i.physicsConstraints.push(n)
              }
              let h = this.readSkin(s, i, !0, a);
              h && (i.defaultSkin = h, i.skins.push(h));
              {
                let t = i.skins.length;
                for (y.setArraySize(i.skins, o = t + s.readInt(!0)); t < o; t++) {
                  let e = this.readSkin(s, i, !1, a);
                  if (!e) throw new Error("readSkin() should not have returned null.");
                  i.skins[t] = e
                }
              }
              o = this.linkedMeshes.length;
              for (let t = 0; t < o; t++) {
                let e = this.linkedMeshes[t];
                const s = i.skins[e.skinIndex];
                if (!e.parent) throw new Error("Linked mesh parent must not be null");
                let n = s.getAttachment(e.slotIndex, e.parent);
                if (!n) throw new Error(`Parent mesh not found: ${e.parent}`);
                e.mesh.timelineAttachment = e.inheritTimeline ? n : e.mesh, e.mesh.setParentMesh(n), null != e.mesh.region && e.mesh.updateRegion()
              }
              this.linkedMeshes.length = 0, o = s.readInt(!0);
              for (let t = 0; t < o; t++) {
                let t = s.readString();
                if (!t) throw new Error("Event data name must not be null");
                let e = new te(t);
                e.intValue = s.readInt(!1), e.floatValue = s.readFloat(), e.stringValue = s.readString(), e.audioPath = s.readString(), e.audioPath && (e.volume = s.readFloat(), e.balance = s.readFloat()), i.events.push(e)
              }
              o = s.readInt(!0);
              for (let t = 0; t < o; t++) {
                let t = s.readString();
                if (!t) throw new Error("Animatio name must not be null.");
                i.animations.push(this.readAnimation(s, t, i))
              }
              return i
            }
            readSkin(t, e, i, s) {
              let n = null,
                r = 0;
              if (i) {
                if (r = t.readInt(!0), 0 == r) return null;
                n = new fe("default")
              } else {
                let i = t.readString();
                if (!i) throw new Error("Skin name must not be null.");
                n = new fe(i), s && u.rgba8888ToColor(n.color, t.readInt32()), n.bones.length = t.readInt(!0);
                for (let i = 0, s = n.bones.length; i < s; i++) n.bones[i] = e.bones[t.readInt(!0)];
                for (let i = 0, s = t.readInt(!0); i < s; i++) n.constraints.push(e.ikConstraints[t.readInt(!0)]);
                for (let i = 0, s = t.readInt(!0); i < s; i++) n.constraints.push(e.transformConstraints[t.readInt(!0)]);
                for (let i = 0, s = t.readInt(!0); i < s; i++) n.constraints.push(e.pathConstraints[t.readInt(!0)]);
                for (let i = 0, s = t.readInt(!0); i < s; i++) n.constraints.push(e.physicsConstraints[t.readInt(!0)]);
                r = t.readInt(!0)
              }
              for (let i = 0; i < r; i++) {
                let i = t.readInt(!0);
                for (let r = 0, a = t.readInt(!0); r < a; r++) {
                  let r = t.readStringRef();
                  if (!r) throw new Error("Attachment name must not be null");
                  let a = this.readAttachment(t, e, n, i, r, s);
                  a && n.setAttachment(i, r, a)
                }
              }
              return n
            }
            readAttachment(t, e, i, s, n, r) {
              let a = this.scale,
                o = t.readByte();
              const h = 8 & o ? t.readStringRef() : n;
              if (!h) throw new Error("Attachment name must not be null");
              switch (7 & o) {
                case 0: {
                  let e = 16 & o ? t.readStringRef() : null;
                  const s = 32 & o ? t.readInt32() : 4294967295,
                    n = 64 & o ? this.readSequence(t) : null;
                  let r = 128 & o ? t.readFloat() : 0,
                    l = t.readFloat(),
                    c = t.readFloat(),
                    d = t.readFloat(),
                    p = t.readFloat(),
                    g = t.readFloat(),
                    m = t.readFloat();
                  e || (e = h);
                  let f = this.attachmentLoader.newRegionAttachment(i, h, e, n);
                  return f ? (f.path = e, f.x = l * a, f.y = c * a, f.scaleX = d, f.scaleY = p, f.rotation = r, f.width = g * a, f.height = m * a, u.rgba8888ToColor(f.color, s), f.sequence = n, null == n && f.updateRegion(), f) : null
                }
                case 1: {
                  let e = this.readVertices(t, !!(16 & o)),
                    s = r ? t.readInt32() : 0,
                    n = this.attachmentLoader.newBoundingBoxAttachment(i, h);
                  return n ? (n.worldVerticesLength = e.length, n.vertices = e.vertices, n.bones = e.bones, r && u.rgba8888ToColor(n.color, s), n) : null
                }
                case 2: {
                  let e = 16 & o ? t.readStringRef() : h;
                  const s = 32 & o ? t.readInt32() : 4294967295,
                    n = 64 & o ? this.readSequence(t) : null,
                    l = t.readInt(!0),
                    c = this.readVertices(t, !!(128 & o)),
                    d = this.readFloatArray(t, c.length, 1),
                    p = this.readShortArray(t, 3 * (c.length - l - 2));
                  let g = [],
                    m = 0,
                    f = 0;
                  r && (g = this.readShortArray(t, t.readInt(!0)), m = t.readFloat(), f = t.readFloat()), e || (e = h);
                  let y = this.attachmentLoader.newMeshAttachment(i, h, e, n);
                  return y ? (y.path = e, u.rgba8888ToColor(y.color, s), y.bones = c.bones, y.vertices = c.vertices, y.worldVerticesLength = c.length, y.triangles = p, y.regionUVs = d, null == n && y.updateRegion(), y.hullLength = l << 1, y.sequence = n, r && (y.edges = g, y.width = m * a, y.height = f * a), y) : null
                }
                case 3: {
                  const e = 16 & o ? t.readStringRef() : h;
                  if (null == e) throw new Error("Path of linked mesh must not be null");
                  const n = 32 & o ? t.readInt32() : 4294967295,
                    l = 64 & o ? this.readSequence(t) : null,
                    c = !!(128 & o),
                    d = t.readInt(!0),
                    p = t.readStringRef();
                  let g = 0,
                    m = 0;
                  r && (g = t.readFloat(), m = t.readFloat());
                  let f = this.attachmentLoader.newMeshAttachment(i, h, e, l);
                  return f ? (f.path = e, u.rgba8888ToColor(f.color, n), f.sequence = l, r && (f.width = g * a, f.height = m * a), this.linkedMeshes.push(new we(f, d, s, p, c)), f) : null
                }
                case 4: {
                  const e = !!(16 & o),
                    s = !!(32 & o),
                    n = this.readVertices(t, !!(64 & o)),
                    l = y.newArray(n.length / 6, 0);
                  for (let e = 0, i = l.length; e < i; e++) l[e] = t.readFloat() * a;
                  const c = r ? t.readInt32() : 0,
                    d = this.attachmentLoader.newPathAttachment(i, h);
                  return d ? (d.closed = e, d.constantSpeed = s, d.worldVerticesLength = n.length, d.vertices = n.vertices, d.bones = n.bones, d.lengths = l, r && u.rgba8888ToColor(d.color, c), d) : null
                }
                case 5: {
                  const e = t.readFloat(),
                    s = t.readFloat(),
                    n = t.readFloat(),
                    o = r ? t.readInt32() : 0,
                    l = this.attachmentLoader.newPointAttachment(i, h);
                  return l ? (l.x = s * a, l.y = n * a, l.rotation = e, r && u.rgba8888ToColor(l.color, o), l) : null
                }
                case 6: {
                  const s = t.readInt(!0),
                    n = this.readVertices(t, !!(16 & o));
                  let a = r ? t.readInt32() : 0,
                    l = this.attachmentLoader.newClippingAttachment(i, h);
                  return l ? (l.endSlot = e.slots[s], l.worldVerticesLength = n.length, l.vertices = n.vertices, l.bones = n.bones, r && u.rgba8888ToColor(l.color, a), l) : null
                }
              }
              return null
            }
            readSequence(t) {
              let e = new C(t.readInt(!0));
              return e.start = t.readInt(!0), e.digits = t.readInt(!0), e.setupIndex = t.readInt(!0), e
            }
            readVertices(t, e) {
              const i = this.scale,
                s = t.readInt(!0),
                n = new Se;
              if (n.length = s << 1, !e) return n.vertices = this.readFloatArray(t, n.length, i), n;
              let r = new Array,
                a = new Array;
              for (let e = 0; e < s; e++) {
                let e = t.readInt(!0);
                a.push(e);
                for (let s = 0; s < e; s++) a.push(t.readInt(!0)), r.push(t.readFloat() * i), r.push(t.readFloat() * i), r.push(t.readFloat())
              }
              return n.vertices = y.toFloatArray(r), n.bones = a, n
            }
            readFloatArray(t, e, i) {
              let s = new Array(e);
              if (1 == i)
                for (let i = 0; i < e; i++) s[i] = t.readFloat();
              else
                for (let n = 0; n < e; n++) s[n] = t.readFloat() * i;
              return s
            }
            readShortArray(t, e) {
              let i = new Array(e);
              for (let s = 0; s < e; s++) i[s] = t.readInt(!0);
              return i
            }
            readAnimation(t, e, i) {
              t.readInt(!0);
              let s = new Array,
                n = this.scale;
              for (let e = 0, i = t.readInt(!0); e < i; e++) {
                let e = t.readInt(!0);
                for (let i = 0, n = t.readInt(!0); i < n; i++) {
                  let i = t.readByte(),
                    n = t.readInt(!0),
                    r = n - 1;
                  switch (i) {
                    case Ne: {
                      let i = new Q(n, e);
                      for (let e = 0; e < n; e++) i.setFrame(e, t.readFloat(), t.readStringRef());
                      s.push(i);
                      break
                    }
                    case Ve: {
                      let i = t.readInt(!0),
                        a = new j(n, i, e),
                        o = t.readFloat(),
                        h = t.readUnsignedByte() / 255,
                        l = t.readUnsignedByte() / 255,
                        c = t.readUnsignedByte() / 255,
                        d = t.readUnsignedByte() / 255;
                      for (let e = 0, i = 0; a.setFrame(e, o, h, l, c, d), e != r; e++) {
                        let s = t.readFloat(),
                          n = t.readUnsignedByte() / 255,
                          r = t.readUnsignedByte() / 255,
                          u = t.readUnsignedByte() / 255,
                          p = t.readUnsignedByte() / 255;
                        switch (t.readByte()) {
                          case si:
                            a.setStepped(e);
                            break;
                          case ni:
                            ke(t, a, i++, e, 0, o, s, h, n, 1), ke(t, a, i++, e, 1, o, s, l, r, 1), ke(t, a, i++, e, 2, o, s, c, u, 1), ke(t, a, i++, e, 3, o, s, d, p, 1)
                        }
                        o = s, h = n, l = r, c = u, d = p
                      }
                      s.push(a);
                      break
                    }
                    case ze: {
                      let i = t.readInt(!0),
                        a = new $(n, i, e),
                        o = t.readFloat(),
                        h = t.readUnsignedByte() / 255,
                        l = t.readUnsignedByte() / 255,
                        c = t.readUnsignedByte() / 255;
                      for (let e = 0, i = 0; a.setFrame(e, o, h, l, c), e != r; e++) {
                        let s = t.readFloat(),
                          n = t.readUnsignedByte() / 255,
                          r = t.readUnsignedByte() / 255,
                          d = t.readUnsignedByte() / 255;
                        switch (t.readByte()) {
                          case si:
                            a.setStepped(e);
                            break;
                          case ni:
                            ke(t, a, i++, e, 0, o, s, h, n, 1), ke(t, a, i++, e, 1, o, s, l, r, 1), ke(t, a, i++, e, 2, o, s, c, d, 1)
                        }
                        o = s, h = n, l = r, c = d
                      }
                      s.push(a);
                      break
                    }
                    case Ue: {
                      let i = t.readInt(!0),
                        a = new q(n, i, e),
                        o = t.readFloat(),
                        h = t.readUnsignedByte() / 255,
                        l = t.readUnsignedByte() / 255,
                        c = t.readUnsignedByte() / 255,
                        d = t.readUnsignedByte() / 255,
                        u = t.readUnsignedByte() / 255,
                        p = t.readUnsignedByte() / 255,
                        g = t.readUnsignedByte() / 255;
                      for (let e = 0, i = 0; a.setFrame(e, o, h, l, c, d, u, p, g), e != r; e++) {
                        let s = t.readFloat(),
                          n = t.readUnsignedByte() / 255,
                          r = t.readUnsignedByte() / 255,
                          m = t.readUnsignedByte() / 255,
                          f = t.readUnsignedByte() / 255,
                          y = t.readUnsignedByte() / 255,
                          _ = t.readUnsignedByte() / 255,
                          b = t.readUnsignedByte() / 255;
                        switch (t.readByte()) {
                          case si:
                            a.setStepped(e);
                            break;
                          case ni:
                            ke(t, a, i++, e, 0, o, s, h, n, 1), ke(t, a, i++, e, 1, o, s, l, r, 1), ke(t, a, i++, e, 2, o, s, c, m, 1), ke(t, a, i++, e, 3, o, s, d, f, 1), ke(t, a, i++, e, 4, o, s, u, y, 1), ke(t, a, i++, e, 5, o, s, p, _, 1), ke(t, a, i++, e, 6, o, s, g, b, 1)
                        }
                        o = s, h = n, l = r, c = m, d = f, u = y, p = _, g = b
                      }
                      s.push(a);
                      break
                    }
                    case He: {
                      let i = t.readInt(!0),
                        a = new Z(n, i, e),
                        o = t.readFloat(),
                        h = t.readUnsignedByte() / 255,
                        l = t.readUnsignedByte() / 255,
                        c = t.readUnsignedByte() / 255,
                        d = t.readUnsignedByte() / 255,
                        u = t.readUnsignedByte() / 255,
                        p = t.readUnsignedByte() / 255;
                      for (let e = 0, i = 0; a.setFrame(e, o, h, l, c, d, u, p), e != r; e++) {
                        let s = t.readFloat(),
                          n = t.readUnsignedByte() / 255,
                          r = t.readUnsignedByte() / 255,
                          g = t.readUnsignedByte() / 255,
                          m = t.readUnsignedByte() / 255,
                          f = t.readUnsignedByte() / 255,
                          y = t.readUnsignedByte() / 255;
                        switch (t.readByte()) {
                          case si:
                            a.setStepped(e);
                            break;
                          case ni:
                            ke(t, a, i++, e, 0, o, s, h, n, 1), ke(t, a, i++, e, 1, o, s, l, r, 1), ke(t, a, i++, e, 2, o, s, c, g, 1), ke(t, a, i++, e, 3, o, s, d, m, 1), ke(t, a, i++, e, 4, o, s, u, f, 1), ke(t, a, i++, e, 5, o, s, p, y, 1)
                        }
                        o = s, h = n, l = r, c = g, d = m, u = f, p = y
                      }
                      s.push(a);
                      break
                    }
                    case We: {
                      let i = new K(n, t.readInt(!0), e),
                        a = t.readFloat(),
                        o = t.readUnsignedByte() / 255;
                      for (let e = 0, s = 0; i.setFrame(e, a, o), e != r; e++) {
                        let n = t.readFloat(),
                          r = t.readUnsignedByte() / 255;
                        switch (t.readByte()) {
                          case si:
                            i.setStepped(e);
                            break;
                          case ni:
                            ke(t, i, s++, e, 0, a, n, o, r, 1)
                        }
                        a = n, o = r
                      }
                      s.push(i)
                    }
                  }
                }
              }
              for (let e = 0, i = t.readInt(!0); e < i; e++) {
                let e = t.readInt(!0);
                for (let i = 0, r = t.readInt(!0); i < r; i++) {
                  let i = t.readByte(),
                    r = t.readInt(!0);
                  if (i == Fe) {
                    let i = new X(r, e);
                    for (let e = 0; e < r; e++) i.setFrame(e, t.readFloat(), t.readByte());
                    s.push(i);
                    continue
                  }
                  let a = t.readInt(!0);
                  switch (i) {
                    case Pe:
                      s.push(Te(t, new L(r, a, e), 1));
                      break;
                    case Ae:
                      s.push(Ce(t, new F(r, a, e), n));
                      break;
                    case Ie:
                      s.push(Te(t, new N(r, a, e), n));
                      break;
                    case Ee:
                      s.push(Te(t, new V(r, a, e), n));
                      break;
                    case Oe:
                      s.push(Ce(t, new z(r, a, e), 1));
                      break;
                    case Me:
                      s.push(Te(t, new U(r, a, e), 1));
                      break;
                    case Be:
                      s.push(Te(t, new H(r, a, e), 1));
                      break;
                    case Re:
                      s.push(Ce(t, new W(r, a, e), 1));
                      break;
                    case De:
                      s.push(Te(t, new Y(r, a, e), 1));
                      break;
                    case Le:
                      s.push(Te(t, new G(r, a, e), 1))
                  }
                }
              }
              for (let e = 0, i = t.readInt(!0); e < i; e++) {
                let e = t.readInt(!0),
                  i = t.readInt(!0),
                  r = i - 1,
                  a = new it(i, t.readInt(!0), e),
                  o = t.readByte(),
                  h = t.readFloat(),
                  l = 1 & o ? 2 & o ? t.readFloat() : 1 : 0,
                  c = 4 & o ? t.readFloat() * n : 0;
                for (let e = 0, i = 0; a.setFrame(e, h, l, c, 8 & o ? 1 : -1, !!(16 & o), !!(32 & o)), e != r; e++) {
                  o = t.readByte();
                  const s = t.readFloat(),
                    r = 1 & o ? 2 & o ? t.readFloat() : 1 : 0,
                    d = 4 & o ? t.readFloat() * n : 0;
                  64 & o ? a.setStepped(e) : !!(128 & o) && (ke(t, a, i++, e, 0, h, s, l, r, 1), ke(t, a, i++, e, 1, h, s, c, d, n)), h = s, l = r, c = d
                }
                s.push(a)
              }
              for (let e = 0, i = t.readInt(!0); e < i; e++) {
                let e = t.readInt(!0),
                  i = t.readInt(!0),
                  n = i - 1,
                  r = new st(i, t.readInt(!0), e),
                  a = t.readFloat(),
                  o = t.readFloat(),
                  h = t.readFloat(),
                  l = t.readFloat(),
                  c = t.readFloat(),
                  d = t.readFloat(),
                  u = t.readFloat();
                for (let e = 0, i = 0; r.setFrame(e, a, o, h, l, c, d, u), e != n; e++) {
                  let s = t.readFloat(),
                    n = t.readFloat(),
                    p = t.readFloat(),
                    g = t.readFloat(),
                    m = t.readFloat(),
                    f = t.readFloat(),
                    y = t.readFloat();
                  switch (t.readByte()) {
                    case si:
                      r.setStepped(e);
                      break;
                    case ni:
                      ke(t, r, i++, e, 0, a, s, o, n, 1), ke(t, r, i++, e, 1, a, s, h, p, 1), ke(t, r, i++, e, 2, a, s, l, g, 1), ke(t, r, i++, e, 3, a, s, c, m, 1), ke(t, r, i++, e, 4, a, s, d, f, 1), ke(t, r, i++, e, 5, a, s, u, y, 1)
                  }
                  a = s, o = n, h = p, l = g, c = m, d = f, u = y
                }
                s.push(r)
              }
              for (let e = 0, r = t.readInt(!0); e < r; e++) {
                let e = t.readInt(!0),
                  r = i.pathConstraints[e];
                for (let i = 0, a = t.readInt(!0); i < a; i++) {
                  const i = t.readByte(),
                    a = t.readInt(!0),
                    o = t.readInt(!0);
                  switch (i) {
                    case Xe:
                      s.push(Te(t, new nt(a, o, e), 0 == r.positionMode ? n : 1));
                      break;
                    case je:
                      s.push(Te(t, new rt(a, o, e), 0 == r.spacingMode || 1 == r.spacingMode ? n : 1));
                      break;
                    case $e:
                      let i = new at(a, o, e),
                        h = t.readFloat(),
                        l = t.readFloat(),
                        c = t.readFloat(),
                        d = t.readFloat();
                      for (let e = 0, s = 0, n = i.getFrameCount() - 1; i.setFrame(e, h, l, c, d), e != n; e++) {
                        let n = t.readFloat(),
                          r = t.readFloat(),
                          a = t.readFloat(),
                          o = t.readFloat();
                        switch (t.readByte()) {
                          case si:
                            i.setStepped(e);
                            break;
                          case ni:
                            ke(t, i, s++, e, 0, h, n, l, r, 1), ke(t, i, s++, e, 1, h, n, c, a, 1), ke(t, i, s++, e, 2, h, n, d, o, 1)
                        }
                        h = n, l = r, c = a, d = o
                      }
                      s.push(i)
                  }
                }
              }
              for (let e = 0, i = t.readInt(!0); e < i; e++) {
                const e = t.readInt(!0) - 1;
                for (let i = 0, n = t.readInt(!0); i < n; i++) {
                  const i = t.readByte(),
                    n = t.readInt(!0);
                  if (i == ii) {
                    const i = new mt(n, e);
                    for (let e = 0; e < n; e++) i.setFrame(e, t.readFloat());
                    s.push(i);
                    continue
                  }
                  const r = t.readInt(!0);
                  switch (i) {
                    case Ke:
                      s.push(Te(t, new ht(n, r, e), 1));
                      break;
                    case qe:
                      s.push(Te(t, new lt(n, r, e), 1));
                      break;
                    case Ze:
                      s.push(Te(t, new ct(n, r, e), 1));
                      break;
                    case Qe:
                      s.push(Te(t, new dt(n, r, e), 1));
                      break;
                    case Je:
                      s.push(Te(t, new ut(n, r, e), 1));
                      break;
                    case ti:
                      s.push(Te(t, new pt(n, r, e), 1));
                      break;
                    case ei:
                      s.push(Te(t, new gt(n, r, e), 1))
                  }
                }
              }
              for (let e = 0, r = t.readInt(!0); e < r; e++) {
                let e = i.skins[t.readInt(!0)];
                for (let i = 0, r = t.readInt(!0); i < r; i++) {
                  let i = t.readInt(!0);
                  for (let r = 0, a = t.readInt(!0); r < a; r++) {
                    let r = t.readStringRef();
                    if (!r) throw new Error("attachmentName must not be null.");
                    let a = e.getAttachment(i, r),
                      o = t.readByte(),
                      h = t.readInt(!0),
                      l = h - 1;
                    switch (o) {
                      case Ye: {
                        let e = a,
                          r = e.bones,
                          o = e.vertices,
                          c = r ? o.length / 3 * 2 : o.length,
                          d = t.readInt(!0),
                          u = new J(h, d, i, e),
                          p = t.readFloat();
                        for (let e = 0, i = 0;; e++) {
                          let s, a = t.readInt(!0);
                          if (0 == a) s = r ? y.newFloatArray(c) : o;
                          else {
                            s = y.newFloatArray(c);
                            let e = t.readInt(!0);
                            if (a += e, 1 == n)
                              for (let i = e; i < a; i++) s[i] = t.readFloat();
                            else
                              for (let i = e; i < a; i++) s[i] = t.readFloat() * n;
                            if (!r)
                              for (let t = 0, e = s.length; t < e; t++) s[t] += o[t]
                          }
                          if (u.setFrame(e, p, s), e == l) break;
                          let h = t.readFloat();
                          switch (t.readByte()) {
                            case si:
                              u.setStepped(e);
                              break;
                            case ni:
                              ke(t, u, i++, e, 0, p, h, 0, 1, 1)
                          }
                          p = h
                        }
                        s.push(u);
                        break
                      }
                      case Ge: {
                        let e = new ft(h, i, a);
                        for (let i = 0; i < h; i++) {
                          let s = t.readFloat(),
                            n = t.readInt32();
                          e.setFrame(i, s, P[15 & n], n >> 4, t.readFloat())
                        }
                        s.push(e);
                        break
                      }
                    }
                  }
                }
              }
              let r = t.readInt(!0);
              if (r > 0) {
                let e = new et(r),
                  n = i.slots.length;
                for (let i = 0; i < r; i++) {
                  let s = t.readFloat(),
                    r = t.readInt(!0),
                    a = y.newArray(n, 0);
                  for (let t = n - 1; t >= 0; t--) a[t] = -1;
                  let o = y.newArray(n - r, 0),
                    h = 0,
                    l = 0;
                  for (let e = 0; e < r; e++) {
                    let e = t.readInt(!0);
                    for (; h != e;) o[l++] = h++;
                    a[h + t.readInt(!0)] = h++
                  }
                  for (; h < n;) o[l++] = h++;
                  for (let t = n - 1; t >= 0; t--) - 1 == a[t] && (a[t] = o[--l]);
                  e.setFrame(i, s, a)
                }
                s.push(e)
              }
              let a = t.readInt(!0);
              if (a > 0) {
                let e = new tt(a);
                for (let s = 0; s < a; s++) {
                  let n = t.readFloat(),
                    r = i.events[t.readInt(!0)],
                    a = new Jt(n, r);
                  a.intValue = t.readInt(!1), a.floatValue = t.readFloat(), a.stringValue = t.readString(), null == a.stringValue && (a.stringValue = r.stringValue), a.data.audioPath && (a.volume = t.readFloat(), a.balance = t.readFloat()), e.setFrame(s, a)
                }
                s.push(e)
              }
              let o = 0;
              for (let t = 0, e = s.length; t < e; t++) o = Math.max(o, s[t].getDuration());
              return new A(e, s, o)
            }
          },
          xe = class {
            constructor(t, e = new Array, i = 0, s = new DataView(t instanceof ArrayBuffer ? t : t.buffer)) {
              this.strings = e, this.index = i, this.buffer = s
            }
            readByte() {
              return this.buffer.getInt8(this.index++)
            }
            readUnsignedByte() {
              return this.buffer.getUint8(this.index++)
            }
            readShort() {
              let t = this.buffer.getInt16(this.index);
              return this.index += 2, t
            }
            readInt32() {
              let t = this.buffer.getInt32(this.index);
              return this.index += 4, t
            }
            readInt(t) {
              let e = this.readByte(),
                i = 127 & e;
              return !!(128 & e) && (e = this.readByte(), i |= (127 & e) << 7, !!(128 & e) && (e = this.readByte(), i |= (127 & e) << 14, !!(128 & e) && (e = this.readByte(), i |= (127 & e) << 21, !!(128 & e) && (e = this.readByte(), i |= (127 & e) << 28)))), t ? i : i >>> 1 ^ -(1 & i)
            }
            readStringRef() {
              let t = this.readInt(!0);
              return 0 == t ? null : this.strings[t - 1]
            }
            readString() {
              let t = this.readInt(!0);
              switch (t) {
                case 0:
                  return null;
                case 1:
                  return ""
              }
              t--;
              let e = "";
              for (let i = 0; i < t;) {
                let t = this.readUnsignedByte();
                switch (t >> 4) {
                  case 12:
                  case 13:
                    e += String.fromCharCode((31 & t) << 6 | 63 & this.readByte()), i += 2;
                    break;
                  case 14:
                    e += String.fromCharCode((15 & t) << 12 | (63 & this.readByte()) << 6 | 63 & this.readByte()), i += 3;
                    break;
                  default:
                    e += String.fromCharCode(t), i++
                }
              }
              return e
            }
            readFloat() {
              let t = this.buffer.getFloat32(this.index);
              return this.index += 4, t
            }
            readBoolean() {
              return 0 != this.readByte()
            }
          },
          we = class {
            parent;
            skinIndex;
            slotIndex;
            mesh;
            inheritTimeline;
            constructor(t, e, i, s, n) {
              this.mesh = t, this.skinIndex = e, this.slotIndex = i, this.parent = s, this.inheritTimeline = n
            }
          },
          Se = class {
            constructor(t = null, e = null, i = 0) {
              this.bones = t, this.vertices = e, this.length = i
            }
          };

        function Te(t, e, i) {
          let s = t.readFloat(),
            n = t.readFloat() * i;
          for (let r = 0, a = 0, o = e.getFrameCount() - 1; e.setFrame(r, s, n), r != o; r++) {
            let o = t.readFloat(),
              h = t.readFloat() * i;
            switch (t.readByte()) {
              case si:
                e.setStepped(r);
                break;
              case ni:
                ke(t, e, a++, r, 0, s, o, n, h, i)
            }
            s = o, n = h
          }
          return e
        }

        function Ce(t, e, i) {
          let s = t.readFloat(),
            n = t.readFloat() * i,
            r = t.readFloat() * i;
          for (let a = 0, o = 0, h = e.getFrameCount() - 1; e.setFrame(a, s, n, r), a != h; a++) {
            let h = t.readFloat(),
              l = t.readFloat() * i,
              c = t.readFloat() * i;
            switch (t.readByte()) {
              case si:
                e.setStepped(a);
                break;
              case ni:
                ke(t, e, o++, a, 0, s, h, n, l, i), ke(t, e, o++, a, 1, s, h, r, c, i)
            }
            s = h, n = l, r = c
          }
          return e
        }

        function ke(t, e, i, s, n, r, a, o, h, l) {
          e.setBezier(i, s, n, r, o, t.readFloat(), t.readFloat() * l, t.readFloat(), t.readFloat() * l, a, h)
        }
        var Pe = 0,
          Ae = 1,
          Ie = 2,
          Ee = 3,
          Oe = 4,
          Me = 5,
          Be = 6,
          Re = 7,
          De = 8,
          Le = 9,
          Fe = 10,
          Ne = 0,
          Ve = 1,
          ze = 2,
          Ue = 3,
          He = 4,
          We = 5,
          Ye = 0,
          Ge = 1,
          Xe = 0,
          je = 1,
          $e = 2,
          Ke = 0,
          qe = 1,
          Ze = 2,
          Qe = 4,
          Je = 5,
          ti = 6,
          ei = 7,
          ii = 8,
          si = 1,
          ni = 2,
          ri = class {
            minX = 0;
            minY = 0;
            maxX = 0;
            maxY = 0;
            boundingBoxes = new Array;
            polygons = new Array;
            polygonPool = new b(() => y.newFloatArray(16));
            update(t, e) {
              if (!t) throw new Error("skeleton cannot be null.");
              let i = this.boundingBoxes,
                s = this.polygons,
                n = this.polygonPool,
                r = t.slots,
                a = r.length;
              i.length = 0, n.freeAll(s), s.length = 0;
              for (let t = 0; t < a; t++) {
                let e = r[t];
                if (!e.bone.active) continue;
                let a = e.getAttachment();
                if (a instanceof Et) {
                  let t = a;
                  i.push(t);
                  let r = n.obtain();
                  r.length != t.worldVerticesLength && (r = y.newFloatArray(t.worldVerticesLength)), s.push(r), t.computeWorldVertices(e, 0, t.worldVerticesLength, r, 0, 2)
                }
              }
              e ? this.aabbCompute() : (this.minX = Number.POSITIVE_INFINITY, this.minY = Number.POSITIVE_INFINITY, this.maxX = Number.NEGATIVE_INFINITY, this.maxY = Number.NEGATIVE_INFINITY)
            }
            aabbCompute() {
              let t = Number.POSITIVE_INFINITY,
                e = Number.POSITIVE_INFINITY,
                i = Number.NEGATIVE_INFINITY,
                s = Number.NEGATIVE_INFINITY,
                n = this.polygons;
              for (let r = 0, a = n.length; r < a; r++) {
                let a = n[r],
                  o = a;
                for (let n = 0, r = a.length; n < r; n += 2) {
                  let r = o[n],
                    a = o[n + 1];
                  t = Math.min(t, r), e = Math.min(e, a), i = Math.max(i, r), s = Math.max(s, a)
                }
              }
              this.minX = t, this.minY = e, this.maxX = i, this.maxY = s
            }
            aabbContainsPoint(t, e) {
              return t >= this.minX && t <= this.maxX && e >= this.minY && e <= this.maxY
            }
            aabbIntersectsSegment(t, e, i, s) {
              let n = this.minX,
                r = this.minY,
                a = this.maxX,
                o = this.maxY;
              if (t <= n && i <= n || e <= r && s <= r || t >= a && i >= a || e >= o && s >= o) return !1;
              let h = (s - e) / (i - t),
                l = h * (n - t) + e;
              if (l > r && l < o || (l = h * (a - t) + e, l > r && l < o)) return !0;
              let c = (r - e) / h + t;
              return c > n && c < a || (c = (o - e) / h + t, c > n && c < a)
            }
            aabbIntersectsSkeleton(t) {
              return this.minX < t.maxX && this.maxX > t.minX && this.minY < t.maxY && this.maxY > t.minY
            }
            containsPoint(t, e) {
              let i = this.polygons;
              for (let s = 0, n = i.length; s < n; s++)
                if (this.containsPointPolygon(i[s], t, e)) return this.boundingBoxes[s];
              return null
            }
            containsPointPolygon(t, e, i) {
              let s = t,
                n = t.length,
                r = n - 2,
                a = !1;
              for (let t = 0; t < n; t += 2) {
                let n = s[t + 1],
                  o = s[r + 1];
                if (n < i && o >= i || o < i && n >= i) {
                  let h = s[t];
                  h + (i - n) / (o - n) * (s[r] - h) < e && (a = !a)
                }
                r = t
              }
              return a
            }
            intersectsSegment(t, e, i, s) {
              let n = this.polygons;
              for (let r = 0, a = n.length; r < a; r++)
                if (this.intersectsSegmentPolygon(n[r], t, e, i, s)) return this.boundingBoxes[r];
              return null
            }
            intersectsSegmentPolygon(t, e, i, s, n) {
              let r = t,
                a = t.length,
                o = e - s,
                h = i - n,
                l = e * n - i * s,
                c = r[a - 2],
                d = r[a - 1];
              for (let t = 0; t < a; t += 2) {
                let a = r[t],
                  u = r[t + 1],
                  p = c * u - d * a,
                  g = c - a,
                  m = d - u,
                  f = o * m - h * g,
                  y = (l * g - o * p) / f;
                if ((y >= c && y <= a || y >= a && y <= c) && (y >= e && y <= s || y >= s && y <= e)) {
                  let t = (l * m - h * p) / f;
                  if ((t >= d && t <= u || t >= u && t <= d) && (t >= i && t <= n || t >= n && t <= i)) return !0
                }
                c = a, d = u
              }
              return !1
            }
            getPolygon(t) {
              if (!t) throw new Error("boundingBox cannot be null.");
              let e = this.boundingBoxes.indexOf(t);
              return -1 == e ? null : this.polygons[e]
            }
            getWidth() {
              return this.maxX - this.minX
            }
            getHeight() {
              return this.maxY - this.minY
            }
          },
          ai = class t {
            convexPolygons = new Array;
            convexPolygonsIndices = new Array;
            indicesArray = new Array;
            isConcaveArray = new Array;
            triangles = new Array;
            polygonPool = new b(() => new Array);
            polygonIndicesPool = new b(() => new Array);
            triangulate(e) {
              let i = e,
                s = e.length >> 1,
                n = this.indicesArray;
              n.length = 0;
              for (let t = 0; t < s; t++) n[t] = t;
              let r = this.isConcaveArray;
              r.length = 0;
              for (let e = 0, a = s; e < a; ++e) r[e] = t.isConcave(e, s, i, n);
              let a = this.triangles;
              for (a.length = 0; s > 3;) {
                let e = s - 1,
                  o = 0,
                  h = 1;
                for (;;) {
                  t: if (!r[o]) {
                    let a = n[e] << 1,
                      l = n[o] << 1,
                      c = n[h] << 1,
                      d = i[a],
                      u = i[a + 1],
                      p = i[l],
                      g = i[l + 1],
                      m = i[c],
                      f = i[c + 1];
                    for (let a = (h + 1) % s; a != e; a = (a + 1) % s) {
                      if (!r[a]) continue;
                      let e = n[a] << 1,
                        s = i[e],
                        o = i[e + 1];
                      if (t.positiveArea(m, f, d, u, s, o) && t.positiveArea(d, u, p, g, s, o) && t.positiveArea(p, g, m, f, s, o)) break t
                    }
                    break
                  }if (0 == h) {
                    do {
                      if (!r[o]) break;
                      o--
                    } while (o > 0);
                    break
                  }
                  e = o,
                  o = h,
                  h = (h + 1) % s
                }
                a.push(n[(s + o - 1) % s]), a.push(n[o]), a.push(n[(o + 1) % s]), n.splice(o, 1), r.splice(o, 1), s--;
                let l = (s + o - 1) % s,
                  c = o == s ? 0 : o;
                r[l] = t.isConcave(l, s, i, n), r[c] = t.isConcave(c, s, i, n)
              }
              return 3 == s && (a.push(n[2]), a.push(n[0]), a.push(n[1])), a
            }
            decompose(e, i) {
              let s = e,
                n = this.convexPolygons;
              this.polygonPool.freeAll(n), n.length = 0;
              let r = this.convexPolygonsIndices;
              this.polygonIndicesPool.freeAll(r), r.length = 0;
              let a = this.polygonIndicesPool.obtain();
              a.length = 0;
              let o = this.polygonPool.obtain();
              o.length = 0;
              let h = -1,
                l = 0;
              for (let e = 0, c = i.length; e < c; e += 3) {
                let c = i[e] << 1,
                  d = i[e + 1] << 1,
                  u = i[e + 2] << 1,
                  p = s[c],
                  g = s[c + 1],
                  m = s[d],
                  f = s[d + 1],
                  y = s[u],
                  _ = s[u + 1],
                  b = !1;
                if (h == c) {
                  let e = o.length - 4,
                    i = t.winding(o[e], o[e + 1], o[e + 2], o[e + 3], y, _),
                    s = t.winding(y, _, o[0], o[1], o[2], o[3]);
                  i == l && s == l && (o.push(y), o.push(_), a.push(u), b = !0)
                }
                b || (o.length > 0 ? (n.push(o), r.push(a)) : (this.polygonPool.free(o), this.polygonIndicesPool.free(a)), o = this.polygonPool.obtain(), o.length = 0, o.push(p), o.push(g), o.push(m), o.push(f), o.push(y), o.push(_), a = this.polygonIndicesPool.obtain(), a.length = 0, a.push(c), a.push(d), a.push(u), l = t.winding(p, g, m, f, y, _), h = c)
              }
              o.length > 0 && (n.push(o), r.push(a));
              for (let e = 0, i = n.length; e < i; e++) {
                if (a = r[e], 0 == a.length) continue;
                let s = a[0],
                  h = a[a.length - 1];
                o = n[e];
                let l = o.length - 4,
                  c = o[l],
                  d = o[l + 1],
                  u = o[l + 2],
                  p = o[l + 3],
                  g = o[0],
                  m = o[1],
                  f = o[2],
                  y = o[3],
                  _ = t.winding(c, d, u, p, g, m);
                for (let l = 0; l < i; l++) {
                  if (l == e) continue;
                  let i = r[l];
                  if (3 != i.length) continue;
                  let b = i[0],
                    v = i[1],
                    x = i[2],
                    w = n[l],
                    S = w[w.length - 2],
                    T = w[w.length - 1];
                  if (b != s || v != h) continue;
                  let C = t.winding(c, d, u, p, S, T),
                    k = t.winding(S, T, g, m, f, y);
                  C == _ && k == _ && (w.length = 0, i.length = 0, o.push(S), o.push(T), a.push(x), c = u, d = p, u = S, p = T, l = 0)
                }
              }
              for (let t = n.length - 1; t >= 0; t--) o = n[t], 0 == o.length && (n.splice(t, 1), this.polygonPool.free(o), a = r[t], r.splice(t, 1), this.polygonIndicesPool.free(a));
              return n
            }
            static isConcave(t, e, i, s) {
              let n = s[(e + t - 1) % e] << 1,
                r = s[t] << 1,
                a = s[(t + 1) % e] << 1;
              return !this.positiveArea(i[n], i[n + 1], i[r], i[r + 1], i[a], i[a + 1])
            }
            static positiveArea(t, e, i, s, n, r) {
              return t * (r - s) + i * (e - r) + n * (s - e) >= 0
            }
            static winding(t, e, i, s, n, r) {
              let a = i - t,
                o = s - e;
              return n * o - r * a + a * e - t * o >= 0 ? 1 : -1
            }
          },
          oi = class t {
            triangulator = new ai;
            clippingPolygon = new Array;
            clipOutput = new Array;
            clippedVertices = new Array;
            clippedUVs = new Array;
            clippedTriangles = new Array;
            scratch = new Array;
            clipAttachment = null;
            clippingPolygons = null;
            clipStart(e, i) {
              if (this.clipAttachment) return 0;
              this.clipAttachment = i;
              let s = i.worldVerticesLength,
                n = y.setArraySize(this.clippingPolygon, s);
              i.computeWorldVertices(e, 0, s, n, 0, 2);
              let r = this.clippingPolygon;
              t.makeClockwise(r);
              let a = this.clippingPolygons = this.triangulator.decompose(r, this.triangulator.triangulate(r));
              for (let e = 0, i = a.length; e < i; e++) {
                let i = a[e];
                t.makeClockwise(i), i.push(i[0]), i.push(i[1])
              }
              return a.length
            }
            clipEndWithSlot(t) {
              this.clipAttachment && this.clipAttachment.endSlot == t.data && this.clipEnd()
            }
            clipEnd() {
              this.clipAttachment && (this.clipAttachment = null, this.clippingPolygons = null, this.clippedVertices.length = 0, this.clippedTriangles.length = 0, this.clippingPolygon.length = 0)
            }
            isClipping() {
              return null != this.clipAttachment
            }
            clipTriangles(t, e, i, s, n, r, a, o) {
              let h, l, c, d, u, p;
              "number" == typeof e ? (h = i, l = s, c = n, d = r, u = a, p = o) : (h = e, l = i, c = s, d = n, u = r, p = a), c && d && u && "boolean" == typeof p ? this.clipTrianglesRender(t, h, l, c, d, u, p) : this.clipTrianglesNoRender(t, h, l)
            }
            clipTrianglesNoRender(t, e, i) {
              let s = this.clipOutput,
                n = this.clippedVertices,
                r = this.clippedTriangles,
                a = this.clippingPolygons,
                o = a.length,
                h = 0;
              n.length = 0, r.length = 0;
              for (let l = 0; l < i; l += 3) {
                let i = e[l] << 1,
                  c = t[i],
                  d = t[i + 1];
                i = e[l + 1] << 1;
                let u = t[i],
                  p = t[i + 1];
                i = e[l + 2] << 1;
                let g = t[i],
                  m = t[i + 1];
                for (let t = 0; t < o; t++) {
                  let e = n.length;
                  if (!this.clip(c, d, u, p, g, m, a[t], s)) {
                    let t = y.setArraySize(n, e + 6);
                    t[e] = c, t[e + 1] = d, t[e + 2] = u, t[e + 3] = p, t[e + 4] = g, t[e + 5] = m, e = r.length;
                    let i = y.setArraySize(r, e + 3);
                    i[e] = h, i[e + 1] = h + 1, i[e + 2] = h + 2, h += 3;
                    break
                  } {
                    let t = s.length;
                    if (0 == t) continue;
                    let i = t >> 1,
                      a = this.clipOutput,
                      o = y.setArraySize(n, e + 2 * i);
                    for (let i = 0; i < t; i += 2, e += 2) {
                      let t = a[i],
                        s = a[i + 1];
                      o[e] = t, o[e + 1] = s
                    }
                    e = r.length;
                    let l = y.setArraySize(r, e + 3 * (i - 2));
                    i--;
                    for (let t = 1; t < i; t++, e += 3) l[e] = h, l[e + 1] = h + t, l[e + 2] = h + t + 1;
                    h += i + 1
                  }
                }
              }
            }
            clipTrianglesRender(t, e, i, s, n, r, a) {
              let o = this.clipOutput,
                h = this.clippedVertices,
                l = this.clippedTriangles,
                c = this.clippingPolygons,
                d = c.length,
                u = a ? 12 : 8,
                p = 0;
              h.length = 0, l.length = 0;
              for (let g = 0; g < i; g += 3) {
                let i = e[g] << 1,
                  m = t[i],
                  f = t[i + 1],
                  _ = s[i],
                  b = s[i + 1];
                i = e[g + 1] << 1;
                let v = t[i],
                  x = t[i + 1],
                  w = s[i],
                  S = s[i + 1];
                i = e[g + 2] << 1;
                let T = t[i],
                  C = t[i + 1],
                  k = s[i],
                  P = s[i + 1];
                for (let t = 0; t < d; t++) {
                  let e = h.length;
                  if (!this.clip(m, f, v, x, T, C, c[t], o)) {
                    let t = y.setArraySize(h, e + 3 * u);
                    t[e] = m, t[e + 1] = f, t[e + 2] = n.r, t[e + 3] = n.g, t[e + 4] = n.b, t[e + 5] = n.a, a ? (t[e + 6] = _, t[e + 7] = b, t[e + 8] = r.r, t[e + 9] = r.g, t[e + 10] = r.b, t[e + 11] = r.a, t[e + 12] = v, t[e + 13] = x, t[e + 14] = n.r, t[e + 15] = n.g, t[e + 16] = n.b, t[e + 17] = n.a, t[e + 18] = w, t[e + 19] = S, t[e + 20] = r.r, t[e + 21] = r.g, t[e + 22] = r.b, t[e + 23] = r.a, t[e + 24] = T, t[e + 25] = C, t[e + 26] = n.r, t[e + 27] = n.g, t[e + 28] = n.b, t[e + 29] = n.a, t[e + 30] = k, t[e + 31] = P, t[e + 32] = r.r, t[e + 33] = r.g, t[e + 34] = r.b, t[e + 35] = r.a) : (t[e + 6] = _, t[e + 7] = b, t[e + 8] = v, t[e + 9] = x, t[e + 10] = n.r, t[e + 11] = n.g, t[e + 12] = n.b, t[e + 13] = n.a, t[e + 14] = w, t[e + 15] = S, t[e + 16] = T, t[e + 17] = C, t[e + 18] = n.r, t[e + 19] = n.g, t[e + 20] = n.b, t[e + 21] = n.a, t[e + 22] = k, t[e + 23] = P), e = l.length;
                    let i = y.setArraySize(l, e + 3);
                    i[e] = p, i[e + 1] = p + 1, i[e + 2] = p + 2, p += 3;
                    break
                  } {
                    let t = o.length;
                    if (0 == t) continue;
                    let i = x - C,
                      s = T - v,
                      c = m - T,
                      d = C - f,
                      g = 1 / (i * c + s * (f - C)),
                      A = t >> 1,
                      I = this.clipOutput,
                      E = y.setArraySize(h, e + A * u);
                    for (let o = 0; o < t; o += 2, e += u) {
                      let t = I[o],
                        h = I[o + 1];
                      E[e] = t, E[e + 1] = h, E[e + 2] = n.r, E[e + 3] = n.g, E[e + 4] = n.b, E[e + 5] = n.a;
                      let l = t - T,
                        u = h - C,
                        p = (i * l + s * u) * g,
                        m = (d * l + c * u) * g,
                        f = 1 - p - m;
                      E[e + 6] = _ * p + w * m + k * f, E[e + 7] = b * p + S * m + P * f, a && (E[e + 8] = r.r, E[e + 9] = r.g, E[e + 10] = r.b, E[e + 11] = r.a)
                    }
                    e = l.length;
                    let O = y.setArraySize(l, e + 3 * (A - 2));
                    A--;
                    for (let t = 1; t < A; t++, e += 3) O[e] = p, O[e + 1] = p + t, O[e + 2] = p + t + 1;
                    p += A + 1
                  }
                }
              }
            }
            clipTrianglesUnpacked(t, e, i, s) {
              let n = this.clipOutput,
                r = this.clippedVertices,
                a = this.clippedUVs,
                o = this.clippedTriangles,
                h = this.clippingPolygons,
                l = h.length,
                c = 0;
              r.length = 0, a.length = 0, o.length = 0;
              for (let d = 0; d < i; d += 3) {
                let i = e[d] << 1,
                  u = t[i],
                  p = t[i + 1],
                  g = s[i],
                  m = s[i + 1];
                i = e[d + 1] << 1;
                let f = t[i],
                  _ = t[i + 1],
                  b = s[i],
                  v = s[i + 1];
                i = e[d + 2] << 1;
                let x = t[i],
                  w = t[i + 1],
                  S = s[i],
                  T = s[i + 1];
                for (let t = 0; t < l; t++) {
                  let e = r.length;
                  if (!this.clip(u, p, f, _, x, w, h[t], n)) {
                    let t = y.setArraySize(r, e + 6);
                    t[e] = u, t[e + 1] = p, t[e + 2] = f, t[e + 3] = _, t[e + 4] = x, t[e + 5] = w;
                    let i = y.setArraySize(a, e + 6);
                    i[e] = g, i[e + 1] = m, i[e + 2] = b, i[e + 3] = v, i[e + 4] = S, i[e + 5] = T, e = o.length;
                    let s = y.setArraySize(o, e + 3);
                    s[e] = c, s[e + 1] = c + 1, s[e + 2] = c + 2, c += 3;
                    break
                  } {
                    let t = n.length;
                    if (0 == t) continue;
                    let i = _ - w,
                      s = x - f,
                      h = u - x,
                      l = w - p,
                      d = 1 / (i * h + s * (p - w)),
                      C = t >> 1,
                      k = this.clipOutput,
                      P = y.setArraySize(r, e + 2 * C),
                      A = y.setArraySize(a, e + 2 * C);
                    for (let n = 0; n < t; n += 2, e += 2) {
                      let t = k[n],
                        r = k[n + 1];
                      P[e] = t, P[e + 1] = r;
                      let a = t - x,
                        o = r - w,
                        c = (i * a + s * o) * d,
                        u = (l * a + h * o) * d,
                        p = 1 - c - u;
                      A[e] = g * c + b * u + S * p, A[e + 1] = m * c + v * u + T * p
                    }
                    e = o.length;
                    let I = y.setArraySize(o, e + 3 * (C - 2));
                    C--;
                    for (let t = 1; t < C; t++, e += 3) I[e] = c, I[e + 1] = c + t, I[e + 2] = c + t + 1;
                    c += C + 1
                  }
                }
              }
            }
            clip(t, e, i, s, n, r, a, o) {
              let h, l = o,
                c = !1;
              a.length % 4 >= 2 ? (h = o, o = this.scratch) : h = this.scratch, h.length = 0, h.push(t), h.push(e), h.push(i), h.push(s), h.push(n), h.push(r), h.push(t), h.push(e), o.length = 0;
              let d = a.length - 4,
                u = a;
              for (let t = 0;; t += 2) {
                let e = u[t],
                  i = u[t + 1],
                  s = e - u[t + 2],
                  n = i - u[t + 3],
                  r = o.length,
                  a = h;
                for (let t = 0, r = h.length - 2; t < r;) {
                  let r = a[t],
                    h = a[t + 1];
                  t += 2;
                  let l = a[t],
                    d = a[t + 1],
                    u = n * (e - l) > s * (i - d),
                    p = n * (e - r) - s * (i - h);
                  if (p > 0) {
                    if (u) {
                      o.push(l), o.push(d);
                      continue
                    }
                    let t = l - r,
                      e = d - h,
                      i = p / (t * n - e * s);
                    if (!(i >= 0 && i <= 1)) {
                      o.push(l), o.push(d);
                      continue
                    }
                    o.push(r + t * i), o.push(h + e * i)
                  } else if (u) {
                    let t = l - r,
                      e = d - h,
                      i = p / (t * n - e * s);
                    if (!(i >= 0 && i <= 1)) {
                      o.push(l), o.push(d);
                      continue
                    }
                    o.push(r + t * i), o.push(h + e * i), o.push(l), o.push(d)
                  }
                  c = !0
                }
                if (r == o.length) return l.length = 0, !0;
                if (o.push(o[0]), o.push(o[1]), t == d) break;
                let p = o;
                (o = h).length = 0, h = p
              }
              if (l != o) {
                l.length = 0;
                for (let t = 0, e = o.length - 2; t < e; t++) l[t] = o[t]
              } else l.length = l.length - 2;
              return c
            }
            static makeClockwise(t) {
              let e = t,
                i = t.length,
                s = e[i - 2] * e[1] - e[0] * e[i - 1],
                n = 0,
                r = 0,
                a = 0,
                o = 0;
              for (let t = 0, h = i - 3; t < h; t += 2) n = e[t], r = e[t + 1], a = e[t + 2], o = e[t + 3], s += n * o - a * r;
              if (!(s < 0))
                for (let t = 0, s = i - 2, n = i >> 1; t < n; t += 2) {
                  let i = e[t],
                    n = e[t + 1],
                    r = s - t;
                  e[t] = e[r], e[t + 1] = e[r + 1], e[r] = i, e[r + 1] = n
                }
            }
          },
          hi = class {
            attachmentLoader;
            scale = 1;
            linkedMeshes = new Array;
            constructor(t) {
              this.attachmentLoader = t
            }
            readSkeletonData(t) {
              let e = this.scale,
                i = new ge,
                s = "string" == typeof t ? JSON.parse(t) : t,
                n = s.skeleton;
              if (n && (i.hash = n.hash, i.version = n.spine, i.x = n.x, i.y = n.y, i.width = n.width, i.height = n.height, i.referenceScale = pi(n, "referenceScale", 100) * e, i.fps = n.fps, i.imagesPath = n.images ?? null, i.audioPath = n.audio ?? null), s.bones)
                for (let t = 0; t < s.bones.length; t++) {
                  let n = s.bones[t],
                    r = null,
                    a = pi(n, "parent", null);
                  a && (r = i.findBone(a));
                  let o = new Xt(i.bones.length, n.name, r);
                  o.length = pi(n, "length", 0) * e, o.x = pi(n, "x", 0) * e, o.y = pi(n, "y", 0) * e, o.rotation = pi(n, "rotation", 0), o.scaleX = pi(n, "scaleX", 1), o.scaleY = pi(n, "scaleY", 1), o.shearX = pi(n, "shearX", 0), o.shearY = pi(n, "shearY", 0), o.inherit = y.enumValue(jt, pi(n, "inherit", "Normal")), o.skinRequired = pi(n, "skin", !1);
                  let h = pi(n, "color", null);
                  h && o.color.setFromString(h), i.bones.push(o)
                }
              if (s.slots)
                for (let t = 0; t < s.slots.length; t++) {
                  let e = s.slots[t],
                    n = e.name,
                    r = i.findBone(e.bone);
                  if (!r) throw new Error(`Couldn't find bone ${e.bone} for slot ${n}`);
                  let a = new ye(i.slots.length, n, r),
                    o = pi(e, "color", null);
                  o && a.color.setFromString(o);
                  let h = pi(e, "dark", null);
                  h && (a.darkColor = u.fromString(h)), a.attachmentName = pi(e, "attachment", null), a.blendMode = y.enumValue(_e, pi(e, "blend", "normal")), a.visible = pi(e, "visible", !0), i.slots.push(a)
                }
              if (s.ik)
                for (let t = 0; t < s.ik.length; t++) {
                  let n = s.ik[t],
                    r = new ie(n.name);
                  r.order = pi(n, "order", 0), r.skinRequired = pi(n, "skin", !1);
                  for (let t = 0; t < n.bones.length; t++) {
                    let e = i.findBone(n.bones[t]);
                    if (!e) throw new Error(`Couldn't find bone ${n.bones[t]} for IK constraint ${n.name}.`);
                    r.bones.push(e)
                  }
                  let a = i.findBone(n.target);
                  if (!a) throw new Error(`Couldn't find target bone ${n.target} for IK constraint ${n.name}.`);
                  r.target = a, r.mix = pi(n, "mix", 1), r.softness = pi(n, "softness", 0) * e, r.bendDirection = pi(n, "bendPositive", !0) ? 1 : -1, r.compress = pi(n, "compress", !1), r.stretch = pi(n, "stretch", !1), r.uniform = pi(n, "uniform", !1), i.ikConstraints.push(r)
                }
              if (s.transform)
                for (let t = 0; t < s.transform.length; t++) {
                  let n = s.transform[t],
                    r = new be(n.name);
                  r.order = pi(n, "order", 0), r.skinRequired = pi(n, "skin", !1);
                  for (let t = 0; t < n.bones.length; t++) {
                    let e = n.bones[t],
                      s = i.findBone(e);
                    if (!s) throw new Error(`Couldn't find bone ${e} for transform constraint ${n.name}.`);
                    r.bones.push(s)
                  }
                  let a = n.target,
                    o = i.findBone(a);
                  if (!o) throw new Error(`Couldn't find target bone ${a} for transform constraint ${n.name}.`);
                  r.target = o, r.local = pi(n, "local", !1), r.relative = pi(n, "relative", !1), r.offsetRotation = pi(n, "rotation", 0), r.offsetX = pi(n, "x", 0) * e, r.offsetY = pi(n, "y", 0) * e, r.offsetScaleX = pi(n, "scaleX", 0), r.offsetScaleY = pi(n, "scaleY", 0), r.offsetShearY = pi(n, "shearY", 0), r.mixRotate = pi(n, "mixRotate", 1), r.mixX = pi(n, "mixX", 1), r.mixY = pi(n, "mixY", r.mixX), r.mixScaleX = pi(n, "mixScaleX", 1), r.mixScaleY = pi(n, "mixScaleY", r.mixScaleX), r.mixShearY = pi(n, "mixShearY", 1), i.transformConstraints.push(r)
                }
              if (s.path)
                for (let t = 0; t < s.path.length; t++) {
                  let n = s.path[t],
                    r = new se(n.name);
                  r.order = pi(n, "order", 0), r.skinRequired = pi(n, "skin", !1);
                  for (let t = 0; t < n.bones.length; t++) {
                    let e = n.bones[t],
                      s = i.findBone(e);
                    if (!s) throw new Error(`Couldn't find bone ${e} for path constraint ${n.name}.`);
                    r.bones.push(s)
                  }
                  let a = n.target,
                    o = i.findSlot(a);
                  if (!o) throw new Error(`Couldn't find target slot ${a} for path constraint ${n.name}.`);
                  r.target = o, r.positionMode = y.enumValue(ne, pi(n, "positionMode", "Percent")), r.spacingMode = y.enumValue(re, pi(n, "spacingMode", "Length")), r.rotateMode = y.enumValue(ae, pi(n, "rotateMode", "Tangent")), r.offsetRotation = pi(n, "rotation", 0), r.position = pi(n, "position", 0), 0 == r.positionMode && (r.position *= e), r.spacing = pi(n, "spacing", 0), (0 == r.spacingMode || 1 == r.spacingMode) && (r.spacing *= e), r.mixRotate = pi(n, "mixRotate", 1), r.mixX = pi(n, "mixX", 1), r.mixY = pi(n, "mixY", r.mixX), i.pathConstraints.push(r)
                }
              if (s.physics)
                for (let t = 0; t < s.physics.length; t++) {
                  const n = s.physics[t],
                    r = new pe(n.name);
                  r.order = pi(n, "order", 0), r.skinRequired = pi(n, "skin", !1);
                  const a = n.bone,
                    o = i.findBone(a);
                  if (null == o) throw new Error("Physics bone not found: " + a);
                  r.bone = o, r.x = pi(n, "x", 0), r.y = pi(n, "y", 0), r.rotate = pi(n, "rotate", 0), r.scaleX = pi(n, "scaleX", 0), r.shearX = pi(n, "shearX", 0), r.limit = pi(n, "limit", 5e3) * e, r.step = 1 / pi(n, "fps", 60), r.inertia = pi(n, "inertia", 1), r.strength = pi(n, "strength", 100), r.damping = pi(n, "damping", 1), r.massInverse = 1 / pi(n, "mass", 1), r.wind = pi(n, "wind", 0), r.gravity = pi(n, "gravity", 0), r.mix = pi(n, "mix", 1), r.inertiaGlobal = pi(n, "inertiaGlobal", !1), r.strengthGlobal = pi(n, "strengthGlobal", !1), r.dampingGlobal = pi(n, "dampingGlobal", !1), r.massGlobal = pi(n, "massGlobal", !1), r.windGlobal = pi(n, "windGlobal", !1), r.gravityGlobal = pi(n, "gravityGlobal", !1), r.mixGlobal = pi(n, "mixGlobal", !1), i.physicsConstraints.push(r)
                }
              if (s.skins)
                for (let t = 0; t < s.skins.length; t++) {
                  let e = s.skins[t],
                    n = new fe(e.name);
                  if (e.bones)
                    for (let t = 0; t < e.bones.length; t++) {
                      let s = e.bones[t],
                        r = i.findBone(s);
                      if (!r) throw new Error(`Couldn't find bone ${s} for skin ${e.name}.`);
                      n.bones.push(r)
                    }
                  if (e.ik)
                    for (let t = 0; t < e.ik.length; t++) {
                      let s = e.ik[t],
                        r = i.findIkConstraint(s);
                      if (!r) throw new Error(`Couldn't find IK constraint ${s} for skin ${e.name}.`);
                      n.constraints.push(r)
                    }
                  if (e.transform)
                    for (let t = 0; t < e.transform.length; t++) {
                      let s = e.transform[t],
                        r = i.findTransformConstraint(s);
                      if (!r) throw new Error(`Couldn't find transform constraint ${s} for skin ${e.name}.`);
                      n.constraints.push(r)
                    }
                  if (e.path)
                    for (let t = 0; t < e.path.length; t++) {
                      let s = e.path[t],
                        r = i.findPathConstraint(s);
                      if (!r) throw new Error(`Couldn't find path constraint ${s} for skin ${e.name}.`);
                      n.constraints.push(r)
                    }
                  if (e.physics)
                    for (let t = 0; t < e.physics.length; t++) {
                      let s = e.physics[t],
                        r = i.findPhysicsConstraint(s);
                      if (!r) throw new Error(`Couldn't find physics constraint ${s} for skin ${e.name}.`);
                      n.constraints.push(r)
                    }
                  for (let t in e.attachments) {
                    let s = i.findSlot(t);
                    if (!s) throw new Error(`Couldn't find slot ${t} for skin ${e.name}.`);
                    let r = e.attachments[t];
                    for (let t in r) {
                      let e = this.readAttachment(r[t], n, s.index, t, i);
                      e && n.setAttachment(s.index, t, e)
                    }
                  }
                  i.skins.push(n), "default" == n.name && (i.defaultSkin = n)
                }
              for (let t = 0, e = this.linkedMeshes.length; t < e; t++) {
                let e = this.linkedMeshes[t],
                  s = e.skin ? i.findSkin(e.skin) : i.defaultSkin;
                if (!s) throw new Error(`Skin not found: ${e.skin}`);
                let n = s.getAttachment(e.slotIndex, e.parent);
                if (!n) throw new Error(`Parent mesh not found: ${e.parent}`);
                e.mesh.timelineAttachment = e.inheritTimeline ? n : e.mesh, e.mesh.setParentMesh(n), null != e.mesh.region && e.mesh.updateRegion()
              }
              if (this.linkedMeshes.length = 0, s.events)
                for (let t in s.events) {
                  let e = s.events[t],
                    n = new te(t);
                  n.intValue = pi(e, "int", 0), n.floatValue = pi(e, "float", 0), n.stringValue = pi(e, "string", ""), n.audioPath = pi(e, "audio", null), n.audioPath && (n.volume = pi(e, "volume", 1), n.balance = pi(e, "balance", 0)), i.events.push(n)
                }
              if (s.animations)
                for (let t in s.animations) {
                  let e = s.animations[t];
                  this.readAnimation(e, t, i)
                }
              return i
            }
            readAttachment(t, e, i, s, n) {
              let r = this.scale;
              switch (s = pi(t, "name", s), pi(t, "type", "region")) {
                case "region": {
                  let i = pi(t, "path", s),
                    n = this.readSequence(pi(t, "sequence", null)),
                    a = this.attachmentLoader.newRegionAttachment(e, s, i, n);
                  if (!a) return null;
                  a.path = i, a.x = pi(t, "x", 0) * r, a.y = pi(t, "y", 0) * r, a.scaleX = pi(t, "scaleX", 1), a.scaleY = pi(t, "scaleY", 1), a.rotation = pi(t, "rotation", 0), a.width = t.width * r, a.height = t.height * r, a.sequence = n;
                  let o = pi(t, "color", null);
                  return o && a.color.setFromString(o), null != a.region && a.updateRegion(), a
                }
                case "boundingbox": {
                  let i = this.attachmentLoader.newBoundingBoxAttachment(e, s);
                  if (!i) return null;
                  this.readVertices(t, i, t.vertexCount << 1);
                  let n = pi(t, "color", null);
                  return n && i.color.setFromString(n), i
                }
                case "mesh":
                case "linkedmesh": {
                  let n = pi(t, "path", s),
                    a = this.readSequence(pi(t, "sequence", null)),
                    o = this.attachmentLoader.newMeshAttachment(e, s, n, a);
                  if (!o) return null;
                  o.path = n;
                  let h = pi(t, "color", null);
                  h && o.color.setFromString(h), o.width = pi(t, "width", 0) * r, o.height = pi(t, "height", 0) * r, o.sequence = a;
                  let l = pi(t, "parent", null);
                  if (l) return this.linkedMeshes.push(new li(o, pi(t, "skin", null), i, l, pi(t, "timelines", !0))), o;
                  let c = t.uvs;
                  return this.readVertices(t, o, c.length), o.triangles = t.triangles, o.regionUVs = c, null != o.region && o.updateRegion(), o.edges = pi(t, "edges", null), o.hullLength = 2 * pi(t, "hull", 0), o
                }
                case "path": {
                  let i = this.attachmentLoader.newPathAttachment(e, s);
                  if (!i) return null;
                  i.closed = pi(t, "closed", !1), i.constantSpeed = pi(t, "constantSpeed", !0);
                  let n = t.vertexCount;
                  this.readVertices(t, i, n << 1);
                  let a = y.newArray(n / 3, 0);
                  for (let e = 0; e < t.lengths.length; e++) a[e] = t.lengths[e] * r;
                  i.lengths = a;
                  let o = pi(t, "color", null);
                  return o && i.color.setFromString(o), i
                }
                case "point": {
                  let i = this.attachmentLoader.newPointAttachment(e, s);
                  if (!i) return null;
                  i.x = pi(t, "x", 0) * r, i.y = pi(t, "y", 0) * r, i.rotation = pi(t, "rotation", 0);
                  let n = pi(t, "color", null);
                  return n && i.color.setFromString(n), i
                }
                case "clipping": {
                  let i = this.attachmentLoader.newClippingAttachment(e, s);
                  if (!i) return null;
                  let r = pi(t, "end", null);
                  r && (i.endSlot = n.findSlot(r));
                  let a = t.vertexCount;
                  this.readVertices(t, i, a << 1);
                  let o = pi(t, "color", null);
                  return o && i.color.setFromString(o), i
                }
              }
              return null
            }
            readSequence(t) {
              if (null == t) return null;
              let e = new C(pi(t, "count", 0));
              return e.start = pi(t, "start", 1), e.digits = pi(t, "digits", 0), e.setupIndex = pi(t, "setup", 0), e
            }
            readVertices(t, e, i) {
              let s = this.scale;
              e.worldVerticesLength = i;
              let n = t.vertices;
              if (i == n.length) {
                let t = y.toFloatArray(n);
                if (1 != s)
                  for (let e = 0, i = n.length; e < i; e++) t[e] *= s;
                return void(e.vertices = t)
              }
              let r = new Array,
                a = new Array;
              for (let t = 0, e = n.length; t < e;) {
                let e = n[t++];
                a.push(e);
                for (let i = t + 4 * e; t < i; t += 4) a.push(n[t]), r.push(n[t + 1] * s), r.push(n[t + 2] * s), r.push(n[t + 3])
              }
              e.bones = a, e.vertices = y.toFloatArray(r)
            }
            readAnimation(t, e, i) {
              let s = this.scale,
                n = new Array;
              if (t.slots)
                for (let e in t.slots) {
                  let s = t.slots[e],
                    r = i.findSlot(e);
                  if (!r) throw new Error("Slot not found: " + e);
                  let a = r.index;
                  for (let t in s) {
                    let e = s[t];
                    if (!e) continue;
                    let i = e.length;
                    if ("attachment" == t) {
                      let t = new Q(i, a);
                      for (let s = 0; s < i; s++) {
                        let i = e[s];
                        t.setFrame(s, pi(i, "time", 0), pi(i, "name", null))
                      }
                      n.push(t)
                    } else if ("rgba" == t) {
                      let t = new j(i, i << 2, a),
                        s = e[0],
                        r = pi(s, "time", 0),
                        o = u.fromString(s.color);
                      for (let i = 0, n = 0;; i++) {
                        t.setFrame(i, r, o.r, o.g, o.b, o.a);
                        let a = e[i + 1];
                        if (!a) {
                          t.shrink(n);
                          break
                        }
                        let h = pi(a, "time", 0),
                          l = u.fromString(a.color),
                          c = s.curve;
                        c && (n = ui(c, t, n, i, 0, r, h, o.r, l.r, 1), n = ui(c, t, n, i, 1, r, h, o.g, l.g, 1), n = ui(c, t, n, i, 2, r, h, o.b, l.b, 1), n = ui(c, t, n, i, 3, r, h, o.a, l.a, 1)), r = h, o = l, s = a
                      }
                      n.push(t)
                    } else if ("rgb" == t) {
                      let t = new $(i, 3 * i, a),
                        s = e[0],
                        r = pi(s, "time", 0),
                        o = u.fromString(s.color);
                      for (let i = 0, n = 0;; i++) {
                        t.setFrame(i, r, o.r, o.g, o.b);
                        let a = e[i + 1];
                        if (!a) {
                          t.shrink(n);
                          break
                        }
                        let h = pi(a, "time", 0),
                          l = u.fromString(a.color),
                          c = s.curve;
                        c && (n = ui(c, t, n, i, 0, r, h, o.r, l.r, 1), n = ui(c, t, n, i, 1, r, h, o.g, l.g, 1), n = ui(c, t, n, i, 2, r, h, o.b, l.b, 1)), r = h, o = l, s = a
                      }
                      n.push(t)
                    } else if ("alpha" == t) n.push(ci(e, new K(i, i, a), 0, 1));
                    else if ("rgba2" == t) {
                      let t = new q(i, 7 * i, a),
                        s = e[0],
                        r = pi(s, "time", 0),
                        o = u.fromString(s.light),
                        h = u.fromString(s.dark);
                      for (let i = 0, n = 0;; i++) {
                        t.setFrame(i, r, o.r, o.g, o.b, o.a, h.r, h.g, h.b);
                        let a = e[i + 1];
                        if (!a) {
                          t.shrink(n);
                          break
                        }
                        let l = pi(a, "time", 0),
                          c = u.fromString(a.light),
                          d = u.fromString(a.dark),
                          p = s.curve;
                        p && (n = ui(p, t, n, i, 0, r, l, o.r, c.r, 1), n = ui(p, t, n, i, 1, r, l, o.g, c.g, 1), n = ui(p, t, n, i, 2, r, l, o.b, c.b, 1), n = ui(p, t, n, i, 3, r, l, o.a, c.a, 1), n = ui(p, t, n, i, 4, r, l, h.r, d.r, 1), n = ui(p, t, n, i, 5, r, l, h.g, d.g, 1), n = ui(p, t, n, i, 6, r, l, h.b, d.b, 1)), r = l, o = c, h = d, s = a
                      }
                      n.push(t)
                    } else if ("rgb2" == t) {
                      let t = new Z(i, 6 * i, a),
                        s = e[0],
                        r = pi(s, "time", 0),
                        o = u.fromString(s.light),
                        h = u.fromString(s.dark);
                      for (let i = 0, n = 0;; i++) {
                        t.setFrame(i, r, o.r, o.g, o.b, h.r, h.g, h.b);
                        let a = e[i + 1];
                        if (!a) {
                          t.shrink(n);
                          break
                        }
                        let l = pi(a, "time", 0),
                          c = u.fromString(a.light),
                          d = u.fromString(a.dark),
                          p = s.curve;
                        p && (n = ui(p, t, n, i, 0, r, l, o.r, c.r, 1), n = ui(p, t, n, i, 1, r, l, o.g, c.g, 1), n = ui(p, t, n, i, 2, r, l, o.b, c.b, 1), n = ui(p, t, n, i, 3, r, l, h.r, d.r, 1), n = ui(p, t, n, i, 4, r, l, h.g, d.g, 1), n = ui(p, t, n, i, 5, r, l, h.b, d.b, 1)), r = l, o = c, h = d, s = a
                      }
                      n.push(t)
                    }
                  }
                }
              if (t.bones)
                for (let e in t.bones) {
                  let r = t.bones[e],
                    a = i.findBone(e);
                  if (!a) throw new Error("Bone not found: " + e);
                  let o = a.index;
                  for (let t in r) {
                    let e = r[t],
                      i = e.length;
                    if (0 != i)
                      if ("rotate" === t) n.push(ci(e, new L(i, i, o), 0, 1));
                      else if ("translate" === t) {
                      let t = new F(i, i << 1, o);
                      n.push(di(e, t, "x", "y", 0, s))
                    } else if ("translatex" === t) {
                      let t = new N(i, i, o);
                      n.push(ci(e, t, 0, s))
                    } else if ("translatey" === t) {
                      let t = new V(i, i, o);
                      n.push(ci(e, t, 0, s))
                    } else if ("scale" === t) {
                      let t = new z(i, i << 1, o);
                      n.push(di(e, t, "x", "y", 1, 1))
                    } else if ("scalex" === t) {
                      let t = new U(i, i, o);
                      n.push(ci(e, t, 1, 1))
                    } else if ("scaley" === t) {
                      let t = new H(i, i, o);
                      n.push(ci(e, t, 1, 1))
                    } else if ("shear" === t) {
                      let t = new W(i, i << 1, o);
                      n.push(di(e, t, "x", "y", 0, 1))
                    } else if ("shearx" === t) {
                      let t = new Y(i, i, o);
                      n.push(ci(e, t, 0, 1))
                    } else if ("sheary" === t) {
                      let t = new G(i, i, o);
                      n.push(ci(e, t, 0, 1))
                    } else if ("inherit" === t) {
                      let t = new X(i, a.index);
                      for (let i = 0; i < e.length; i++) {
                        let s = e[i];
                        t.setFrame(i, pi(s, "time", 0), y.enumValue(jt, pi(s, "inherit", "Normal")))
                      }
                      n.push(t)
                    }
                  }
                }
              if (t.ik)
                for (let e in t.ik) {
                  let r = t.ik[e],
                    a = r[0];
                  if (!a) continue;
                  let o = i.findIkConstraint(e);
                  if (!o) throw new Error("IK Constraint not found: " + e);
                  let h = i.ikConstraints.indexOf(o),
                    l = new it(r.length, r.length << 1, h),
                    c = pi(a, "time", 0),
                    d = pi(a, "mix", 1),
                    u = pi(a, "softness", 0) * s;
                  for (let t = 0, e = 0;; t++) {
                    l.setFrame(t, c, d, u, pi(a, "bendPositive", !0) ? 1 : -1, pi(a, "compress", !1), pi(a, "stretch", !1));
                    let i = r[t + 1];
                    if (!i) {
                      l.shrink(e);
                      break
                    }
                    let n = pi(i, "time", 0),
                      o = pi(i, "mix", 1),
                      h = pi(i, "softness", 0) * s,
                      p = a.curve;
                    p && (e = ui(p, l, e, t, 0, c, n, d, o, 1), e = ui(p, l, e, t, 1, c, n, u, h, s)), c = n, d = o, u = h, a = i
                  }
                  n.push(l)
                }
              if (t.transform)
                for (let e in t.transform) {
                  let s = t.transform[e],
                    r = s[0];
                  if (!r) continue;
                  let a = i.findTransformConstraint(e);
                  if (!a) throw new Error("Transform constraint not found: " + e);
                  let o = i.transformConstraints.indexOf(a),
                    h = new st(s.length, 6 * s.length, o),
                    l = pi(r, "time", 0),
                    c = pi(r, "mixRotate", 1),
                    d = pi(r, "mixX", 1),
                    u = pi(r, "mixY", d),
                    p = pi(r, "mixScaleX", 1),
                    g = pi(r, "mixScaleY", p),
                    m = pi(r, "mixShearY", 1);
                  for (let t = 0, e = 0;; t++) {
                    h.setFrame(t, l, c, d, u, p, g, m);
                    let i = s[t + 1];
                    if (!i) {
                      h.shrink(e);
                      break
                    }
                    let n = pi(i, "time", 0),
                      a = pi(i, "mixRotate", 1),
                      o = pi(i, "mixX", 1),
                      f = pi(i, "mixY", o),
                      y = pi(i, "mixScaleX", 1),
                      _ = pi(i, "mixScaleY", y),
                      b = pi(i, "mixShearY", 1),
                      v = r.curve;
                    v && (e = ui(v, h, e, t, 0, l, n, c, a, 1), e = ui(v, h, e, t, 1, l, n, d, o, 1), e = ui(v, h, e, t, 2, l, n, u, f, 1), e = ui(v, h, e, t, 3, l, n, p, y, 1), e = ui(v, h, e, t, 4, l, n, g, _, 1), e = ui(v, h, e, t, 5, l, n, m, b, 1)), l = n, c = a, d = o, u = f, p = y, g = _, p = y, r = i
                  }
                  n.push(h)
                }
              if (t.path)
                for (let e in t.path) {
                  let r = t.path[e],
                    a = i.findPathConstraint(e);
                  if (!a) throw new Error("Path constraint not found: " + e);
                  let o = i.pathConstraints.indexOf(a);
                  for (let t in r) {
                    let e = r[t],
                      i = e[0];
                    if (!i) continue;
                    let h = e.length;
                    if ("position" === t) {
                      let t = new nt(h, h, o);
                      n.push(ci(e, t, 0, 0 == a.positionMode ? s : 1))
                    } else if ("spacing" === t) {
                      let t = new rt(h, h, o);
                      n.push(ci(e, t, 0, 0 == a.spacingMode || 1 == a.spacingMode ? s : 1))
                    } else if ("mix" === t) {
                      let t = new at(h, 3 * h, o),
                        s = pi(i, "time", 0),
                        r = pi(i, "mixRotate", 1),
                        a = pi(i, "mixX", 1),
                        l = pi(i, "mixY", a);
                      for (let n = 0, o = 0;; n++) {
                        t.setFrame(n, s, r, a, l);
                        let h = e[n + 1];
                        if (!h) {
                          t.shrink(o);
                          break
                        }
                        let c = pi(h, "time", 0),
                          d = pi(h, "mixRotate", 1),
                          u = pi(h, "mixX", 1),
                          p = pi(h, "mixY", u),
                          g = i.curve;
                        g && (o = ui(g, t, o, n, 0, s, c, r, d, 1), o = ui(g, t, o, n, 1, s, c, a, u, 1), o = ui(g, t, o, n, 2, s, c, l, p, 1)), s = c, r = d, a = u, l = p, i = h
                      }
                      n.push(t)
                    }
                  }
                }
              if (t.physics)
                for (let e in t.physics) {
                  let s = t.physics[e],
                    r = -1;
                  if (e.length > 0) {
                    let t = i.findPhysicsConstraint(e);
                    if (!t) throw new Error("Physics constraint not found: " + e);
                    r = i.physicsConstraints.indexOf(t)
                  }
                  for (let t in s) {
                    let e = s[t],
                      i = e[0];
                    if (!i) continue;
                    let a, o = e.length;
                    if ("reset" == t) {
                      const t = new mt(o, r);
                      for (let s = 0; null != i; i = e[s + 1], s++) t.setFrame(s, pi(i, "time", 0));
                      n.push(t);
                      continue
                    }
                    if ("inertia" == t) a = new ht(o, o, r);
                    else if ("strength" == t) a = new lt(o, o, r);
                    else if ("damping" == t) a = new ct(o, o, r);
                    else if ("mass" == t) a = new dt(o, o, r);
                    else if ("wind" == t) a = new ut(o, o, r);
                    else if ("gravity" == t) a = new pt(o, o, r);
                    else {
                      if ("mix" != t) continue;
                      a = new gt(o, o, r)
                    }
                    n.push(ci(e, a, 0, 1))
                  }
                }
              if (t.attachments)
                for (let e in t.attachments) {
                  let r = t.attachments[e],
                    a = i.findSkin(e);
                  if (!a) throw new Error("Skin not found: " + e);
                  for (let t in r) {
                    let e = r[t],
                      o = i.findSlot(t);
                    if (!o) throw new Error("Slot not found: " + t);
                    let h = o.index;
                    for (let t in e) {
                      let i = e[t],
                        r = a.getAttachment(h, t);
                      for (let t in i) {
                        let e = i[t],
                          a = e[0];
                        if (a)
                          if ("deform" == t) {
                            let t = r.bones,
                              i = r.vertices,
                              o = t ? i.length / 3 * 2 : i.length,
                              l = new J(e.length, e.length, h, r),
                              c = pi(a, "time", 0);
                            for (let n = 0, r = 0;; n++) {
                              let h, d = pi(a, "vertices", null);
                              if (d) {
                                h = y.newFloatArray(o);
                                let e = pi(a, "offset", 0);
                                if (y.arrayCopy(d, 0, h, e, d.length), 1 != s)
                                  for (let t = e, i = t + d.length; t < i; t++) h[t] *= s;
                                if (!t)
                                  for (let t = 0; t < o; t++) h[t] += i[t]
                              } else h = t ? y.newFloatArray(o) : i;
                              l.setFrame(n, c, h);
                              let u = e[n + 1];
                              if (!u) {
                                l.shrink(r);
                                break
                              }
                              let p = pi(u, "time", 0),
                                g = a.curve;
                              g && (r = ui(g, l, r, n, 0, c, p, 0, 1, 1)), c = p, a = u
                            }
                            n.push(l)
                          } else if ("sequence" == t) {
                          let t = new ft(e.length, h, r),
                            i = 0;
                          for (let s = 0; s < e.length; s++) {
                            let n = pi(a, "delay", i),
                              r = pi(a, "time", 0),
                              o = k[pi(a, "mode", "hold")],
                              h = pi(a, "index", 0);
                            t.setFrame(s, r, o, h, n), i = n, a = e[s + 1]
                          }
                          n.push(t)
                        }
                      }
                    }
                  }
                }
              if (t.drawOrder) {
                let e = new et(t.drawOrder.length),
                  s = i.slots.length,
                  r = 0;
                for (let n = 0; n < t.drawOrder.length; n++, r++) {
                  let a = t.drawOrder[n],
                    o = null,
                    h = pi(a, "offsets", null);
                  if (h) {
                    o = y.newArray(s, -1);
                    let t = y.newArray(s - h.length, 0),
                      e = 0,
                      n = 0;
                    for (let s = 0; s < h.length; s++) {
                      let r = h[s],
                        a = i.findSlot(r.slot);
                      if (!a) throw new Error("Slot not found: " + a);
                      let l = a.index;
                      for (; e != l;) t[n++] = e++;
                      o[e + r.offset] = e++
                    }
                    for (; e < s;) t[n++] = e++;
                    for (let e = s - 1; e >= 0; e--) - 1 == o[e] && (o[e] = t[--n])
                  }
                  e.setFrame(r, pi(a, "time", 0), o)
                }
                n.push(e)
              }
              if (t.events) {
                let e = new tt(t.events.length),
                  s = 0;
                for (let n = 0; n < t.events.length; n++, s++) {
                  let r = t.events[n],
                    a = i.findEvent(r.name);
                  if (!a) throw new Error("Event not found: " + r.name);
                  let o = new Jt(y.toSinglePrecision(pi(r, "time", 0)), a);
                  o.intValue = pi(r, "int", a.intValue), o.floatValue = pi(r, "float", a.floatValue), o.stringValue = pi(r, "string", a.stringValue), o.data.audioPath && (o.volume = pi(r, "volume", 1), o.balance = pi(r, "balance", 0)), e.setFrame(s, o)
                }
                n.push(e)
              }
              let r = 0;
              for (let t = 0, e = n.length; t < e; t++) r = Math.max(r, n[t].getDuration());
              i.animations.push(new A(e, n, r))
            }
          },
          li = class {
            parent;
            skin;
            slotIndex;
            mesh;
            inheritTimeline;
            constructor(t, e, i, s, n) {
              this.mesh = t, this.skin = e, this.slotIndex = i, this.parent = s, this.inheritTimeline = n
            }
          };

        function ci(t, e, i, s) {
          let n = t[0],
            r = pi(n, "time", 0),
            a = pi(n, "value", i) * s,
            o = 0;
          for (let h = 0;; h++) {
            e.setFrame(h, r, a);
            let l = t[h + 1];
            if (!l) return e.shrink(o), e;
            let c = pi(l, "time", 0),
              d = pi(l, "value", i) * s;
            n.curve && (o = ui(n.curve, e, o, h, 0, r, c, a, d, s)), r = c, a = d, n = l
          }
        }

        function di(t, e, i, s, n, r) {
          let a = t[0],
            o = pi(a, "time", 0),
            h = pi(a, i, n) * r,
            l = pi(a, s, n) * r,
            c = 0;
          for (let d = 0;; d++) {
            e.setFrame(d, o, h, l);
            let u = t[d + 1];
            if (!u) return e.shrink(c), e;
            let p = pi(u, "time", 0),
              g = pi(u, i, n) * r,
              m = pi(u, s, n) * r,
              f = a.curve;
            f && (c = ui(f, e, c, d, 0, o, p, h, g, r), c = ui(f, e, c, d, 1, o, p, l, m, r)), o = p, h = g, l = m, a = u
          }
        }

        function ui(t, e, i, s, n, r, a, o, h, l) {
          if ("stepped" == t) return e.setStepped(s), i;
          let c = n << 2,
            d = t[c],
            u = t[c + 1] * l,
            p = t[c + 2],
            g = t[c + 3] * l;
          return e.setBezier(i, s, n, r, o, d, u, p, g, a, h), i + 1
        }

        function pi(t, e, i) {
          return void 0 !== t[e] ? t[e] : i
        }
        typeof Math.fround > "u" && (Math.fround = function(t) {
          return function(e) {
            return t[0] = e, t[0]
          }
        }(new Float32Array(1)));
        var gi, mi, fi = class extends Mt {
            constructor(t) {
              super(t)
            }
            setFilters(t, e) {}
            setWraps(t, e) {}
            dispose() {}
          },
          yi = y.newFloatArray(8),
          _i = class t {
            static QUAD_TRIANGLES = [0, 1, 2, 2, 3, 0];
            static VERTEX_SIZE = 8;
            ctx;
            triangleRendering = !1;
            debugRendering = !1;
            vertices = y.newFloatArray(8192);
            tempColor = new u;
            constructor(t) {
              this.ctx = t
            }
            draw(t) {
              this.triangleRendering ? this.drawTriangles(t) : this.drawImages(t)
            }
            drawImages(t) {
              let e = this.ctx,
                i = this.tempColor,
                s = t.color,
                n = t.drawOrder;
              this.debugRendering && (e.strokeStyle = "green");
              for (let t = 0, r = n.length; t < r; t++) {
                let r = n[t],
                  a = r.bone;
                if (!a.active) continue;
                let o = r.getAttachment();
                if (!(o instanceof Yt)) continue;
                o.computeWorldVertices(r, yi, 0, 2);
                let h = o.region,
                  l = h.texture.getImage(),
                  c = r.color,
                  d = o.color;
                i.set(s.r * c.r * d.r, s.g * c.g * d.g, s.b * c.b * d.b, s.a * c.a * d.a), e.save(), e.transform(a.a, a.c, a.b, a.d, a.worldX, a.worldY), e.translate(o.offset[0], o.offset[1]), e.rotate(o.rotation * Math.PI / 180);
                let u = o.width / h.originalWidth;
                e.scale(u * o.scaleX, u * o.scaleY);
                let p = h.width,
                  g = h.height;
                if (e.translate(p / 2, g / 2), 90 == o.region.degrees) {
                  let t = p;
                  p = g, g = t, e.rotate(-Math.PI / 2)
                }
                e.scale(1, -1), e.translate(-p / 2, -g / 2), e.globalAlpha = i.a, e.drawImage(l, l.width * h.u, l.height * h.v, p, g, 0, 0, p, g), this.debugRendering && e.strokeRect(0, 0, p, g), e.restore()
              }
            }
            drawTriangles(e) {
              let i = this.ctx,
                s = this.tempColor,
                n = e.color,
                r = e.drawOrder,
                a = null,
                o = this.vertices,
                h = null;
              for (let e = 0, c = r.length; e < c; e++) {
                let c, d = r[e],
                  u = d.getAttachment();
                if (u instanceof Yt) {
                  let e = u;
                  o = this.computeRegionVertices(d, e, !1), h = t.QUAD_TRIANGLES, c = e.region.texture.getImage()
                } else {
                  if (!(u instanceof Ut)) continue;
                  {
                    let t = u;
                    o = this.computeMeshVertices(d, t, !1), h = t.triangles, c = t.region.texture.getImage()
                  }
                }
                if (c) {
                  d.data.blendMode != a && (a = d.data.blendMode);
                  let t = d.color,
                    e = u.color;
                  s.set(n.r * t.r * e.r, n.g * t.g * e.g, n.b * t.b * e.b, n.a * t.a * e.a), i.globalAlpha = s.a;
                  for (var l = 0; l < h.length; l += 3) {
                    let t = 8 * h[l],
                      e = 8 * h[l + 1],
                      s = 8 * h[l + 2],
                      n = o[t],
                      r = o[t + 1],
                      a = o[t + 6],
                      d = o[t + 7],
                      u = o[e],
                      p = o[e + 1],
                      g = o[e + 6],
                      m = o[e + 7],
                      f = o[s],
                      y = o[s + 1],
                      _ = o[s + 6],
                      b = o[s + 7];
                    this.drawTriangle(c, n, r, a, d, u, p, g, m, f, y, _, b), this.debugRendering && (i.strokeStyle = "green", i.beginPath(), i.moveTo(n, r), i.lineTo(u, p), i.lineTo(f, y), i.lineTo(n, r), i.stroke())
                  }
                }
              }
              this.ctx.globalAlpha = 1
            }
            drawTriangle(t, e, i, s, n, r, a, o, h, l, c, d, u) {
              let p = this.ctx;
              const g = t.width - 1,
                m = t.height - 1;
              s *= g, n *= m, o *= g, h *= m, d *= g, u *= m, p.beginPath(), p.moveTo(e, i), p.lineTo(r, a), p.lineTo(l, c), p.closePath();
              let f = (o -= s) * (u -= n) - (d -= s) * (h -= n);
              if (0 == f) return;
              f = 1 / f;
              const y = (u * (r -= e) - h * (l -= e)) * f,
                _ = (u * (a -= i) - h * (c -= i)) * f,
                b = (o * l - d * r) * f,
                v = (o * c - d * a) * f,
                x = e - y * s - b * n,
                w = i - _ * s - v * n;
              p.save(), p.transform(y, _, b, v, x, w), p.clip(), p.drawImage(t, 0, 0), p.restore()
            }
            computeRegionVertices(e, i, s) {
              let n = e.bone.skeleton.color,
                r = e.color,
                a = i.color,
                o = n.a * r.a * a.a,
                h = s ? o : 1,
                l = this.tempColor;
              l.set(n.r * r.r * a.r * h, n.g * r.g * a.g * h, n.b * r.b * a.b * h, o), i.computeWorldVertices(e, this.vertices, 0, t.VERTEX_SIZE);
              let c = this.vertices,
                d = i.uvs;
              return c[Yt.C1R] = l.r, c[Yt.C1G] = l.g, c[Yt.C1B] = l.b, c[Yt.C1A] = l.a, c[Yt.U1] = d[0], c[Yt.V1] = d[1], c[Yt.C2R] = l.r, c[Yt.C2G] = l.g, c[Yt.C2B] = l.b, c[Yt.C2A] = l.a, c[Yt.U2] = d[2], c[Yt.V2] = d[3], c[Yt.C3R] = l.r, c[Yt.C3G] = l.g, c[Yt.C3B] = l.b, c[Yt.C3A] = l.a, c[Yt.U3] = d[4], c[Yt.V3] = d[5], c[Yt.C4R] = l.r, c[Yt.C4G] = l.g, c[Yt.C4B] = l.b, c[Yt.C4A] = l.a, c[Yt.U4] = d[6], c[Yt.V4] = d[7], c
            }
            computeMeshVertices(e, i, s) {
              let n = e.bone.skeleton.color,
                r = e.color,
                a = i.color,
                o = n.a * r.a * a.a,
                h = s ? o : 1,
                l = this.tempColor;
              l.set(n.r * r.r * a.r * h, n.g * r.g * a.g * h, n.b * r.b * a.b * h, o);
              let c = i.worldVerticesLength / 2,
                d = this.vertices;
              d.length < i.worldVerticesLength && (this.vertices = d = y.newFloatArray(i.worldVerticesLength)), i.computeWorldVertices(e, 0, i.worldVerticesLength, d, 0, t.VERTEX_SIZE);
              let u = i.uvs;
              for (let t = 0, e = 0, i = 2; t < c; t++) d[i++] = l.r, d[i++] = l.g, d[i++] = l.b, d[i++] = l.a, d[i++] = u[e++], d[i++] = u[e++], i += 2;
              return d
            }
          },
          bi = class {
            canvas;
            gl;
            restorables = [];
            constructor(t, e = {
              alpha: !0
            }) {
              if (t instanceof WebGLRenderingContext || typeof WebGL2RenderingContext < "u" && t instanceof WebGL2RenderingContext) this.gl = t, this.canvas = this.gl.canvas;
              else {
                const i = t;
                this.gl = i.getContext("webgl2", e) || i.getContext("webgl", e), this.canvas = i, i.addEventListener("webglcontextlost", this.contextLostHandler), i.addEventListener("webglcontextrestored", this.contextRestoredHandler)
              }
            }
            contextLostHandler = t => {
              t && t.preventDefault()
            };
            contextRestoredHandler = () => {
              for (let t = 0, e = this.restorables.length; t < e; t++) this.restorables[t].restore()
            };
            dispose() {
              this.canvas.removeEventListener("webglcontextlost", this.contextLostHandler), this.canvas.removeEventListener("webglcontextrestored", this.contextRestoredHandler)
            }
            addRestorable(t) {
              this.restorables.push(t)
            }
            removeRestorable(t) {
              const e = this.restorables.indexOf(t);
              e > -1 && this.restorables.splice(e, 1)
            }
          },
          vi = class t extends Mt {
            context;
            texture = null;
            boundUnit = 0;
            useMipMaps = !1;
            static DISABLE_UNPACK_PREMULTIPLIED_ALPHA_WEBGL = !1;
            constructor(t, e, i = !1) {
              super(e), this.context = t instanceof bi ? t : new bi(t), this.useMipMaps = i, this.restore(), this.context.addRestorable(this)
            }
            setFilters(e, i) {
              let s = this.context.gl;
              this.bind(), s.texParameteri(s.TEXTURE_2D, s.TEXTURE_MIN_FILTER, e), s.texParameteri(s.TEXTURE_2D, s.TEXTURE_MAG_FILTER, t.validateMagFilter(i)), this.useMipMaps = t.usesMipMaps(e), this.useMipMaps && s.generateMipmap(s.TEXTURE_2D)
            }
            static validateMagFilter(t) {
              switch (t) {
                case 9987:
                case 9985:
                case 9986:
                case 9984:
                  return 9729;
                default:
                  return t
              }
            }
            static usesMipMaps(t) {
              switch (t) {
                case 9987:
                case 9985:
                case 9986:
                case 9984:
                  return !0;
                default:
                  return !1
              }
            }
            setWraps(t, e) {
              let i = this.context.gl;
              this.bind(), i.texParameteri(i.TEXTURE_2D, i.TEXTURE_WRAP_S, t), i.texParameteri(i.TEXTURE_2D, i.TEXTURE_WRAP_T, e)
            }
            update(e) {
              let i = this.context.gl;
              this.texture || (this.texture = this.context.gl.createTexture()), this.bind(), t.DISABLE_UNPACK_PREMULTIPLIED_ALPHA_WEBGL && i.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL, !1), i.texImage2D(i.TEXTURE_2D, 0, i.RGBA, i.RGBA, i.UNSIGNED_BYTE, this._image), i.texParameteri(i.TEXTURE_2D, i.TEXTURE_MAG_FILTER, i.LINEAR), i.texParameteri(i.TEXTURE_2D, i.TEXTURE_MIN_FILTER, e ? i.LINEAR_MIPMAP_LINEAR : i.LINEAR), i.texParameteri(i.TEXTURE_2D, i.TEXTURE_WRAP_S, i.CLAMP_TO_EDGE), i.texParameteri(i.TEXTURE_2D, i.TEXTURE_WRAP_T, i.CLAMP_TO_EDGE), e && i.generateMipmap(i.TEXTURE_2D)
            }
            restore() {
              this.texture = null, this.update(this.useMipMaps)
            }
            bind(t = 0) {
              let e = this.context.gl;
              this.boundUnit = t, e.activeTexture(e.TEXTURE0 + t), e.bindTexture(e.TEXTURE_2D, this.texture)
            }
            unbind() {
              let t = this.context.gl;
              t.activeTexture(t.TEXTURE0 + this.boundUnit), t.bindTexture(t.TEXTURE_2D, null)
            }
            dispose() {
              this.context.removeRestorable(this), this.context.gl.deleteTexture(this.texture)
            }
          },
          xi = class extends qt {
            constructor(t, e = "", i = new Qt) {
              super(e => new vi(t, e), e, i)
            }
          },
          wi = class {
            x = 0;
            y = 0;
            z = 0;
            constructor(t = 0, e = 0, i = 0) {
              this.x = t, this.y = e, this.z = i
            }
            setFrom(t) {
              return this.x = t.x, this.y = t.y, this.z = t.z, this
            }
            set(t, e, i) {
              return this.x = t, this.y = e, this.z = i, this
            }
            add(t) {
              return this.x += t.x, this.y += t.y, this.z += t.z, this
            }
            sub(t) {
              return this.x -= t.x, this.y -= t.y, this.z -= t.z, this
            }
            scale(t) {
              return this.x *= t, this.y *= t, this.z *= t, this
            }
            normalize() {
              let t = this.length();
              return 0 == t || (t = 1 / t, this.x *= t, this.y *= t, this.z *= t), this
            }
            cross(t) {
              return this.set(this.y * t.z - this.z * t.y, this.z * t.x - this.x * t.z, this.x * t.y - this.y * t.x)
            }
            multiply(t) {
              let e = t.values;
              return this.set(this.x * e[Si] + this.y * e[Ti] + this.z * e[Ci] + e[ki], this.x * e[Pi] + this.y * e[Ai] + this.z * e[Ii] + e[Ei], this.x * e[Oi] + this.y * e[Mi] + this.z * e[Bi] + e[Ri])
            }
            project(t) {
              let e = t.values,
                i = 1 / (this.x * e[Di] + this.y * e[Li] + this.z * e[Fi] + e[Ni]);
              return this.set((this.x * e[Si] + this.y * e[Ti] + this.z * e[Ci] + e[ki]) * i, (this.x * e[Pi] + this.y * e[Ai] + this.z * e[Ii] + e[Ei]) * i, (this.x * e[Oi] + this.y * e[Mi] + this.z * e[Bi] + e[Ri]) * i)
            }
            dot(t) {
              return this.x * t.x + this.y * t.y + this.z * t.z
            }
            length() {
              return Math.sqrt(this.x * this.x + this.y * this.y + this.z * this.z)
            }
            distance(t) {
              let e = t.x - this.x,
                i = t.y - this.y,
                s = t.z - this.z;
              return Math.sqrt(e * e + i * i + s * s)
            }
          },
          Si = 0,
          Ti = 4,
          Ci = 8,
          ki = 12,
          Pi = 1,
          Ai = 5,
          Ii = 9,
          Ei = 13,
          Oi = 2,
          Mi = 6,
          Bi = 10,
          Ri = 14,
          Di = 3,
          Li = 7,
          Fi = 11,
          Ni = 15,
          Vi = class t {
            temp = new Float32Array(16);
            values = new Float32Array(16);
            static xAxis = new wi;
            static yAxis = new wi;
            static zAxis = new wi;
            static tmpMatrix = new t;
            constructor() {
              let t = this.values;
              t[Si] = 1, t[Ai] = 1, t[Bi] = 1, t[Ni] = 1
            }
            set(t) {
              return this.values.set(t), this
            }
            transpose() {
              let t = this.temp,
                e = this.values;
              return t[Si] = e[Si], t[Ti] = e[Pi], t[Ci] = e[Oi], t[ki] = e[Di], t[Pi] = e[Ti], t[Ai] = e[Ai], t[Ii] = e[Mi], t[Ei] = e[Li], t[Oi] = e[Ci], t[Mi] = e[Ii], t[Bi] = e[Bi], t[Ri] = e[Fi], t[Di] = e[ki], t[Li] = e[Ei], t[Fi] = e[Ri], t[Ni] = e[Ni], this.set(t)
            }
            identity() {
              let t = this.values;
              return t[Si] = 1, t[Ti] = 0, t[Ci] = 0, t[ki] = 0, t[Pi] = 0, t[Ai] = 1, t[Ii] = 0, t[Ei] = 0, t[Oi] = 0, t[Mi] = 0, t[Bi] = 1, t[Ri] = 0, t[Di] = 0, t[Li] = 0, t[Fi] = 0, t[Ni] = 1, this
            }
            invert() {
              let t = this.values,
                e = this.temp,
                i = t[Di] * t[Mi] * t[Ii] * t[ki] - t[Oi] * t[Li] * t[Ii] * t[ki] - t[Di] * t[Ai] * t[Bi] * t[ki] + t[Pi] * t[Li] * t[Bi] * t[ki] + t[Oi] * t[Ai] * t[Fi] * t[ki] - t[Pi] * t[Mi] * t[Fi] * t[ki] - t[Di] * t[Mi] * t[Ci] * t[Ei] + t[Oi] * t[Li] * t[Ci] * t[Ei] + t[Di] * t[Ti] * t[Bi] * t[Ei] - t[Si] * t[Li] * t[Bi] * t[Ei] - t[Oi] * t[Ti] * t[Fi] * t[Ei] + t[Si] * t[Mi] * t[Fi] * t[Ei] + t[Di] * t[Ai] * t[Ci] * t[Ri] - t[Pi] * t[Li] * t[Ci] * t[Ri] - t[Di] * t[Ti] * t[Ii] * t[Ri] + t[Si] * t[Li] * t[Ii] * t[Ri] + t[Pi] * t[Ti] * t[Fi] * t[Ri] - t[Si] * t[Ai] * t[Fi] * t[Ri] - t[Oi] * t[Ai] * t[Ci] * t[Ni] + t[Pi] * t[Mi] * t[Ci] * t[Ni] + t[Oi] * t[Ti] * t[Ii] * t[Ni] - t[Si] * t[Mi] * t[Ii] * t[Ni] - t[Pi] * t[Ti] * t[Bi] * t[Ni] + t[Si] * t[Ai] * t[Bi] * t[Ni];
              if (0 == i) throw new Error("non-invertible matrix");
              let s = 1 / i;
              return e[Si] = t[Ii] * t[Ri] * t[Li] - t[Ei] * t[Bi] * t[Li] + t[Ei] * t[Mi] * t[Fi] - t[Ai] * t[Ri] * t[Fi] - t[Ii] * t[Mi] * t[Ni] + t[Ai] * t[Bi] * t[Ni], e[Ti] = t[ki] * t[Bi] * t[Li] - t[Ci] * t[Ri] * t[Li] - t[ki] * t[Mi] * t[Fi] + t[Ti] * t[Ri] * t[Fi] + t[Ci] * t[Mi] * t[Ni] - t[Ti] * t[Bi] * t[Ni], e[Ci] = t[Ci] * t[Ei] * t[Li] - t[ki] * t[Ii] * t[Li] + t[ki] * t[Ai] * t[Fi] - t[Ti] * t[Ei] * t[Fi] - t[Ci] * t[Ai] * t[Ni] + t[Ti] * t[Ii] * t[Ni], e[ki] = t[ki] * t[Ii] * t[Mi] - t[Ci] * t[Ei] * t[Mi] - t[ki] * t[Ai] * t[Bi] + t[Ti] * t[Ei] * t[Bi] + t[Ci] * t[Ai] * t[Ri] - t[Ti] * t[Ii] * t[Ri], e[Pi] = t[Ei] * t[Bi] * t[Di] - t[Ii] * t[Ri] * t[Di] - t[Ei] * t[Oi] * t[Fi] + t[Pi] * t[Ri] * t[Fi] + t[Ii] * t[Oi] * t[Ni] - t[Pi] * t[Bi] * t[Ni], e[Ai] = t[Ci] * t[Ri] * t[Di] - t[ki] * t[Bi] * t[Di] + t[ki] * t[Oi] * t[Fi] - t[Si] * t[Ri] * t[Fi] - t[Ci] * t[Oi] * t[Ni] + t[Si] * t[Bi] * t[Ni], e[Ii] = t[ki] * t[Ii] * t[Di] - t[Ci] * t[Ei] * t[Di] - t[ki] * t[Pi] * t[Fi] + t[Si] * t[Ei] * t[Fi] + t[Ci] * t[Pi] * t[Ni] - t[Si] * t[Ii] * t[Ni], e[Ei] = t[Ci] * t[Ei] * t[Oi] - t[ki] * t[Ii] * t[Oi] + t[ki] * t[Pi] * t[Bi] - t[Si] * t[Ei] * t[Bi] - t[Ci] * t[Pi] * t[Ri] + t[Si] * t[Ii] * t[Ri], e[Oi] = t[Ai] * t[Ri] * t[Di] - t[Ei] * t[Mi] * t[Di] + t[Ei] * t[Oi] * t[Li] - t[Pi] * t[Ri] * t[Li] - t[Ai] * t[Oi] * t[Ni] + t[Pi] * t[Mi] * t[Ni], e[Mi] = t[ki] * t[Mi] * t[Di] - t[Ti] * t[Ri] * t[Di] - t[ki] * t[Oi] * t[Li] + t[Si] * t[Ri] * t[Li] + t[Ti] * t[Oi] * t[Ni] - t[Si] * t[Mi] * t[Ni], e[Bi] = t[Ti] * t[Ei] * t[Di] - t[ki] * t[Ai] * t[Di] + t[ki] * t[Pi] * t[Li] - t[Si] * t[Ei] * t[Li] - t[Ti] * t[Pi] * t[Ni] + t[Si] * t[Ai] * t[Ni], e[Ri] = t[ki] * t[Ai] * t[Oi] - t[Ti] * t[Ei] * t[Oi] - t[ki] * t[Pi] * t[Mi] + t[Si] * t[Ei] * t[Mi] + t[Ti] * t[Pi] * t[Ri] - t[Si] * t[Ai] * t[Ri], e[Di] = t[Ii] * t[Mi] * t[Di] - t[Ai] * t[Bi] * t[Di] - t[Ii] * t[Oi] * t[Li] + t[Pi] * t[Bi] * t[Li] + t[Ai] * t[Oi] * t[Fi] - t[Pi] * t[Mi] * t[Fi], e[Li] = t[Ti] * t[Bi] * t[Di] - t[Ci] * t[Mi] * t[Di] + t[Ci] * t[Oi] * t[Li] - t[Si] * t[Bi] * t[Li] - t[Ti] * t[Oi] * t[Fi] + t[Si] * t[Mi] * t[Fi], e[Fi] = t[Ci] * t[Ai] * t[Di] - t[Ti] * t[Ii] * t[Di] - t[Ci] * t[Pi] * t[Li] + t[Si] * t[Ii] * t[Li] + t[Ti] * t[Pi] * t[Fi] - t[Si] * t[Ai] * t[Fi], e[Ni] = t[Ti] * t[Ii] * t[Oi] - t[Ci] * t[Ai] * t[Oi] + t[Ci] * t[Pi] * t[Mi] - t[Si] * t[Ii] * t[Mi] - t[Ti] * t[Pi] * t[Bi] + t[Si] * t[Ai] * t[Bi], t[Si] = e[Si] * s, t[Ti] = e[Ti] * s, t[Ci] = e[Ci] * s, t[ki] = e[ki] * s, t[Pi] = e[Pi] * s, t[Ai] = e[Ai] * s, t[Ii] = e[Ii] * s, t[Ei] = e[Ei] * s, t[Oi] = e[Oi] * s, t[Mi] = e[Mi] * s, t[Bi] = e[Bi] * s, t[Ri] = e[Ri] * s, t[Di] = e[Di] * s, t[Li] = e[Li] * s, t[Fi] = e[Fi] * s, t[Ni] = e[Ni] * s, this
            }
            determinant() {
              let t = this.values;
              return t[Di] * t[Mi] * t[Ii] * t[ki] - t[Oi] * t[Li] * t[Ii] * t[ki] - t[Di] * t[Ai] * t[Bi] * t[ki] + t[Pi] * t[Li] * t[Bi] * t[ki] + t[Oi] * t[Ai] * t[Fi] * t[ki] - t[Pi] * t[Mi] * t[Fi] * t[ki] - t[Di] * t[Mi] * t[Ci] * t[Ei] + t[Oi] * t[Li] * t[Ci] * t[Ei] + t[Di] * t[Ti] * t[Bi] * t[Ei] - t[Si] * t[Li] * t[Bi] * t[Ei] - t[Oi] * t[Ti] * t[Fi] * t[Ei] + t[Si] * t[Mi] * t[Fi] * t[Ei] + t[Di] * t[Ai] * t[Ci] * t[Ri] - t[Pi] * t[Li] * t[Ci] * t[Ri] - t[Di] * t[Ti] * t[Ii] * t[Ri] + t[Si] * t[Li] * t[Ii] * t[Ri] + t[Pi] * t[Ti] * t[Fi] * t[Ri] - t[Si] * t[Ai] * t[Fi] * t[Ri] - t[Oi] * t[Ai] * t[Ci] * t[Ni] + t[Pi] * t[Mi] * t[Ci] * t[Ni] + t[Oi] * t[Ti] * t[Ii] * t[Ni] - t[Si] * t[Mi] * t[Ii] * t[Ni] - t[Pi] * t[Ti] * t[Bi] * t[Ni] + t[Si] * t[Ai] * t[Bi] * t[Ni]
            }
            translate(t, e, i) {
              let s = this.values;
              return s[ki] += t, s[Ei] += e, s[Ri] += i, this
            }
            copy() {
              return (new t).set(this.values)
            }
            projection(t, e, i, s) {
              this.identity();
              let n = 1 / Math.tan(i * (Math.PI / 180) / 2),
                r = (e + t) / (t - e),
                a = 2 * e * t / (t - e),
                o = this.values;
              return o[Si] = n / s, o[Pi] = 0, o[Oi] = 0, o[Di] = 0, o[Ti] = 0, o[Ai] = n, o[Mi] = 0, o[Li] = 0, o[Ci] = 0, o[Ii] = 0, o[Bi] = r, o[Fi] = -1, o[ki] = 0, o[Ei] = 0, o[Ri] = a, o[Ni] = 0, this
            }
            ortho2d(t, e, i, s) {
              return this.ortho(t, t + i, e, e + s, 0, 1)
            }
            ortho(t, e, i, s, n, r) {
              this.identity();
              let a = 2 / (e - t),
                o = 2 / (s - i),
                h = -2 / (r - n),
                l = -(e + t) / (e - t),
                c = -(s + i) / (s - i),
                d = -(r + n) / (r - n),
                u = this.values;
              return u[Si] = a, u[Pi] = 0, u[Oi] = 0, u[Di] = 0, u[Ti] = 0, u[Ai] = o, u[Mi] = 0, u[Li] = 0, u[Ci] = 0, u[Ii] = 0, u[Bi] = h, u[Fi] = 0, u[ki] = l, u[Ei] = c, u[Ri] = d, u[Ni] = 1, this
            }
            multiply(t) {
              let e = this.temp,
                i = this.values,
                s = t.values;
              return e[Si] = i[Si] * s[Si] + i[Ti] * s[Pi] + i[Ci] * s[Oi] + i[ki] * s[Di], e[Ti] = i[Si] * s[Ti] + i[Ti] * s[Ai] + i[Ci] * s[Mi] + i[ki] * s[Li], e[Ci] = i[Si] * s[Ci] + i[Ti] * s[Ii] + i[Ci] * s[Bi] + i[ki] * s[Fi], e[ki] = i[Si] * s[ki] + i[Ti] * s[Ei] + i[Ci] * s[Ri] + i[ki] * s[Ni], e[Pi] = i[Pi] * s[Si] + i[Ai] * s[Pi] + i[Ii] * s[Oi] + i[Ei] * s[Di], e[Ai] = i[Pi] * s[Ti] + i[Ai] * s[Ai] + i[Ii] * s[Mi] + i[Ei] * s[Li], e[Ii] = i[Pi] * s[Ci] + i[Ai] * s[Ii] + i[Ii] * s[Bi] + i[Ei] * s[Fi], e[Ei] = i[Pi] * s[ki] + i[Ai] * s[Ei] + i[Ii] * s[Ri] + i[Ei] * s[Ni], e[Oi] = i[Oi] * s[Si] + i[Mi] * s[Pi] + i[Bi] * s[Oi] + i[Ri] * s[Di], e[Mi] = i[Oi] * s[Ti] + i[Mi] * s[Ai] + i[Bi] * s[Mi] + i[Ri] * s[Li], e[Bi] = i[Oi] * s[Ci] + i[Mi] * s[Ii] + i[Bi] * s[Bi] + i[Ri] * s[Fi], e[Ri] = i[Oi] * s[ki] + i[Mi] * s[Ei] + i[Bi] * s[Ri] + i[Ri] * s[Ni], e[Di] = i[Di] * s[Si] + i[Li] * s[Pi] + i[Fi] * s[Oi] + i[Ni] * s[Di], e[Li] = i[Di] * s[Ti] + i[Li] * s[Ai] + i[Fi] * s[Mi] + i[Ni] * s[Li], e[Fi] = i[Di] * s[Ci] + i[Li] * s[Ii] + i[Fi] * s[Bi] + i[Ni] * s[Fi], e[Ni] = i[Di] * s[ki] + i[Li] * s[Ei] + i[Fi] * s[Ri] + i[Ni] * s[Ni], this.set(this.temp)
            }
            multiplyLeft(t) {
              let e = this.temp,
                i = this.values,
                s = t.values;
              return e[Si] = s[Si] * i[Si] + s[Ti] * i[Pi] + s[Ci] * i[Oi] + s[ki] * i[Di], e[Ti] = s[Si] * i[Ti] + s[Ti] * i[Ai] + s[Ci] * i[Mi] + s[ki] * i[Li], e[Ci] = s[Si] * i[Ci] + s[Ti] * i[Ii] + s[Ci] * i[Bi] + s[ki] * i[Fi], e[ki] = s[Si] * i[ki] + s[Ti] * i[Ei] + s[Ci] * i[Ri] + s[ki] * i[Ni], e[Pi] = s[Pi] * i[Si] + s[Ai] * i[Pi] + s[Ii] * i[Oi] + s[Ei] * i[Di], e[Ai] = s[Pi] * i[Ti] + s[Ai] * i[Ai] + s[Ii] * i[Mi] + s[Ei] * i[Li], e[Ii] = s[Pi] * i[Ci] + s[Ai] * i[Ii] + s[Ii] * i[Bi] + s[Ei] * i[Fi], e[Ei] = s[Pi] * i[ki] + s[Ai] * i[Ei] + s[Ii] * i[Ri] + s[Ei] * i[Ni], e[Oi] = s[Oi] * i[Si] + s[Mi] * i[Pi] + s[Bi] * i[Oi] + s[Ri] * i[Di], e[Mi] = s[Oi] * i[Ti] + s[Mi] * i[Ai] + s[Bi] * i[Mi] + s[Ri] * i[Li], e[Bi] = s[Oi] * i[Ci] + s[Mi] * i[Ii] + s[Bi] * i[Bi] + s[Ri] * i[Fi], e[Ri] = s[Oi] * i[ki] + s[Mi] * i[Ei] + s[Bi] * i[Ri] + s[Ri] * i[Ni], e[Di] = s[Di] * i[Si] + s[Li] * i[Pi] + s[Fi] * i[Oi] + s[Ni] * i[Di], e[Li] = s[Di] * i[Ti] + s[Li] * i[Ai] + s[Fi] * i[Mi] + s[Ni] * i[Li], e[Fi] = s[Di] * i[Ci] + s[Li] * i[Ii] + s[Fi] * i[Bi] + s[Ni] * i[Fi], e[Ni] = s[Di] * i[ki] + s[Li] * i[Ei] + s[Fi] * i[Ri] + s[Ni] * i[Ni], this.set(this.temp)
            }
            lookAt(e, i, s) {
              let n = t.xAxis,
                r = t.yAxis,
                a = t.zAxis;
              a.setFrom(i).normalize(), n.setFrom(i).normalize(), n.cross(s).normalize(), r.setFrom(n).cross(a).normalize(), this.identity();
              let o = this.values;
              return o[Si] = n.x, o[Ti] = n.y, o[Ci] = n.z, o[Pi] = r.x, o[Ai] = r.y, o[Ii] = r.z, o[Oi] = -a.x, o[Mi] = -a.y, o[Bi] = -a.z, t.tmpMatrix.identity(), t.tmpMatrix.values[ki] = -e.x, t.tmpMatrix.values[Ei] = -e.y, t.tmpMatrix.values[Ri] = -e.z, this.multiply(t.tmpMatrix), this
            }
          },
          zi = class {
            position = new wi(0, 0, 0);
            direction = new wi(0, 0, -1);
            up = new wi(0, 1, 0);
            near = 0;
            far = 100;
            zoom = 1;
            viewportWidth = 0;
            viewportHeight = 0;
            projectionView = new Vi;
            inverseProjectionView = new Vi;
            projection = new Vi;
            view = new Vi;
            constructor(t, e) {
              this.viewportWidth = t, this.viewportHeight = e, this.update()
            }
            update() {
              let t = this.projection,
                e = this.view,
                i = this.projectionView,
                s = this.inverseProjectionView,
                n = this.zoom,
                r = this.viewportWidth,
                a = this.viewportHeight;
              t.ortho(n * (-r / 2), n * (r / 2), n * (-a / 2), n * (a / 2), this.near, this.far), e.lookAt(this.position, this.direction, this.up), i.set(t.values), i.multiply(e), s.set(i.values).invert()
            }
            screenToWorld(t, e, i) {
              let s = t.x,
                n = i - t.y - 1;
              return t.x = 2 * s / e - 1, t.y = 2 * n / i - 1, t.z = 2 * t.z - 1, t.project(this.inverseProjectionView), t
            }
            worldToScreen(t, e, i) {
              return t.project(this.projectionView), t.x = e * (t.x + 1) / 2, t.y = i * (t.y + 1) / 2, t.z = (t.z + 1) / 2, t
            }
            setViewport(t, e) {
              this.viewportWidth = t, this.viewportHeight = e
            }
          },
          Ui = class {
            element;
            mouseX = 0;
            mouseY = 0;
            buttonDown = !1;
            touch0 = null;
            touch1 = null;
            initialPinchDistance = 0;
            listeners = new Array;
            autoPreventDefault;
            isTouch = !1;
            callbacks;
            constructor(t, e = !0) {
              this.element = t, this.autoPreventDefault = e, this.callbacks = this.setupCallbacks(t)
            }
            setupCallbacks(t) {
              const e = e => {
                  if (e instanceof MouseEvent && !this.isTouch) {
                    let i = t.getBoundingClientRect();
                    this.mouseX = e.clientX - i.left, this.mouseY = e.clientY - i.top, this.buttonDown = !0, this.listeners.map(t => {
                      t.down && t.down(this.mouseX, this.mouseY, e)
                    })
                  }
                },
                i = e => {
                  if (e instanceof MouseEvent && !this.isTouch) {
                    let i = t.getBoundingClientRect();
                    this.mouseX = e.clientX - i.left, this.mouseY = e.clientY - i.top, this.listeners.map(t => {
                      this.buttonDown ? t.dragged && t.dragged(this.mouseX, this.mouseY, e) : t.moved && t.moved(this.mouseX, this.mouseY, e)
                    })
                  }
                },
                s = e => {
                  if (e instanceof MouseEvent && !this.isTouch) {
                    let i = t.getBoundingClientRect();
                    this.mouseX = e.clientX - i.left, this.mouseY = e.clientY - i.top, this.buttonDown = !1, this.listeners.map(t => {
                      t.up && t.up(this.mouseX, this.mouseY, e)
                    })
                  }
                },
                n = t => {
                  this.autoPreventDefault && t.preventDefault();
                  let e = t.deltaY;
                  t.deltaMode == WheelEvent.DOM_DELTA_LINE && (e *= 8), t.deltaMode == WheelEvent.DOM_DELTA_PAGE && (e *= 24), this.listeners.map(e => {
                    e.wheel && e.wheel(t.deltaY, t)
                  })
                },
                r = e => {
                  if (this.isTouch = !0, !this.touch0 || !this.touch1) {
                    let i = e.changedTouches.item(0);
                    if (!i) return;
                    let s = t.getBoundingClientRect(),
                      n = i.clientX - s.left,
                      r = i.clientY - s.top,
                      a = new Hi(i.identifier, n, r);
                    if (this.mouseX = n, this.mouseY = r, this.buttonDown = !0, this.touch0) {
                      if (!this.touch1) {
                        this.touch1 = a;
                        let t = this.touch1.x - this.touch0.x,
                          i = this.touch1.x - this.touch0.x;
                        this.initialPinchDistance = Math.sqrt(t * t + i * i), this.listeners.map(t => {
                          t.zoom && t.zoom(this.initialPinchDistance, this.initialPinchDistance, e)
                        })
                      }
                    } else this.touch0 = a, this.listeners.map(t => {
                      t.down && t.down(a.x, a.y, e)
                    })
                  }
                  this.autoPreventDefault && e.preventDefault()
                },
                a = e => {
                  if (this.isTouch = !0, this.touch0) {
                    var i = e.changedTouches;
                    let r = t.getBoundingClientRect();
                    for (var s = 0; s < i.length; s++) {
                      var n = i[s];
                      let t = n.clientX - r.left,
                        a = n.clientY - r.top;
                      this.touch0.identifier === n.identifier && (this.touch0.x = this.mouseX = t, this.touch0.y = this.mouseY = a, this.listeners.map(i => {
                        i.dragged && i.dragged(t, a, e)
                      })), this.touch1 && this.touch1.identifier === n.identifier && (this.touch1.x = this.mouseX = t, this.touch1.y = this.mouseY = a)
                    }
                    if (this.touch0 && this.touch1) {
                      let t = this.touch1.x - this.touch0.x,
                        i = this.touch1.x - this.touch0.x,
                        s = Math.sqrt(t * t + i * i);
                      this.listeners.map(t => {
                        t.zoom && t.zoom(this.initialPinchDistance, s, e)
                      })
                    }
                  }
                  this.autoPreventDefault && e.preventDefault()
                },
                o = e => {
                  if (this.isTouch = !0, this.touch0) {
                    var i = e.changedTouches;
                    let r = t.getBoundingClientRect();
                    for (var s = 0; s < i.length; s++) {
                      var n = i[s];
                      let t = n.clientX - r.left,
                        a = n.clientY - r.top;
                      if (this.touch0.identifier === n.identifier) {
                        if (this.touch0 = null, this.mouseX = t, this.mouseY = a, this.listeners.map(i => {
                            i.up && i.up(t, a, e)
                          }), !this.touch1) {
                          this.buttonDown = !1;
                          break
                        }
                        this.touch0 = this.touch1, this.touch1 = null, this.mouseX = this.touch0.x, this.mouseX = this.touch0.x, this.buttonDown = !0, this.listeners.map(t => {
                          t.down && t.down(this.touch0.x, this.touch0.y, e)
                        })
                      }
                      this.touch1 && this.touch1.identifier && (this.touch1 = null)
                    }
                  }
                  this.autoPreventDefault && e.preventDefault()
                };
              return t.addEventListener("mousedown", e, !0), t.addEventListener("mousemove", i, !0), t.addEventListener("mouseup", s, !0), t.addEventListener("wheel", n, !0), t.addEventListener("touchstart", r, {
                passive: !1,
                capture: !1
              }), t.addEventListener("touchmove", a, {
                passive: !1,
                capture: !1
              }), t.addEventListener("touchend", o, {
                passive: !1,
                capture: !1
              }), t.addEventListener("touchcancel", o), {
                mouseDown: e,
                mouseMove: i,
                mouseUp: s,
                mouseWheel: n,
                touchStart: r,
                touchMove: a,
                touchEnd: o
              }
            }
            dispose() {
              const t = this.element;
              t.removeEventListener("mousedown", this.callbacks.mouseDown, !0), t.removeEventListener("mousemove", this.callbacks.mouseMove, !0), t.removeEventListener("mouseup", this.callbacks.mouseUp, !0), t.removeEventListener("wheel", this.callbacks.mouseWheel, !0), t.removeEventListener("touchstart", this.callbacks.touchStart, {
                capture: !1
              }), t.removeEventListener("touchmove", this.callbacks.touchMove, {
                capture: !1
              }), t.removeEventListener("touchend", this.callbacks.touchEnd, {
                capture: !1
              }), t.removeEventListener("touchcancel", this.callbacks.touchEnd), this.listeners.length = 0
            }
            addListener(t) {
              this.listeners.push(t)
            }
            removeListener(t) {
              let e = this.listeners.indexOf(t);
              e > -1 && this.listeners.splice(e, 1)
            }
          },
          Hi = class {
            constructor(t, e, i) {
              this.identifier = t, this.x = e, this.y = i
            }
          },
          Wi = class {
            constructor(t, e) {
              this.canvas = t, this.camera = e;
              let i = 0,
                s = 0,
                n = 0,
                r = 0,
                a = 0,
                o = 0,
                h = 0;
              new Ui(t).addListener({
                down: (t, l) => {
                  i = e.position.x, s = e.position.y, n = a = t, r = o = l, h = e.zoom
                },
                dragged: (h, l) => {
                  let c = h - n,
                    d = l - r,
                    u = e.screenToWorld(new wi(0, 0), t.clientWidth, t.clientHeight),
                    p = e.screenToWorld(new wi(c, d), t.clientWidth, t.clientHeight).sub(u);
                  e.position.set(i - p.x, s - p.y, 0), e.update(), a = h, o = l
                },
                wheel: i => {
                  let s = i / 200 * e.zoom,
                    n = e.zoom + s;
                  if (n > 0) {
                    let s = 0,
                      r = 0;
                    if (i < 0) s = a, r = o;
                    else {
                      let e = new wi(t.clientWidth / 2 + 15, t.clientHeight / 2),
                        i = a - e.x,
                        n = t.clientHeight - 1 - o - e.y;
                      s = e.x - i, r = t.clientHeight - 1 - e.y + n
                    }
                    let h = e.screenToWorld(new wi(s, r), t.clientWidth, t.clientHeight);
                    e.zoom = n, e.update();
                    let l = e.screenToWorld(new wi(s, r), t.clientWidth, t.clientHeight);
                    e.position.add(h.sub(l)), e.update()
                  }
                },
                zoom: (t, i) => {
                  let s = t / i;
                  e.zoom = h * s
                },
                up: (t, e) => {
                  a = t, o = e
                },
                moved: (t, e) => {
                  a = t, o = e
                }
              })
            }
          },
          Yi = class t {
            constructor(t, e, i) {
              this.vertexShader = e, this.fragmentShader = i, this.vsSource = e, this.fsSource = i, this.context = t instanceof bi ? t : new bi(t), this.context.addRestorable(this), this.compile()
            }
            static MVP_MATRIX = "u_projTrans";
            static POSITION = "a_position";
            static COLOR = "a_color";
            static COLOR2 = "a_color2";
            static TEXCOORDS = "a_texCoords";
            static SAMPLER = "u_texture";
            context;
            vs = null;
            vsSource;
            fs = null;
            fsSource;
            program = null;
            tmp2x2 = new Float32Array(4);
            tmp3x3 = new Float32Array(9);
            tmp4x4 = new Float32Array(16);
            getProgram() {
              return this.program
            }
            getVertexShader() {
              return this.vertexShader
            }
            getFragmentShader() {
              return this.fragmentShader
            }
            getVertexShaderSource() {
              return this.vsSource
            }
            getFragmentSource() {
              return this.fsSource
            }
            compile() {
              let t = this.context.gl;
              try {
                if (this.vs = this.compileShader(t.VERTEX_SHADER, this.vertexShader), !this.vs) throw new Error("Couldn't compile vertex shader.");
                if (this.fs = this.compileShader(t.FRAGMENT_SHADER, this.fragmentShader), !this.fs) throw new Error("Couldn#t compile fragment shader.");
                this.program = this.compileProgram(this.vs, this.fs)
              } catch (t) {
                throw this.dispose(), t
              }
            }
            compileShader(t, e) {
              let i = this.context.gl,
                s = i.createShader(t);
              if (!s) throw new Error("Couldn't create shader.");
              if (i.shaderSource(s, e), i.compileShader(s), !i.getShaderParameter(s, i.COMPILE_STATUS)) {
                let t = "Couldn't compile shader: " + i.getShaderInfoLog(s);
                if (i.deleteShader(s), !i.isContextLost()) throw new Error(t)
              }
              return s
            }
            compileProgram(t, e) {
              let i = this.context.gl,
                s = i.createProgram();
              if (!s) throw new Error("Couldn't compile program.");
              if (i.attachShader(s, t), i.attachShader(s, e), i.linkProgram(s), !i.getProgramParameter(s, i.LINK_STATUS)) {
                let t = "Couldn't compile shader program: " + i.getProgramInfoLog(s);
                if (i.deleteProgram(s), !i.isContextLost()) throw new Error(t)
              }
              return s
            }
            restore() {
              this.compile()
            }
            bind() {
              this.context.gl.useProgram(this.program)
            }
            unbind() {
              this.context.gl.useProgram(null)
            }
            setUniformi(t, e) {
              this.context.gl.uniform1i(this.getUniformLocation(t), e)
            }
            setUniformf(t, e) {
              this.context.gl.uniform1f(this.getUniformLocation(t), e)
            }
            setUniform2f(t, e, i) {
              this.context.gl.uniform2f(this.getUniformLocation(t), e, i)
            }
            setUniform3f(t, e, i, s) {
              this.context.gl.uniform3f(this.getUniformLocation(t), e, i, s)
            }
            setUniform4f(t, e, i, s, n) {
              this.context.gl.uniform4f(this.getUniformLocation(t), e, i, s, n)
            }
            setUniform2x2f(t, e) {
              let i = this.context.gl;
              this.tmp2x2.set(e), i.uniformMatrix2fv(this.getUniformLocation(t), !1, this.tmp2x2)
            }
            setUniform3x3f(t, e) {
              let i = this.context.gl;
              this.tmp3x3.set(e), i.uniformMatrix3fv(this.getUniformLocation(t), !1, this.tmp3x3)
            }
            setUniform4x4f(t, e) {
              let i = this.context.gl;
              this.tmp4x4.set(e), i.uniformMatrix4fv(this.getUniformLocation(t), !1, this.tmp4x4)
            }
            getUniformLocation(t) {
              let e = this.context.gl;
              if (!this.program) throw new Error("Shader not compiled.");
              let i = e.getUniformLocation(this.program, t);
              if (!i && !e.isContextLost()) throw new Error(`Couldn't find location for uniform ${t}`);
              return i
            }
            getAttributeLocation(t) {
              let e = this.context.gl;
              if (!this.program) throw new Error("Shader not compiled.");
              let i = e.getAttribLocation(this.program, t);
              if (-1 == i && !e.isContextLost()) throw new Error(`Couldn't find location for attribute ${t}`);
              return i
            }
            dispose() {
              this.context.removeRestorable(this);
              let t = this.context.gl;
              this.vs && (t.deleteShader(this.vs), this.vs = null), this.fs && (t.deleteShader(this.fs), this.fs = null), this.program && (t.deleteProgram(this.program), this.program = null)
            }
            static newColoredTextured(e) {
              let i = `\nattribute vec4 ${t.POSITION};\nattribute vec4 ${t.COLOR};\nattribute vec2 ${t.TEXCOORDS};\nuniform mat4 ${t.MVP_MATRIX};\nvarying vec4 v_color;\nvarying vec2 v_texCoords;\n\nvoid main () {\n\tv_color = ${t.COLOR};\n\tv_texCoords = ${t.TEXCOORDS};\n\tgl_Position = ${t.MVP_MATRIX} * ${t.POSITION};\n}\n`;
              return new t(e, i, "\n#ifdef GL_ES\n\t#define LOWP lowp\n\tprecision mediump float;\n#else\n\t#define LOWP\n#endif\nvarying LOWP vec4 v_color;\nvarying vec2 v_texCoords;\nuniform sampler2D u_texture;\n\nvoid main () {\n\tgl_FragColor = v_color * texture2D(u_texture, v_texCoords);\n}\n")
            }
            static newTwoColoredTextured(e) {
              let i = `\nattribute vec4 ${t.POSITION};\nattribute vec4 ${t.COLOR};\nattribute vec4 ${t.COLOR2};\nattribute vec2 ${t.TEXCOORDS};\nuniform mat4 ${t.MVP_MATRIX};\nvarying vec4 v_light;\nvarying vec4 v_dark;\nvarying vec2 v_texCoords;\n\nvoid main () {\n\tv_light = ${t.COLOR};\n\tv_dark = ${t.COLOR2};\n\tv_texCoords = ${t.TEXCOORDS};\n\tgl_Position = ${t.MVP_MATRIX} * ${t.POSITION};\n}\n`;
              return new t(e, i, "\n#ifdef GL_ES\n\t#define LOWP lowp\n\tprecision mediump float;\n#else\n\t#define LOWP\n#endif\nvarying LOWP vec4 v_light;\nvarying LOWP vec4 v_dark;\nvarying vec2 v_texCoords;\nuniform sampler2D u_texture;\n\nvoid main () {\n\tvec4 texColor = texture2D(u_texture, v_texCoords);\n\tgl_FragColor.a = texColor.a * v_light.a;\n\tgl_FragColor.rgb = ((texColor.a - 1.0) * v_dark.a + 1.0 - texColor.rgb) * v_dark.rgb + texColor.rgb * v_light.rgb;\n}\n")
            }
            static newColored(e) {
              let i = `\nattribute vec4 ${t.POSITION};\nattribute vec4 ${t.COLOR};\nuniform mat4 ${t.MVP_MATRIX};\nvarying vec4 v_color;\n\nvoid main () {\n\tv_color = ${t.COLOR};\n\tgl_Position = ${t.MVP_MATRIX} * ${t.POSITION};\n}\n`;
              return new t(e, i, "\n#ifdef GL_ES\n\t#define LOWP lowp\n\tprecision mediump float;\n#else\n\t#define LOWP\n#endif\nvarying LOWP vec4 v_color;\n\nvoid main () {\n\tgl_FragColor = v_color;\n}\n")
            }
          },
          Gi = class {
            constructor(t, e, i, s) {
              this.attributes = e, this.context = t instanceof bi ? t : new bi(t), this.elementsPerVertex = 0;
              for (let t = 0; t < e.length; t++) this.elementsPerVertex += e[t].numElements;
              this.vertices = new Float32Array(i * this.elementsPerVertex), this.indices = new Uint16Array(s), this.context.addRestorable(this)
            }
            context;
            vertices;
            verticesBuffer = null;
            verticesLength = 0;
            dirtyVertices = !1;
            indices;
            indicesBuffer = null;
            indicesLength = 0;
            dirtyIndices = !1;
            elementsPerVertex = 0;
            getAttributes() {
              return this.attributes
            }
            maxVertices() {
              return this.vertices.length / this.elementsPerVertex
            }
            numVertices() {
              return this.verticesLength / this.elementsPerVertex
            }
            setVerticesLength(t) {
              this.dirtyVertices = !0, this.verticesLength = t
            }
            getVertices() {
              return this.vertices
            }
            maxIndices() {
              return this.indices.length
            }
            numIndices() {
              return this.indicesLength
            }
            setIndicesLength(t) {
              this.dirtyIndices = !0, this.indicesLength = t
            }
            getIndices() {
              return this.indices
            }
            getVertexSizeInFloats() {
              let t = 0;
              for (var e = 0; e < this.attributes.length; e++) {
                t += this.attributes[e].numElements
              }
              return t
            }
            setVertices(t) {
              if (this.dirtyVertices = !0, t.length > this.vertices.length) throw Error("Mesh can't store more than " + this.maxVertices() + " vertices");
              this.vertices.set(t, 0), this.verticesLength = t.length
            }
            setIndices(t) {
              if (this.dirtyIndices = !0, t.length > this.indices.length) throw Error("Mesh can't store more than " + this.maxIndices() + " indices");
              this.indices.set(t, 0), this.indicesLength = t.length
            }
            draw(t, e) {
              this.drawWithOffset(t, e, 0, this.indicesLength > 0 ? this.indicesLength : this.verticesLength / this.elementsPerVertex)
            }
            drawWithOffset(t, e, i, s) {
              let n = this.context.gl;
              (this.dirtyVertices || this.dirtyIndices) && this.update(), this.bind(t), this.indicesLength > 0 ? n.drawElements(e, s, n.UNSIGNED_SHORT, 2 * i) : n.drawArrays(e, i, s), this.unbind(t)
            }
            bind(t) {
              let e = this.context.gl;
              e.bindBuffer(e.ARRAY_BUFFER, this.verticesBuffer);
              let i = 0;
              for (let s = 0; s < this.attributes.length; s++) {
                let n = this.attributes[s],
                  r = t.getAttributeLocation(n.name);
                e.enableVertexAttribArray(r), e.vertexAttribPointer(r, n.numElements, e.FLOAT, !1, 4 * this.elementsPerVertex, 4 * i), i += n.numElements
              }
              this.indicesLength > 0 && e.bindBuffer(e.ELEMENT_ARRAY_BUFFER, this.indicesBuffer)
            }
            unbind(t) {
              let e = this.context.gl;
              for (let i = 0; i < this.attributes.length; i++) {
                let s = this.attributes[i],
                  n = t.getAttributeLocation(s.name);
                e.disableVertexAttribArray(n)
              }
              e.bindBuffer(e.ARRAY_BUFFER, null), this.indicesLength > 0 && e.bindBuffer(e.ELEMENT_ARRAY_BUFFER, null)
            }
            update() {
              let t = this.context.gl;
              this.dirtyVertices && (this.verticesBuffer || (this.verticesBuffer = t.createBuffer()), t.bindBuffer(t.ARRAY_BUFFER, this.verticesBuffer), t.bufferData(t.ARRAY_BUFFER, this.vertices.subarray(0, this.verticesLength), t.DYNAMIC_DRAW), this.dirtyVertices = !1), this.dirtyIndices && (this.indicesBuffer || (this.indicesBuffer = t.createBuffer()), t.bindBuffer(t.ELEMENT_ARRAY_BUFFER, this.indicesBuffer), t.bufferData(t.ELEMENT_ARRAY_BUFFER, this.indices.subarray(0, this.indicesLength), t.DYNAMIC_DRAW), this.dirtyIndices = !1)
            }
            restore() {
              this.verticesBuffer = null, this.indicesBuffer = null, this.update()
            }
            dispose() {
              this.context.removeRestorable(this);
              let t = this.context.gl;
              t.deleteBuffer(this.verticesBuffer), t.deleteBuffer(this.indicesBuffer)
            }
          },
          Xi = class {
            constructor(t, e, i) {
              this.name = t, this.type = e, this.numElements = i
            }
          },
          ji = class extends Xi {
            constructor() {
              super(Yi.POSITION, 0, 2)
            }
          },
          $i = class extends Xi {
            constructor() {
              super(Yi.POSITION, 0, 3)
            }
          },
          Ki = class extends Xi {
            constructor(t = 0) {
              super(Yi.TEXCOORDS + (0 == t ? "" : t), 0, 2)
            }
          },
          qi = class extends Xi {
            constructor() {
              super(Yi.COLOR, 0, 4)
            }
          },
          Zi = class extends Xi {
            constructor() {
              super(Yi.COLOR2, 0, 4)
            }
          },
          Qi = (t => (t[t.Float = 0] = "Float", t))(Qi || {}),
          Ji = class t {
            static disableCulling = !1;
            context;
            drawCalls = 0;
            static globalDrawCalls = 0;
            isDrawing = !1;
            mesh;
            shader = null;
            lastTexture = null;
            verticesLength = 0;
            indicesLength = 0;
            srcColorBlend;
            srcAlphaBlend;
            dstBlend;
            cullWasEnabled = !1;
            constructor(t, e = !0, i = 10920) {
              if (i > 10920) throw new Error("Can't have more than 10920 triangles per batch: " + i);
              this.context = t instanceof bi ? t : new bi(t);
              let s = e ? [new ji, new qi, new Ki, new Zi] : [new ji, new qi, new Ki];
              this.mesh = new Gi(t, s, i, 3 * i);
              let n = this.context.gl;
              this.srcColorBlend = n.SRC_ALPHA, this.srcAlphaBlend = n.ONE, this.dstBlend = n.ONE_MINUS_SRC_ALPHA
            }
            begin(e) {
              if (this.isDrawing) throw new Error("PolygonBatch is already drawing. Call PolygonBatch.end() before calling PolygonBatch.begin()");
              this.drawCalls = 0, this.shader = e, this.lastTexture = null, this.isDrawing = !0;
              let i = this.context.gl;
              i.enable(i.BLEND), i.blendFuncSeparate(this.srcColorBlend, this.dstBlend, this.srcAlphaBlend, this.dstBlend), t.disableCulling && (this.cullWasEnabled = i.isEnabled(i.CULL_FACE), this.cullWasEnabled && i.disable(i.CULL_FACE))
            }
            static blendModesGL = [{
              srcRgb: 770,
              srcRgbPma: 1,
              dstRgb: 771,
              srcAlpha: 1
            }, {
              srcRgb: 770,
              srcRgbPma: 1,
              dstRgb: 1,
              srcAlpha: 1
            }, {
              srcRgb: 774,
              srcRgbPma: 774,
              dstRgb: 771,
              srcAlpha: 1
            }, {
              srcRgb: 1,
              srcRgbPma: 1,
              dstRgb: 769,
              srcAlpha: 1
            }];
            setBlendMode(e, i) {
              const s = t.blendModesGL[e],
                n = i ? s.srcRgbPma : s.srcRgb,
                r = s.srcAlpha,
                a = s.dstRgb;
              this.srcColorBlend == n && this.srcAlphaBlend == r && this.dstBlend == a || (this.srcColorBlend = n, this.srcAlphaBlend = r, this.dstBlend = a, this.isDrawing && this.flush(), this.context.gl.blendFuncSeparate(n, a, r, a))
            }
            draw(t, e, i) {
              t != this.lastTexture ? (this.flush(), this.lastTexture = t) : (this.verticesLength + e.length > this.mesh.getVertices().length || this.indicesLength + i.length > this.mesh.getIndices().length) && this.flush();
              let s = this.mesh.numVertices();
              this.mesh.getVertices().set(e, this.verticesLength), this.verticesLength += e.length, this.mesh.setVerticesLength(this.verticesLength);
              let n = this.mesh.getIndices();
              for (let t = this.indicesLength, e = 0; e < i.length; t++, e++) n[t] = i[e] + s;
              this.indicesLength += i.length, this.mesh.setIndicesLength(this.indicesLength)
            }
            flush() {
              if (0 != this.verticesLength) {
                if (!this.lastTexture) throw new Error("No texture set.");
                if (!this.shader) throw new Error("No shader set.");
                this.lastTexture.bind(), this.mesh.draw(this.shader, this.context.gl.TRIANGLES), this.verticesLength = 0, this.indicesLength = 0, this.mesh.setVerticesLength(0), this.mesh.setIndicesLength(0), this.drawCalls++, t.globalDrawCalls++
              }
            }
            end() {
              if (!this.isDrawing) throw new Error("PolygonBatch is not drawing. Call PolygonBatch.begin() before calling PolygonBatch.end()");
              (this.verticesLength > 0 || this.indicesLength > 0) && this.flush(), this.shader = null, this.lastTexture = null, this.isDrawing = !1;
              let e = this.context.gl;
              e.disable(e.BLEND), t.disableCulling && this.cullWasEnabled && e.enable(e.CULL_FACE)
            }
            getDrawCalls() {
              return this.drawCalls
            }
            static getAndResetGlobalDrawCalls() {
              let e = t.globalDrawCalls;
              return t.globalDrawCalls = 0, e
            }
            dispose() {
              this.mesh.dispose()
            }
          },
          ts = class {
            context;
            isDrawing = !1;
            mesh;
            shapeType = 4;
            color = new u(1, 1, 1, 1);
            shader = null;
            vertexIndex = 0;
            tmp = new v;
            srcColorBlend;
            srcAlphaBlend;
            dstBlend;
            constructor(t, e = 10920) {
              if (e > 10920) throw new Error("Can't have more than 10920 triangles per batch: " + e);
              this.context = t instanceof bi ? t : new bi(t), this.mesh = new Gi(t, [new ji, new qi], e, 0);
              let i = this.context.gl;
              this.srcColorBlend = i.SRC_ALPHA, this.srcAlphaBlend = i.ONE, this.dstBlend = i.ONE_MINUS_SRC_ALPHA
            }
            begin(t) {
              if (this.isDrawing) throw new Error("ShapeRenderer.begin() has already been called");
              this.shader = t, this.vertexIndex = 0, this.isDrawing = !0;
              let e = this.context.gl;
              e.enable(e.BLEND), e.blendFuncSeparate(this.srcColorBlend, this.dstBlend, this.srcAlphaBlend, this.dstBlend)
            }
            setBlendMode(t, e, i) {
              this.srcColorBlend = t, this.srcAlphaBlend = e, this.dstBlend = i, this.isDrawing && (this.flush(), this.context.gl.blendFuncSeparate(t, i, e, i))
            }
            setColor(t) {
              this.color.setFromColor(t)
            }
            setColorWith(t, e, i, s) {
              this.color.set(t, e, i, s)
            }
            point(t, e, i) {
              this.check(0, 1), i || (i = this.color), this.vertex(t, e, i)
            }
            line(t, e, i, s, n) {
              this.check(1, 2);
              this.mesh.getVertices(), this.vertexIndex;
              n || (n = this.color), this.vertex(t, e, n), this.vertex(i, s, n)
            }
            triangle(t, e, i, s, n, r, a, o, h, l) {
              this.check(t ? 4 : 1, 3);
              this.mesh.getVertices(), this.vertexIndex;
              o || (o = this.color), h || (h = this.color), l || (l = this.color), t ? (this.vertex(e, i, o), this.vertex(s, n, h), this.vertex(r, a, l)) : (this.vertex(e, i, o), this.vertex(s, n, h), this.vertex(s, n, o), this.vertex(r, a, h), this.vertex(r, a, o), this.vertex(e, i, h))
            }
            quad(t, e, i, s, n, r, a, o, h, l, c, d, u) {
              this.check(t ? 4 : 1, 3);
              this.mesh.getVertices(), this.vertexIndex;
              l || (l = this.color), c || (c = this.color), d || (d = this.color), u || (u = this.color), t ? (this.vertex(e, i, l), this.vertex(s, n, c), this.vertex(r, a, d), this.vertex(r, a, d), this.vertex(o, h, u), this.vertex(e, i, l)) : (this.vertex(e, i, l), this.vertex(s, n, c), this.vertex(s, n, c), this.vertex(r, a, d), this.vertex(r, a, d), this.vertex(o, h, u), this.vertex(o, h, u), this.vertex(e, i, l))
            }
            rect(t, e, i, s, n, r) {
              this.quad(t, e, i, e + s, i, e + s, i + n, e, i + n, r, r, r, r)
            }
            rectLine(t, e, i, s, n, r, a) {
              this.check(t ? 4 : 1, 8), a || (a = this.color);
              let o = this.tmp.set(n - i, e - s);
              o.normalize(), r *= .5;
              let h = o.x * r,
                l = o.y * r;
              t ? (this.vertex(e + h, i + l, a), this.vertex(e - h, i - l, a), this.vertex(s + h, n + l, a), this.vertex(s - h, n - l, a), this.vertex(s + h, n + l, a), this.vertex(e - h, i - l, a)) : (this.vertex(e + h, i + l, a), this.vertex(e - h, i - l, a), this.vertex(s + h, n + l, a), this.vertex(s - h, n - l, a), this.vertex(s + h, n + l, a), this.vertex(e + h, i + l, a), this.vertex(s - h, n - l, a), this.vertex(e - h, i - l, a))
            }
            x(t, e, i) {
              this.line(t - i, e - i, t + i, e + i), this.line(t - i, e + i, t + i, e - i)
            }
            polygon(t, e, i, s) {
              if (i < 3) throw new Error("Polygon must contain at least 3 vertices");
              this.check(1, 2 * i), s || (s = this.color);
              this.mesh.getVertices(), this.vertexIndex;
              i <<= 1;
              let n = t[e <<= 1],
                r = t[e + 1],
                a = e + i;
              for (let o = e, h = e + i - 2; o < h; o += 2) {
                let e = t[o],
                  i = t[o + 1],
                  h = 0,
                  l = 0;
                o + 2 >= a ? (h = n, l = r) : (h = t[o + 2], l = t[o + 3]), this.vertex(e, i, s), this.vertex(h, l, s)
              }
            }
            circle(t, e, i, s, n, r = 0) {
              if (0 == r && (r = Math.max(1, 6 * p.cbrt(s) | 0)), r <= 0) throw new Error("segments must be > 0.");
              n || (n = this.color);
              let a = 2 * p.PI / r,
                o = Math.cos(a),
                h = Math.sin(a),
                l = s,
                c = 0;
              if (t) {
                this.check(4, 3 * r + 3), r--;
                for (let t = 0; t < r; t++) {
                  this.vertex(e, i, n), this.vertex(e + l, i + c, n);
                  let t = l;
                  l = o * l - h * c, c = h * t + o * c, this.vertex(e + l, i + c, n)
                }
                this.vertex(e, i, n), this.vertex(e + l, i + c, n)
              } else {
                this.check(1, 2 * r + 2);
                for (let t = 0; t < r; t++) {
                  this.vertex(e + l, i + c, n);
                  let t = l;
                  l = o * l - h * c, c = h * t + o * c, this.vertex(e + l, i + c, n)
                }
                this.vertex(e + l, i + c, n)
              }
              l = s, c = 0, this.vertex(e + l, i + c, n)
            }
            curve(t, e, i, s, n, r, a, o, h, l) {
              this.check(1, 2 * h + 2), l || (l = this.color);
              let c = 1 / h,
                d = c * c,
                u = c * c * c,
                p = 3 * c,
                g = 3 * d,
                m = 6 * d,
                f = 6 * u,
                y = t - 2 * i + n,
                _ = e - 2 * s + r,
                b = 3 * (i - n) - t + a,
                v = 3 * (s - r) - e + o,
                x = t,
                w = e,
                S = (i - t) * p + y * g + b * u,
                T = (s - e) * p + _ * g + v * u,
                C = y * m + b * f,
                k = _ * m + v * f,
                P = b * f,
                A = v * f;
              for (; h-- > 0;) this.vertex(x, w, l), x += S, w += T, S += C, T += k, C += P, k += A, this.vertex(x, w, l);
              this.vertex(x, w, l), this.vertex(a, o, l)
            }
            vertex(t, e, i) {
              let s = this.vertexIndex,
                n = this.mesh.getVertices();
              n[s++] = t, n[s++] = e, n[s++] = i.r, n[s++] = i.g, n[s++] = i.b, n[s++] = i.a, this.vertexIndex = s
            }
            end() {
              if (!this.isDrawing) throw new Error("ShapeRenderer.begin() has not been called");
              this.flush();
              let t = this.context.gl;
              t.disable(t.BLEND), this.isDrawing = !1
            }
            flush() {
              if (0 != this.vertexIndex) {
                if (!this.shader) throw new Error("No shader set.");
                this.mesh.setVerticesLength(this.vertexIndex), this.mesh.draw(this.shader, this.shapeType), this.vertexIndex = 0
              }
            }
            check(t, e) {
              if (!this.isDrawing) throw new Error("ShapeRenderer.begin() has not been called");
              if (this.shapeType == t) {
                if (!(this.mesh.maxVertices() - this.mesh.numVertices() < e)) return;
                this.flush()
              } else this.flush(), this.shapeType = t
            }
            dispose() {
              this.mesh.dispose()
            }
          },
          es = (t => (t[t.Point = 0] = "Point", t[t.Line = 1] = "Line", t[t.Filled = 4] = "Filled", t))(es || {}),
          is = class t {
            boneLineColor = new u(1, 0, 0, 1);
            boneOriginColor = new u(0, 1, 0, 1);
            attachmentLineColor = new u(0, 0, 1, .5);
            triangleLineColor = new u(1, .64, 0, .5);
            pathColor = (new u).setFromString("FF7F00");
            clipColor = new u(.8, 0, 0, 2);
            aabbColor = new u(0, 1, 0, .5);
            drawBones = !0;
            drawRegionAttachments = !0;
            drawBoundingBoxes = !0;
            drawMeshHull = !0;
            drawMeshTriangles = !0;
            drawPaths = !0;
            drawSkeletonXY = !1;
            drawClipping = !0;
            premultipliedAlpha = !1;
            scale = 1;
            boneWidth = 2;
            context;
            bounds = new ri;
            temp = new Array;
            vertices = y.newFloatArray(2048);
            static LIGHT_GRAY = new u(192 / 255, 192 / 255, 192 / 255, 1);
            static GREEN = new u(0, 1, 0, 1);
            constructor(t) {
              this.context = t instanceof bi ? t : new bi(t)
            }
            draw(e, i, s) {
              let n = i.x,
                r = i.y,
                a = this.context.gl,
                o = this.premultipliedAlpha ? a.ONE : a.SRC_ALPHA;
              e.setBlendMode(o, a.ONE, a.ONE_MINUS_SRC_ALPHA);
              let h = i.bones;
              if (this.drawBones) {
                e.setColor(this.boneLineColor);
                for (let t = 0, i = h.length; t < i; t++) {
                  let i = h[t];
                  if (s && s.indexOf(i.data.name) > -1 || !i.parent) continue;
                  let n = i.data.length * i.a + i.worldX,
                    r = i.data.length * i.c + i.worldY;
                  e.rectLine(!0, i.worldX, i.worldY, n, r, this.boneWidth * this.scale)
                }
                this.drawSkeletonXY && e.x(n, r, 4 * this.scale)
              }
              if (this.drawRegionAttachments) {
                e.setColor(this.attachmentLineColor);
                let t = i.slots;
                for (let i = 0, s = t.length; i < s; i++) {
                  let s = t[i],
                    n = s.getAttachment();
                  if (n instanceof Yt) {
                    let t = n,
                      i = this.vertices;
                    t.computeWorldVertices(s, i, 0, 2), e.line(i[0], i[1], i[2], i[3]), e.line(i[2], i[3], i[4], i[5]), e.line(i[4], i[5], i[6], i[7]), e.line(i[6], i[7], i[0], i[1])
                  }
                }
              }
              if (this.drawMeshHull || this.drawMeshTriangles) {
                let t = i.slots;
                for (let i = 0, s = t.length; i < s; i++) {
                  let s = t[i];
                  if (!s.bone.active) continue;
                  let n = s.getAttachment();
                  if (!(n instanceof Ut)) continue;
                  let r = n,
                    a = this.vertices;
                  r.computeWorldVertices(s, 0, r.worldVerticesLength, a, 0, 2);
                  let o = r.triangles,
                    h = r.hullLength;
                  if (this.drawMeshTriangles) {
                    e.setColor(this.triangleLineColor);
                    for (let t = 0, i = o.length; t < i; t += 3) {
                      let i = 2 * o[t],
                        s = 2 * o[t + 1],
                        n = 2 * o[t + 2];
                      e.triangle(!1, a[i], a[i + 1], a[s], a[s + 1], a[n], a[n + 1])
                    }
                  }
                  if (this.drawMeshHull && h > 0) {
                    e.setColor(this.attachmentLineColor), h = 2 * (h >> 1);
                    let t = a[h - 2],
                      i = a[h - 1];
                    for (let s = 0, n = h; s < n; s += 2) {
                      let n = a[s],
                        r = a[s + 1];
                      e.line(n, r, t, i), t = n, i = r
                    }
                  }
                }
              }
              if (this.drawBoundingBoxes) {
                let t = this.bounds;
                t.update(i, !0), e.setColor(this.aabbColor), e.rect(!1, t.minX, t.minY, t.getWidth(), t.getHeight());
                let s = t.polygons,
                  n = t.boundingBoxes;
                for (let t = 0, i = s.length; t < i; t++) {
                  let i = s[t];
                  e.setColor(n[t].color), e.polygon(i, 0, i.length)
                }
              }
              if (this.drawPaths) {
                let s = i.slots;
                for (let i = 0, n = s.length; i < n; i++) {
                  let n = s[i];
                  if (!n.bone.active) continue;
                  let r = n.getAttachment();
                  if (!(r instanceof Ht)) continue;
                  let a = r,
                    o = a.worldVerticesLength,
                    h = this.temp = y.setArraySize(this.temp, o, 0);
                  a.computeWorldVertices(n, 0, o, h, 0, 2);
                  let l = this.pathColor,
                    c = h[2],
                    d = h[3],
                    u = 0,
                    p = 0;
                  if (a.closed) {
                    e.setColor(l);
                    let i = h[0],
                      s = h[1],
                      n = h[o - 2],
                      r = h[o - 1];
                    u = h[o - 4], p = h[o - 3], e.curve(c, d, i, s, n, r, u, p, 32), e.setColor(t.LIGHT_GRAY), e.line(c, d, i, s), e.line(u, p, n, r)
                  }
                  o -= 4;
                  for (let i = 4; i < o; i += 6) {
                    let s = h[i],
                      n = h[i + 1],
                      r = h[i + 2],
                      a = h[i + 3];
                    u = h[i + 4], p = h[i + 5], e.setColor(l), e.curve(c, d, s, n, r, a, u, p, 32), e.setColor(t.LIGHT_GRAY), e.line(c, d, s, n), e.line(u, p, r, a), c = u, d = p
                  }
                }
              }
              if (this.drawBones) {
                e.setColor(this.boneOriginColor);
                for (let t = 0, i = h.length; t < i; t++) {
                  let i = h[t];
                  s && s.indexOf(i.data.name) > -1 || e.circle(!0, i.worldX, i.worldY, 3 * this.scale, this.boneOriginColor, 8)
                }
              }
              if (this.drawClipping) {
                let t = i.slots;
                e.setColor(this.clipColor);
                for (let i = 0, s = t.length; i < s; i++) {
                  let s = t[i];
                  if (!s.bone.active) continue;
                  let n = s.getAttachment();
                  if (!(n instanceof Ot)) continue;
                  let r = n,
                    a = r.worldVerticesLength,
                    o = this.temp = y.setArraySize(this.temp, a, 0);
                  r.computeWorldVertices(s, 0, a, o, 0, 2);
                  for (let t = 0, i = o.length; t < i; t += 2) {
                    let i = o[t],
                      s = o[t + 1],
                      n = o[(t + 2) % o.length],
                      r = o[(t + 3) % o.length];
                    e.line(i, s, n, r)
                  }
                }
              }
            }
            dispose() {}
          },
          ss = class {
            constructor(t, e, i) {
              this.vertices = t, this.numVertices = e, this.numFloats = i
            }
          },
          ns = class t {
            static QUAD_TRIANGLES = [0, 1, 2, 2, 3, 0];
            premultipliedAlpha = !1;
            tempColor = new u;
            tempColor2 = new u;
            vertices;
            vertexSize = 8;
            twoColorTint = !1;
            renderable = new ss([], 0, 0);
            clipper = new oi;
            temp = new v;
            temp2 = new v;
            temp3 = new u;
            temp4 = new u;
            constructor(t, e = !0) {
              this.twoColorTint = e, e && (this.vertexSize += 4), this.vertices = y.newFloatArray(1024 * this.vertexSize)
            }
            draw(e, i, s = -1, n = -1, r = null) {
              let a, o, h, l = this.clipper,
                c = this.premultipliedAlpha,
                d = this.twoColorTint,
                u = null,
                p = this.renderable,
                g = i.drawOrder,
                m = i.color,
                f = d ? 12 : 8,
                _ = !1; - 1 == s && (_ = !0);
              for (let i = 0, b = g.length; i < b; i++) {
                let b = l.isClipping() ? 2 : f,
                  v = g[i];
                if (!v.bone.active) {
                  l.clipEndWithSlot(v);
                  continue
                }
                if (s >= 0 && s == v.data.index && (_ = !0), !_) {
                  l.clipEndWithSlot(v);
                  continue
                }
                n >= 0 && n == v.data.index && (_ = !1);
                let x, w = v.getAttachment();
                if (w instanceof Yt) {
                  let e = w;
                  p.vertices = this.vertices, p.numVertices = 4, p.numFloats = b << 2, e.computeWorldVertices(v, p.vertices, 0, b), o = t.QUAD_TRIANGLES, a = e.uvs, x = e.region.texture, h = e.color
                } else {
                  if (!(w instanceof Ut)) {
                    if (w instanceof Ot) {
                      let t = w;
                      l.clipStart(v, t);
                      continue
                    }
                    l.clipEndWithSlot(v);
                    continue
                  } {
                    let t = w;
                    p.vertices = this.vertices, p.numVertices = t.worldVerticesLength >> 1, p.numFloats = p.numVertices * b, p.numFloats > p.vertices.length && (p.vertices = this.vertices = y.newFloatArray(p.numFloats)), t.computeWorldVertices(v, 0, t.worldVerticesLength, p.vertices, 0, b), o = t.triangles, x = t.region.texture, a = t.uvs, h = t.color
                  }
                }
                if (x) {
                  let t = v.color,
                    i = this.tempColor;
                  i.r = m.r * t.r * h.r, i.g = m.g * t.g * h.g, i.b = m.b * t.b * h.b, i.a = m.a * t.a * h.a, c && (i.r *= i.a, i.g *= i.a, i.b *= i.a);
                  let s = this.tempColor2;
                  v.darkColor ? (c ? (s.r = v.darkColor.r * i.a, s.g = v.darkColor.g * i.a, s.b = v.darkColor.b * i.a) : s.setFromColor(v.darkColor), s.a = c ? 1 : 0) : s.set(0, 0, 0, 1);
                  let n = v.data.blendMode;
                  if (n != u && (u = n, e.setBlendMode(u, c)), l.isClipping()) {
                    l.clipTriangles(p.vertices, o, o.length, a, i, s, d);
                    let t = new Float32Array(l.clippedVertices),
                      n = l.clippedTriangles;
                    r && r(t, t.length, f), e.draw(x, t, n)
                  } else {
                    let t = p.vertices;
                    if (d)
                      for (let e = 2, n = 0, r = p.numFloats; e < r; e += f, n += 2) t[e] = i.r, t[e + 1] = i.g, t[e + 2] = i.b, t[e + 3] = i.a, t[e + 4] = a[n], t[e + 5] = a[n + 1], t[e + 6] = s.r, t[e + 7] = s.g, t[e + 8] = s.b, t[e + 9] = s.a;
                    else
                      for (let e = 2, s = 0, n = p.numFloats; e < n; e += f, s += 2) t[e] = i.r, t[e + 1] = i.g, t[e + 2] = i.b, t[e + 3] = i.a, t[e + 4] = a[s], t[e + 5] = a[s + 1];
                    let n = p.vertices.subarray(0, p.numFloats);
                    r && r(p.vertices, p.numFloats, f), e.draw(x, n, o)
                  }
                }
                l.clipEndWithSlot(v)
              }
              l.clipEnd()
            }
            getSkeletonClipping() {
              return this.clipper
            }
          },
          rs = [0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0],
          as = [0, 1, 2, 2, 3, 0],
          os = new u(1, 1, 1, 1),
          hs = class {
            context;
            canvas;
            camera;
            batcher;
            twoColorTint = !1;
            batcherShader;
            shapes;
            shapesShader;
            activeRenderer = null;
            skeletonRenderer;
            skeletonDebugRenderer;
            constructor(t, e, i = !0) {
              this.canvas = t, this.context = e instanceof bi ? e : new bi(e), this.twoColorTint = i, this.camera = new zi(t.width, t.height), this.batcherShader = i ? Yi.newTwoColoredTextured(this.context) : Yi.newColoredTextured(this.context), this.batcher = new Ji(this.context, i), this.shapesShader = Yi.newColored(this.context), this.shapes = new ts(this.context), this.skeletonRenderer = new ns(this.context, i), this.skeletonDebugRenderer = new is(this.context)
            }
            dispose() {
              this.batcher.dispose(), this.batcherShader.dispose(), this.shapes.dispose(), this.shapesShader.dispose(), this.skeletonDebugRenderer.dispose()
            }
            begin() {
              this.camera.update(), this.enableRenderer(this.batcher)
            }
            drawSkeleton(t, e = !1, i = -1, s = -1, n = null) {
              this.enableRenderer(this.batcher), this.skeletonRenderer.premultipliedAlpha = e, this.skeletonRenderer.draw(this.batcher, t, i, s, n)
            }
            drawSkeletonDebug(t, e = !1, i) {
              this.enableRenderer(this.shapes), this.skeletonDebugRenderer.premultipliedAlpha = e, this.skeletonDebugRenderer.draw(this.shapes, t, i)
            }
            drawTexture(t, e, i, s, n, r) {
              this.enableRenderer(this.batcher), r || (r = os);
              var a = 0;
              rs[a++] = e, rs[a++] = i, rs[a++] = r.r, rs[a++] = r.g, rs[a++] = r.b, rs[a++] = r.a, rs[a++] = 0, rs[a++] = 1, this.twoColorTint && (rs[a++] = 0, rs[a++] = 0, rs[a++] = 0, rs[a++] = 0), rs[a++] = e + s, rs[a++] = i, rs[a++] = r.r, rs[a++] = r.g, rs[a++] = r.b, rs[a++] = r.a, rs[a++] = 1, rs[a++] = 1, this.twoColorTint && (rs[a++] = 0, rs[a++] = 0, rs[a++] = 0, rs[a++] = 0), rs[a++] = e + s, rs[a++] = i + n, rs[a++] = r.r, rs[a++] = r.g, rs[a++] = r.b, rs[a++] = r.a, rs[a++] = 1, rs[a++] = 0, this.twoColorTint && (rs[a++] = 0, rs[a++] = 0, rs[a++] = 0, rs[a++] = 0), rs[a++] = e, rs[a++] = i + n, rs[a++] = r.r, rs[a++] = r.g, rs[a++] = r.b, rs[a++] = r.a, rs[a++] = 0, rs[a++] = 0, this.twoColorTint && (rs[a++] = 0, rs[a++] = 0, rs[a++] = 0, rs[a] = 0), this.batcher.draw(t, rs, as)
            }
            drawTextureUV(t, e, i, s, n, r, a, o, h, l) {
              this.enableRenderer(this.batcher), l || (l = os);
              var c = 0;
              rs[c++] = e, rs[c++] = i, rs[c++] = l.r, rs[c++] = l.g, rs[c++] = l.b, rs[c++] = l.a, rs[c++] = r, rs[c++] = a, this.twoColorTint && (rs[c++] = 0, rs[c++] = 0, rs[c++] = 0, rs[c++] = 0), rs[c++] = e + s, rs[c++] = i, rs[c++] = l.r, rs[c++] = l.g, rs[c++] = l.b, rs[c++] = l.a, rs[c++] = o, rs[c++] = a, this.twoColorTint && (rs[c++] = 0, rs[c++] = 0, rs[c++] = 0, rs[c++] = 0), rs[c++] = e + s, rs[c++] = i + n, rs[c++] = l.r, rs[c++] = l.g, rs[c++] = l.b, rs[c++] = l.a, rs[c++] = o, rs[c++] = h, this.twoColorTint && (rs[c++] = 0, rs[c++] = 0, rs[c++] = 0, rs[c++] = 0), rs[c++] = e, rs[c++] = i + n, rs[c++] = l.r, rs[c++] = l.g, rs[c++] = l.b, rs[c++] = l.a, rs[c++] = r, rs[c++] = h, this.twoColorTint && (rs[c++] = 0, rs[c++] = 0, rs[c++] = 0, rs[c] = 0), this.batcher.draw(t, rs, as)
            }
            drawTextureRotated(t, e, i, s, n, r, a, o, h) {
              this.enableRenderer(this.batcher), h || (h = os);
              let l = e + r,
                c = i + a,
                d = -r,
                u = -a,
                g = s - r,
                m = n - a,
                f = d,
                y = u,
                _ = d,
                b = m,
                v = g,
                x = m,
                w = g,
                S = u,
                T = 0,
                C = 0,
                k = 0,
                P = 0,
                A = 0,
                I = 0,
                E = 0,
                O = 0;
              if (0 != o) {
                let t = p.cosDeg(o),
                  e = p.sinDeg(o);
                T = t * f - e * y, C = e * f + t * y, E = t * _ - e * b, O = e * _ + t * b, A = t * v - e * x, I = e * v + t * x, k = A + (T - E), P = I + (C - O)
              } else T = f, C = y, E = _, O = b, A = v, I = x, k = w, P = S;
              T += l, C += c, k += l, P += c, A += l, I += c, E += l, O += c;
              var M = 0;
              rs[M++] = T, rs[M++] = C, rs[M++] = h.r, rs[M++] = h.g, rs[M++] = h.b, rs[M++] = h.a, rs[M++] = 0, rs[M++] = 1, this.twoColorTint && (rs[M++] = 0, rs[M++] = 0, rs[M++] = 0, rs[M++] = 0), rs[M++] = k, rs[M++] = P, rs[M++] = h.r, rs[M++] = h.g, rs[M++] = h.b, rs[M++] = h.a, rs[M++] = 1, rs[M++] = 1, this.twoColorTint && (rs[M++] = 0, rs[M++] = 0, rs[M++] = 0, rs[M++] = 0), rs[M++] = A, rs[M++] = I, rs[M++] = h.r, rs[M++] = h.g, rs[M++] = h.b, rs[M++] = h.a, rs[M++] = 1, rs[M++] = 0, this.twoColorTint && (rs[M++] = 0, rs[M++] = 0, rs[M++] = 0, rs[M++] = 0), rs[M++] = E, rs[M++] = O, rs[M++] = h.r, rs[M++] = h.g, rs[M++] = h.b, rs[M++] = h.a, rs[M++] = 0, rs[M++] = 0, this.twoColorTint && (rs[M++] = 0, rs[M++] = 0, rs[M++] = 0, rs[M] = 0), this.batcher.draw(t, rs, as)
            }
            drawRegion(t, e, i, s, n, r) {
              this.enableRenderer(this.batcher), r || (r = os);
              var a = 0;
              rs[a++] = e, rs[a++] = i, rs[a++] = r.r, rs[a++] = r.g, rs[a++] = r.b, rs[a++] = r.a, rs[a++] = t.u, rs[a++] = t.v2, this.twoColorTint && (rs[a++] = 0, rs[a++] = 0, rs[a++] = 0, rs[a++] = 0), rs[a++] = e + s, rs[a++] = i, rs[a++] = r.r, rs[a++] = r.g, rs[a++] = r.b, rs[a++] = r.a, rs[a++] = t.u2, rs[a++] = t.v2, this.twoColorTint && (rs[a++] = 0, rs[a++] = 0, rs[a++] = 0, rs[a++] = 0), rs[a++] = e + s, rs[a++] = i + n, rs[a++] = r.r, rs[a++] = r.g, rs[a++] = r.b, rs[a++] = r.a, rs[a++] = t.u2, rs[a++] = t.v, this.twoColorTint && (rs[a++] = 0, rs[a++] = 0, rs[a++] = 0, rs[a++] = 0), rs[a++] = e, rs[a++] = i + n, rs[a++] = r.r, rs[a++] = r.g, rs[a++] = r.b, rs[a++] = r.a, rs[a++] = t.u, rs[a++] = t.v, this.twoColorTint && (rs[a++] = 0, rs[a++] = 0, rs[a++] = 0, rs[a] = 0), this.batcher.draw(t.page.texture, rs, as)
            }
            line(t, e, i, s, n, r) {
              this.enableRenderer(this.shapes), this.shapes.line(t, e, i, s, n)
            }
            triangle(t, e, i, s, n, r, a, o, h, l) {
              this.enableRenderer(this.shapes), this.shapes.triangle(t, e, i, s, n, r, a, o, h, l)
            }
            quad(t, e, i, s, n, r, a, o, h, l, c, d, u) {
              this.enableRenderer(this.shapes), this.shapes.quad(t, e, i, s, n, r, a, o, h, l, c, d, u)
            }
            rect(t, e, i, s, n, r) {
              this.enableRenderer(this.shapes), this.shapes.rect(t, e, i, s, n, r)
            }
            rectLine(t, e, i, s, n, r, a) {
              this.enableRenderer(this.shapes), this.shapes.rectLine(t, e, i, s, n, r, a)
            }
            polygon(t, e, i, s) {
              this.enableRenderer(this.shapes), this.shapes.polygon(t, e, i, s)
            }
            circle(t, e, i, s, n, r = 0) {
              this.enableRenderer(this.shapes), this.shapes.circle(t, e, i, s, n, r)
            }
            curve(t, e, i, s, n, r, a, o, h, l) {
              this.enableRenderer(this.shapes), this.shapes.curve(t, e, i, s, n, r, a, o, h, l)
            }
            end() {
              this.activeRenderer === this.batcher ? this.batcher.end() : this.activeRenderer === this.shapes && this.shapes.end(), this.activeRenderer = null
            }
            resize(t) {
              let e = this.canvas;
              var i = window.devicePixelRatio || 1,
                s = Math.round(e.clientWidth * i),
                n = Math.round(e.clientHeight * i);
              if ((e.width != s || e.height != n) && (e.width = s, e.height = n), this.context.gl.viewport(0, 0, e.width, e.height), 1 === t) this.camera.setViewport(s, n);
              else if (2 === t) {
                let t = e.width,
                  i = e.height,
                  s = this.camera.viewportWidth,
                  n = this.camera.viewportHeight,
                  r = n / s < i / t ? s / t : n / i;
                this.camera.setViewport(t * r, i * r)
              }
              this.camera.update()
            }
            enableRenderer(t) {
              this.activeRenderer !== t && (this.end(), t instanceof Ji ? (this.batcherShader.bind(), this.batcherShader.setUniform4x4f(Yi.MVP_MATRIX, this.camera.projectionView.values), this.batcherShader.setUniformi("u_texture", 0), this.batcher.begin(this.batcherShader), this.activeRenderer = this.batcher) : t instanceof ts ? (this.shapesShader.bind(), this.shapesShader.setUniform4x4f(Yi.MVP_MATRIX, this.camera.projectionView.values), this.shapes.begin(this.shapesShader), this.activeRenderer = this.shapes) : this.activeRenderer = this.skeletonDebugRenderer)
            }
          },
          ls = (t => (t[t.Stretch = 0] = "Stretch", t[t.Expand = 1] = "Expand", t[t.Fit = 2] = "Fit", t))(ls || {}),
          cs = 0,
          ds = 165,
          us = 108,
          ps = 163,
          gs = class {
            renderer;
            logo = null;
            spinner = null;
            angle = 0;
            fadeOut = 0;
            fadeIn = 0;
            timeKeeper = new x;
            backgroundColor = new u(.135, .135, .135, 1);
            tempColor = new u;
            constructor(t) {
              if (this.renderer = t, this.timeKeeper.maxDelta = 9, !mi) {
                let t = navigator.userAgent.indexOf("Safari") > -1,
                  e = () => cs++;
                (mi = new Image).src = fs, t || (mi.crossOrigin = "anonymous"), mi.onload = e, (gi = new Image).src = ms, t || (gi.crossOrigin = "anonymous"), gi.onload = e
              }
            }
            dispose() {
              this.logo?.dispose(), this.spinner?.dispose()
            }
            draw(t = !1) {
              if (cs < 2 || t && this.fadeOut > 1) return;
              this.timeKeeper.update();
              let e = Math.abs(Math.sin(this.timeKeeper.totalTime + .25));
              this.angle -= 200 * this.timeKeeper.delta * (1 + 1.5 * Math.pow(e, 5));
              let i = this.tempColor,
                s = this.renderer,
                n = s.canvas,
                r = s.context.gl;
              if (s.resize(1), s.camera.position.set(n.width / 2, n.height / 2, 0), s.batcher.setBlendMode(0, !0), t) {
                if (this.fadeOut += this.timeKeeper.delta * (this.timeKeeper.totalTime < 1 ? 2 : 1), this.fadeOut > 1) return;
                i.setFromColor(this.backgroundColor), e = 1 - this.fadeOut / 1, e = 1 - (e - 1) * (e - 1), i.a *= e, i.a > 0 && (s.camera.zoom = 1, s.begin(), s.quad(!0, 0, 0, n.width, 0, n.width, n.height, 0, n.height, i, i, i, i), s.end())
              } else this.fadeIn += this.timeKeeper.delta, this.backgroundColor.a > 0 && (r.clearColor(this.backgroundColor.r, this.backgroundColor.g, this.backgroundColor.b, this.backgroundColor.a), r.clear(r.COLOR_BUFFER_BIT)), e = 1;
              e *= Math.min(this.fadeIn / 1, 1), i.set(e, e, e, e), this.logo || (this.logo = new vi(s.context, mi), this.spinner = new vi(s.context, gi)), s.camera.zoom = Math.max(1, ps / n.height), s.begin(), s.drawTexture(this.logo, (n.width - ds) / 2, (n.height - us) / 2, ds, us, i), this.spinner && s.drawTextureRotated(this.spinner, (n.width - ps) / 2, (n.height - ps) / 2, ps, ps, 81.5, 81.5, this.angle, i), s.end()
            }
            drawInCoordinates(t, e) {
              if (cs < 2) return;
              this.timeKeeper.update();
              let i = this.renderer;
              i.batcher.setBlendMode(0, !0), this.logo || (this.logo = new vi(i.context, mi), this.spinner = new vi(i.context, gi));
              const s = t - 82.5,
                n = e - 54;
              i.drawTexture(this.logo, s, n, ds, us), this.angle -= 500 * this.timeKeeper.delta, this.spinner && i.drawTextureRotated(this.spinner, s, n - 25, ps, ps, 81.5, 81.5, this.angle)
            }
          },
          ms = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAKMAAACjCAYAAADmbK6AAAALKElEQVR42u2de2iW5R/GPzuqcwfnnKfNmafl5tTNHWzqNi3DEMQykcAoJSsySkspjSIk0iD/07Kf4R+FnVBDUTshZGpWUEJaaiWFgZlUFmXmIe3HNXthyebeZ77P9H13ffBG8Y8H7ut7vff93N/7fu4vGGPiFZiez/Qtw9lytJajfzfw9z/j+efPOv7cV8W+lUNY2a8T/ayTCRsWFLJA5rtUO1LLkV5p9LJeJizQiHeqnlOtmVFtdTGrrZkJCxYXsTgaI6r9MY4/UpNItW4mFDaXsTlaM6qVZlBq3UwofFrJp0HMWJ9DvXUzobCznJ1BzFjWlTLrZkJh/TDWBzFjTgo51s2EgnKI0Rrx+FiOWzNzVaym91Syx5qZsGBWb2ZFa0ZN6dbMhAWTcpkUrRmXD2K5NTNhgVbH0Zpxbl/mWjMTFvRIo0e0ZpzcncnWzISKtvmiMWNRJ4qslwmVXRXsas2Ix8ZwzFqZsGFREYtaM+Oaa1ljrUzYkJ9G/ok6TlzKjJWZVFor0y7c1Zu7WjLiqiGsskamXdHopyT4vALmzS9k/t19uHtKHlOSIMn6xAtARjIZ1sFcUSZ0Y4La+G6M18hS2IlCn4a+WoC0JNL0d/dUupdnUj40g6EJ2VEdMnhrOG/p5f/jUXz8SgmvaGU6KpNRNsLVQV0OdXf24s63h/P2gWoOrBjMCr2GJFQnnxnIM3q5P1PPmaYv+4ev4/C6UtbpV2gzXCkgL5W8Bwt48OIc6ul6Tp+s4+SyASxLiI4+PYCn1bHzDZxvaQW6vZzto7MYnQIpNkf7kp5EuozYUroqEjcNKHHd0Tl9mBPN1pk+hFeieGBnBtog7UXjsj9pWg+m6duecw2cay1OC/uxMC47KmP9OIYfoz1YoC20J/rzRG4quTZK2EAyJGs20qwUbYw0aNRmUxtvfUW/uEtNzc1NB1/X8LVyd15hh82F43AvD+VlXcsSJEZa1CQ3ejleAO7oxR3RDP0XN91X4+NXYb8nkv7UNTwV7e0YTdu7I3g33t7tuaEbNwSZpps2fSyvs4M2Tjhot+jb0Xzbltj8r5j/xVt/6Z1Ob93U1ZYO691EhhzchcHeXosVjcNZysyezLw4xRZt05R+fTeuj8vOj+zKyG0j2aZcVVs6v+QalnjrMFZASQYl2nBoSyz06e3j/Xk8rgWYmMvEICu2pm1HOTuc7okV8FgRj0XukwzanhvCc/F+72TjoQjdObN1OFuDLmh0xP+WHtxiI10ukJlCprb4guiv1fP+avZrS1C7NAkliHZjDtZwMMgqbukAltpMlwuMy2FcEBPqvfLLar5Uqi0hBdEwryy+Mv5n6zkbjTBa+dlMlwvUZFETZKGiFM7tvbhdJ3gSVRO0wzIjnxmvl/J6a6JsGMYGrahtpssFeqbR841S3mhN80OjOaSDEdqd6SjaMKgzgzRK7q1ib3PT9sYyNo7JZoyNFNvRcVMZmy7WOvIuryv/Zvdmdt90+nY0bRp3AvROohFwdwW7dTG7RFlbwlqdrbOBYg005NAQmZU0HWt1rXMBH1Xw0dQ8pmqzoaPmdhun7bHZjNVe9qP9eFQfO1VkUmHjhAVUZ1GtnKFSbjrkrPfy4i4UW5t/6ZxM54J0CqxFe81KpGsQyE4h23oYY4wxxhhjjDHGGGOMMcYYY4wxxhhjjDHGGGOMMcYYY4wxxhhjjDHGGGOMMcYYY4wxxhhjjLna+bdOy+IiFquIpGq16Pb79cNYv3IIK/X/ugx+Ui6TVKvYVU9Nc8gX8od8Ir/IN/KPfCQ/yVfyl/6/pfJvLChkQdD6wyqntquCXYuKWJSfRr6D0dEAxV3xlw/khyD+kd/ku/88cHo+09tS3LBpO1HHCVUqcIA6CqB4K+6X6x35L/JM2loXurlWmUmlA5XogOIcK8/If5HncrSWo7F6cKIWPjT/RXGOlWfkv8hzaWsN4uaaysE6WIkOKM6x8oz8F3kusXqo2vxC5jtYiQ4ozrH0TeS5qIZcrB7qkrwdA8U5Vp6R/yLPZV8V+2L14Cl5THGwEh1QnGPlGfkv8lyUlIzFQ1cNYVVHrcjZ0VCcFe9Y+Eb+izy3ceclUl43aFN52DXXssYpnY6a4qFS8ZcP2uIf+e7inRh6pdFrdTGrm8uiHx/L8T2V7NGWzvJBLJ/bl7mTuzO5qBNFDoiJID/IF/KHfCK/yDfyT3O7d/KbfNfS80hNIrU0g9L6HOq1x5iTQo6FNpeLfCQ/yVfyl3xmXYwxxhhjjDHGGGOMMcYYY4wxxhhjjDHGGGOMMcYYY4wxxhhjjDHGGGOMMcYYY4wxxhhjjDHNk9z4JwJ0SqKTdQkbyEwhU393T6V7zzR6pieR3tE1ITeVXImhe6BXDGZFdRbVeank2TBhcaEMr0rwbixj49IBLL2/L/ffmMuNHfqO9tFZjJYBd1ewO3Lx+IcVfKhqna5nHZYR6XFPH+5R3eeI5t9fx/fvjeC9Jdew5OKZKqFR/RDVKL6vL/f9PJafmyvHsL+a/ff24V6NmjZQbGchVbY6UM2BluqHv1rCqzVZ1KQlkZboepCdQvacPsz5bjTfXao+yMEaDt7Wk9tSIMVGig3TejCtJSM2bSpkPjWPqd1S6Zao+lORSYWmgkOjORRNwZqd5ezMSiHLRooNr5XwWjS6/1XHX9vL2T67N7M1iyXa9JCrYjVrS1gbpJyw6hBfsmiNCYT0P9/A+Wj1/6qGr5YNYFlJBiWJogEzezLz/ZG8/9s4fgtSyuvNYbyp1IONFBtu7sHNv4/j9yAxUHWrdaWsG9+N8XHd+YxkMpSy+aySz841cC5oXbmHCnnI74yxAgZ3YbDeB4PEQCOpBpFNZWwa2ZWRcdnxLsl00crtRB0n2lLg8JNRfDKoM4NsolgBSmw/UMADba1+qpmqfyf6x1u/0a/og3I+aEunP6/i86osqmygcGarF4p54dex/Bo0LqfqOfVwIQ/HW5/RSkwV1oN2WLlHTc82TljAwM4M1O5LWwYKZTjibYXNS0N5KcjKTe10PadfLObFuJwK4ozp+UzXDBTUjL+M5ZcBnRkQV53dMIwNQTu6bSTbVEzbi5awuVByd2E/FgaN0Tc1fKOzBHHV2aAdVSdv6s5NNkp7cSH/++xAng2yyHx+CM/H21YhfdPp+0U1X0TbSZnXx8faG9Aop0MS0cToh1p+iLcpOkLj9t/JOk5eqoPHxnDsyf486an5yqCDK7XZ1O4oZ4dWyy3FSXHUAYq47uyYbMZoGmhpG3DlEFb6uNiVBhpyaHhnBO8oJmfqOROJjzIiP43hJ8UxITqqX56S2Hur2KsOnq3nrE6PPNKPRwrSKbAZrjTQNZmuE7oxYXMZmxWbw9dxWFu4W4ezVedOE6qzI7oyYkY+M7TPeWsPbk2UX1qioSN+E3OZqOR2cReKE+qQRFN0Pi7y73g/UawU1KzezJpXwLz5hczX1ueUPKYkNb6GJQZ+j7/aAfRZREsv+quGsMoamXZBW2Gt5eU0alorEzYsKmJRa/m4NdeyxlqZsCGa84DKnVorEzboC7podis69DfIJmwufHMc7famvvmxZiYsKOtKWbRm1OcW1syEBboSJFozLh/EcmtmwgIluaM14/phrLdmJixYXMTiaM24p5I91syEBTphFOR7Y2tmwgJNvUFOr+tov3UzoaAv44KYUatv62ZCoemdhtG0+hzqrZsJBR08DWLG0gxKrZu50qvpxos3U5NItW4mFPp1ot+lPlpq2lYXs9qamVBZUMiC1ox4pJYjvlfStAu6GmTLcLboMtPIV4/6im5fFfuUi9QIap2MiWP+D96R1vPmsD/fAAAAAElFTkSuQmCC",
          fs = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAKUAAABsCAYAAAALzHKmAAAQ7klEQVR42u3da4xdVRUA4D0zd2Y6nZY59DVtZ1puS9+lzC0YAi2UQ8AAQczFpPgA9VIeIQbirRqJ0cBUBVGjDr/QCKSNRSMmpuODxAdxqhgwxkhFjf6Sxh/+UUNVNGJCzR7uTvas7LXX2q9zzp3em6y0gTN3Zu75utZe5+yztxC9V+/Ve5X9En1Vjd7J6SFbLNF7naPw+l2jh7YHMBWssqMHtlsRdim4qsLtIawaPiHEQOLoNrA9iIkQDnRrVA1qD2LZ8ISoxYqKo13sQAtBWBayQWZUAXGRQM9JjCngDVY0UqJNDbQrMcaGmArdUKpIjbYiQLsCZCyIMQBy8QwnilR4Q5AuCpxFYvRFmBLbEiwKwpsSaWycVQGZBKMrwBjA9BhxDe57u2L2hOoKNCbOrgAZitEVYUxoKSMErQvSxYIzCkguRg5EF4AUhqUlhy/YUKSxcRaKsioYOQhD4I0yYxkR3PcJBcuFysmgsXAWBTMJyBCMIQh9kGGxXIXvexCQXbHGAMrBWTbM2CCpMSMLIxehC77lSJwXGth7M0FzoVJIXXDWQnGmhOkL0ic7YhhtWdGGkAuPAjUWGoF4faCmwBkbZmyUqUCyMqMLRA4+E6IsdTjidUHKBYrh9CnpRcH0ypKxsyOGEYNIIeTCOz91OIJ1QYoB5eAMyZo+MFNnyVTZ0YiRC9EGEMOyAgshxErHsL2XK1gOUgwohtM1a5YNM7Rsu4K0ZkcbRm4mpPBRwFZ5hg9eCqkrUB+csWGGogzNkqEgrdnRhpGLkINudaLgwvVB6oqzCjCTZElb2Y4B0gUjBtEG0ARnDRLjjoG9DwcshtQGlIPTljVjwUySLWNkyRCQVHa0ZUUTRAwgF91a33BEy0VKAcVwwqwZC2bqbOlUurllOxQkJzNyINoAYqjWhYYjWg5SCiiG05Q1U8FMjTIoS8YE6YORi1BHtJ4KIcQEEtTXUWAxpK44YVlPBdO1jCdFWTZIE8bVGEYMIRPcZGBw4HKQcoBiOE1ZMzbMgVQwU6JMAdKEEcuIJogUvg1YCCE2gsCO42DlIIVAKZwpYJaSLVNnSU6XjYHUmxhTmXaFaMO3EYkLqMC+FsLlIoVAKZzMrEnBhJeLfLNlKMrYWRIDCbOkFSSVHbHM6AKRC6/ODUewNqQ+OLlZkxpjUmV8MBbMUJSxyzY3Q1IgTRgxiBRCHdem0KDAUkBh9sRwwjEnAXMMgTnKhFlUtiwkS5rGka4g9SaGgxFmRC7AzTCEEBcyA36dDSsXqAtOLkysjGMwY5XxVChjZ0kuSCo7YlkRQsQQYtDEFsegsLoCxUp7Kpgps2UslFGzJGccSYHUmxhOZqwzEZqAbfUMCisHKIZzgsCpl3MTzMwTpi1bYp2477gyFKUxS7qWbdjY2EBS2dGE0QQRA7gNCyHEdhjE8RhUDlBT9tzgmjWZMFNlSy+Urk1OzCyJlW0XkK4YOQh1cDtcgwBrQmoDWkdgboBZE8mYsJSHlnFbJ+5bwmOPJ7lZkirbC8aRsMvmgtTHjBhGE0QbwJ2egUE1ITVlUC5OmDVdYNrKuN70xM6WoShjlW4464dbtiFIWK6x7GjESEHUUe0iYncnbMdQSE0Z1ITTNOb0hRmjjLtmS9dmJ2rp1jtuKktyyrb6YLEMCUHq2dGG0QQRQ7f72kzc+cJecerne8Wvv7JNPHPvenEkz8Sh3UtFc92QyGt9Yko/HgOLAIUZlItTz5ouMF3KuE+2jFLCQ1D6lm6fLMkBacuOJowYRBUXyfjuHjF3NhdnsfjvAfH6E9vFt9XxKgikEKgJZyyYalzOLeMu2bLbULI6bh+QGwmQ+rgRlumdGEQAao+K56bEL2woVUwOiev0r8OAUjiJrMmFCbvykGxZRAmPitK1dHM7bohyMsuyi/I8f0+e57fJYIKEZXpXo9E4mOf5XTKyLLvCBLETF8uY2SKepkC+dpX4T02Ivepr4HvZcOZ5fmee54fyPL+DmTUhzAs6n4n8bN5dr9f3YdkSg8nsxG0lPBVKVpNjG0/aGhzfLDmRZdnumZmZp8+c+cdZPV555fSr7Xb7s0jJ3i5Pcue4MxKkPPkvvXTqz/B92u32l0wYOzG1fkhcd/py8Rcbyq/vFM/KY1WA95h/3zzP71bfU6JsNpsfgj+P/FlbrdaDGExYyuXvLz8H+DudODH700ajcSM3W6Yu4alQ1spCOTd38jcKocTZbh9+9NixY99XJ8AEUkcpo9W64yH197m5k7+bnZ19QT+J09NHntQhwji/Jg58qi6++ofLxJ8gSFneVw2Ka4QQDfh1Ok4dZavVmtZ/nrm5k7/Vf55O1tRhboUw5+ZOvqyOl5+R/FyOHj32PYVU/tloNG5IXcKrhJIzngwp3fNjomazea/64BuNxts646f50lWv169utw9/DmtqdJQyZFaSJVuV6nq9fqMEof5/vV6/CYBqgJDlee+yAbF/+4i4ZWqZeNfaIfHWzn+Hx0KcEuU9+s8jv3ej0bhVlXOZydX/k0iRMeb8P0D5e6tj8zy/Xb9UJIc56h/yqVOnXul8lmuZ2bJslKmbHG7XrbpCmCXFRLvdfqQD6jTS3Jiy5I4OykM6ADV+1Eu1DmV6evopBORexzDi1L+X/HnGxsb2w3Hm9PSRJ9QxWPOTZdmlKht2hi+w6dkox5bqffI8fye3hDteGqKaHVsHXihKl0tB+h0cY+lute54AGRKDCW89LNTRynHb7ChUWVVjetOnJh9EYBUyPZeNCoOtsbFQwdXi4/esELcd+tq8cCHJ8UXp+viy9efLz7AgamjlKXc1AA1m83DoIRDlFubzeb96hhZLVTlgJ24gttutx+ONa50bHZKRenaeTs1OfpAfnr6yOOdE7EZdNwmlKocntXLNkA5JTGq47Ds+Lf94lWsyfnXleLfnIwJUN4DOnNYwuUxh2A3Ln9XULrfK8t3J27Tu3BVwiOjXJqoAy8UZej1yclGo3GTLN+gu3w+z/P3YaWbQqk3Ne12e4ZC+c8rxWsYytcPiP9RpZxCqWDKnxOiBNlyAUpOnGsoh4tA2Rm8X9xqtT6md5wyZmYe+0YRKL+1S/wYQ3n8zctBl5SBUv5djivfjMOPduIzcizeiYfr9foVvUwZG+XCuzibZKnSceZ5/v4QlKp8y7ElhnJlTeTP7BI/kllRYfzrfvHqFy4UX1vaL/aVlSmROzwbwdS29T2UcEwZF+V8ozM2lu1VY812u/15akypGh3TmFJesJbHHD167IdUxz3YJy5bNySuX1mbvy55CbMLtzU6tjGlsdFptVqfUMc0Go23F4wy1l2dSnbfvpMwVPe9WWVLDsrOJaF9MFu2Wq1PqmNkGce67xiXhTjdNwdlvV6/BgxfbPfBfVCetxi6b9/rlCup65QzM48dl2OjLMv26CibzeZ96sTIzEFdpwQXz9U1yrtVlpR/Zll2Fec65Y6l4pbbx8XHH9kknvzJlPjlHy8Tp29eKT5ou0aJoIT3w3dBlLDzVpfAJEZ1XOdaJZxnOSlvPMjPzxFljIvng914RwebsjYO7uhMyHu46sOfnf3Oz2TXDW6vvYxdFoIXz3Wc8J5zs9n8iOn2IrxTc2BM3Glqdp7dI553uaOjxrhwcob+MyuUpjs6WZZdon8OcigjPx8V+u+GTWFTSWEx3WYcdJ225jNDSE4q0GHCzlueHOyujn6bUWYgeb9ZZUaQPe+GzQ+Gc8+oOGhC+c1d4gfI16n3XDAhQ7+9qE9l01E2Go132GYKyXE1NiFDTcpoNpv3LOYJGWXNErJNW9sEp63p2RKiVPMn1bS1DgxsyhoGdGpmizj+xtXiDYnx7/vFmce3iWdW1cTVGEY4hQ2ZW0nNq8Qm/M6XbXm3S100lwGedFybuvNOibLI+ZS2ceU4eAxiEuvCkfmU8ycToDxETe6FgCBQHeqyAbFvfEhcO7BwDuXFCEbTZF840XeHK0jYcbs2OIGle0mVJ/mmnClEPQqxyTY5I8/zFhif7fSZee4bnrPOU4AssnRXHaVTCTd14dRDY3UbTIiSeFhsN/aMjgnqthFx880rxX3yATL5p3y4LPXzOaBkUyBjZMlYpbtQlIOBD475ZEusjMNSvkXe6VEoJVDkeZ2dzIfIFsRzU+JF2OyM9M9fTC/6SUYOyFQPjQ2nWiUjxnPfw5EeHqMWIqAeIFsAU847lJM2JM6xsewt1OIDLs99P7ZFHNdB/upS8XtPiD7PfLuCXJNolYyyFiNI/Zit65ItrOVafFbHcFohY7hPTN21Tjz4uc3iqfsnxKdX1MTl1OoYRFaMsToGB6Trw2JFP/OdZC2hJZ7ZkrMoAbbSGmelDJ91hFKuJeS7jlBMkJnrAqqJlgMUZS/dArPlGHNdSg5M3xXXtvquuEatvIYtDRhpxbUJuIgqsU5lGWtUploK0KuEU9mSW8YpmFQ556xNuYW7NiW13B+FkMiKHIy+C6eGgBxJvMR0oSv5hi6+z4HJyZoU0M2RVvDlrOQbcxVfX5AhZbuqy0v7ZstYMLHlAVlLTF9ALLbvu9Y5Zylpn/XOsd0ibIvxr2KCLHpp6SCUIdnSZSF+WzfOhem6GD+1KwR3Z4jNjrtDpNoZwmWd8yrupZN6Hx3fbMmFSe0Swdq2ZIPjxk1112Duo8OBGLrBkw/IoncdK2XHsdC9dHz204m50xh3tzFq1zFqtzHXrfCw7OgDsqyNnZLszVijsmXgrmNcmGtS78lIoMX2aJz03fKO2sDJddPQSCDPiQ1DfWBycY6XtXstc2PQKuxgG2McmXTPb9/9vmuJYXKyJrWjbeg+3xPM4O73nWqvbyw7xgZZSJbEUBa157cNJjdr2vb+5iA1YV3HxYscj30PDCEHIgcjtfm8K8hSsmRotkwFk5s1TTghUAopB6xrjHMBBkI0YYTZ0dZlxwLpkiWDULpmy5gwqayZgZNkA7oKQQCxctByYg0XIIEQQuRitGVHblMTA2ShKGPDpC6wu+DEgJqg2rDGDBtAF4Q6RAojp1xXGmSMbImVcR+YWNY04eQCtUG1ofUJ2/uvcETIgUhhdAE5GAlkKShjwHTNmhhODKgJqQ2sC14uOgyfD0IbRF+MlQaZAiZWyn2yJsTJATqGnHQO2Jhh+xlsACFCG0QbRtdyzQFZCZSxYPpmTS7Q5cjJHYNBYIkZpu99HoUQ/o4QIYSIZUZfjJ4ZMjZI32wZBDMU5yhy8pZTULl4XYP5fagMyEVoy4oupTpGduwnkloSlKEwY+AcQU4MhRTD6ovXBRwFzwWgCSEF0QVjJUGmgEllTS5OLlCIlIN1mS9mx/cZ5eLDALpCTI2RAhkTZQqYoTgpoCPECbaBHQ2ETL3PUl98ECAXYijG0OyYAmQoTG7W5ODkAF1CnVgm2JQx4okPA+gCMTbGskBGgRmaOblAh5GTORIrfKFx4VH4EIAxIXIxlg2SBbMvECY3e7oApbDaIgQu5/2HmeEKEINYiwSRi7EQkLFgumZOCuggctKGI4ULZN/vMeSLj0AYMytWEqMLzFg4fYDaoKaC6wvOFR4FkIPQFaILxrJAOsHsc/zlfYDWXE8qF22s8Pz5KHxcgEVALBtjJXBSSEOwFhk1Zgy4hitCT4hVw+gFs8/zwxqIBbUgyK7fcyA0PD9XX4iVxhiC0xdof6STWCsoBmKF7+cVCWFXQYyBMxRpf+STX1b0x45AhN0OMSrOGEirhrY/dfQAdjvS7oy+WCF6r1RIFxXWvlTRg1YVqFWBmxZbD99ig9pt0YPQw9rD1nstVri9V+/Ve3XrS/wfim4P5fIFxLoAAAAASUVORK5CYII=",
          ys = class {
            constructor(t, e) {
              this.config = e, e.pathPrefix || (e.pathPrefix = ""), e.app || (e.app = {
                loadAssets: () => {},
                initialize: () => {},
                update: () => {},
                render: () => {},
                error: () => {},
                dispose: () => {}
              }), e.webglConfig || (e.webglConfig = {
                alpha: !0
              }), this.htmlCanvas = t, this.context = new bi(t, e.webglConfig), this.renderer = new hs(t, this.context), this.gl = this.context.gl, this.assetManager = new xi(this.context, e.pathPrefix), this.input = new Ui(t), e.app.loadAssets && e.app.loadAssets(this);
              let i = () => {
                  this.disposed || (requestAnimationFrame(i), this.time.update(), e.app.update && e.app.update(this, this.time.delta), e.app.render && e.app.render(this))
                },
                s = () => {
                  if (!this.disposed) {
                    if (this.assetManager.isLoadingComplete()) return void(this.assetManager.hasErrors() ? e.app.error && e.app.error(this, this.assetManager.getErrors()) : (e.app.initialize && e.app.initialize(this), i()));
                    requestAnimationFrame(s)
                  }
                };
              requestAnimationFrame(s)
            }
            context;
            time = new x;
            htmlCanvas;
            gl;
            renderer;
            assetManager;
            input;
            disposed = !1;
            clear(t, e, i, s) {
              this.gl.clearColor(t, e, i, s), this.gl.clear(this.gl.COLOR_BUFFER_BIT)
            }
            dispose() {
              this.config.app.dispose && this.config.app.dispose(this), this.disposed = !0
            }
          },
          _s = ((t, s, n) => (n = null != t ? e(r(t)) : {}, h(!s && t && t.__esModule ? n : i(n, "default", {
            value: t,
            enumerable: !0
          }), t)))(__PhaserShim, 1),
          bs = "spine",
          vs = Phaser.GameObjects.Components,
          xs = vs.ComputedSize,
          ws = vs.Depth,
          Ss = vs.Flip,
          Ts = vs.ScrollFactor,
          Cs = vs.Transform,
          ks = vs.Visible,
          Ps = vs.Origin,
          As = vs.Alpha;

        function Is(...t) {
          return e => (Phaser.Class.mixin(e, t), e)
        }
        var Es = Is(xs),
          Os = Is(ws),
          Ms = Is(Ss),
          Bs = Is(Ts),
          Rs = Is(Cs),
          Ds = Is(ks),
          Ls = Is(Ps),
          Fs = Is(As),
          Ns = class extends Phaser.GameObjects.GameObject {
            constructor(t, e) {
              super(t, e)
            }
          },
          Vs = class {
            constructor(t, e, i, s) {
              this.x = t, this.y = e, this.width = i, this.height = s
            }
            calculateBounds() {
              return {
                x: this.x,
                y: this.y,
                width: this.width,
                height: this.height
              }
            }
          },
          zs = class {
            constructor(t = !1) {
              this.clipping = t
            }
            calculateBounds(t) {
              if (!t.skeleton) return {
                x: 0,
                y: 0,
                width: 0,
                height: 0
              };
              const e = new de(t.skeleton.data);
              e.setToSetupPose(), e.updateWorldTransform(2);
              const i = e.getBoundsRect(this.clipping ? new oi : void 0);
              return i.width == Number.NEGATIVE_INFINITY ? {
                x: 0,
                y: 0,
                width: 0,
                height: 0
              } : i
            }
          },
          Us = class {
            constructor(t, e = [], i = .05, s = !1) {
              this.animation = t, this.skins = e, this.timeStep = i, this.clipping = s
            }
            calculateBounds(t) {
              if (!t.skeleton || !t.animationState) return {
                x: 0,
                y: 0,
                width: 0,
                height: 0
              };
              const e = new yt(t.animationState.data),
                i = new de(t.skeleton.data),
                s = this.clipping ? new oi : void 0,
                n = i.data;
              if (this.skins.length > 0) {
                let t = new fe("custom-skin");
                for (const e of this.skins) {
                  const i = n.findSkin(e);
                  null != i && t.addSkin(i)
                }
                i.setSkin(t)
              }
              i.setToSetupPose();
              const r = null != this.animation ? n.findAnimation(this.animation) : null;
              if (null == r) {
                i.updateWorldTransform(2);
                const t = i.getBoundsRect(s);
                return t.width == Number.NEGATIVE_INFINITY ? {
                  x: 0,
                  y: 0,
                  width: 0,
                  height: 0
                } : t
              } {
                let t = Number.POSITIVE_INFINITY,
                  n = Number.POSITIVE_INFINITY,
                  a = Number.NEGATIVE_INFINITY,
                  o = Number.NEGATIVE_INFINITY;
                e.clearTracks(), e.setAnimationWith(0, r, !1);
                const h = Math.max(r.duration / this.timeStep, 1);
                for (let r = 0; r < h; r++) {
                  const h = r > 0 ? this.timeStep : 0;
                  e.update(h), e.apply(i), i.update(h), i.updateWorldTransform(2);
                  const l = i.getBoundsRect(s);
                  t = Math.min(t, l.x), n = Math.min(n, l.y), a = Math.max(a, l.x + l.width), o = Math.max(o, l.y + l.height)
                }
                const l = {
                  x: t,
                  y: n,
                  width: a - t,
                  height: o - n
                };
                return l.width == Number.NEGATIVE_INFINITY ? {
                  x: 0,
                  y: 0,
                  width: 0,
                  height: 0
                } : l
              }
            }
          },
          Hs = class extends(Os(Ls(Es(Ms(Bs(Rs(Ds(Fs(Ns))))))))) {
            constructor(t, e, i, s, n, r, a = new zs) {
              super(t, window.SPINE_GAME_OBJECT_TYPE ? window.SPINE_GAME_OBJECT_TYPE : bs), this.plugin = e, this.boundsProvider = a, this.setPosition(i, s), this.premultipliedAlpha = this.plugin.isAtlasPremultiplied(r), this.skeleton = this.plugin.createSkeleton(n, r), this.animationStateData = new It(this.skeleton.data), this.animationState = new yt(this.animationStateData), this.skeleton.updateWorldTransform(2), this.updateSize()
            }
            blendMode = -1;
            skeleton;
            animationStateData;
            animationState;
            beforeUpdateWorldTransforms = () => {};
            afterUpdateWorldTransforms = () => {};
            premultipliedAlpha = !1;
            offsetX = 0;
            offsetY = 0;
            updateSize() {
              if (!this.skeleton) return;
              let t = this.boundsProvider.calculateBounds(this);
              this.width = t.width, this.height = t.height, this.setDisplayOrigin(-t.x, -t.y), this.offsetX = -t.x, this.offsetY = -t.y
            }
            skeletonToPhaserWorldCoordinates(t) {
              let e = this.getWorldTransformMatrix(),
                i = e.a,
                s = e.b,
                n = e.c,
                r = e.d,
                a = e.tx,
                o = e.ty,
                h = t.x,
                l = t.y;
              t.x = h * i + l * n + a, t.y = h * s + l * r + o
            }
            phaserWorldCoordinatesToSkeleton(t) {
              let e = this.getWorldTransformMatrix();
              e = e.invert();
              let i = e.a,
                s = e.b,
                n = e.c,
                r = e.d,
                a = e.tx,
                o = e.ty,
                h = t.x,
                l = t.y;
              t.x = h * i + l * n + a, t.y = h * s + l * r + o
            }
            phaserWorldCoordinatesToBone(t, e) {
              this.phaserWorldCoordinatesToSkeleton(t), e.parent ? e.parent.worldToLocal(t) : e.worldToLocal(t)
            }
            updatePose(t) {
              this.animationState.update(t / 1e3), this.animationState.apply(this.skeleton), this.beforeUpdateWorldTransforms(this), this.skeleton.update(t / 1e3), this.skeleton.updateWorldTransform(2), this.afterUpdateWorldTransforms(this)
            }
            preUpdate(t, e) {
              !this.skeleton || !this.animationState || this.updatePose(e)
            }
            preDestroy() {}
            willRender(t) {
              var e = !this.skeleton || !(15 !== this.renderFlags || 0 !== this.cameraFilter && this.cameraFilter & t.id);
              if (this.visible || (e = !1), !e && this.parentContainer && this.plugin.webGLRenderer) {
                var i = this.plugin.webGLRenderer;
                this.plugin.gl && this.plugin.phaserRenderer instanceof Phaser.Renderer.WebGL.WebGLRenderer && i.batcher.isDrawing && (i.end(), this.plugin.phaserRenderer.pipelines.rebind())
              }
              return e
            }
            renderWebGL(t, e, i, s) {
              if (!this.skeleton || !this.animationState || !this.plugin.webGLRenderer) return;
              let n = this.plugin.webGLRenderer;
              t.newType && (t.pipelines.clear(), n.begin()), i.addToRenderList(e);
              let r = Phaser.GameObjects.GetCalcMatrix(e, i, s).calc,
                a = r.a,
                o = r.b,
                h = r.c,
                l = r.d,
                c = r.tx,
                d = r.ty,
                u = e.offsetX - e.displayOriginX,
                p = e.offsetY - e.displayOriginY;
              n.drawSkeleton(e.skeleton, e.premultipliedAlpha, -1, -1, (t, e, i) => {
                for (let s = 0; s < e; s += i) {
                  let e = t[s] + u,
                    i = t[s + 1] + p;
                  t[s] = e * a + i * h + c, t[s + 1] = e * o + i * l + d
                }
              }), t.nextTypeMatch || (n.end(), t.pipelines.rebind())
            }
            renderCanvas(t, e, i, s) {
              if (!this.skeleton || !this.animationState || !this.plugin.canvasRenderer) return;
              let n = t.currentContext,
                r = this.plugin.canvasRenderer;
              r.ctx = n, i.addToRenderList(e);
              let a = Phaser.GameObjects.GetCalcMatrix(e, i, s).calc,
                o = this.skeleton;
              o.x = a.tx, o.y = a.ty, o.scaleX = a.scaleX, o.scaleY = a.scaleY, o.getRootBone().rotation = -p.radiansToDegrees * a.rotationNormalized, this.skeleton.updateWorldTransform(2), n.save(), r.draw(o), n.restore()
            }
          };
        de.yDown = !0;
        var Ws = class t extends _s.Plugins.ScenePlugin {
            game;
            isWebGL;
            gl;
            static gameWebGLRenderer = null;
            get webGLRenderer() {
              return t.gameWebGLRenderer
            }
            canvasRenderer;
            phaserRenderer;
            skeletonDataCache;
            atlasCache;
            constructor(t, e, i) {
              super(t, e, i), this.game = e.game, this.isWebGL = 2 === this.game.config.renderType, this.gl = this.isWebGL ? this.game.renderer.gl : null, this.phaserRenderer = this.game.renderer, this.canvasRenderer = null, this.skeletonDataCache = this.game.cache.addCustom("esotericsoftware.spine.skeletonFile.cache"), this.atlasCache = this.game.cache.addCustom("esotericsoftware.spine.atlas.cache");
              e.registerFileType("spineJson", function(t, e, i) {
                let s = new Ys(this, t, e, 0, i);
                return this.addFile(s.files), this
              }, t);
              e.registerFileType("spineBinary", function(t, e, i) {
                let s = new Ys(this, t, e, 1, i);
                return this.addFile(s.files), this
              }, t);
              e.registerFileType("spineAtlas", function(t, e, i, s) {
                let n = new Gs(this, t, e, i, s);
                return this.addFile(n.files), this
              }, t);
              e.registerGameObject(window.SPINE_GAME_OBJECT_TYPE ? window.SPINE_GAME_OBJECT_TYPE : bs, function(t, e, s, n, r) {
                this.scene.sys.renderer instanceof _s.Renderer.WebGL.WebGLRenderer && this.scene.sys.renderer.pipelines.clear();
                const a = this.scene.sys[i];
                let o = new Hs(this.scene, a, t, e, s, n, r);
                return this.displayList.add(o), this.updateList.add(o), this.scene.sys.renderer instanceof _s.Renderer.WebGL.WebGLRenderer && this.scene.sys.renderer.pipelines.rebind(), o
              }, function(t, e = !1) {
                this.scene.sys.renderer instanceof _s.Renderer.WebGL.WebGLRenderer && this.scene.sys.renderer.pipelines.clear();
                let s = t.x ? t.x : 0,
                  n = t.y ? t.y : 0,
                  r = t.boundsProvider ? t.boundsProvider : void 0;
                const a = this.scene.sys[i];
                let o = new Hs(this.scene, a, s, n, t.dataKey, t.atlasKey, r);
                return void 0 !== e && (t.add = e), this.scene.sys.renderer instanceof _s.Renderer.WebGL.WebGLRenderer && this.scene.sys.renderer.pipelines.rebind(), _s.GameObjects.BuildGameObject(this.scene, o, t)
              })
            }
            static rendererId = 0;
            boot() {
              this.isWebGL && this.gl ? t.gameWebGLRenderer ||= new hs(this.game.renderer.canvas, this.gl, !0) : this.scene && (this.canvasRenderer ||= new _i(this.scene.sys.context)), this.onResize(), this.systems && (this.systems.events.once("destroy", this.destroy, this), this.systems.events.on("start", this.onStart, this), this.systems.events.on("shutdown", this.shutdown, this)), this.game.events.once("destroy", this.gameDestroy, this)
            }
            onResize() {
              const t = this.game.renderer,
                e = this.webGLRenderer;
              if (t && e) {
                const i = t.width,
                  s = t.height;
                e.camera.position.x = i / 2, e.camera.position.y = s / 2, e.camera.up.y = -1, e.camera.direction.z = 1, e.camera.setViewport(i, s)
              }
            }
            onStart() {
              this.game.scale.on(_s.Scale.Events.RESIZE, this.onResize, this)
            }
            shutdown() {
              this.isWebGL && this.game.scale.off(_s.Scale.Events.RESIZE, this.onResize, this)
            }
            destroy() {
              this.shutdown(), this.systems?.events.off("start", this.onStart, this), this.systems?.events.off("shutdown", this.shutdown, this)
            }
            gameDestroy() {
              this.pluginManager.removeGameObject(window.SPINE_GAME_OBJECT_TYPE ? window.SPINE_GAME_OBJECT_TYPE : bs, !0, !0), this.webGLRenderer && this.webGLRenderer.dispose(), t.gameWebGLRenderer = null
            }
            getAtlas(t) {
              let e;
              if (this.atlasCache.exists(t)) e = this.atlasCache.get(t);
              else {
                let i = this.game.cache.text.get(t);
                if (e = new Ft(i.data), this.isWebGL) {
                  let i = this.gl;
                  const s = i.getParameter(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL);
                  s && i.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL, !1);
                  for (let s of e.pages) s.setTexture(new vi(i, this.game.textures.get(t + "!" + s.name).getSourceImage(), !1));
                  s && i.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL, !0)
                } else
                  for (let i of e.pages) i.setTexture(new fi(this.game.textures.get(t + "!" + i.name).getSourceImage()));
                this.atlasCache.add(t, e)
              }
              return e
            }
            isAtlasPremultiplied(t) {
              let e = this.game.cache.text.get(t);
              return !!e && e.premultipliedAlpha
            }
            getSkeletonData(t, e) {
              const i = this.getAtlas(e),
                s = t + e;
              let n;
              if (this.skeletonDataCache.exists(s)) n = this.skeletonDataCache.get(s);
              else {
                if (this.game.cache.json.exists(t)) {
                  let e = this.game.cache.json.get(t);
                  n = new hi(new Gt(i)).readSkeletonData(e)
                } else {
                  let e = this.game.cache.binary.get(t);
                  n = new ve(new Gt(i)).readSkeletonData(new Uint8Array(e))
                }
                this.skeletonDataCache.add(s, n)
              }
              return n
            }
            createSkeleton(t, e) {
              return new de(this.getSkeletonData(t, e))
            }
          },
          Ys = class extends _s.Loader.MultiFile {
            constructor(t, e, i, s, n) {
              if ("string" != typeof e) {
                const t = e;
                e = t.key, i = t.url, s = "spineJson" === t.type ? 0 : 1, n = t.xhrSettings
              }
              let r = null;
              r = 0 == s ? new _s.Loader.FileTypes.JSONFile(t, {
                key: e,
                url: i,
                extension: "json",
                xhrSettings: n
              }) : new _s.Loader.FileTypes.BinaryFile(t, {
                key: e,
                url: i,
                extension: "skel",
                xhrSettings: n
              }), super(t, "spineSkeletonData", e, [r]), this.fileType = s
            }
            onFileComplete(t) {
              this.pending--
            }
            addToCache() {
              this.isReadyToProcess() && this.files[0].addToCache()
            }
          },
          Gs = class extends _s.Loader.MultiFile {
            constructor(t, e, i, s, n) {
              if ("string" != typeof e) {
                const t = e;
                e = t.key, i = t.url, s = t.premultipliedAlpha, n = t.xhrSettings
              }
              super(t, "spineAtlasData", e, [new _s.Loader.FileTypes.TextFile(t, {
                key: e,
                url: i,
                xhrSettings: n,
                extension: "atlas"
              })]), this.premultipliedAlpha = s
            }
            onFileComplete(t) {
              if (-1 != this.files.indexOf(t) && (this.pending--, "text" == t.type)) {
                var e = t.data.split(/\r\n|\r|\n/);
                let h = [];
                h.push(e[0]);
                for (var i = 1; i < e.length; i++) {
                  var s = e[i];
                  "" === s.trim() && i < e.length - 1 && (s = e[i + 1], h.push(s))
                }
                let l = (t.src.match(/^.*\//) ?? "").toString();
                this.loader.path && this.loader.path.length > 0 && l.startsWith(this.loader.path) && (l = l.slice(this.loader.path.length));
                for (var n = 0; n < h.length; n++) {
                  var r = l + h[n],
                    a = t.key + "!" + h[n],
                    o = new _s.Loader.FileTypes.ImageFile(this.loader, a, r);
                  this.loader.keyExists(o) || (this.addToMultiFile(o), this.loader.addFile(o))
                }
              }
            }
            addToCache() {
              if (this.isReadyToProcess()) {
                let t = this.loader.textureManager;
                for (let e of this.files) "image" == e.type ? t.exists(e.key) || t.addImage(e.key, e.data) : (this.premultipliedAlpha = this.premultipliedAlpha ?? (e.data.indexOf("pma: true") >= 0 || e.data.indexOf("pma:true") >= 0), e.data = {
                  data: e.data,
                  premultipliedAlpha: this.premultipliedAlpha
                }, e.addToCache())
              }
            }
          };
  global.SpineOfficial = Object.assign({}, l, { CanvasTexture: fi, CanvasSkeletonRenderer: _i });
})(typeof window !== 'undefined' ? window : globalThis);
