import os
import shutil
import urllib.request
from pathlib import Path

DEST_DIR = Path("web/static/assets/icons")
DEST_DIR.mkdir(parents=True, exist_ok=True)
REF_HUD_DIR = Path("reference_archive/pro_prison_bot/assets")
HUD_REFERENCE_MAP = {
    "cigarettes.webp": "HUD_cigarettes.webp",
    "rubles.webp": "HUD_rubles.webp",
    "sugar.webp": "HUD_sugar.webp",
    "soap.webp": "HUD_soap.webp",
    "boss.webp": "PrisonV3_bosses_all_bosses.webp",
    "stash.webp": "poker_hidesicon.webp",
    "room_reward.webp": "PrisonV3_bosses_all_camerReward.webp",
    "complect.webp": "PrisonV3_bosses_all_complectReward.webp",
    "podogrev.webp": "podogrev_pagePodogrev.webp",
    "authority.webp": "Avtoritet.webp",
}

# URL sources map: target_name -> [fallback_urls]
ICON_SOURCES = {
    # Currencies (HUD quality assets)
    "rubles.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/HUD_rubles.webp",
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/HUD/HUD_rubles.png",
    ],
    "soap.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/HUD_soap.webp",
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/HUD/HUD_soap.png",
    ],
    "sugar.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/HUD_sugar.webp",
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/HUD/HUD_sugar.png",
    ],
    "cigarettes.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/HUD_cigarettes.webp",
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/HUD/HUD_cigarettes.png",
    ],
    "paper.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/BARIGA/img/icon_B_paper.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/BARIGA/img/icon_B_paper.webp",
    ],
    "signet.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/bagBaul/Opened/Baul_signet.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/bagBaul/Opened/Baul_signet.webp",
    ],
    "ore_signet.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/bagBaul/Opened/Baul_ore_signet.webp",
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/Zaruba/ZarubActiv/ore_icon.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/bagBaul/Opened/Baul_ore_signet.webp",
    ],
    # Weapons
    "knife.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/PrisonV3_Friend_knifeIcon.webp",
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/Friend/knifeIcon.webp",
    ],
    "poison.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/PrisonV3_Friend_poisonIcon.webp",
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/Friend/poisonIcon.webp",
    ],
    "gunshot.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/PrisonV3_Friend_gunIcon.webp",
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/Friend/gunIcon.webp",
    ],
    # Stats
    "energy.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/Energy.webp",
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/Energy.webp",
    ],
    "authority.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/All/AvtoritetDamage.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/All/AvtoritetDamage.webp",
    ],
    "biceps.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/interaction/bitsepsAdd.png",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/interaction/bitsepsAdd.png",
    ],
    "keys.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/bossKeyDrop.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/bossKeyDrop.webp",
    ],
    "talents.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/talents/image/all/tallent.png",
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/talents/butPrivateFileInLib.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/talents/image/all/tallent.png",
    ],
    "boss.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/All/bossWine.png",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/All/bossWine.png",
    ],
    "vote.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/PrisonV3_interaction_iconVote3.webp",
    ],
    # Boss hits
    "punchChest.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/PrisonV3_WeaponsScene_icon_4_1.webp",
    ],
    "kickBalls.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/PrisonV3_WeaponsScene_icon_4_2.webp",
    ],
    "pokeEyes.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/PrisonV3_WeaponsScene_icon_4_3.webp",
    ],
    "kneeEar.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/PrisonV3_WeaponsScene_icon_4_4.webp",
    ],
    # Categories / sources
    "kolsik.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/Tattoos/kolsik.png",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/Tattoos/kolsik.png",
    ],
    "baul.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/SceneMainRoom/363.png",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/SceneMainRoom/363.png",
    ],
    "stash.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/talents/image/all/icon_jurnal.png",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/talents/image/all/icon_jurnal.png",
    ],
    "combo.webp": [
        "https://pro-prison-bot.003220.xyz/images/combo-donate.webp",
    ],
    "podogrev.webp": [
        "https://pro-prison-bot.003220.xyz/game-icons/podogrev_pagePodogrev.webp",
    ],
    # Base body sprite for character layers
    "PlayerSprite.png": [
        "https://pro-prison-bot.003220.xyz/cdn/assets/PlayerSprite.png",
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PlayerSprite.png",
    ],
    # Brigade & Shodnyak Boosts
    "guild_buff_poison.png": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/common/guildBoosts/icon_8.png",
        "https://pro-prison-bot.003220.xyz/cdn/assets/common/guildBoosts/icon_8.png",
    ],
    "guild_buff_gunshot.png": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/common/guildBoosts/icon_9.png",
        "https://pro-prison-bot.003220.xyz/cdn/assets/common/guildBoosts/icon_9.png",
    ],
    "icon_Solo.png": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/bosses/Icon/icon_Solo.png",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/bosses/Icon/icon_Solo.png",
    ],
    "shodnyak_zloba.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_zloba.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_zloba.webp",
    ],
    "shodnyak_pepel.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_pepel.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_pepel.webp",
    ],
    "shodnyak_zhalo.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_zhalo.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_zhalo.webp",
    ],
    "shodnyak_vzryvchatka.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_vzryvchatka.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_vzryvchatka.webp",
    ],
    "shodnyak_zhestokiy.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_zhestokiy.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_zhestokiy.webp",
    ],
    "shodnyak_shrapnel.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_shrapnel.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_shrapnel.webp",
    ],
    "shodnyak_otrava.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_otrava.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_otrava.webp",
    ],
    "shodnyak_kislota.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_kislota.webp",
        "https://pro-prison-bot.003220.xyz/cdn/assets/PrisonV3/bafss/icon/shodnyak/shodnyak_kislota.webp",
    ],
    # Fitting Room Back View & Rotate Button
    "back_player_sprite.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/backPlayerSprite/back_player_sprite.webp",
    ],
    "back_poworot.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/backPlayerSprite/back_poworot.webp",
    ],
    "back_Mask.webp": [
        "https://oldprison-prod-assets-cdn-yandex.luckygem.online/assets/backPlayerSprite/back_Mask.webp",
    ]
}


