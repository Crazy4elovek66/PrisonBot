/**
 * Официальный рендер комнат (хат) для Примерочной:
 * 1. Spine 4.2 / 4.3 (хаты 27..37) через window.SpineOfficial (из bundle.js игры)
 * 2. Flash room.bundle (хаты 39, 40, 41, 42, 44, 45, 54) через window.BundleCodec
 * 3. Покадровые эффекты effect_config.json (1..10, 14, 15, 18..26, 42, 43, 46..48)
 * Без каких-либо самодельных анимаций, обрезков или синтетических покачиваний.
 */
(function (global) {
  "use strict";

  const VIEWPORT = { x: 485, y: 217, w: 755, h: 562 };
  const STAGE = { cx: 1000, cy: 800, dx: -138, dy: -302, scale: 1.302 };

  const SPINE_ROOM_IDS = new Set([27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37]);
  const SPINE_ALT_ROOT_IDS = new Set([30, 31, 32, 33, 34, 35, 37]);
  const BUNDLE_ROOM_IDS = new Set([39, 40, 41, 42, 44, 45, 54]);
  const EFFECT_ROOM_IDS = new Set([
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    14, 15,
    18, 19, 20, 21, 22, 23, 24, 25, 26,
    42, 43, 46, 47, 48,
  ]);
  const ROOM_54_SKIP_PLACEMENTS = new Set([449, 494, 697, 699, 701]);
  const FLASH_BLEND_MODES = {
    3: "multiply",
    4: "screen",
    5: "lighten",
    6: "darken",
    7: "difference",
    8: "lighter",
    13: "overlay",
    14: "hard-light",
  };

  function proxyAssetUrl(relPath) {
    if (typeof window !== "undefined" && typeof window.proxyAssetUrl === "function") {
      return window.proxyAssetUrl(relPath);
    }
    const clean = String(relPath || "").replace(/^\/+/, "");
    return `/api/v1/assets/proxy?path=${encodeURIComponent(clean)}`;
  }

  function loadImageUrl(url) {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = url;
    });
  }

  function decodePngBlob(bytes) {
    const blob = new Blob([bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)], {
      type: "image/png",
    });
    const url = URL.createObjectURL(blob);
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        resolve(img);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("Failed to decode bundle PNG shape"));
      };
      img.src = url;
    });
  }

  function imageToCanvas(img) {
    const c = document.createElement("canvas");
    c.width = img.naturalWidth || img.width || 1;
    c.height = img.naturalHeight || img.height || 1;
    const g = c.getContext("2d");
    g.drawImage(img, 0, 0);
    return c;
  }

  function extractAtlasTextures(atlasText) {
    const files = [];
    const lines = String(atlasText || "").split(/\r?\n/);
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      if (/\.(?:webp|png)$/i.test(line) && !line.includes(":")) {
        files.push(line);
      }
    }
    return files;
  }

  async function loadSpineRoom(roomId) {
    const Spine = global.SpineOfficial;
    if (!Spine || !Spine.TextureAtlas || !Spine.SkeletonJson || !Spine.CanvasSkeletonRenderer) {
      return null;
    }
    const base = `assets/PrisonV3/RoomCameraUrl/${roomId}`;
    const [skelResp, atlasResp] = await Promise.all([
      fetch(proxyAssetUrl(`${base}/skeleton.json`)),
      fetch(proxyAssetUrl(`${base}/skeleton.atlas`)),
    ]);
    if (!skelResp.ok || !atlasResp.ok) return null;

    const [skelJson, atlasText] = await Promise.all([
      skelResp.json().catch(() => null),
      atlasResp.text().catch(() => ""),
    ]);
    if (!skelJson || !skelJson.bones || !atlasText.trim()) return null;

    const pageNames = extractAtlasTextures(atlasText);
    const atlas = new Spine.TextureAtlas(atlasText);
    const textures = new Map();

    await Promise.all(
      atlas.pages.map(async (page, idx) => {
        const texName = page.name || pageNames[idx] || "skeleton.webp";
        let img = await loadImageUrl(proxyAssetUrl(`${base}/${texName}`));
        if ((!img || img.naturalWidth <= 1) && /\.png$/i.test(texName)) {
          img = await loadImageUrl(proxyAssetUrl(`${base}/${texName.replace(/\.png$/i, ".webp")}`));
        }
        if (img && img.naturalWidth > 1) {
          const texCanvas = imageToCanvas(img);
          page.setTexture(new Spine.CanvasTexture(texCanvas));
          textures.set(texName, texCanvas);
        }
      })
    );

    if (textures.size === 0) return null;

    if (Spine.Skeleton) {
      Spine.Skeleton.yDown = true;
    }

    const loader = new Spine.AtlasAttachmentLoader(atlas);
    const sj = new Spine.SkeletonJson(loader);
    const skeletonData = sj.readSkeletonData(skelJson);
    const skeleton = new Spine.Skeleton(skeletonData);
    skeleton.setToSetupPose();

    const stateData = new Spine.AnimationStateData(skeletonData);
    const animState = new Spine.AnimationState(stateData);
    const firstAnim = (skeletonData.animations && skeletonData.animations[0]) || null;
    if (firstAnim) {
      animState.setAnimation(0, firstAnim.name, true);
    }

    const physUpdate = Spine.Physics ? Spine.Physics.update : 0;
    skeleton.updateWorldTransform(physUpdate);

    return {
      kind: "spine",
      roomId: Number(roomId),
      skeleton,
      skeletonData,
      animState,
      physUpdate,
      hasAnimation: Boolean(firstAnim && firstAnim.duration > 0),
      altRoot: SPINE_ALT_ROOT_IDS.has(Number(roomId)),
      lastTimeMs: null,
      renderer: null,
      rendererCtx: null,
    };
  }

  function renderSpineRoom(ctx, entry, timeMs) {
    const Spine = global.SpineOfficial;
    if (!Spine || !entry || !entry.skeleton) return false;

    if (Spine.Skeleton) {
      Spine.Skeleton.yDown = true;
    }

    if (entry.rendererCtx !== ctx || !entry.renderer) {
      entry.renderer = new Spine.CanvasSkeletonRenderer(ctx);
      entry.renderer.triangleRendering = true;
      entry.rendererCtx = ctx;
    }

    let dtSec = 0;
    if (entry.hasAnimation) {
      if (entry.lastTimeMs == null) {
        dtSec = 0.016;
      } else {
        dtSec = Math.min(0.1, Math.max(0, (timeMs - entry.lastTimeMs) / 1000));
      }
      entry.lastTimeMs = timeMs;
      entry.animState.update(dtSec);
      entry.animState.apply(entry.skeleton);
      entry.skeleton.updateWorldTransform(entry.physUpdate);
    }

    const BlendMode = Spine.BlendMode || {};
    const blendMap = new Map([
      [BlendMode.Additive, "lighter"],
      [BlendMode.Multiply, "multiply"],
      [BlendMode.Screen, "screen"],
    ]);

    const dx = entry.altRoot ? STAGE.dx - 376 : STAGE.dx;
    const dy = entry.altRoot ? STAGE.dy - 279 : STAGE.dy;

    const origOrder = entry.skeleton.drawOrder;
    ctx.save();
    try {
      ctx.translate(-VIEWPORT.x, -VIEWPORT.y);
      ctx.translate(STAGE.cx + dx, STAGE.cy + dy);
      ctx.scale(STAGE.scale, STAGE.scale);

      let i = 0;
      while (i < origOrder.length) {
        const bm = origOrder[i].data.blendMode;
        let j = i + 1;
        while (j < origOrder.length && origOrder[j].data.blendMode === bm) {
          j++;
        }
        ctx.globalCompositeOperation = blendMap.get(bm) || "source-over";
        entry.skeleton.drawOrder = origOrder.slice(i, j);
        entry.renderer.draw(entry.skeleton);
        i = j;
      }
    } finally {
      entry.skeleton.drawOrder = origOrder;
      ctx.restore();
    }
    return true;
  }

  // ---- Flash room.bundle decoder + renderer ----

  function getBundleTimeline(clip, startFrame) {
    let tl = clip.timelines.get(startFrame);
    if (tl) return tl;
    const frames = [];
    const seen = new Map();
    let cur = startFrame;
    let loopAt = null;
    for (; ;) {
      const prevIdx = seen.get(cur);
      if (prevIdx != null) {
        if (prevIdx < frames.length) loopAt = prevIdx;
        break;
      }
      const act = clip.actions ? clip.actions[cur] : null;
      seen.set(cur, frames.length);
      if (act && act[0] === 1 && act[1] !== cur) {
        cur = act[1];
        continue;
      }
      if (act && act[0] === 2) {
        frames.push(act[1]);
        break;
      }
      frames.push(cur);
      if (act && act[0] === 0) break;
      cur = (cur + 1) % clip.frames.length;
    }
    tl = { frames, loopAt };
    clip.timelines.set(startFrame, tl);
    return tl;
  }

  function resolveBundleFrame(clip, startFrame, tick) {
    if (clip.frames.length <= 1) return 0;
    if (!clip.actions) return (startFrame + tick) % clip.frames.length;
    const { frames, loopAt } = getBundleTimeline(clip, startFrame);
    if (tick < frames.length) return frames[tick];
    if (loopAt != null) return frames[loopAt + ((tick - loopAt) % (frames.length - loopAt))];
    return frames[frames.length - 1] ?? startFrame;
  }

  function readShapePixels(img) {
    const c = document.createElement("canvas");
    c.width = img.naturalWidth || img.width || 1;
    c.height = img.naturalHeight || img.height || 1;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(img, 0, 0);
    return {
      canvas: c,
      ctx,
      pixels: ctx.getImageData(0, 0, c.width, c.height),
    };
  }

  function buildShapeMaskPath(shape) {
    if (shape.mask) return shape.mask;
    const { canvas, pixels } = readShapePixels(shape.image);
    const { width: w, height: h } = canvas;
    const sx = shape.width / w;
    const sy = shape.height / h;
    const path = new Path2D();
    let openRuns = new Map();

    for (let y = 0; y <= h; y++) {
      const nextRuns = new Map();
      for (let x = 0; y < h && x < w;) {
        if (pixels.data[(y * w + x) * 4 + 3] < 128) {
          x += 1;
          continue;
        }
        const x0 = x++;
        for (; x < w && pixels.data[(y * w + x) * 4 + 3] >= 128;) x += 1;
        const key = x0 * (w + 1) + x;
        nextRuns.set(key, openRuns.get(key) ?? y);
        openRuns.delete(key);
      }
      for (const [key, y0] of openRuns) {
        const x0 = Math.floor(key / (w + 1));
        const x1 = key % (w + 1);
        path.rect(shape.x + x0 * sx, shape.y + y0 * sy, (x1 - x0) * sx, (y - y0) * sy);
      }
      openRuns = nextRuns;
    }
    shape.mask = path;
    return path;
  }

  function getTintedShapeImage(bundle, charId, shape, colorCx, colorMatrix) {
    const mulAdd = colorCx ? colorCx.slice(0, 6) : null;
    if (!colorMatrix && (!mulAdd || mulAdd.every((v, i) => v === 1 - (i % 2)))) {
      return shape.image;
    }
    const cacheKey = `${charId}:${mulAdd ? mulAdd.join(",") : ""}:${colorMatrix ? colorMatrix.join(",") : ""}`;
    const existing = bundle.tinted.get(cacheKey);
    if (existing) return existing;

    const { canvas, ctx, pixels } = readShapePixels(shape.image);
    const d = pixels.data;
    for (let i = 0; i < d.length; i += 4) {
      if (!d[i + 3]) continue;
      if (mulAdd) {
        for (let ch = 0; ch < 3; ch++) {
          d[i + ch] = d[i + ch] * mulAdd[2 * ch] + mulAdd[2 * ch + 1];
        }
      }
      if (colorMatrix) {
        const r = d[i], g = d[i + 1], b = d[i + 2], a = d[i + 3];
        for (let ch = 0; ch < 4; ch++) {
          const base = 5 * ch;
          d[i + ch] =
            colorMatrix[base] * r +
            colorMatrix[base + 1] * g +
            colorMatrix[base + 2] * b +
            colorMatrix[base + 3] * a +
            colorMatrix[base + 4];
        }
      }
    }
    ctx.putImageData(pixels, 0, 0);
    bundle.tinted.set(cacheKey, canvas);
    if (bundle.tinted.size > 48) {
      const oldest = bundle.tinted.keys().next().value;
      if (oldest !== undefined) bundle.tinted.delete(oldest);
    }
    return canvas;
  }

  function buildFlashFilterCss(filters, ctx) {
    const m = ctx.getTransform();
    const scale = (Math.hypot(m.a, m.b) + Math.hypot(m.c, m.d)) / 2;
    return filters
      .flatMap((flt) => {
        const [kind, nums, colorInt] = flt;
        const [p0, p1, p2, p3, p4] = nums;
        const hex = (0xffffff & colorInt).toString(16).padStart(6, "0");
        switch (kind) {
          case 0:
            return [`drop-shadow(0 0 ${(Math.max(p0, p1) * scale) / 2}px #${hex})`];
          case 1: {
            const ox = Math.cos(p0) * p1 * scale;
            const oy = Math.sin(p0) * p1 * scale;
            const alpha = Math.round(255 * Math.min(1, p4)).toString(16).padStart(2, "0");
            return [`drop-shadow(${ox}px ${oy}px ${(Math.max(p2, p3) * scale) / 2}px #${hex}${alpha})`];
          }
          case 3:
            return [`blur(${(Math.hypot(p0, p1) * scale * Math.sqrt(p2)) / 4}px)`];
          default:
            return [];
        }
      })
      .join(" ");
  }

  function computePlacementAge(clip, startFrame, tick, placement) {
    if (clip.frames.length <= 1 || tick === 0) return tick;
    const cached = clip.placementAges.get(placement);
    if (cached != null) return Math.min(tick, cached);

    const [depth, charId, , , , , , ratio = -1] = placement;
    const tl = clip.actions && getBundleTimeline(clip, startFrame);
    const maxLen = tl && tl.loopAt == null ? tl.frames.length - 1 : tick;
    const offset = Math.max(0, tick - Math.max(0, maxLen));
    const limit = clip.actions ? Math.min(tick, offset + clip.frames.length) : clip.frames.length;

    let age = offset;
    for (; age < limit; age++) {
      let idx = tick - age - 1;
      if (idx < 0) idx += clip.frames.length;
      const prev = clip.frames[resolveBundleFrame(clip, startFrame, idx)].find((pl) => pl[0] === depth);
      if (!prev || prev[1] !== charId || (prev[7] ?? -1) !== ratio) {
        if (!clip.actions) clip.placementAges.set(placement, age);
        return Math.min(tick, age);
      }
    }
    if (!clip.actions) clip.placementAges.set(placement, Infinity);
    return tick;
  }

  function drawBundleNode(ctx, bundle, nodeId, tick, colorCx, startFrame = 0, isRoot = false, colorMatrix = undefined) {
    const shape = bundle.shapes.get(nodeId);
    if (shape) {
      if (colorCx) {
        ctx.globalAlpha *= Math.min(1, Math.max(0, colorCx[6] + colorCx[7] / 255));
      }
      const img = getTintedShapeImage(bundle, nodeId, shape, colorCx, colorMatrix);
      ctx.drawImage(img, shape.x, shape.y, shape.width, shape.height);
      return;
    }

    const clip = bundle.clips.get(nodeId);
    if (!clip || !clip.frames.length) return;
    const frameStart = startFrame % clip.frames.length;
    const placements = clip.frames[resolveBundleFrame(clip, frameStart, isRoot ? 0 : tick)];

    let activeMaskDepth = -1;
    let room44Masked = false;

    for (const pl of placements) {
      const [depth, charId, matrix, localCx, clipDepth, blendMode, filters, ratio = -1] = pl;
      if (activeMaskDepth >= 0 && depth > activeMaskDepth) {
        ctx.restore();
        activeMaskDepth = -1;
      }

      if (clipDepth > 0) {
        const maskShape = bundle.shapes.get(charId);
        if (!maskShape) continue;
        if (activeMaskDepth >= 0) ctx.restore();
        ctx.save();
        const savedTransform = ctx.getTransform();
        ctx.transform(matrix[0], matrix[2], matrix[3], matrix[1], matrix[4], matrix[5]);
        ctx.clip(buildShapeMaskPath(maskShape));
        ctx.setTransform(savedTransform);
        activeMaskDepth = clipDepth;
        continue;
      }

      if (bundle.roomId === "44" && nodeId === 21 && depth > 6 && depth <= 18 && !room44Masked) {
        if (activeMaskDepth >= 0) ctx.restore();
        ctx.save();
        ctx.beginPath();
        ctx.ellipse(203, 100, 165, 150, 0, 0, Math.PI * 2);
        ctx.clip();
        activeMaskDepth = 18;
        room44Masked = true;
      }

      ctx.save();
      ctx.transform(matrix[0], matrix[2], matrix[3], matrix[1], matrix[4], matrix[5]);

      const comp = bundle.roomId === "45" && blendMode === 3 ? undefined : FLASH_BLEND_MODES[blendMode];
      if (comp) ctx.globalCompositeOperation = comp;

      if (filters && filters.length && "filter" in ctx) {
        const cssFlt = buildFlashFilterCss(filters, ctx);
        if (cssFlt) ctx.filter = ctx.filter === "none" ? cssFlt : `${ctx.filter} ${cssFlt}`;
      }

      const hasChildClip = bundle.clips.has(charId);
      const childTick = isRoot || !hasChildClip ? tick : computePlacementAge(clip, frameStart, tick, pl);
      const childColorMat = (filters && filters.find((flt) => flt[0] === 2)?.[1]) ?? colorMatrix;

      const combinedCx =
        colorCx && localCx
          ? [
            colorCx[0] * localCx[0],
            colorCx[0] * localCx[1] + colorCx[1],
            colorCx[2] * localCx[2],
            colorCx[2] * localCx[3] + colorCx[3],
            colorCx[4] * localCx[4],
            colorCx[4] * localCx[5] + colorCx[5],
            colorCx[6] * localCx[6],
            colorCx[6] * localCx[7] + colorCx[7],
          ]
          : colorCx ?? localCx;

      drawBundleNode(ctx, bundle, charId, childTick, combinedCx, Math.max(0, ratio), false, childColorMat);
      ctx.restore();
    }

    if (activeMaskDepth >= 0) {
      ctx.restore();
    }
  }

  async function loadBundleRoom(roomId) {
    const Codec = global.BundleCodec;
    if (!Codec || !Codec.parseZip || !Codec.decodeMsgpack) return null;

    const rid = String(roomId);
    const resp = await fetch(proxyAssetUrl(`assets/PrisonV3/RoomCameraUrl/${rid}/room.bundle`));
    if (!resp.ok) return null;

    const zipEntries = Codec.parseZip(new Uint8Array(await resp.arrayBuffer()));
    const manifestBytes = zipEntries.get("manifest.bin");
    if (!manifestBytes) return null;

    const [lib, rawClips, rawShapes, rawBitmaps] = Codec.decodeMsgpack(manifestBytes);
    const bgEntry = Object.entries(lib || {}).find(([name]) => /^background\d+$/.test(name));
    if (!bgEntry) return null;

    const rootId = bgEntry[1];
    const frontId = rid === "54" ? lib.gameBirthday_back_front : undefined;
    const emptyFriendId = rid === "54" ? lib.gameBirthday_add_friend : undefined;

    const visited = new Set();
    const clips = new Map();
    const pendingShapes = [];

    const collect = (nodeId) => {
      if (nodeId == null || visited.has(nodeId)) return;
      visited.add(nodeId);
      const clipDef = rawClips[nodeId];
      const bmpDef = rawBitmaps ? rawBitmaps[nodeId] : undefined;
      const shapeDef = (rawShapes && rawShapes[nodeId]) ?? (bmpDef && [bmpDef[0], 0, 0, bmpDef[1], bmpDef[2]]);
      if (shapeDef) {
        pendingShapes.push([nodeId, shapeDef]);
      } else if (clipDef) {
        const frames =
          rid === "42" && nodeId === 52
            ? [[]]
            : clipDef[0].map(([placements]) =>
              placements
                .filter((pl) => {
                  const [, charId, , , clipDepth] = pl;
                  if (nodeId === frontId && ROOM_54_SKIP_PLACEMENTS.has(charId)) return false;
                  if (rid === "54" && clipDepth && charId === 23) return false;
                  return true;
                })
                .sort((a, b) => a[0] - b[0])
            );
        clips.set(nodeId, {
          frames,
          actions: clipDef[2],
          timelines: new Map(),
          placementAges: new Map(),
        });
        for (const frame of frames) {
          for (const [, childId] of frame) collect(childId);
        }
      }
    };

    collect(rootId);
    if (frontId != null) collect(frontId);
    if (emptyFriendId != null) collect(emptyFriendId);

    const shapes = new Map();
    for (let i = 0; i < pendingShapes.length; i += 24) {
      await Promise.all(
        pendingShapes.slice(i, i + 24).map(async ([id, [path, x, y, w, h]]) => {
          const fileBytes = zipEntries.get(path);
          if (!fileBytes) return;
          const img = await decodePngBlob(fileBytes);
          shapes.set(id, { image: img, x, y, width: w, height: h });
        })
      );
    }

    return {
      kind: "bundle",
      roomId: rid,
      root: rootId,
      front: frontId,
      emptyFriend: emptyFriendId,
      clips,
      shapes,
      tinted: new Map(),
    };
  }

  function renderBundleLayer(ctx, entry, timeMs, layerName) {
    const bundle = entry && entry.bundle;
    if (!bundle) return false;
    const nodeId = layerName === "back" ? bundle.root : bundle.front;
    if (nodeId == null) return false;

    const [ox, oy] = bundle.roomId === "42" ? [-4.9, -6] : bundle.roomId === "45" ? [-12, -5.3] : [0, 0];
    const tick = Math.floor((30 * Math.max(0, timeMs)) / 1000);

    ctx.save();
    try {
      ctx.translate(-VIEWPORT.x, -VIEWPORT.y);
      ctx.translate(
        STAGE.cx + STAGE.dx - (290 + ox) * STAGE.scale,
        STAGE.cy + STAGE.dy - (215 + oy) * STAGE.scale
      );
      ctx.scale(STAGE.scale, STAGE.scale);
      drawBundleNode(ctx, bundle, nodeId, tick, null, 0, true);
      if (layerName === "front" && bundle.emptyFriend != null) {
        for (const fx of [175, 350]) {
          ctx.save();
          ctx.translate(fx, 245);
          drawBundleNode(ctx, bundle, bundle.emptyFriend, tick, null, 0, true);
          ctx.restore();
        }
      }
    } finally {
      ctx.restore();
    }
    return true;
  }

  // ---- effect_config.json sequence overlays ----

  function parseEffectFrame(raw) {
    return {
      x: raw.frame?.x ?? 0,
      y: raw.frame?.y ?? 0,
      w: raw.frame?.w ?? 0,
      h: raw.frame?.h ?? 0,
      ox: raw.spriteSourceSize?.x ?? 0,
      oy: raw.spriteSourceSize?.y ?? 0,
      sw: raw.sourceSize?.w ?? raw.frame?.w ?? 0,
      sh: raw.sourceSize?.h ?? raw.frame?.h ?? 0,
    };
  }

  async function loadEffectAtlas(folder, name) {
    const [atlasResp, cfgResp] = await Promise.all([
      fetch(proxyAssetUrl(`${folder}${name}.json`)),
      fetch(proxyAssetUrl(`${folder}${name}_config.json`)),
    ]);
    if (!atlasResp.ok) return null;
    const atlasJson = await atlasResp.json().catch(() => null);
    if (!atlasJson || !atlasJson.frames) return null;
    const cfgJson = cfgResp.ok ? await cfgResp.json().catch(() => null) : null;

    const imageMeta = atlasJson.meta?.image;
    let page = imageMeta ? await loadImageUrl(proxyAssetUrl(`${folder}${imageMeta}`)) : null;
    if (!page || page.naturalWidth <= 1) {
      page = await loadImageUrl(proxyAssetUrl(`${folder}${name}.webp`));
    }
    if ((!page || page.naturalWidth <= 1) && imageMeta !== `${name}.png`) {
      page = await loadImageUrl(proxyAssetUrl(`${folder}${name}.png`));
    }
    if (!page || page.naturalWidth <= 1) return null;

    const frames = new Map();
    const order = [];
    if (Array.isArray(atlasJson.frames)) {
      for (const f of atlasJson.frames) {
        const key = String(f.filename ?? f.name ?? order.length);
        frames.set(key, parseEffectFrame(f));
        order.push(key);
      }
    } else {
      for (const [key, f] of Object.entries(atlasJson.frames)) {
        frames.set(key, parseEffectFrame(f));
        order.push(key);
      }
    }
    if (!order.length) return null;

    let sequence = null;
    if (Array.isArray(cfgJson?.sequence) && cfgJson.sequence.length) {
      sequence = cfgJson.sequence.map((s) => ({
        frame: String(s.frame),
        delay: Math.max(1, Number(s.delay) || 100),
      }));
    }
    return { page, frames, order, sequence, zoom: Number(cfgJson?.zoom) || 1 };
  }

  function pickEffectFrame(atlas, timeMs) {
    const seq = atlas.sequence;
    if (!seq || !seq.length) {
      return atlas.frames.get(atlas.order[0]) || null;
    }
    const total = seq.reduce((acc, s) => acc + s.delay, 0);
    let rem = total > 0 ? timeMs % total : 0;
    let frameName = seq[seq.length - 1].frame;
    for (const s of seq) {
      if (rem < s.delay) {
        frameName = s.frame;
        break;
      }
      rem -= s.delay;
    }
    let f = atlas.frames.get(frameName);
    if (!f) {
      const clean = String(frameName).replace(/\.(png|webp)$/i, "");
      f = atlas.frames.get(clean) || atlas.frames.get(`${clean}.webp`) || atlas.frames.get(`${clean}.png`);
    }
    return f || atlas.frames.values().next().value;
  }

  async function loadRoomEffects(roomId) {
    const rid = Number(roomId);
    if (!EFFECT_ROOM_IDS.has(rid)) return null;
    const base = `assets/PrisonV3/RoomCameraUrl/${rid}/`;
    const cfgResp = await fetch(proxyAssetUrl(`${base}effect_config.json`));
    if (!cfgResp.ok) return null;
    const cfg = await cfgResp.json().catch(() => null);
    if (!cfg || typeof cfg !== "object" || Object.keys(cfg).length === 0) return null;

    const list = await Promise.all(
      Object.entries(cfg).map(async ([name, eCfg]) => {
        if (!eCfg || typeof eCfg !== "object") return null;
        const [atlas, maskImg] = await Promise.all([
          loadEffectAtlas(`${base}effect/${name}/`, name),
          eCfg.mask ? loadImageUrl(proxyAssetUrl(`${base}masks/${eCfg.mask}`)) : Promise.resolve(null),
        ]);
        if (!atlas || !atlas.sequence || !atlas.sequence.length) return null;
        if (eCfg.mask && (!maskImg || maskImg.naturalWidth <= 1)) return null;

        let maskObj = null;
        if (maskImg) {
          const c = document.createElement("canvas");
          c.width = VIEWPORT.w;
          c.height = VIEWPORT.h;
          const surface = c.getContext("2d");
          if (!surface) return null;
          maskObj = { image: maskImg, surface };
        }
        const durationMs =
          eCfg.clickToPlay || eCfg.clickZone || atlas.sequence.length < 2
            ? 0
            : atlas.sequence.reduce((acc, s) => acc + s.delay, 0);
        return { config: eCfg, atlas, mask: maskObj, durationMs };
      })
    );
    const valid = list.filter(Boolean);
    return valid.length ? valid : null;
  }

  function renderEffectsOverlay(ctx, effects, timeMs) {
    if (!effects || !effects.length) return false;
    ctx.save();
    try {
      ctx.translate(-VIEWPORT.x, -VIEWPORT.y);
      for (const eff of effects) {
        const { config, atlas, mask, durationMs } = eff;
        const tMs = durationMs ? (config.playOnce ? Math.min(timeMs, durationMs - 1) : timeMs) : 0;
        const f = pickEffectFrame(atlas, tMs);
        if (!f || !f.w || !f.h) continue;
        const scale = (config.scale ?? 1) / (atlas.zoom || 1);
        const dx = config.x + (f.ox - f.sw / 2) * scale;
        const dy = config.y + (f.oy - f.sh / 2) * scale;
        const target = mask ? mask.surface : ctx;
        const ox = mask ? VIEWPORT.x : 0;
        const oy = mask ? VIEWPORT.y : 0;
        if (mask) {
          target.clearRect(0, 0, VIEWPORT.w, VIEWPORT.h);
          target.globalCompositeOperation = "source-over";
        }
        target.drawImage(atlas.page, f.x, f.y, f.w, f.h, dx - ox, dy - oy, f.w * scale, f.h * scale);
        if (mask) {
          const mw = mask.image.naturalWidth * (config.maskScale ?? 1);
          const mh = mask.image.naturalHeight * (config.maskScale ?? 1);
          target.globalCompositeOperation = "destination-in";
          target.drawImage(mask.image, config.x - ox - mw / 2, config.y - oy - mh / 2, mw, mh);
          target.globalCompositeOperation = "source-over";
          ctx.drawImage(mask.surface.canvas, ox, oy);
        }
      }
    } finally {
      ctx.restore();
    }
    return true;
  }

  // ---- Unified public controller ----

  class OfficialRoomPlayer {
    constructor() {
      this._cache = new Map();
      this._pending = new Map();
      this._activeRoomId = null;
    }

    isAnimatedRoom(roomId) {
      const id = Number(roomId);
      return SPINE_ROOM_IDS.has(id) || BUNDLE_ROOM_IDS.has(id) || EFFECT_ROOM_IDS.has(id);
    }

    hasBundleFront(roomId) {
      const entry = this._cache.get(String(roomId));
      return Boolean(entry && entry.bundle && entry.bundle.front != null);
    }

    hasFullBackground(roomId) {
      const entry = this._cache.get(String(roomId));
      return Boolean(entry && (entry.spine || entry.bundle));
    }

    isReady(roomId) {
      const id = String(roomId || "");
      const entry = this._cache.get(id);
      if (!entry) return false;
      return Boolean(entry.spine || entry.bundle || (entry.effects && entry.effects.length > 0));
    }

    stop() {
      this._activeRoomId = null;
    }

    async preload(roomId) {
      const idNum = Number(roomId);
      const idKey = String(roomId);
      this._activeRoomId = idKey;

      if (!this.isAnimatedRoom(idNum)) return false;
      if (this._cache.has(idKey)) return this.isReady(idKey);
      if (this._pending.has(idKey)) return this._pending.get(idKey);

      const job = (async () => {
        try {
          let spine = null;
          let bundle = null;
          let effects = null;

          if (SPINE_ROOM_IDS.has(idNum)) {
            spine = await loadSpineRoom(idNum).catch((e) => {
              console.warn("Spine load failed for room", idNum, e);
              return null;
            });
          } else if (BUNDLE_ROOM_IDS.has(idNum)) {
            const [bRes, eRes] = await Promise.all([
              loadBundleRoom(idNum).catch((e) => {
                console.warn("Bundle load failed for room", idNum, e);
                return null;
              }),
              idNum === 42 ? loadRoomEffects(idNum).catch(() => null) : Promise.resolve(null),
            ]);
            bundle = bRes;
            effects = eRes;
          } else if (EFFECT_ROOM_IDS.has(idNum)) {
            effects = await loadRoomEffects(idNum).catch(() => null);
          }

          if (!spine && !bundle && (!effects || !effects.length)) {
            return false;
          }

          this._cache.set(idKey, { spine, bundle, effects });
          if (this._cache.size > 4) {
            const oldestKey = this._cache.keys().next().value;
            if (oldestKey !== undefined && oldestKey !== idKey) {
              this._cache.delete(oldestKey);
            }
          }
          return true;
        } finally {
          this._pending.delete(idKey);
        }
      })();

      this._pending.set(idKey, job);
      return job;
    }

    renderBack(ctx, _width, _height, timeMs, roomId = null) {
      const idKey = String(roomId || this._activeRoomId || "");
      const entry = this._cache.get(idKey);
      if (!entry) return false;
      let drewBackground = false;
      if (entry.spine) {
        drewBackground = renderSpineRoom(ctx, entry.spine, timeMs);
      } else if (entry.bundle) {
        drewBackground = renderBundleLayer(ctx, entry, timeMs, "back");
      }
      return drewBackground;
    }

    renderEffects(ctx, _width, _height, timeMs, roomId = null) {
      const idKey = String(roomId || this._activeRoomId || "");
      const entry = this._cache.get(idKey);
      if (!entry || !entry.effects) return false;
      return renderEffectsOverlay(ctx, entry.effects, timeMs);
    }

    renderFront(ctx, _width, _height, timeMs, roomId = null) {
      const idKey = String(roomId || this._activeRoomId || "");
      const entry = this._cache.get(idKey);
      if (!entry || !entry.bundle || entry.bundle.front == null) return false;
      return renderBundleLayer(ctx, entry, timeMs, "front");
    }

    renderFrame(ctx, width, height, timeMs, roomId = null) {
      return this.renderBack(ctx, width, height, timeMs, roomId);
    }
  }

  global.SpineRoomPlayer = new OfficialRoomPlayer();
})(typeof window !== "undefined" ? window : globalThis);
