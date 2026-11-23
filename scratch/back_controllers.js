gBlocker.setVisible(!1)
        }
      }
      _setUserId(t) {
        const e = t ? String(t) : null;
        e !== this._userId && (this._userId = e, this.friendSummary?.setUserId?.(e))
      }
      async activateTab(t) {
        this._activeKey !== t && (this._activeKey = t, qt.x.init(this.scene).playSound("guildTabClick"), Object.entries(this._tabButtons).forEach(([e, {
          btn: i,
          txt: s
        }]) => {
          const n = e === t;
          i.setTexture(n ? "btnKnigaActicv" : "btnKniganoActicv"), s.setAlpha(n ? 1 : .6)
        }), this.summaryContainer.setVisible("summary" === t), this.achievementsContainer.setVisible("achievements" === t), "summary" === t && this.friendSummary?.reload?.(), this.emit("tab:changed", t))
      }
      mountSummary(t) {
        this.summaryContainer.add(t)
      }
      mountAchievements(t) {
        this.achievementsContainer.add(t)
      }
      close(t = !1) {
        this.active && (this.active = !1, this._onShutdown && (this.scene.events.off("shutdown", this._onShutdown), this.scene.events.off("destroy", this._onShutdown), this._onShutdown = null), t || qt.x.init(this.scene).playSound("close"), this.destroy(), po.current === this && (po.current = null))
      }
    }
    class go extends gr {
      constructor(t, e, i) {
        super(t, e, i, i), this.allowed = new Set(Array.from({
          length: 20
        }, (t, e) => 23 + e))
      }
      _enterTattoo14Mode() {}
      _exitTattoo14Mode() {}
      syncTattoo14VisibilityByZone6() {}
      _syncTattoo14VisibilityByRealHand() {}
      _filterZonesObject(t) {
        const e = {};
        for (const [i, s] of Object.entries(t || {})) {
          const t = parseInt(i);
          this.allowed.has(t) && (e[t] = s)
        }
        return e
      }
      _isAllowed(t) {
        const e = parseInt(t);
        return this.allowed.has(e)
      }
      async setTattoos(t) {
        return super.setTattoos(this._filterZonesObject(t))
      }
      async previewTattoo(t, e) {
        if (this._isAllowed(t)) return super.previewTattoo(t, e)
      }
      async applyTattoo(t, e) {
        if (this._isAllowed(t)) return super.applyTattoo(t, e)
      }
      async previewSet(t) {
        return super.previewSet(this._filterZonesObject(t))
      }
      clearTattoo(t) {
        if (this._isAllowed(t)) return super.clearTattoo(t)
      }
    }
    class mo {
      constructor(t, e, i) {
        this.scene = t, this.container = e, this.baseSprite = i, this.image = null, this.currentPhase = 0, this.offsetX = -205, this.offsetY = -285, this.scale = 1
      }
      setOffset(t, e) {
        this.offsetX = t, this.offsetY = e, this.updatePosition()
      }
      setScale(t) {
        this.scale = t, this.image && this.image.setScale(t / yr(this.image.frame, mr.BACK))
      }
      setBeard(t) {
        if (t === this.currentPhase) return;
        if (this.currentPhase = t, this.image && (this.image.destroy(), this.image = null), 0 === t) return;
        const e = Xt(t),
          i = `${Zt.E.rootPath()}/Beard/BardDayBack/${t}.png`,
          s = () => {
            this.image = this.scene.add.image(this.baseSprite.x + this.offsetX, this.baseSprite.y + this.offsetY, e), this.image.setScale(this.scale / yr(this.image.frame, mr.BACK)), this.container.add(this.image)
          };
        this.scene.textures.exists(e) ? s() : (this.scene.load.image(e, i), this.scene.load.once(`filecomplete-image-${e}`, () => {
          this.currentPhase === t && s()
        }), this.scene.load.start())
      }
      clearBeard() {
        this.image && (this.image.destroy(), this.image = null), this.currentPhase = 0
      }
      updatePosition() {
        this.image && this.image.setPosition(this.baseSprite.x + this.offsetX, this.baseSprite.y + this.offsetY)
      }
      destroy() {
        this.clearBeard()
      }
    }
    class fo {
      constructor(t, e, i) {
        this.scene = t, this.parent = e, this.container = i, this.clothing = {}, this.previewItems = {}, this.currentUrls = {}, this.appliedZones = new Set, this.zoneOffsets = {}, this._queue = []
      }
      getTextureKey(t) {
        t = this._normalizeImageUrl(t);
        try {
          return `backcloth_${btoa(t)}`
        } catch {
          return `backcloth_${t.replace(/[^a-zA-Z0-9]/g,"")}`
        }
      }
      _queueImage(t, e) {
        e && !this.scene.textures.exists(t) && (this.scene.load.image(t, e), this._queue.push(t))
      }
      async _flushLoader() {
        this._queue.length && (await new Promise(t => {
          this.scene.load.once("complete", t), this.scene.load.start()
        }), this._queue = [])
      }
      _makeSpriteFor(t, e) {
        const i = this.parent?.sprite,
          s = i?.originX ?? 1,
          n = i?.originY ?? 1,
          r = this.scene.add.image(0, 0, e).setOrigin(s, n).setFlip(i?.flipX ?? !1, i?.flipY ?? !1).setVisible(!0),
          a = i?.displayWidth ?? 0,
          o = i?.displayHeight ?? 0,
          h = r.width,
          l = r.height;
        r.x += s * (h - a), r.y += (1 - n) * (o - l);
        const c = this.zoneOffsets[t] || {
          dx: 0,
          dy: 0
        };
        return (c.dx || c.dy) && r.setPosition(r.x + c.dx, r.y + c.dy), r._zone = t, r
      }
      syncToParentTransform() {
        const t = this.parent?.sprite;
        if (!t) return;
        const e = e => {
          e && (e.setOrigin(t.originX, t.originY), e.setFlip(t.flipX, t.flipY))
        };
        Object.values(this.clothing).forEach(e), Object.values(this.previewItems).forEach(e)
      }
      _sortLayers() {
        this.container && this.container.list && (this.container.list.sort((t, e) => {
          const i = Number(t?._zone ?? 0),
            s = Number(e?._zone ?? 0);
          return i - s ? 7 - i - (7 - s) : 0
        }), "function" == typeof this.container.sortChildren && this.container.sortChildren())
      }
      async setClothing(t) {
        if (!this.scene) return;
        const e = new Set(Object.keys(t || {}));
        for (const t of Object.keys(this.clothing)) e.has(t) || this.clearClothing(parseInt(t, 10));
        const i = {};
        for (const [e, s] of Object.entries(t || {})) i[e] = "string" == typeof s ? {
          clothingId: 0,
          imageUrl: this._normalizeImageUrl(s)
        } : {
          ...s,
          imageUrl: this._normalizeImageUrl(s?.imageUrl)
        };
        for (const [, t] of Object.entries(i)) {
          if (!t?.imageUrl || t.imageUrl.endsWith("/")) continue;
          const e = this.getTextureKey(t.imageUrl);
          this._queueImage(e, t.imageUrl)
        }
        await this._flushLoader();
        for (const [t, e] of Object.entries(i)) {
          const i = parseInt(t, 10);
          e?.imageUrl && !e.imageUrl.endsWith("/") && await this.applyClothing(i, e.imageUrl, e.clothingId || 0)
        }
        this._sortLayers()
      }
      async previewClothing(t, e) {
        if (e = this._normalizeImageUrl(e), !this.scene || !e || e.endsWith("/")) return;
        const i = this.getTextureKey(e);
        this.scene.textures.exists(i) || (this._queueImage(i, e), await this._flushLoader()), this.clearPreview(t);
        const s = this._makeSpriteFor(t, i);
        s._sourceUrl = e, this.container.add(s), this.previewItems[t] = s, this.clothing[t] && this.clothing[t].setVisible(!1), this._sortLayers()
      }
      async applyClothing(t, e, i = 0) {
        if (e = this._normalizeImageUrl(e), !this.scene || !e || e.endsWith("/")) return;
        const s = this.getTextureKey(e);
        this.scene.textures.exists(s) || (this._queueImage(s, e), await this._flushLoader()), this.clothing[t] && (this.clothing[t].destroy(), delete this.clothing[t]);
        const n = this._makeSpriteFor(t, s);
        n._sourceUrl = e, this.container.add(n), this.clothing[t] = n, this.currentUrls[t] = e, this.appliedZones.add(t), this.parent && this.parent.tempClothingZones && (this.parent.tempClothingZones[t] = {
          clothingId: i,
          imageUrl: e
        }), this._sortLayers()
      }
      previewSet(t) {
        this.clearPreview();
        for (const [e, i] of Object.entries(t || {})) {
          const t = parseInt(e, 10),
            s = this._normalizeImageUrl("string" == typeof i ? i : i?.imageUrl);
          s && !s.endsWith("/") && this.previewClothing(t, s)
        }
      }
      clearPreview(t = null) {
        if (null != t) {
          const e = this.previewItems[t];
          return e && e.destroy(), delete this.previewItems[t], void(this.clothing[t] && this.clothing[t].setVisible(!0))
        }
        Object.values(this.previewItems).forEach(t => t?.destroy()), this.previewItems = {}, this.showAppliedClothing()
      }
      clearClothing(t) {
        const e = this.clothing[t];
        e && e.destroy(), delete this.clothing[t], delete this.currentUrls[t], this.appliedZones.delete(t), this.parent && this.parent.tempClothingZones && delete this.parent.tempClothingZones[t]
      }
      showAppliedClothing() {
        Object.values(this.clothing).forEach(t => t?.setVisible(!0))
      }
      setAlpha(t) {
        Object.values(this.clothing).forEach(e => e?.setAlpha(t)), Object.values(this.previewItems).forEach(e => e?.setAlpha(t))
      }
      updatePosition() {}
      destroy() {
        Object.values(this.clothing).forEach(t => t?.destroy()), Object.values(this.previewItems).forEach(t => t?.destroy()), this.clothing = {}, this.previewItems = {}, this.currentUrls = {}, this.appliedZones.clear(), this.container && (this.container.destroy(), this.container = null), this.scene = null, this.parent = null
      }
      _normalizeImageUrl(t) {
        return Zt.E.resolveRuntimeAssetUrl(t)
      }
    }
    var yo = i(440);
    class _o extends yo.GameObjects.Container {
      constructor(t, e, i, s = "PlayerSpriteBack", n = {}) {
        if (super(t, e, i), this._autoloadFromPlayerData = !1 !== n?.autoloadFromPlayerData, this.tempTattooZones = {}, this.tempClothingZones = {}, this.setVisible(!1), this.setAlpha(0), this.sprite = t.make.image({
            x: 0,
            y: 0,
            key: s,
            add: !1
          }).setOrigin(1, 1), this.sprite.setScale(1 / yr(this.sprite.frame, mr.BACK)), this.add(this.sprite), this.tattooBackContainer = t.make.container({
            x: 0,
            y: 0,
            add: !1
          }), this.add(this.tattooBackContainer), this.beardBackContainer = t.make.container({
            x: 0,
            y: 0,
            add: !1
          }), this.add(this.beardBackContainer), this.backClothingContainer = t.make.container({
            x: 0,
            y: 0,
            add: !1
          }), this.add(this.backClothingContainer), this.backTattooController = new go(t, this, this.tattooBackContainer), this.backBeardController = new mo(t, this.beardBackContainer, this.sprite), this.backClothingController = new fo(t, this, this.backClothingContainer), this.anchorOffsetX = 0, this.anchorOffsetY = 0, this.setModelScale(1), this.backTattooController.setTattooScale(1), this._syncCenterToSprite(), t.add.existing(this), this._autoloadFromPlayerData) {
          const t = ke.PlayerDataStore.get("beardPhase") || 0;
          this.setBeardPhase(t);
          const e = ke.PlayerDataStore.get("clothingBackZones") || {};
          e && Object.keys(e).length && this.setBackClothing(e)
        }
      }
      _syncCenterToSprite() {
        if (!this.sprite) return;
        const t = this.sprite.displayWidth || 0,
          e = this.sprite.displayHeight || 0,
          i = -(this.sprite.originX ?? .5) * t + t / 2,
          s = -(this.sprite.originY ?? .5) * e + e / 2;
        let n = this.anchorOffsetX || 0,
          r = this.anchorOffsetY || 0;
        this.sprite.flipX && (n = -n), this.sprite.flipY && (r = -r), this.backTattooController?.setDisplayCenter(i + n, s + r)
      }
      setAnchorOffsets(t = 0, e = 0) {
        this.anchorOffsetX = t, this.anchorOffsetY = e, this._syncCenterToSprite()
      }
      setTexture(t) {
        this.sprite && this.scene.textures.exists(t) && (this.sprite.setTexture(t), this._syncCenterToSprite())
      }
      setModelScale(t) {
        this.setScale(t)
      }
      setModelAlpha(t) {
        this.setAlpha(t)
      }
      setModelFlip(t = !1, e = !1) {
        this.sprite.setFlip(t, e), this._syncCenterToSprite()
      }
      setDisplayCenter(t, e) {
        this.backTattooController?.setDisplayCenter?.(t, e)
      }
      async setBackTattoos(t) {
        await this.backTattooController.setTattoos(t)
      }
      async previewBackTattoo(t, e) {
        await this.backTattooController.previewTattoo(t, e)
      }
      async applyBackTattoo(t, e) {
        await this.backTattooController.applyTattoo(t, e)
      }
      clearBackPreview() {
        this.backTattooController.clearPreview?.()
      }
      async setBackClothing(t) {
        const e = {};
        for (const [i, s] of Object.entries(t || {})) e[i] = "string" == typeof s ? {
          clothingId: 0,
          imageUrl: s
        } : s;
        await this.backClothingController.setClothing(e)
      }
      async previewBackClothing(t, e) {
        await this.backClothingController.previewClothing(t, e)
      }
      clearBackClothingPreview(t = null) {
        this.backClothingController.clearPreview(t)
      }
      clearBackClothing(t) {
        this.backClothingController.clearClothing(t)
      }
      setBeardPhase(t) {
        this.backBeardController?.setBeard(t || 0)
      }
      clearBackBeard() {
        this.backBeardController?.clearBeard?.()
      }
      showFade(t = 120) {
        this.setVisible(!0), this.scene.tweens.add({
          targets: this,
          alpha: 1,
          duration: t,
          ease: "Quad.easeOut"
        })
      }
      hideFade(t = 80) {
        this.scene.tweens.add({
          targets: this,
          alpha: 0,
          duration: t,
          ease: "Quad.easeIn",
          onComplete: () => this.setVisible(!1)
        })
      }
      update() {
        this.backTattooController?.updatePosition?.(), this.backBeardController?.updatePosition?.(), this.backClothingController?.updatePosition?.()
      }
      destroy(t) {
        this.backTattooController?.destroy?.(), this.backBeardController?.destroy?.(), this.backClothingController?.destroy?.(), this.sprite?.destroy?.(), super.destroy(t)
      }
    }
    var bo = i(440);
    const vo = Zt.E.rootPath() + "/Guild/emblema",
      xo = ".webp",
      wo = {
        1: 16711680,
        2: 12952,
        3: 2660608,
        4: 16737536,
        5: 16759326,
        6: 0,
        7: 16777215
      };

    function So(t, ...e) {
      if (!t || "object" != typeof t) return null;
      for (const i of e)
        if (void 0 !== t[i] && null !== t[i]) return t[i];
      return null
    }

    function To(t) {
      const e = Number(t) || 0;
      return wo[e] ?? 16777215
    }

    function Co(t, e) {
      return `guild_emblem_${t}_${e}`
    }

    funct