def fetch_icon(target_name: str, urls: list) -> bool:
    target_path = DEST_DIR / target_name
    ref_name = HUD_REFERENCE_MAP.get(target_name)
    if ref_name:
        ref_path = REF_HUD_DIR / ref_name
        if ref_path.exists() and ref_path.stat().st_size > 0:
            shutil.copyfile(ref_path, target_path)
            print(f"[SYNCED_HUD] {target_name} <- {ref_path} ({target_path.stat().st_size} bytes)")
            return True

    if target_path.exists() and target_path.stat().st_size > 0:
        print(f"[EXISTS] {target_name} ({target_path.stat().st_size} bytes)")
        return True

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                if len(data) > 0:
                    with open(target_path, "wb") as f:
                        f.write(data)
                    print(f"[DOWNLOADED] {target_name} from {url} ({len(data)} bytes)")
                    return True
        except Exception as e:
            # Try next url
            continue
    print(f"[FAILED] {target_name} from all sources")
    return False


def main():
    print(f"Fetching game icons to {DEST_DIR.resolve()}...")
    success = 0
    total = len(ICON_SOURCES)
    for name, urls in ICON_SOURCES.items():
        if fetch_icon(name, urls):
            success += 1

    # Convert back_player_sprite.webp to PlayerSpriteBack.png if needed
    webp_back = DEST_DIR / "back_player_sprite.webp"
    png_back = DEST_DIR / "PlayerSpriteBack.png"
    if webp_back.exists() and not png_back.exists():
        try:
            from PIL import Image
            with Image.open(webp_back) as img:
                img.save(png_back, "PNG")
            print(f"[CONVERTED] Generated {png_back.name} ({png_back.stat().st_size} bytes)")
        except Exception as e:
            print(f"[WARN] Failed to convert PlayerSpriteBack.png: {e}")

    print(f"\nDone: {success}/{total} icons successfully saved to {DEST_DIR}.")


if __name__ == "__main__":
    main()
