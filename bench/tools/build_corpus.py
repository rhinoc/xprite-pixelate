#!/usr/bin/env python3
"""Build the native-1x ground-truth corpus for the pixel-art recovery benchmark.

The script reads CC0 (and optionally CC-BY) pixel-art downloads, slices or crops
them with fixed recipes, checks that every result is native 1x art, and writes:

  bench/corpus/images/<id>.png   RGBA, lossless, optimised
  bench/corpus/manifest.json     one record per image
  bench/corpus/CREDITS.md        one row per source pack
  bench/corpus/contact-sheet.png labelled preview of all images

The output is deterministic: the same downloads give the same files.

Usage (run with an isolated interpreter, the downloads are untrusted data):

  python -I bench/tools/build_corpus.py \
      --scout /tmp/pixelart-dataset-scout \
      --dcss /tmp/dl-crawl-tiles/repo \
      --game1x /tmp/xprite-pr138-eval/game1x-data \
      --buch-rpg /tmp/dl-buch-rpgportraits

Download notes:
  --scout     directories from the earlier scout (OGA / itch / Kenney packs).
  --dcss      git clone of https://github.com/crawl/tiles (CC0). Tiles listed in
              its TILES_UNDER_UNKNOWN_LICENSE.md are always rejected.
  --game1x    only the kenney-*.png files are read (CC0). gtn-* and lpc-* files
              are CC-BY-SA and are never read.
  --buch-rpg  https://opengameart.org/sites/default/files/rpgportraits.png
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_BENCH = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_BENCH / "corpus"

DEFAULT_SCOUT = Path("/tmp/pixelart-dataset-scout")
DEFAULT_DCSS = Path("/tmp/dl-crawl-tiles/repo")
DEFAULT_GAME1X = Path("/tmp/xprite-pr138-eval/game1x-data")
DEFAULT_BUCH_RPG = Path("/tmp/dl-buch-rpgportraits")

VISIBLE_ALPHA = 128           # a pixel counts as visible at alpha >= 128
MIN_VISIBLE_PIXELS = 6
MIN_COLORS = 2
MAX_COLORS = 600              # hand-pixelled art rarely goes above this
MIN_SIDE = 8
MAX_SIDE = 320
UPSCALE_FACTORS = range(2, 9)
TRANSLUCENT_FRACTION = 0.01   # share of non-empty pixels with 0 < alpha < 255
TRANSPARENT_FRACTION = 0.02   # share of pixels with alpha 0 for "transparent"
NEAR_DUP_SAME_PIXELS = 0.85   # sheet auto-pick: skip cells this similar
MIN_CROP_VISIBLE = 0.25       # crops must not be mostly empty
MAX_DOMINANT_SHARE = 0.95     # reject near-flat images (one colour covers this share)
TRIM_MARGIN = 1

SIZE_BINS = [("tiny", 8, 16), ("small", 17, 48), ("medium", 49, 128), ("large", 129, 320)]
PALETTE_BINS = [("2-4", 2, 4), ("5-16", 5, 16), ("17-64", 17, 64), ("65+", 65, 10**9)]
GENRES = {"character", "monster", "item", "tile", "portrait", "scene",
          "isometric", "ui", "animation-frame"}
TAGS = {"transparent", "opaque", "dithered", "anti-aliased", "translucent"}

REJECT_NAME_PARTS = ("sample", "preview", "_x2", "x2.png", "2x.png")
REJECT_FILES = {"everface.png", "32x32_portraits_preview_2.png", "cnossus-tiles5.png"}
REJECT_EXTS = {".jpg", ".jpeg"}

DCSS_TAGS: dict[str, tuple[str, ...]] = {}

# Packs whose high-colour art is painted with smooth shading and blended
# (anti-aliased) outlines. Checked by eye on the contact sheet.
AA_SOURCES = {"dcss", "jetrel-frogatto", "marcavis-frogatto", "cawfeecrow-neko", "denzi"}
AA_MIN_COLORS = 65

DEZRA_BG = (200, 191, 231)    # flat sheet background of the Dezra sheet
DEZRA_PITCH = 33              # 32 px cells separated by 1 px black guide lines

CONTACT_CELL = 96
CONTACT_LABEL = 12
CONTACT_COLS = 12

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

OGA = "https://opengameart.org/content/"


@dataclass(frozen=True)
class Source:
    key: str
    pack: str
    author: str
    url: str
    root: str          # "scout", "dcss", "game1x", "buch_rpg"
    subdir: str = ""
    license: str = "CC0-1.0"
    attribution: str = ""


SOURCES = {s.key: s for s in [
    Source("denzi", "Denzi's public domain art", "Denzi", OGA + "denzis-public-domain-art", "scout", "denzi"),
    Source("dcss", "Dungeon Crawl Stone Soup tiles (Nov-2015 release)", "DCSS tile artists (see ARTISTS.md)",
           "https://github.com/crawl/tiles", "dcss", "releases/Nov-2015"),
    Source("kenney-micro", "Kenney Micro Roguelike", "Kenney", "https://kenney.nl/assets/micro-roguelike",
           "scout", "kenney-micro-roguelike/x"),
    Source("kenney-tinydungeon", "Kenney Tiny Dungeon", "Kenney", "https://kenney.nl/assets/tiny-dungeon",
           "scout", "kenney-tiny-dungeon/x"),
    Source("kenney-pico8city", "Kenney Pico-8 City", "Kenney", "https://kenney.nl/assets/pico-8-city",
           "scout", "kenney-pico8-city/x"),
    Source("kenney-1bit", "Kenney 1-Bit Pack", "Kenney", "https://kenney.nl/assets/1-bit-pack",
           "scout", "kenney-1bit/x"),
    Source("kenney-pixelplatformer", "Kenney Pixel Platformer", "Kenney", "https://kenney.nl/assets/pixel-platformer",
           "game1x"),
    Source("kenney-pixelshmup", "Kenney Pixel Shmup", "Kenney", "https://kenney.nl/assets/pixel-shmup", "game1x"),
    Source("kenney-rtspixel", "Kenney RTS Medieval (Pixel)", "Kenney", "https://kenney.nl/assets/medieval-rts",
           "game1x"),
    Source("0x72", "16x16 DungeonTileset II v1.7", "0x72", "https://0x72.itch.io/dungeontileset-ii",
           "scout", "0x72-dungeon/0x72_DungeonTilesetII_v1.7_x/0x72_DungeonTilesetII_v1.7"),
    Source("urizen", "Urizen 1Bit Tileset v2.0", "vurmux", "https://vurmux.itch.io/urizen-onebit-tileset",
           "scout", "urizen"),
    Source("luizmelo", "Monsters Creatures Fantasy", "LuizMelo", "https://luizmelo.itch.io/monsters-creatures-fantasy",
           "scout", "luizmelo-monsters/Monsters_Creatures_Fantasy_x/Monsters_Creatures_Fantasy"),
    Source("ansimuz-sv", "Sideview Fantasy Patreon Collection", "ansimuz", OGA + "sideview-fantasy-patreon-collection",
           "scout", "ansimuz-sideview-fantasy/x/Sideview Fantasy Patreon Collection"),
    Source("ansimuz-gothic", "Gothicvania Town", "ansimuz", OGA + "gothicvania-town",
           "scout", "ansimuz-gothicvania-town/gothicvania-town-files/GothicVania-town-files/PNG"),
    Source("ansimuz-cliffs", "Magic Cliffs Environment", "ansimuz", OGA + "magic-cliffs-environment",
           "scout", "ansimuz-magiccliffs/Magic-Cliffs-Environment/Magic-Cliffs-Environment/PNG"),
    Source("ansimuz-mountain", "Mountain at Dusk Background", "ansimuz", OGA + "mountain-at-dusk-background",
           "scout", "ansimuz-mountain/parallax_mountain_pack/parallax_mountain_pack/layers"),
    Source("ansimuz-warped", "Warped City", "ansimuz", "https://ansimuz.itch.io/warped-city",
           "scout", "ansimuz-warped/Warped City Assets Files_x/warped city files/Assets"),
    Source("ansimuz-faune", "Legend of Faune", "ansimuz", OGA + "legend-of-faune", "scout", "ansimuz-faune"),
    Source("surt-monsterboy", "Monster Boy in Wonder World mockup assets", "surt",
           OGA + "monsterboy-in-wonder-world-mockup-assets", "scout", "surt-monsterboy"),
    Source("jetrel-jpiso", "Japanese buildings isometric strategy game mockup", "Jetrel",
           OGA + "japanese-buildings-isometric-strategy-game-mockup", "scout", "jetrel-jp-iso"),
    Source("dezra-iso", "Isometric classic hero tiles 32x32", "DezrasDragons",
           OGA + "isometric-classic-hero-tiles-32x32", "scout", "dezra-iso"),
    Source("jetrel-frogatto", "Old Frogatto tile art", "Jetrel", OGA + "old-frogatto-tile-art",
           "scout", "jetrel-frogatto"),
    Source("marcavis-frogatto", "Old Frogatto parallax layers", "marcavis", OGA + "old-frogatto-parallax-layers",
           "scout", "marcavis-frogatto-parallax/x"),
    Source("fisherg-city", "Parallax City Night (4 colors)", "fisherg", OGA + "parallax-city-night-4-colors",
           "scout", "fisherg-city4/x/CityBackground"),
    Source("phoenix-portraits", "25 Portrait Pixel Art pack 1", "phoenix1291", OGA + "25-portrait-pixel-art-pack1",
           "scout", "phoenix-25-portraits/x/25_Portrait_Pixel_Art_pack1"),
    Source("efilheim-everface", "Everface", "efilheim", OGA + "everface", "scout", "efilheim-everface"),
    Source("buch-doodle", "2-bit doodle people", "Buch", OGA + "2-bit-doodle-people", "scout", "buch-2bit-faces"),
    Source("buch-rpg", "RPG portraits", "Buch", OGA + "rpg-portraits", "buch_rpg"),
    Source("blarumyrran-faceset", "Faceset 2-bit", "Blarumyrran", OGA + "faceset-2-bit",
           "scout", "blarumyrran-faceset"),
    Source("cawfeecrow-neko", "Nekomimi girl portrait", "cawfeecrow", OGA + "nekomimi-girl-portrait",
           "scout", "cawfeecrow-neko"),
]}

# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------


@dataclass
class Item:
    id: str
    src: str
    file: str
    genre: str
    rect: tuple[int, int, int, int] | None = None   # x, y, w, h in the source
    trim: bool = False                               # trim to alpha bbox + margin
    downscale: int = 1                               # source is an integer upscale
    tags: tuple[str, ...] = ()
    allow_many_colors: bool = False
    key_color: tuple[int, int, int] | None = None    # flat sheet background made transparent
    note: str = ""


@dataclass
class SheetPick:
    """Deterministic diverse pick of cells from a regular grid sheet."""
    prefix: str
    src: str
    file: str
    genre: str
    cell: tuple[int, int]
    pitch: tuple[int, int] | None = None
    offset: tuple[int, int] = (0, 0)
    count: int = 8
    skip: tuple[tuple[int, int], ...] = ()       # (row, col) cells never picked
    only: tuple[tuple[int, int], ...] = ()       # if set, pick exactly these
    tags: tuple[str, ...] = ()
    genre_by_cell: dict = field(default_factory=dict)


@dataclass
class WindowPick:
    """Pick the most colourful non-overlapping aligned windows of a sheet."""
    prefix: str
    src: str
    file: str
    genre: str
    size: tuple[int, int]
    step: int
    count: int
    tags: tuple[str, ...] = ()


def recipes() -> list:
    r: list = []
    I = Item

    # --- Denzi (CC0) --------------------------------------------------------
    r.append(SheetPick("denzi-tile", "denzi", "DENZI_CC0_32x32_tileset.png", "tile", (32, 32), count=5))
    r.append(SheetPick("denzi-monster", "denzi", "DENZI_CC0_32x48_monsters.png", "monster", (32, 48),
                       # rows 0, 1 and 3 hold separate heads and wings (paper-doll parts): pick whole monsters
                       only=((2, 6), (4, 1), (4, 8), (5, 3), (9, 5), (10, 2))))
    r.append(WindowPick("denzi-crop-m", "denzi", "DENZI_CC0_32x32_tileset.png", "tile", (96, 96), 32, 4))
    r.append(WindowPick("denzi-crop-l", "denzi", "DENZI_CC0_32x32_tileset.png", "tile", (256, 192), 32, 2))
    r.append(WindowPick("denzi-crop-xl", "denzi", "DENZI_CC0_32x32_tileset.png", "tile", (160, 160), 32, 2))
    r.append(WindowPick("denzi-crop-s", "denzi", "DENZI_CC0_32x32_tileset.png", "tile", (128, 64), 32, 2))
    r.append(WindowPick("denzi-monster-crop", "denzi", "DENZI_CC0_32x48_monsters.png", "monster", (96, 96), 32, 1))

    # --- Dungeon Crawl Stone Soup (CC0) -------------------------------------
    dcss = [
        # 65+ colours
        ("mon/griffon.png", "monster", False), ("mon/dragons/quicksilver_dragon.png", "monster", False),
        ("mon/unique/ereshkigal.png", "monster", False), ("mon/unique/ignacio.png", "character", False),
        ("mon/demons/shadow_fiend.png", "monster", False), ("mon/animals/scorpion.png", "monster", False),
        ("mon/undead/ghoul.png", "monster", False),
        ("mon/nonliving/flesh_golem.png", "monster", False), ("mon/fungi_plants/treant.png", "monster", False),
        ("item/food/strawberry.png", "item", True),
        ("dngn/altars/fedhas.png", "tile", False),
        ("dngn/doors/runed_door.png", "tile", False), ("dngn/wall/church0.png", "tile", False),
        ("dngn/floor/mosaic0.png", "tile", False), 
        ("gui/spells/conjuration/orb_of_destruction.png", "ui", False),
        ("dngn/vaults/statue_elephant_jade.png", "tile", False), 
        # 17-64 colours
        ("mon/orc_knight.png", "character", False), ("mon/naga_mage.png", "character", False),
        ("mon/tengu_warrior.png", "character", False), ("mon/sphinx.png", "monster", False),
        ("item/weapon/ranged/stone.png", "item", True),
        ("misc/icons/constricted.png", "ui", True),
        # 5-16 colours
        ("mon/undead/lich.png", "monster", False), ("dngn/statues/orcish_idol.png", "tile", False),
        ("item/wand/gem_gold.png", "item", True), ("item/scroll/i-acquirement.png", "item", True),
        # tiny (<= 16 px after trim) with 17+ colours
        ("player/hand1/mace2.png", "item", True), ("player/hand1/hand_axe2.png", "item", True),
        ("mon/panlord/demon_head_incubus.png", "monster", True),
        # 2-4 colours
        ("item/ring/i-flight.png", "item", True), ("item/staff/i-staff_energy.png", "item", True),
        ("mon/undead/missing_ghost.png", "monster", True),
    ]
    for path, genre, trim in dcss:
        parent, name = path.rsplit("/", 2)[-2:]
        stem = name[:-4].replace("_", "-").lower()
        if stem[:1].isdigit():
            stem = f"{parent}-{stem}"
        r.append(I(f"dcss-{stem}", "dcss", path, genre, trim=trim, tags=tuple(DCSS_TAGS.get(path, ()))))

    # --- Kenney (CC0) -------------------------------------------------------
    r.append(SheetPick("kenney-micro", "kenney-micro", "Tilemap/colored_tilemap_packed.png", "tile", (8, 8), count=5))
    r.append(SheetPick("kenney-pico8city", "kenney-pico8city", "Tilemap/tilemap_packed.png", "tile", (8, 8), count=3))
    r.append(SheetPick("kenney-tinydungeon", "kenney-tinydungeon", "Tilemap/tilemap_packed.png", "tile", (16, 16),
                       count=9, skip=((0, 1),)))  # (0, 1) is a near-flat wall corner
    r.append(SheetPick("kenney-1bit", "kenney-1bit", "Tilesheet/colored_packed.png", "tile", (16, 16), count=4))
    for f, src, genre in [
        ("kenney-pp-char-0000.png", "kenney-pixelplatformer", "character"),
        ("kenney-pp-tile-0000.png", "kenney-pixelplatformer", "tile"),
        ("kenney-shmup-ship-ship_0000.png", "kenney-pixelshmup", "item"),
        ("kenney-shmup-tile-0107.png", "kenney-pixelshmup", "tile"),
        ("kenney-rts-tile-0129.png", "kenney-rtspixel", "tile"),
    ]:
        r.append(I(f[:-4].replace("_", "-").replace("ship-ship-", "ship-"), src, f, genre))

    # --- 0x72 DungeonTileset II (CC0) ---------------------------------------
    for f, genre in [
        ("big_demon_idle_anim_f0", "monster"), ("elf_f_idle_anim_f0", "character"),
        ("lizard_f_run_anim_f1", "animation-frame"), ("wizzard_m_idle_anim_f0", "character"),
        ("chest_full_open_anim_f2", "item"),
        ("flask_big_green", "item"), ("weapon_golden_sword", "item"), ("ui_heart_half", "ui"),
    ]:
        r.append(I(f"0x72-{f.replace('_', '-')}", "0x72", f"frames/{f}.png", genre, trim=True))

    # --- Urizen 1-bit (CC0): 12 px tiles with 1 px gaps ---------------------
    r.append(SheetPick("urizen-tile", "urizen", "urizen_onebit_tileset__v2d0.png", "tile", (12, 12),
                       pitch=(13, 13), offset=(1, 1), count=4,
                       skip=tuple((49, c) for c in range(206))))  # row 49 holds font glyphs

    # --- LuizMelo monsters (CC0): 150 px frames in strips -------------------
    for d, f, i, genre in [
        ("Goblin", "Idle", 0, "monster"), ("Goblin", "Attack", 6, "animation-frame"),
        ("Skeleton", "Attack", 6, "animation-frame"), 
        ("Flying eye", "Flight", 0, "monster"),
    ]:
        r.append(I(f"luizmelo-{d.lower().replace(' ', '')}-{f.lower()}-f{i}", "luizmelo", f"{d}/{f}.png", genre,
                   rect=(150 * i, 0, 150, 150), trim=True))

    # --- Ansimuz Sideview Fantasy (CC0) -------------------------------------
    sv = "ansimuz-sv"
    E, S = "Environments/", "Sprites/"
    r += [
        I("ansimuz-sv-bunny-idle", sv, S + "sunny-bunny/PNG/layers/idle/_0000_Layer-1.png", "character", trim=True),
        I("ansimuz-sv-froggy-taunt", sv, S + "sunny-froggy/PNG/layers/taunting/_0000_Layer-1.png", "monster",
          trim=True),
        I("ansimuz-sv-mushroom-walk", sv, S + "sunny-mushroom/PNG/sprites/walking/0__0000_Layer-1.png", "monster",
          trim=True),
        I("ansimuz-sv-boss-dragon", sv, S + "Grotto-escape-2-boss-dragon/PNG/sprites/idle/_0000_Layer-1.png",
          "monster", trim=True),
        I("ansimuz-sv-sunny-dragon", sv, S + "sunny-dragon/PNG/sprites/_0000_Layer-1.png", "monster", trim=True),
        I("ansimuz-sv-fx-death", sv, S + "Grotto-escape-2-FX/PNG/sprites/enemy-death/_0002_Layer-3.png",
          "animation-frame", trim=True),
        I("ansimuz-sv-fx-field", sv, S + "Grotto-escape-2-FX/PNG/sprites/energy-field/_0000_Layer-1.png",
          "animation-frame", trim=True),
        I("ansimuz-sv-ghost-f0", sv, S + "enemy-ghost/PNG/transparent-no-particles.png", "monster",
          rect=(0, 0, 64, 64), trim=True),
        I("ansimuz-sv-bird-f0", sv, S + "flying-bird/sprites/flying-creature-cycle-skin.png", "animation-frame",
          rect=(0, 0, 32, 32), trim=True),
        I("ansimuz-sv-rocky-bg", sv, E + "Rocky-Tileset/PNG/layers/rocky-tileset-background.png", "scene",
          rect=(0, 0, 320, 192)),
        I("ansimuz-sv-sunny-hills", sv, E + "sunny-rocky-mountains/PNG/sunny-mountains-hills.png", "scene"),
        I("ansimuz-sv-lava-bg", sv, E + "lava-background/PNG/background.png", "scene", rect=(56, 0, 320, 240)),
        I("ansimuz-sv-mist-trees", sv, E + "mist-forest-background/layers/mist-forest-background-back-trees.png",
          "scene"),
        I("ansimuz-sv-mist-rocks", sv, E + "mist-forest-background/layers/mist-forest-background-rocks.png", "scene"),
        I("ansimuz-sv-forest-road", sv, E + "forest-road-background/PNG/front.png", "scene"),
        I("ansimuz-sv-modular-tiles", sv, E + "Modular-tileset/layers/modular-tileset.png", "tile",
          rect=(0, 0, 320, 272)),
        I("ansimuz-sv-day-trees", sv, E + "Day-Platformer/PNG/trees.png", "scene"),
        I("ansimuz-sv-rock-tiles", sv, E + "Rocks-Textures/PNG/tiles/all-rock-tiles.png", "tile"),
        I("ansimuz-sv-back-gold", sv, E + "treasure-hoard-platform/PNG/back-gold.png", "scene", rect=(0, 0, 320, 60)),
        I("ansimuz-sv-boat-front", sv, E + "ships-graveyard/PNG/layers/boat-front.png", "scene", trim=True),
        I("ansimuz-sv-vegetation", sv, E + "colorful-tileset/PNG/layers/back-vegetation.png", "scene"),
        I("ansimuz-sv-lava-tile", sv, E + "lava-background/PNG/lava-tile.png", "tile"),
    ]

    # --- Ansimuz Gothicvania Town (CC0) -------------------------------------
    g = "ansimuz-gothic"
    r += [
        I("ansimuz-gothic-well", g, "environment/props-sliced/well.png", "item"),
        I("ansimuz-gothic-wagon", g, "environment/props-sliced/wagon.png", "item"),
        I("ansimuz-gothic-roof", g, "environment/layers/sliced-tileset/left-roof.png", "tile"),
        I("ansimuz-gothic-bg", g, "environment/layers/background.png", "scene", rect=(0, 0, 320, 288)),
        I("ansimuz-gothic-oldman", g, "sprites/oldman-walk/oldman-walk-1.png", "character", trim=True),
        I("ansimuz-gothic-title", g, "title-screen/title-screen.png", "ui"),
        I("ansimuz-gothic-press-enter", g, "title-screen/press-enter-text.png", "ui"),
    ]

    # --- Ansimuz Magic Cliffs, Mountain, Warped City, Faune (CC0) -----------
    r += [
        I("ansimuz-cliffs-tiles", "ansimuz-cliffs", "tileset.png", "tile", rect=(0, 0, 320, 320)),
        I("ansimuz-cliffs-sea", "ansimuz-cliffs", "sea.png", "scene"),
        I("ansimuz-cliffs-clouds", "ansimuz-cliffs", "clouds.png", "scene", rect=(0, 0, 320, 236)),
        I("ansimuz-cliffs-sky", "ansimuz-cliffs", "sky.png", "scene"),
        I("ansimuz-mountain-bg", "ansimuz-mountain", "parallax-mountain-bg.png", "scene"),
        I("ansimuz-mountain-far", "ansimuz-mountain", "parallax-mountain-montain-far.png", "scene"),
        I("ansimuz-warped-skyline", "ansimuz-warped", "ENVIRONMENT/background/skyline-a.png", "scene"),
        I("ansimuz-warped-police", "ansimuz-warped", "SPRITES/vehicles/v-police.png", "item", trim=True),
        I("ansimuz-warped-player", "ansimuz-warped", "SPRITES/player/idle/idle-1.png", "character", trim=True),
        I("ansimuz-warped-drone", "ansimuz-warped", "SPRITES/misc/drone/drone-1.png", "monster", trim=True),
        I("ansimuz-warped-explosion", "ansimuz-warped", "SPRITES/misc/enemy-explosion/enemy-explosion-3.png",
          "animation-frame", trim=True),
        I("ansimuz-warped-monitor", "ansimuz-warped", "ENVIRONMENT/props/monitorface/monitor-face-1.png", "ui"),
        # Legend of Faune 01-sprites/02-environment are preview boards with text labels: not used.
        I("ansimuz-warped-near-bg", "ansimuz-warped", "ENVIRONMENT/background/near-buildings-bg.png", "scene",
          rect=(0, 81, 128, 128)),
        I("ansimuz-gothic-house-c", "ansimuz-gothic", "environment/props-sliced/house-c.png", "scene",
          rect=(0, 0, 221, 183)),
        I("ansimuz-sv-day-tiles-m", "ansimuz-sv", "Environments/Day-Platformer/PNG/tileset.png", "tile",
          rect=(192, 0, 112, 112)),
        I("ansimuz-sv-modular-m", "ansimuz-sv", "Environments/Modular-tileset/layers/modular-tileset.png", "tile",
          rect=(240, 144, 128, 128)),
    ]

    # --- Scenes and isometric mockups (CC0) ---------------------------------
    r += [
        I("surt-monsterboy-a", "surt-monsterboy", "monsterboy_0.png", "scene", rect=(0, 0, 320, 240)),
        I("surt-monsterboy-b", "surt-monsterboy", "monsterboy_0.png", "scene", rect=(320, 360, 320, 240)),
        I("surt-monsterboy-c", "surt-monsterboy", "monsterboy_0.png", "scene", rect=(0, 720, 320, 240)),
        I("surt-monsterboy-m1", "surt-monsterboy", "monsterboy_0.png", "scene", rect=(160, 960, 128, 96)),
        I("surt-monsterboy-m2", "surt-monsterboy", "monsterboy_0.png", "scene", rect=(480, 600, 128, 112)),
        I("jetrel-jpiso-full", "jetrel-jpiso", "jpisotbs.png", "isometric"),
        I("jetrel-jpiso-crop", "jetrel-jpiso", "jpisotbs.png", "isometric", rect=(100, 50, 112, 96)),
        I("marcavis-frogatto-layer5", "marcavis-frogatto", "forestbg-layer5.png", "scene", rect=(0, 121, 128, 128)),
        I("jetrel-frogatto-l", "jetrel-frogatto", "dirt-tiles.png", "tile", rect=(0, 0, 256, 256)),
        I("jetrel-frogatto-m", "jetrel-frogatto", "dirt-tiles.png", "tile", rect=(192, 0, 192, 192)),
        I("marcavis-frogatto-trees", "marcavis-frogatto", "bg-trees1.png", "scene", rect=(0, 96, 256, 320)),
        I("marcavis-frogatto-layer7", "marcavis-frogatto", "forestbg-layer7.png", "scene", rect=(0, 0, 297, 147)),
        I("marcavis-frogatto-layer1", "marcavis-frogatto", "forestbg-layer1.png", "scene", rect=(0, 0, 297, 60)),
        I("marcavis-frogatto-layer10", "marcavis-frogatto", "forestbg-layer10.png", "scene", rect=(0, 0, 297, 109)),
        I("fisherg-city-mid", "fisherg-city", "sCityMid.png", "scene"),
        I("fisherg-city-mockup", "fisherg-city", "sMockup.png", "scene", downscale=6,
          note="source is a 6x nearest upscale; downscaled by 6"),
    ]

    # --- Dezra isometric heroes (CC0): 32 px cells inside 1 px black guide lines on a flat
    # lavender board. The board colour is keyed out to make transparent sprites.
    for r_, c_, genre in [(3, 2, "isometric"), (8, 11, "isometric"), (10, 10, "isometric"),
                          (12, 13, "isometric"), (14, 12, "item")]:
        x, y = 1 + DEZRA_PITCH * c_, 1 + DEZRA_PITCH * r_
        r.append(I(f"dezra-iso-r{r_:02d}c{c_:02d}", "dezra-iso", "isometric_hero_dezrasdragons.png", genre,
                   rect=(x, y, 32, 32), key_color=DEZRA_BG, trim=True))

    # --- Portraits (CC0) ----------------------------------------------------
    for n in (1, 19, 8, 14):
        r.append(I(f"phoenix-portrait-{n:02d}", "phoenix-portraits", f"Pixel_art_Portrait_{n}.png", "portrait"))
    r.append(SheetPick("efilheim-everface", "efilheim-everface", "everface1.0.png", "portrait", (24, 24),
                       only=((0, 0), (0, 11), (0, 15))))
    r.append(SheetPick("buch-doodle", "buch-doodle", "2bit_faces.png", "portrait", (24, 32),
                       only=((0, 0), (1, 2), (2, 3))))
    r.append(SheetPick("buch-rpg", "buch-rpg", "rpgportraits.png", "portrait", (32, 32), pitch=(36, 36),
                       offset=(4, 4), only=((0, 0), (2, 2))))
    for i, x in enumerate((4, 75, 146, 217, 288)):
        if i in (0, 2, 4):
            r.append(I(f"blarumyrran-face-{i}", "blarumyrran-faceset", "faceset_16.png", "portrait",
                       rect=(x, 3, 63, 79)))
    r.append(I("cawfeecrow-neko", "cawfeecrow-neko", "nekoportrait-expression1.png", "portrait"))
    return r


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def load_rgba(path: Path) -> np.ndarray:
    if path.suffix.lower() in REJECT_EXTS:
        raise Reject("JPEG source")
    with Image.open(path) as im:
        if im.format not in ("PNG", "GIF"):
            raise Reject(f"unexpected format {im.format}")
        return np.asarray(im.convert("RGBA")).copy()


def unique_colors(a: np.ndarray) -> int:
    v = a[..., 3] >= VISIBLE_ALPHA
    if not v.any():
        return 0
    rgb = a[v][:, :3].astype(np.uint32)
    return int(np.unique((rgb[:, 0] << 16) | (rgb[:, 1] << 8) | rgb[:, 2]).size)


def upscale_factor(a: np.ndarray) -> int:
    """Largest k in 2..8 such that the image is an exact k-times nearest upscale, else 1."""
    h, w = a.shape[:2]
    best = 1
    for k in UPSCALE_FACTORS:
        if w % k or h % k:
            continue
        small = a[::k, ::k]
        if np.array_equal(np.repeat(np.repeat(small, k, 0), k, 1), a):
            best = k
    return best


def trim(a: np.ndarray, margin: int = TRIM_MARGIN) -> np.ndarray:
    ys, xs = np.nonzero(a[..., 3] > 0)
    if xs.size == 0:
        return a
    y0, y1 = max(0, ys.min() - margin), min(a.shape[0], ys.max() + 1 + margin)
    x0, x1 = max(0, xs.min() - margin), min(a.shape[1], xs.max() + 1 + margin)
    return a[y0:y1, x0:x1]


def bbox_rect(a: np.ndarray, margin: int = TRIM_MARGIN) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(a[..., 3] > 0)
    y0, y1 = max(0, ys.min() - margin), min(a.shape[0], ys.max() + 1 + margin)
    x0, x1 = max(0, xs.min() - margin), min(a.shape[1], xs.max() + 1 + margin)
    return int(x0), int(y0), int(x1 - x0), int(y1 - y0)


def bin_of(value: int, bins) -> str | None:
    for name, lo, hi in bins:
        if lo <= value <= hi:
            return name
    return None


def is_dithered(a: np.ndarray) -> bool:
    """Checkerboard 2x2 blocks (a b / b a, a != b) among visible pixels."""
    rgb = a[..., :3].astype(np.int32)
    key = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
    key = np.where(a[..., 3] >= VISIBLE_ALPHA, key, -1)
    p, q, r_, s = key[:-1, :-1], key[:-1, 1:], key[1:, :-1], key[1:, 1:]
    checker = (p == s) & (q == r_) & (p != q) & (p >= 0) & (q >= 0)
    # require the pattern to extend: 3x3 alternating neighbourhoods
    if checker.shape[0] < 2 or checker.shape[1] < 2:
        return False
    run = checker[:-1, :-1] & checker[1:, 1:] & checker[:-1, 1:] & checker[1:, :-1]
    visible = (a[..., 3] >= VISIBLE_ALPHA).sum()
    return bool(run.sum() >= 4 and run.sum() >= 0.004 * visible)


class Reject(Exception):
    pass


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


class Builder:
    def __init__(self, roots: dict[str, Path], out: Path):
        self.roots = roots
        self.out = out
        self.records: list[dict] = []
        self.rejected: list[tuple[str, str]] = []
        self.hashes: dict[str, str] = {}
        self.dcss_excluded = self._load_dcss_exclusions()

    def _load_dcss_exclusions(self) -> set[str]:
        p = self.roots["dcss"] / "TILES_UNDER_UNKNOWN_LICENSE.md"
        names = set()
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("- ") and line.endswith(".png"):
                names.add(line[2:].strip())
        if not names:
            raise SystemExit("DCSS exclusion list is empty; refusing to continue")
        return names

    def src_path(self, src: Source, file: str) -> Path:
        base = self.roots[src.root]
        if src.subdir:
            base = base / src.subdir
        return base / file

    # -- checks -------------------------------------------------------------
    def check_source_name(self, src: Source, file: str) -> None:
        name = file.rsplit("/", 1)[-1]
        low = name.lower()
        if name in REJECT_FILES or any(part in low for part in REJECT_NAME_PARTS):
            raise Reject("promo/preview/sample or 2x copy")
        if src.root == "game1x" and not name.startswith("kenney-"):
            raise Reject("non-Kenney game1x file (CC-BY-SA)")
        if src.key == "dcss" and name in self.dcss_excluded:
            raise Reject("DCSS tile under unknown licence")

    def check_image(self, a: np.ndarray, tags: set[str], allow_many: bool, is_crop: bool) -> dict:
        h, w = a.shape[:2]
        if max(w, h) > MAX_SIDE:
            raise Reject(f"too big {w}x{h}")
        if max(w, h) < MIN_SIDE:
            raise Reject(f"too small {w}x{h}")
        k = upscale_factor(a)
        if k > 1:
            raise Reject(f"exact {k}x nearest upscale")
        visible = int((a[..., 3] >= VISIBLE_ALPHA).sum())
        if visible < MIN_VISIBLE_PIXELS:
            raise Reject("fewer than 6 visible pixels")
        if is_crop and visible < MIN_CROP_VISIBLE * w * h:
            raise Reject("crop is mostly empty")
        colors = unique_colors(a)
        v = a[..., 3] >= VISIBLE_ALPHA
        _, counts = np.unique(a[v][:, :3], axis=0, return_counts=True)
        if counts.max() / counts.sum() > MAX_DOMINANT_SHARE:
            raise Reject("near-flat: one colour covers > 95% of visible pixels")
        if colors < MIN_COLORS:
            raise Reject("single colour")
        if colors > MAX_COLORS and not allow_many:
            raise Reject(f"{colors} colours")
        alpha = a[..., 3]
        nonempty = int((alpha > 0).sum())
        partial = int(((alpha > 0) & (alpha < 255)).sum())
        if nonempty and partial / nonempty > TRANSLUCENT_FRACTION and "translucent" not in tags:
            raise Reject(f"{partial} partly transparent pixels (not tagged translucent)")
        return {"colors": colors, "visible": visible}

    # -- emit ---------------------------------------------------------------
    def emit(self, id_: str, src: Source, file: str, a: np.ndarray, genre: str, rect, extra_tags=(),
             allow_many=False, is_crop=False, note="") -> bool:
        assert genre in GENRES, genre
        tags = set(extra_tags)
        assert tags <= TAGS, tags
        try:
            info = self.check_image(a, tags, allow_many, is_crop)
        except Reject as e:
            self.rejected.append((id_, str(e)))
            return False
        digest = hashlib.sha256(a.tobytes() + bytes(str(a.shape), "ascii")).hexdigest()
        if digest in self.hashes:
            self.rejected.append((id_, f"duplicate of {self.hashes[digest]}"))
            return False
        self.hashes[digest] = id_
        h, w = a.shape[:2]
        transparent = (a[..., 3] == 0).mean() >= TRANSPARENT_FRACTION
        tags.add("transparent" if transparent else "opaque")
        tags.discard("opaque" if transparent else "transparent")
        if is_dithered(a):
            tags.add("dithered")
        if src.key in AA_SOURCES and info["colors"] >= AA_MIN_COLORS:
            tags.add("anti-aliased")
        rec = {
            "id": id_,
            "file": f"images/{id_}.png",
            "width": int(w),
            "height": int(h),
            "colors": info["colors"],
            "size_bin": bin_of(max(w, h), SIZE_BINS),
            "palette_bin": bin_of(info["colors"], PALETTE_BINS),
            "genre": genre,
            "tags": sorted(tags),
            "source": src.pack,
            "author": src.author,
            "source_url": src.url,
            "file_in_source": {"file": file, "rect": list(rect) if rect else [0, 0, int(w), int(h)]},
            "license": src.license,
            "attribution": src.attribution,
        }
        if note:
            rec["note"] = note
        self.records.append(rec)
        self._write_png(self.out / rec["file"], a)
        return True

    @staticmethod
    def _write_png(path: Path, a: np.ndarray) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        im = Image.fromarray(a, "RGBA")
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True, compress_level=9)
        path.write_bytes(buf.getvalue())

    # -- recipe kinds -------------------------------------------------------
    def run_item(self, it: Item) -> None:
        src = SOURCES[it.src]
        try:
            self.check_source_name(src, it.file)
            a = load_rgba(self.src_path(src, it.file))
        except (Reject, FileNotFoundError) as e:
            self.rejected.append((it.id, str(e)))
            return
        rect = it.rect
        if it.downscale > 1:
            k = it.downscale
            if upscale_factor(a) % k != 0 and not np.array_equal(
                    np.repeat(np.repeat(a[::k, ::k], k, 0), k, 1), a):
                self.rejected.append((it.id, f"source is not an exact {k}x upscale"))
                return
            a = a[::k, ::k]
        if rect:
            x, y, w, h = rect
            if x + w > a.shape[1] or y + h > a.shape[0]:
                self.rejected.append((it.id, "rect outside source"))
                return
            a = a[y:y + h, x:x + w]
        if it.key_color is not None:
            a = a.copy()
            a[(a[..., :3] == np.array(it.key_color, dtype=np.uint8)).all(-1)] = 0
        if it.trim:
            tx, ty, tw, th = bbox_rect(a)
            a = a[ty:ty + th, tx:tx + tw]
            ox, oy = (rect[0], rect[1]) if rect else (0, 0)
            rect = (ox + tx, oy + ty, tw, th)
        self.emit(it.id, src, it.file, np.ascontiguousarray(a), it.genre, rect, it.tags,
                  it.allow_many_colors, is_crop=bool(it.rect) and not it.trim, note=it.note)

    def run_sheet(self, sp: SheetPick) -> None:
        src = SOURCES[sp.src]
        try:
            self.check_source_name(src, sp.file)
            a = load_rgba(self.src_path(src, sp.file))
        except (Reject, FileNotFoundError) as e:
            self.rejected.append((sp.prefix, str(e)))
            return
        cw, ch = sp.cell
        px, py = sp.pitch or sp.cell
        ox, oy = sp.offset
        H, W = a.shape[:2]
        cells = []
        for r, y in enumerate(range(oy, H - ch + 1, py)):
            for c, x in enumerate(range(ox, W - cw + 1, px)):
                cells.append((r, c, x, y, a[y:y + ch, x:x + cw]))
        if sp.only:
            want = {rc: i for i, rc in enumerate(sp.only)}
            chosen = sorted((cell for cell in cells if (cell[0], cell[1]) in want),
                            key=lambda cell: want[(cell[0], cell[1])])
        else:
            chosen = self._diverse(cells, sp)
        for r, c, x, y, t in chosen:
            genre = sp.genre_by_cell.get((r, c), sp.genre)
            self.emit(f"{sp.prefix}-r{r:02d}c{c:02d}", src, sp.file, np.ascontiguousarray(t), genre,
                      (x, y, cw, ch), sp.tags)

    def _diverse(self, cells, sp: SheetPick):
        """Stratify valid cells by palette bin, then take evenly spaced cells per bin."""
        skip = set(sp.skip)
        valid = []
        seen = set()
        for r, c, x, y, t in cells:
            if (r, c) in skip:
                continue
            vis = t[..., 3] >= VISIBLE_ALPHA
            n = int(vis.sum())
            if n < max(MIN_VISIBLE_PIXELS, 0.15 * t.shape[0] * t.shape[1]):
                continue
            cols = unique_colors(t)
            if cols < MIN_COLORS or cols > MAX_COLORS:
                continue
            _, cnt = np.unique(t[vis][:, :3], axis=0, return_counts=True)
            if cnt.max() / cnt.sum() > MAX_DOMINANT_SHARE:
                continue
            if ((t[..., 3] > 0) & (t[..., 3] < 255)).sum() > TRANSLUCENT_FRACTION * max(1, (t[..., 3] > 0).sum()):
                continue
            if upscale_factor(t) > 1:
                continue
            h = t.tobytes()
            if h in seen:
                continue
            seen.add(h)
            valid.append((r, c, x, y, t, cols))
        by_bin: dict[str, list] = {}
        for v in valid:
            by_bin.setdefault(bin_of(v[5], PALETTE_BINS), []).append(v)
        order = [b for b, _, _ in PALETTE_BINS if b in by_bin]
        # spread picks across bins proportionally but give every bin at least one
        quota = {b: 1 for b in order}
        remaining = sp.count - len(order)
        total = sum(len(by_bin[b]) for b in order)
        for b in order:
            quota[b] += int(remaining * len(by_bin[b]) / total) if total else 0
        while sum(quota.values()) < sp.count and order:
            for b in sorted(order, key=lambda b: -len(by_bin[b])):
                if sum(quota.values()) >= sp.count:
                    break
                quota[b] += 1
        picked = []
        for b in order:
            pool = by_bin[b]
            q = min(quota[b], len(pool))
            if q <= 0:
                continue
            idx = [int(round(i * (len(pool) - 1) / max(1, q - 1))) if q > 1 else len(pool) // 2 for i in range(q)]
            got = 0
            tried = set()
            for start in idx + list(range(len(pool))):
                if got >= q:
                    break
                if start in tried:
                    continue
                tried.add(start)
                cand = pool[start]
                if any(self._near_dup(cand[4], p[4]) for p in picked):
                    continue
                picked.append(cand)
                got += 1
        picked.sort(key=lambda v: (v[0], v[1]))
        return [(r, c, x, y, t) for r, c, x, y, t, _ in picked]

    @staticmethod
    def _near_dup(a: np.ndarray, b: np.ndarray) -> bool:
        if a.shape != b.shape:
            return False
        return (a == b).all(axis=2).mean() >= NEAR_DUP_SAME_PIXELS

    def run_window(self, wp: WindowPick) -> None:
        src = SOURCES[wp.src]
        try:
            self.check_source_name(src, wp.file)
            a = load_rgba(self.src_path(src, wp.file))
        except (Reject, FileNotFoundError) as e:
            self.rejected.append((wp.prefix, str(e)))
            return
        w, h = wp.size
        H, W = a.shape[:2]
        cands = []
        for y in range(0, H - h + 1, wp.step):
            for x in range(0, W - w + 1, wp.step):
                t = a[y:y + h, x:x + w]
                vis = (t[..., 3] >= VISIBLE_ALPHA).mean()
                if vis < 0.6:
                    continue
                cands.append((-unique_colors(t), y, x))
        cands.sort()
        taken: list[tuple[int, int]] = []
        n = 0
        for negc, y, x in cands:
            if n >= wp.count:
                break
            if any(abs(x - tx) < w and abs(y - ty) < h for tx, ty in taken):
                continue
            # also avoid overlap with windows of earlier WindowPicks on the same file
            if any(abs(x - tx) < max(w, tw) and abs(y - ty) < max(h, th)
                   for (f, tx, ty, tw, th) in getattr(self, "_win_taken", []) if f == wp.file):
                continue
            taken.append((x, y))
            self.__dict__.setdefault("_win_taken", []).append((wp.file, x, y, w, h))
            n += 1
            self.emit(f"{wp.prefix}-{n:02d}", src, wp.file, np.ascontiguousarray(a[y:y + h, x:x + w]), wp.genre,
                      (x, y, w, h), wp.tags, is_crop=True)

    # -- outputs ------------------------------------------------------------
    def build(self, items) -> None:
        img_dir = self.out / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        for old in img_dir.glob("*.png"):
            old.unlink()
        for it in items:
            if isinstance(it, Item):
                self.run_item(it)
            elif isinstance(it, SheetPick):
                self.run_sheet(it)
            elif isinstance(it, WindowPick):
                self.run_window(it)
        self.records.sort(key=lambda r: r["id"])
        (self.out / "manifest.json").write_text(json.dumps(self.records, indent=2) + "\n", encoding="utf-8")
        self.write_credits()
        self.write_contact_sheet()

    def write_credits(self) -> None:
        counts: dict[str, int] = {}
        for r in self.records:
            counts[r["source"]] = counts.get(r["source"], 0) + 1
        lines = [
            "# Corpus credits",
            "",
            "All images in `images/` are native 1x pixel art cut from the packs below.",
            "CC0 items need no attribution; the authors are credited here anyway.",
            "Each record in `manifest.json` names its pack, author, licence page and source rectangle.",
            "",
            "| Pack | Author | Link | Licence | Images |",
            "|---|---|---|---|---|",
        ]
        used = [s for s in SOURCES.values() if s.pack in counts]
        for s in sorted(used, key=lambda s: s.pack.lower()):
            lines.append(f"| {s.pack} | {s.author} | <{s.url}> | {s.license} | {counts[s.pack]} |")
        ccby = [s for s in used if s.license != "CC0-1.0"]
        lines.append("")
        if ccby:
            lines.append("## Attribution required")
            lines.append("")
            for s in ccby:
                lines.append(f"- {s.attribution} ({s.license}, <{s.url}>)")
        else:
            lines.append("No image in this corpus needs attribution: every source is CC0-1.0.")
        lines += [
            "",
            "Dungeon Crawl Stone Soup tiles come from the CC0 export at <https://github.com/crawl/tiles>;",
            "tiles named in its `TILES_UNDER_UNKNOWN_LICENSE.md` are excluded. Artists are listed in its `ARTISTS.md`.",
            "",
        ]
        (self.out / "CREDITS.md").write_text("\n".join(lines), encoding="utf-8")

    def write_contact_sheet(self) -> None:
        n = len(self.records)
        rows = (n + CONTACT_COLS - 1) // CONTACT_COLS
        cw, chh = CONTACT_CELL + 8, CONTACT_CELL + CONTACT_LABEL + 8
        sheet = Image.new("RGB", (CONTACT_COLS * cw, rows * chh), (32, 32, 36))
        d = ImageDraw.Draw(sheet)
        for i, rec in enumerate(self.records):
            im = Image.open(self.out / rec["file"]).convert("RGBA")
            w, h = im.size
            s = CONTACT_CELL / max(w, h)
            if s >= 1:
                k = int(s)
                nw, nh = w * k, h * k
            else:
                nw, nh = max(1, round(w * s)), max(1, round(h * s))
            im = im.resize((nw, nh), Image.NEAREST)
            bg = Image.new("RGBA", (nw, nh))
            tile = 4
            yy, xx = np.mgrid[0:nh, 0:nw]
            chk = (((yy // tile) + (xx // tile)) % 2).astype(np.uint8)
            bga = np.stack([np.where(chk, 200, 150)] * 3 + [np.full_like(chk, 255)], -1).astype(np.uint8)
            bg = Image.fromarray(bga, "RGBA")
            bg.alpha_composite(im)
            X, Y = (i % CONTACT_COLS) * cw + 4, (i // CONTACT_COLS) * chh + 4
            sheet.paste(bg.convert("RGB"), (X + (CONTACT_CELL - nw) // 2, Y + (CONTACT_CELL - nh) // 2))
            label = rec["id"]
            if len(label) > 17:
                label = label[:8] + "~" + label[-8:]
            d.text((X, Y + CONTACT_CELL + 1), label, fill=(230, 230, 120))
        sheet.save(self.out / "contact-sheet.png", optimize=True)


def summarize(records: list[dict]) -> str:
    out = []
    for key, bins in (("size_bin", [b for b, _, _ in SIZE_BINS]), ("palette_bin", [b for b, _, _ in PALETTE_BINS])):
        c = {b: 0 for b in bins}
        for r in records:
            c[r[key]] += 1
        out.append(f"{key}: {c}")
    g: dict[str, int] = {}
    t: dict[str, int] = {}
    for r in records:
        g[r["genre"]] = g.get(r["genre"], 0) + 1
        for tag in r["tags"]:
            t[tag] = t.get(tag, 0) + 1
    out.append(f"genre: {dict(sorted(g.items()))}")
    out.append(f"tags: {dict(sorted(t.items()))}")
    pb = [b for b, _, _ in PALETTE_BINS]
    out.append("size x palette: " + " ".join(f"{b:>6}" for b in pb))
    for s, _, _ in SIZE_BINS:
        row = [sum(1 for r in records if r["size_bin"] == s and r["palette_bin"] == b) for b in pb]
        out.append(f"  {s:>12}: " + " ".join(f"{v:>6}" for v in row))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scout", type=Path, default=DEFAULT_SCOUT)
    ap.add_argument("--dcss", type=Path, default=DEFAULT_DCSS)
    ap.add_argument("--game1x", type=Path, default=DEFAULT_GAME1X)
    ap.add_argument("--buch-rpg", type=Path, default=DEFAULT_BUCH_RPG)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    roots = {"scout": args.scout, "dcss": args.dcss, "game1x": args.game1x, "buch_rpg": args.buch_rpg}
    b = Builder(roots, args.out)
    b.build(recipes())
    print(f"images: {len(b.records)}")
    print(summarize(b.records))
    if b.rejected:
        print("rejected:")
        for id_, why in b.rejected:
            print(f"  {id_}: {why}")
    total = sum((args.out / r["file"]).stat().st_size for r in b.records)
    print(f"total image bytes: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
