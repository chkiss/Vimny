#!/usr/bin/env python3
# Vimny — a Vim-teaching dungeon crawler.
# Copyright (C) 2026 Chas Kissick
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Generate art/vocab_plain.txt and art/vocab_mixed.txt.

The division is FUNCTIONAL, keyed to the engine's word-class rule
(engine.motion._is_word_char — Vim's utf_class, under which the entire
untypable symbol set below is PUNCTUATION: vim's {0x20a0,0x27ff} "all kinds
of symbols" range):

Plain:  typable characters only, and each token is a SINGLE w-word — no
        internal word-class break, so w/b/e treat it exactly like W/B/E do.
Mixed:  every token carries an untypable symbol and/or an internal w/b/e word
        break (typable punctuation like ':' or '^' breaks too — ':map' lives
        here, not in plain). Words are CRAFTED with semantic meaning, not
        mechanical prefix+symbol.
"""
import pathlib
import sys
from collections import defaultdict

BASE = pathlib.Path(__file__).parent
sys.path.insert(0, str(BASE.parent))
from engine.motion import _is_word_char   # the single source of word-class truth


def _has_word_break(w: str) -> bool:
    """True if w/b/e split the token into more than one sub-word — i.e. the
    word-char class flips anywhere inside it. All the untypable symbols here
    are punctuation in vim, so a symbol next to a letter flips the class; an
    adjacent symbol RUN ('♠♥♦') stays one punctuation word (no flip)."""
    return any(_is_word_char(a) != _is_word_char(b) for a, b in zip(w, w[1:]))

# ── Untypable char sets ──────────────────────────────────────────────────────
_ORIG  = '∘·◦§‽°¶†‡⁂≃≈∞∴⌘'
_SUPP  = '☆☘☤☥☩☶☷☼☽☾☿♀♁♂♃♄♅♆♇♔♕♖♗♘♙♚♛♜♝♞♟♠♡♢♣♤♥♦♧♩♪♫♬♭♮♯♺♻⚀⚁⚂⚃⚄⚅⚆⚇⚈⚉⚊⚋⚌⚍⚎⚏⚐⚑⚒⚙⚜⚝⚞⚟⚛⛤⛥⛦⛧'
ALL_U  = _ORIG + _SUPP          # 92 chars
U_SET  = set(ALL_U)

# ── Plain vocabulary ─────────────────────────────────────────────────────────
VOCAB = """
vim cmd esc del ins buf tab set map let var reg :wq wbe WBE hjk jkl 3dd 5yy
str dex int wis cha lv1 lv2 lv3 hp0 xp2 ac5 mp3 sp1 con luk def atk res
axe bow orb gem key rod elf orc imp bat rat fog pit war rog wiz die hit win
den ore ice ash oak ivy dew fen zen bog fir gnu hop ink jab keg nib oar pew
rye tor urn vow wax yew jay koi foe dun elm dam cav hex
bin bit asm ram rom cpu gpu ptr nil err sys log lib raw dat obj exe pkt eof
nop ack syn sub can etx tty dev mux css php sql lua bbs crt vdu bcd udp tcp
ftp irc mac lan wan vpn dns pop uri xml jmp xor seg irq dma alu fpu mmu pll
adc dac pwm i2c spi usb pci agp ide ata nas nfs cps fps khz mhz ghz sgr
csi osi rpm hub rgb led lcd lut dpi ppi hsl hsv yuv ycc gcr mfm clv cav
dsp pcm pwm fsk psk qam v90 v92 rj11 bel dsdd
e^x x^2 a+b i++ n-1 0x0 x=y a&b x|y
age ago aid aim air ale ant apt arc arm art ask aye bay bed big boy bud bus
buy cab cap cue cup cut dry due ear eat eve eye few fit fly fur gap gel get
god had ham hat hay hen him hog hue hum ill ion ire jar jaw jet joy jug kin
kit lad lag lap law lay led leg lie lip lit lot low lug mad mar mat mob mod
mud mug net new nor nun odd off old opt our out owl own pad pan pat pay pen
pet pin pod pot pro pub pun pup put ran rap ray rib rid rip row rub rum sag
sap saw say sea shy sin sir ski sky sly spa spy sue sum sun tan tap tar tax
tea ten tin tip toe ton top toy tub tug two van via wag wed wet who why wig
wit woe won woo yam yap yea yet red grn blu dim

hjkl nvim word line char buff edit norm undo redo mark jump fold :set :map
:cmd :let rune void cave maze room door boss mage wand helm robe ring warp
loot gold hero slay kill trap dark glow burn smit ruin lore bane dusk dawn
mist gale vale mere mire cove bard monk sage seer fist hilt bolt pike club
mace dart raid lair keep glen dale ford bool uint long enum node goto null
true dump lore ruin bane
byte flag addr heap mmap fork exec pipe read seek stat load call push pull
hash sort grep find curl wget ping tmux baud code core data disk dump fast
gate halt idle init kern loop mode open poke peek page port scan skip uart
vram zero echo font mono cyan free path link list tree root base rate size
type name test unit time step axis rows cols mask bits vals keys
tube beam grid yoke iron lamp neon dial knob bios fifo dram sram sata swap
term ansi vt52 grab send recv wait poll sync lock cond dsdd dsed fsck qpsk
v34 bell pstn voip isdn adsl vdsl hdsl hayes rj11 head hub shutter sector
track media motor notch index
0xFF 0b10 3.14 i+=1 e^pi 2^10 pi*r
cyan gray teal lime navy ruby rose aqua buff ecru fawn jade plum wine
bark bone clay dune fern gust haze hill kelp lava moss moor palm peat pond
reef rock rust salt sand silk snow soil stem tide twig vine wave wood worm
yarn alba aloe burl coil damp dike drip drop dust eddy fang fell floe foam
fume gore grit gulf hive hoar hull husk iris isle junk keel loam loom lure
marl moat nook opal rime ruts scud seam silt slag sloe smog snag spar spec
spew spur stag stud tarn thaw tilt toll torc tuft vane veil veld vole weir
weld welt wend wold yore yurt zeal zone
able away back born came city days done each even fill give gone good half
hand hard have here high hold home hope idea into just keep kind know last
late left less like live look lose made make many mean more most move must
near need next nice nine none note once only past plan play real rich rise
road role rule runs same save self show side sign slow some soon stay such
sure take talk tell then they thin told took town turn upon used very view
walk want ways well went what when whom wide will with work year your

nmode imode vmode xmode count macro regex :help q:cmd %goto ]next [prev
:tabn :tabp :vspl :hspl 5hjkl :next :prev :edit
sword staff rogue quest magic spell blade cloak vault crypt golem troll
gnome druid witch curse bless smite charm valor guard chest tower lance
realm steed grail ember shade storm raven wight fleet
bytes flags stack queue table cache alloc deref scanf chmod mkdir rmdir
print sleep yield break const while catch throw tuple union async await
store fetch parse build spawn dodge false array slice range match
inode ioctl epoll mutex uname semop debug erase flush trace
blink blank frame modem audio video cable drive laser light power reset
clock pulse pixel amber ivory slate glyph codec retro serif ascii ochre
sepia taupe
birch cedar clove coral crane delta drain eagle fence finch fjord flame
flint flume forge frost gorge grove hedge heron holly ledge lemon maple
marsh notch petal plume prism ridge robin rocky runic shell shale shrub
shore spore spray sprig stone swamp swirl thorn thyme tidal tiger trout
trunk tulip vapor vigil viola viper vista vixen wedge whale wheat wrath
wreck yacht
e=mc2 x^2+1 i+=10
about above abuse actor acute admit adopt adult after again agent agree
ahead alarm album alert alias align alley allow alone along alter ample
anger angle annex apply ardor aroma arrow arson atlas atone audit augur
aural avian awash axiom azure basic batch beach bench biome birth black
blast blaze bleed bliss block blood blown board bonus booth bound brave
bread breed brisk brood brush brute buddy bugle bulge bully burst cabin
camel cargo carry carve chain chalk chaos chasm cheap check chess child
chill civic claim clamp clash class clasp clean clear clerk click cliff
cling cloud clump coast comet could crash crawl creak creek creep crisp
cross crowd crown cruel crush curve daily dance death decoy depot depth
digit dirty ditch dizzy doubt downy drake drawn dream dress drift drive
drone drown dusky dusty dwarf dying earth eight elite enact enjoy enter
envoy equip error evade evoke exact exert exile fable facet fairy faith
fancy fatal feast fever fiber fifth fight final first fixed flaky flare
flash flask flock flood floor fluid fully fungi funny fuzzy gamma gauze
ghoul giant giddy given gizmo glaze gloom gloss grasp gravy graze greed
greet grind grimy groan gross gruel gruff guise gulch gusto hasty haunt
haven heavy heist hinge hoist honor hotel hover humid hurry husky igloo
inane incur ingot inlay inset inter intro ionic irate itchy jazzy jerky
jolly joust jumpy juror kneel knife knock knoll known laden lanky large
latch later leafy leaky leapt legal liner liver lodge logic lower lucky
lumpy lusty lying magic manly manor march marry mealy medic merry messy
might miner minty mirth mixed moody moral mound mount mourn muddy murky
musty muted naive nasty nerve never newly nexus night nippy noble noisy
north noted novel nymph oaken often onset order outdo oxide paint panic
pause peace penal perch perky petty phase pithy plaid plain plane plant
plaza pluck plumb plump polar poppy pouty press price pride prime privy
probe prone proof proud proxy psalm pudgy pulse punky purse pushy pygmy
queen query quick quiet quirk quota quote rainy rally reach ready rebel
recap refer reign relax remix renew repay repel rerun revel risky ritzy
rivet rowdy royal rugby ruler rusty sadly saint savvy scald scalp scamp
scant scare scarf scary scene scone scoop scope scorn scout scowl scram
scrap screw scrub seedy serve seven shack shaft shake shall shank sharp
shear shelf shift shine shirt shock shone shook shoot short shout shove
shown shrug shunt sigma sinew sixth sixty skier skimp skirt slant slash
sleek sleet slick slide slink slope slosh slump smack small smear smell
smelt smirk smoke snaky snare sneak snore snort solar sooty sorry south
spade spare spark spasm speak speck speed spend spice spill spine spite
splat split spoke spook spoon squat squid stale stall stand stark start
state steam steel steep steer stern stick stiff sting stock stoic stomp
stout stray strip strum stuck study stump stung style suave sugar sunny
super surge swear sweep sweet swept swirl swoon swoop syrup tabby tacky
taffy tally tangy taste taunt tense tenth thick thief thing think third
those three threw thrum thumb tiger tilde timid tired title today token
tonal tonic topaz torch total touch toxic trace track trade trail train
trait tramp trash tread trend trick tried truly trust tunic turbo twist
typed ultra uncut under undue unfit unify unite untie unwed upper upset
urban usher vague valid value valve vigil vital vivid vocal voice vouch

normal insert visual escape buffer window splits motion search global
goblin wizard potion shadow portal knight archer shield scroll undead
dragon ranger zombie wraith cursed ghosts giants cleric thieve amulet
locket miasma quests swords staves thrall lurker raptor mortar blight
famine plague reaper squire valley cavern forest tundra summit desert
slayer hunter magick rafter vexing
struct thread socket malloc printf sizeof return static extern inline
kernel signal string vector matrix lambda object module import export
public hidden method packet header footer filter stream config option
parser cursor indent syntax screen pixels serial
raster bitmap mosaic glitch strobe ceefax oracle triode photon sector
analog cosine divide decade duplex ferric parity pinout platen stereo
indigo violet maroon sienna bisque salmon cobalt
e=mc^2 0xDEAD 0xBEEF 2^16-1 pi*r^2 f(x,y) a[n-1] i+=100
acacia aurora basalt carbon cirrus clover cobble cinder cactus canopy
canyon coarse candle cellar chilly cotton dagger damsel debris decade
domain donjon fallow feline fennel fickle flinty floret flurry fogged
frigid frosty frozen funnel galley garnet garble harbor icecap ignite
impure impish inland jungle kennel lagoon lavish lichen limber linden
lintel mantle marble marrow meadow mellow menace midday nettle nickel
nimbus obsess pallor pamper pampas parcel pardon patter pebble pennon
perish pewter pinion plaque plasma plinth podium quartz quiver radish
ravine recess reflex relish remote render rescue reveal ribbon riddle
ripple ritual robust rocket rosary rotate rubble russet sallow samite
savage scanty scarce scorch scruff sentry serene settle simmer sizzle
sliver smudge sombre soothe sorrel sprout spurge squash stanza tallow
tangle tartan tatter tendon thatch tidbit timber tinder tinker tissue
toggle tonsil toucan tousle trance tunnel triode vacuum valour velvet
vermin vertex warden wicker wiggle willow wither woolen yonder
asleep battle before behind beyond bright bundle butter button camper
castle center change charge choice clover corner damage dancer danger
ending fallen family famous figure finger flower follow formal garden
gentle happen hardly honest island keeper launch leader leaves listen
little lively longer maiden manner master mirror motion moving nature
nearly number object obtain occupy office opaque origin palace parent
parish partly patent people pepper pillar pillow pirate police policy
prefer pretty prince profit proven purple puzzle rather really reason
rebels remedy repeat retire review revive rising roller saddle seldom
sender simple singly sister slowly social stable stated stolen street
strong submit subtle sudden summer supply tackle talent temple tender
theory thrill titled travel tribal trophy trying twelve unless useful
victim virtue vision volume wander warmth weapon wealth weekly weight
widely winter within wonder worthy yearly

command mapping folding marking jumping :normal :global :visual replace
pattern forward dungeon goblins wizards potions shadows portals knights
archers shields scrolls warrior warlock paladin fighter phantom specter
vampire crawler ancient verdant monster blessed descent lurking slaying
healing binding casting burning glowing walking passage chamber hallway
doorway pathway sanctum citadel undying obscure eclipse sorcery alchemy
entropy discord archery destiny empires legends horrors abyssal haunted
twisted cursing wailing howling ravaged malware rootkit sandbox darkens
seeping looting
netcode latency timeout bitrate payload hashing looping pointer integer
boolean typedef include routine compile runtime process segment console
monitor display desktop classic vintage charset network
cathode refresh scanout flicker silicon alumina ferrite ceramic crystal
lattice quantum tritium
bramble cascade circuit compost compass contour coppice cordage cottage
crevice crimson diorama dolphin doppler drapery dredger drizzle erosion
estuary fissure flannel flatten flutter foghorn forbear foxtrot freckle
fresnel garland habitat harvest hemlock hessian hexagon hickory iceberg
impasse ingress inkblot juniper justice keyhole kingdom lamprey lantern
monarch monsoon moonbow niobium nitride nucleus nullify obelisk paddock
pasture pelican pendant pennant perform persist rampart ravager redwood
reflect regency remnant reserve residue respite restart restore sawdust
scarlet scuttle sequoia serpent shelter shimmer taffeta tankard taproot
tendril terrace texture thistle topsail topsoil torrent trestle
triceps triplet ululate umbrage uniform unravel unusual vagrant valiant
walkway warpath welding wetland willowy
another arrange artisan balance between cabinet capable captain careful
certain chapter citizen collect compact concept conduct confirm connect
content control correct counsel counter culture curtain drawing durable
eastern edition elected element embrace emotion empower enabled enforce
engaged enhance essence evident examine example exposed faction failure
fashion finance foreign fortune freight further general granted greatly
harvest highest holding however imagine kingdom learned message natural
nothing observe officer opening origins outcome outside overall percent
perfect picture planned plastic popular portion premise present problem
proceed produce program protect provide purpose quality quietly reality
realize receive reforms refused related release remains request require
reserve resolve respond restore results retired returns seeking service
setting several sharing showing similar soldier someone somehow sources
special student subject suppose surface sustain symbols teacher telling
thought through tonight towards traffic trouble turning usually valence
version village visible virtual waiting warning watched weapons welcome
whereas whether willing without working writing

keyboard operator function variable template overload callback register
iterator movement :command dungeons darkness treasure monsters guardian
wanderer sorcerer skeleton crawlers phantoms specters blighted ravaging
haunting twisting warriors warlocks paladins fighters vampires pathways
chambers passages citadels wizardry enchants questlog bossroom voidgate
segfault deadlock heapfree stackptr nodelink linklist hashcode bytecode
compiled executed returned rootkits moonrise imported
terminal compiler debugger profiler readline scanline pipeline mainloop
gameloop userdata metadata datatype typecast bitshift codepage overflow
filesize filepath filename pathname hostname checksum compress encoding
decoding soulbind firebolt iceshock darkpool deepvoid irongate cavepath
mazepath lootroom warchest shifting swapping dropping skipping spawning
deleting scanning building
phosphor cathodes halftone scanrate pixelmap bitplane colormap dithered
baudrate bitdepth bootable cascaded checkbit datagram dialcode electron
ferrites firmware flatline flipflop flowcode hardwire hexdumps junction
loadaddr loadfile logfiles modulate textfile textline textmode textscan
unipolar wavefile waveform wordbank wordwrap zeropage zeroword
blizzard boulders brambles branches calculus cataract cisterns clavicle
cloister clusters crevices crossbow crumbled crystals dolomite drenched
dwelling emission encircle enthrall entrance envision feldspar fervency
filament flagrant flaxseed gargoyle glimmers glinting glistens hawthorn
ironwood latticed nitrogen nutshell obsidian oxidized pearlite quarried
rainfall rhyolite rockface sandbank sandfall sapphire sediment seawater
seashell tidepool timeworn volcanic
absolute accuracy acquired adjusted adoption advanced affinity analysis
announce aperture appeared approval argument assembly assigned assuming
attached attitude auditing automata balanced barracks baseline basement
behavior believed boundary building calendar captured carnival category
centered champion changing charging choosing circular clearing climbing
clothing collapse colonial combined commence compared compiled complete
composed conceals concepts concerns conclude conflict congress consider
consumed contains coverage creative criminal cultural currency cylinder
deadline declared defeated delivers demanded depicted designed detailed
directed directly disaster discover displays document domestic dominant
doubling drawings election embedded employed engaging entirely equation
excluded executor expanded exported explored extended external familiar
featured findings finished followed forensic formally fraction frequent
gathered generous globally governed granting greatest guidance handling
happened hardened honoring included incoming indicate instance intended
interact involved isolated launched learning licensed limiting location
majority measured membrane military minority mirrored modified monetary
mounting movement multiple national negative observed obtained occupied
official openings operated ordering outreach outlined overview overcome
overload patience peaceful personal platform pleasure position possibly
practice prepared prestige previous priority probable produced programs
proposed provides quantity received recently recovery reformed regarded
regiment removing reported requires reserved resigned response resulted
retained returned reviewed revision rewarded selected separate shortage
situated solution somewhat spending standard standing strategy students
switched taxation teaching thousand together tracking training transfer
treating ultimate unlikely updating utilized verified versions violated
l33t r00t h4ck d00m n00b h4x 3gg xp0 sp3 d3f
b055 v01d z3r0 s1n k1ll w1n g0ld r3d bl4 gr3
3l33t h4x0r k3rn3 d4rkn r00tk d3@d d0wn s3gf

d10 d12 d20 fey lich drow gnoll crit thac0 nat20 kobold abjure bugbear
cantrip tiefling halfling beholder illithid aasimar duergar evoke feat
xeroc yendor quagga medusa aquator centaur kestrel griffin
matu dilto sopic calfo lorto ninja bishop halito mogref katino manifo
zilwan bamatu dialko werdna trebor samurai madalto montino lomilwa
kadorto malikto dumapic mahalito makanito mamorlis
plato moria tutor talko avatar empire pedit5 airfight
w3m lynx http html https gopher elinks keymap bookmark
dorf urist dorfs magma moody siege titan embark zlevel lithic
migrant tantrum aquifer mcurist minecart fortress migrants
""".split()

# ── Build plain dict ─────────────────────────────────────────────────────────
# Typable tokens that SPLIT under w/b/e (':map', 'x^2+1', 'i++', …) are routed
# to the mixed file — plain holds single w-words only.
plain = defaultdict(list)
seen_plain = set()
BANNED = set('!○') | U_SET
MOVED_TO_MIXED = []
for w in VOCAB:
    if any(c in BANNED for c in w):
        continue
    n = len(w)
    if not (1 <= n <= 8) or w in seen_plain:
        continue
    seen_plain.add(w)
    if _has_word_break(w):
        MOVED_TO_MIXED.append(w)
    else:
        plain[n].append(w)

# ── CRAFTED mixed words ──────────────────────────────────────────────────────
# Symbols used:
#   ° degree, ♠♥♦♣♤♡♢♧ suits, ♔♕♖♗♘♙♚♛♜♝♞♟ chess
#   ⚀⚁⚂⚃⚄⚅ dice (1-6), ⚙ gear, ⚛ atom, ⚐⚑ flags
#   ☼☽☾ sun/moon, ☥☤ ankh/caduceus, ☘ shamrock
#   ⛤⛧ stars, ⚞⚟ brackets, ♻♺ recycle, ⚒ pick
#   ⚜ fleur-de-lis, ♂♀☿♄♃♅♆♇ planets
#   ♩♪♫♬♭♮♯ music, ∞∴≈≃ math, †‡ daggers
#   § section, ‽ interrobang, ¶ pilcrow, ⁂ asterism
#   ⌘ command, ∘·◦ bullets, ☆ star, ☩ cross, ☶☷ trigrams
#   ☤ caduceus, ♁ earth, ♇ pluto, ⚝ star, ⚞⚟ chevrons
#   ⚆⚇⚈⚉ circles, ⚊⚋⚌⚍⚎⚏ lines

# dice digit helpers (1-based)
D = ['', '⚀', '⚁', '⚂', '⚃', '⚄', '⚅']  # D[1]=⚀ .. D[6]=⚅

RAW_MIXED = []

def add(*words):
    for w in words:
        w = w.strip()
        if w and len(w) <= 8:
            RAW_MIXED.append(w)

# ── 1-char: individual untypable glyphs ──────────────────────────────────────
for c in ALL_U:
    add(c)

# ── 2-char ───────────────────────────────────────────────────────────────────
# Suits as pairs
add('♠♥', '♦♣', '♤♡', '♢♧', '♠♦', '♥♣')
# Chess pieces
add('♔K', 'K♔', 'Q♕', '♕Q', 'R♖', '♜R', 'B♗', '♞N', 'P♙', '♟p')
# Card shorthand: rank+suit
for rank in ['A','K','Q','J']:
    for suit in '♠♥♦♣':
        add(rank + suit)
# Dice pairs for famous numbers
add(D[6]+D[4], D[6]+D[6], D[1]+D[6])  # 64, 66, 16
add(D[2]+D[6], D[3]+D[2], D[4]+D[4])  # 26, 32, 44
# Degree shorts
add('0°', '1°', '2°', '3°', '4°', '5°', '6°', '7°', '8°', '9°')
# Planet symbols with letter
add('♂e', 'e♂', '♀e', 'e♀', '☿e', 'e☿', '♄e', '♃e')
# Musical notes
add('♩♪', '♪♫', '♫♬', '♩♫', '♩♬')
# Gear/atom
add('⚙v', 'v⚙', '⚛H', 'H⚛', '⚛e', 'e⚛')
# Sun/moon
add('☼°', '☽°', '☾°', '☼☽', '☽☾')
# Flags
add('⚐!', '⚑0', '0⚑', '⚑1', '1⚑')
# Brackets as word delimiters
add('⚞v', 'v⚟', '⚞g', 'g⚟', '⚞0', '0⚟')
# Math/logic
add('∞°', '∴§', '≈°', '∞∴', '∞≈', '†‡')
# Daggers
add('†+', '+†', '‡+', '+‡')
# Section/pilcrow/interrobang
add('§1', '1§', '¶1', '‽?', '?‽')
# Recycle/pick
add('♻0', '0♻', '⚒g', 'g⚒', '⚜g', 'g⚜')
# Shamrock
add('☘4', '4☘', '☘1', '☘+')
# Life
add('☥+', '+☥', '☤+', '+☤')
# Occult
add('⛤1', '⛧1', '⛤+', '⛧+')
# Ankh / cross
add('☥1', '1☥', '☩1', '1☩')
# Atomic number shorthands
add('⚛1', '⚛2', '⚛8', '⚛6', '⚛7')
# Orbits
add('∘1', '1∘', '·1', '1·', '◦1', '1◦')

# ── 3-char ───────────────────────────────────────────────────────────────────
# Four-suit combos  (3 suits = 3 chars)
add('♠♥♦', '♥♦♣', '♠♥♣', '♠♦♣', '♤♡♢', '♡♢♧', '♤♡♧')
# Card + rank: A♠K = "Ace of spades King"
for suit in '♠♥♦♣':
    for r1, r2 in [('A','K'), ('A','Q'), ('K','Q'), ('A','J'), ('K','J')]:
        w = r1 + suit + r2
        if len(w) == 3:
            add(w)
# Dice: famous 3-digit combos
add(D[2]+D[5]+D[6],   # 256
    D[2]+D[5]+D[5],   # 255
    D[6]+D[4]+D[6],   # 646
    D[1]+D[2]+D[8] if 8 <= 6 else '',  # skip
    D[1]+D[2]+D[4],   # 124
    D[1]+D[2]+D[8-2], # 126
    D[3]+D[2]+D[0] if 0 > 0 else '',   # skip
    )
add(D[6]+D[4]+'k',    # 64k
    D[6]+D[6]+'M',    # 66M
    D[2]+D[5]+D[6],   # 256
    D[2]+D[5]+D[5],   # 255
    D[1]+D[2]+D[8-6], # 122
    )
# Degree combos
add('90°', '45°', '30°', '60°', '15°', '72°', '36°', '18°')
add('0°C', '0°K', '0°F')
# Planet + element
add('Fe♂', '♂Fe', 'Cu♀', '♀Cu', 'Hg☿', '☿Hg', 'Pb♄', '♄Pb', 'Sn♃', '♃Sn')
# Sun/moon words
add('☼Au', 'Au☼', '☽Ag', 'Ag☽', '☾Pb', 'Pb☾')  # gold, silver, lead
add('☼°C', '☽°C', '☾°C')
# Music theory: key signatures
for note in ['A','B','C','D','E','F','G']:
    add(note + '♭', note + '♯')
# Music + text
add('sid♩', 'opl♩', '8♩t', '♩bpm')
# Gear + 2-char code words
add('⚙vm', '⚙io', '⚙os', 'vm⚙', 'io⚙', 'os⚙', 'gc⚙', '⚙gc')
# Atomic
add('⚛H2', 'H⚛2', '⚛U5', 'U⚛5', '⚛CO')
# Flags
add('⚐ok', 'ok⚐', '⚑ok', 'ok⚑', '⚑gg', 'gg⚑', '⚐gg', 'gg⚐')
add('err⚐', '⚑win', 'win⚑')
# Brackets
add('⚞ok⚟'[:3], '⚞gg', 'gg⚟', '⚞io', 'io⚟')
# Life
add('hp☥', '☥hp', 'mp☥', '☥mp', '☤hp', 'hp☤')
# Shamrock luck
add('☘hp', 'hp☘', '☘xp', 'xp☘', '☘luk')
# Occult
add('doom'[:3] + '⛧', '⛧vim', 'vim⛧', '⛤vim', 'vim⛤')
# Recycle code
add('gc♻', '♻gc', '♻rm', 'rm♻', '⚒ore', 'ore⚒')
# Fleur
add('⚜lv', 'lv⚜', '⚜xp', 'xp⚜')
# Math formulas
add('e∞π', 'π∞e', '∞+1', '1+∞', '∞-1', '∴+1')
# Interrobang / section / pilcrow
add('§42', '42§', '¶42', '‽hp', 'hp‽', '‽xp')
# Chess tactics (symbol embedded)
add('k♔g', 'k♚g', 'r♖k', 'b♗g', 'n♞g')
# Leet + single symbol
add('l33'+'†', '133'+'☥', 'r00'+'†', 'h4x'+'⚙')
# dice + letter
add(D[6]+D[4]+'k', D[6]+D[4]+'b', D[2]+D[5]+D[6])
# Bullet / dot notation
add('∘hp', 'hp∘', '·hp', 'hp·', '◦xp', 'xp◦')
# RPG dice notation
add('d'+D[4], 'd'+D[6], 'd'+D[3], 'd'+D[5])
add('1d'+D[6], '2d'+D[6], '3d'+D[6], '4d'+D[4])

# Themed 3-char vocab (D&D · Rogue · Wizardry · PLATO · Lynx · DF)
add('d♯0',   # d20 (twenty-sided die)
    '♔ac',   # AC (armor class) with king
    'dc⛧',   # D&D class + pentagram endpoint
    )

# ── 4-char ───────────────────────────────────────────────────────────────────
# All 4 suits
add('♠♥♦♣', '♤♡♢♧', '♠♡♦♧', '♤♥♢♣')
# Card hands
for suit in '♠♥♦♣':
    add('AK' + suit + 'Q', 'A' + suit + 'KQ')
# Degree temps
add('100°', '180°', '360°', '273°', '451°', '-40°', '37°C', '98°F',
    '-273°', '212°F')
# Planet alchemy
add('Fe=♂', '♂=Fe', 'Cu=♀', '♀=Cu', 'Hg=☿', '☿=Hg', 'Pb=♄', 'Sn=♃')
add('♄ring', '♂war', '♀gem', '☿spd')
# Music
add('A♭7', 'B♭m', 'C♯m', 'F♯m', 'A♭m', 'G♯m', 'D♭m', 'E♭m')
add('♩=60', '♩120', '440♩', 'sid♩4')
# Leet + symbol (4 chars)
add('l33t'[:3]+'†',  # l33†
    '133☥',          # 4 chars
    'r00t'[:3]+'♛',  # r00♛
    'd00m'[:3]+'♚',  # d00♚
    'n00b'[:3]+'♟',  # n00♟
    'h4ck'[:3]+'⚙',  # h4c⚙
    'b055'[:3]+'♚',  # b05♚
    'v01d'[:3]+'⛧',  # v01⛧
    )
# Dice famous numbers
add(D[2]+D[5]+D[6]+'k',   # 256k
    D[6]+D[4]+'kb',        # 64kb
    D[6]+D[4]+'mb',        # 64mb
    D[6]+D[6]+'mhz'[:2],   # 66mh
    D[1]+D[2]+D[8-6]+'k',  # 122k -- skip if >8
    '2d'+D[6]+D[6],        # 2d66
    D[6]+D[6]+D[6]+'=',    # 666=
    )
# Gear code terms
add('⚙vim', 'vim⚙', '⚙gcc', 'gcc⚙', '⚙cpu', 'cpu⚙', '⚙sys', 'sys⚙',
    'kern⚙', 'make⚙', 'fork⚙', 'pipe⚙', 'proc⚙', '⚙kern', '⚙make',
    '⚙pipe')
# Atomic physics
add('⚛fus', 'fus⚛', '⚛E=m', 'U235⚛'[:4])
# Flags (win, err, done)
add('win⚑', '⚑win', 'err⚐', '⚐err', 'halt⚑', 'done⚑', 'r00t⚑')
# Brackets
add('⚞ok⚟', '⚞gg⚟', '⚞io⚟', '⚞π⚟')
# Sun/moon
add('☼gold'[:4], 'gold☼'[:4], '☽luna', 'luna☽', '☾dark', 'dark☾',
    '☼dawn', 'dawn☼', '☽dusk', 'dusk☽')
# Life/heal
add('hp☥4', '☥hp4', '☤heal'[:4], 'heal☤'[:4], 'life☥'[:4], '☥life'[:4])
# Shamrock
add('☘luck', 'luck☘', '☘gold', 'gold☘', '☘crit', 'crit☘')
# Occult
add('boss⛧', 'doom⛧', 'void⛧', 'dark⛧', 'evil⛧')
# Recycle
add('gc♻2', '♻buf', 'buf♻', '♺ram', 'ram♺', '♻bin', 'bin♻')
# Mining
add('⚒ore', 'ore⚒', '⚒mine', '⚒gold', '⚒rock')
# Fleur guild
add('⚜lv9', '⚜rank', 'rank⚜', 'gild⚜', '⚜gild')
# Chess words (symbol inside word)
add('k♥ng', 'k♣ng', 'k♦ng', 'k♠ng',   # king with suit
    'q♣en', 'q♥en', 'q♠en', 'q♦en',   # queen short
    'b♝sh', 'r♜ok', 'kn♞t')            # bishop, rook, knight
# Physics formulas
add('F=ma', 'E=hf', 'mc^2', 'baud'+'☿'[:0])  # plain formula, no sym here
add('F♂ma', 'E♩hf', '☼mc2', 'bau☿', 'MHz☿')  # with symbols
# Music + retro chip
add('sid♩', 'opl♩', '8bt♩', 'chp♩', 'mdl♩')
# Math
add('∞+∞', '∞*2', '2*∞', '∴+∞', '∞=∞', '≈∞+', '+∞≈')
# Section marker
add('§hp4', '§xp4', '§lv4', '4§hp', '4§lv')
# Leet deeper
add('3l3t', 'h4x0', 'k3rn', 'l33†', 'r00†')
# Bullet sequences
add('∘∘∘∘', '····', '◦◦◦◦', '∘·◦·')

# Themed 4-char vocab (D&D · Rogue · Wizardry · PLATO · Lynx · DF)
add('h††p',   # http (both t's → † ✓)
    'dnd⛧',   # D&D + pentagram endpoint
    'fey†',   # D&D fey + dagger endpoint
    'fey⛧',   # D&D fey + pentagram
    'orc⛧',   # D&D orc + pentagram
    'kes†',   # Rogue kestrel truncated + dagger
    'hal†',   # Wizardry halito truncated + dagger
    'lor†',   # Wizardry lorto truncated + dagger
    'dil†',   # Wizardry dilto truncated + dagger
    'nat†',   # D&D nat + dagger endpoint
    'w3m☾',   # Lynx w3m browser + crescent
    )

# ── 5-char ───────────────────────────────────────────────────────────────────
# Leet + symbol (5 chars)
add('l33t†',    # 5: l33t+dagger
    '133☥7',    # 133 ankh 7
    '1337♔',    # leet + white king
    'r00t♛',    # root + black queen
    'd00m♚',    # doom + black king
    'n00b♟',    # noob + pawn
    'h4ck⚙',    # hack + gear
    'b055♚',    # boss + black king
    'v01d⛧',    # void + pentagram
    'h4x0r'[:4]+'♕',  # h4x0+queen
    '3l33t'[:4]+'♔',  # 3l33+king
    'k3rn3'[:4]+'⚙',  # k3rn+gear
    'd4rk☾',    # dark + crescent
    'd3@d♠',    # dead + spade
    's3gf♯',    # segf + sharp
    )
# Degree temps (5 chars)
add('37°C', '100°C'[:5], '273°K'[:5], '451°F'[:5], '-40°C'[:5],
    '98.6°'[:5], '180°C'[:5], '360°C'[:5])
# Four suits (4) + rank letter
add('♠♥♦♣A', '♠♥♦♣K', '♠♥♦♣Q', '♠♥♦♣J')
# Chess word embedding
add('kn♞ght',   # knight — ♞ replaces 'i'
    'b♝shop',   # bishop — ♝ replaces 'i'
    'f♟rk2',    # fork (chess tactic)
    )
# Dice combos (5)
add(D[2]+D[5]+D[6]+'kb',   # 256kb
    D[6]+D[4]+'kbp',       # 64kbp
    D[6]+D[6]+'mhz',       # 66mhz
    D[1]+D[2]+D[8-6]+'kh', # skip >5
    '2d'+D[6]+D[6]+'p',    # 2d66p
    D[6]+D[6]+D[6]+'=6',   # 666=6
    D[6]+D[4]+'bit',       # 64bit
    D[6]+D[4]+'bps',       # 64bps
    D[2]+D[5]+D[6]+'b',    # 256b
    )
# Planet alchemy (5)
add('♄ring', '♂wars', '♀gems', '☿+spd', 'Fe=♂2', 'Hg=☿2',
    '☿=Hg2', '♃=Sn2', '♄=Pb2')
# Music (5)
add('♩=120', '♩=60i', '440♩A', '4/4♩', '3/4♩', '6/8♩',
    'sid♩4', 'opl♩4', '8bit♩', 'chip♩', 'midi♩')
# Gear/code (5)
add('⚙kern', 'kern⚙', '⚙proc', 'proc⚙', '⚙make', 'make⚙',
    '⚙fork', 'fork⚙', '⚙pipe', 'pipe⚙', 'cpu+⚙', '⚙+cpu')
# Atomic (5)
add('⚛bomb', 'bomb⚛', '⚛fuse', 'fuse⚛', 'H⚛ium', 'U⚛235'[:5],
    'e=m⚛2', '⚛e=mc')
# Brackets (5)
add('⚞ok⚟5', '⚞gg⚟5', '⚞err⚟', '⚞vim⚟', '⚞io⚟5')
# Sun/moon (5)
add('☼gold', 'gold☼', '☽luna', 'luna☽', '☾tomb', 'tomb☾',
    '☼dawn', 'dawn☼', '☽dusk', 'dusk☽', '☽silv')
# Life (5)
add('☥heal', 'heal☥', '☤heal', 'heal☤', '☥life', 'life☥',
    '☥hp+5', '☤hp+5', 'hp+5☥', 'hp+5☤')
# Shamrock (5)
add('☘luck', 'luck☘', '☘gold', 'gold☘', '☘crit', 'crit☘',
    '☘luk5', '☘xp+5')
# Occult (5)
add('boss⛧', 'doom⛧', 'void⛧', 'dark⛧', 'evil⛧', 'chaos'[:4]+'⛧',
    '⛧boss', '⛧doom', '⛧void', '⛧dark')
# Recycle (5)
add('gc+♻', '♻buf5', 'buf5♻', '♺ram5', 'ram5♺', '♻bin5', '♻heap')
# Mining (5)
add('⚒ore5', '⚒mine', 'mine⚒', '⚒gold', 'gold⚒', '⚒rock', 'rock⚒')
# Fleur (5)
add('⚜rank', 'rank⚜', '⚜ques', 'ques⚜', '⚜roya', 'roya⚜',
    '⚜gild', 'gild⚜')
# Formulas (5)
add('F=ma♂', 'E=hf♩', 'mc^2☼', 'baud☿', 'MHz☿5', 'kbps☿',
    '♂=mav', '♩=hfv')
# Math (5)
add('∞+∞=∞', '2x∞+1', '∴∞+∞', '∞≈∞+1'[:5])
# Section / pilcrow (5)
add('§lv99', 'lv99§', '§hp99', 'hp99§', '§xp99', 'xp99§')
# Leet tech (5)
add('0v3rf', 'sc4nf', 'd3@dl', 's3gf4', 'k3rn3', 'l1nkl', 'h34pl')
# Card suits word-embedded (5)

# Themed 5-char vocab (D&D · Rogue · Wizardry · PLATO · Lynx · DF)
add('lich†',   # D&D lich + dagger endpoint (undead)
    'pla†o',   # PLATO system (†=t ✓)
    'dorf⚒',   # DF dorf + pickaxe endpoint
    'dal†o',   # Wizardry dalto (†=t ✓)
    'h††ps',   # https (both t's → † ✓)
    'gnol⛧',   # D&D gnoll truncated + pentagram
    'nat♯0',   # nat20 with sharp (♯ for 2)
    'thac†',   # thac0 + dagger endpoint
    'uris†',   # DF urist (†=t endpoint ✓)
    'drow☾',   # D&D drow + crescent (dark elf)
    'crit⚅',   # D&D crit + die face endpoint
    'matu§',   # Wizardry matu + section endpoint
    'http⚙',   # http + gear endpoint
    'lynx☾',   # Lynx browser + crescent
    'mori⛧',   # Rogue moria truncated + pentagram
    )

# ── 6-char ───────────────────────────────────────────────────────────────────
# Leet (6)
add('l33t♔k', 'l33t♔q', '1337♔6',
    'r00t♛6', 'd00m♚6', 'n00b♟6',
    'h4ck⚙6', 'b055♚6', 'v01d⛧6',
    '3l33t♔', 'h4x0r♕', 'k3rn3l'[:5]+'⚙',
    'd4rk☾6', 'd3@dl♠', '0v3rfl'[:5]+'♟',
    's3gf4l'[:5]+'†',
    )
# Degree (6)
add('37.5°C', '98.6°F', '273.1°', '-273°K', '100.0°', '451.0°', '180.0°')
# Planet (6)
add('♄rings', '♂+wars', '♀+gems', 'Fe=♂+2', '☿Hg+sp',
    'Hg=☿+2', '♃Sn+ti', '♄Pb+le')
# Music (6)
add('♩=120s', '♩=60bp', '440♩Hz', '4/4♩m', '3/4♩m',
    'sid♩64', 'opl♩ad', '8bit♩6', 'chip♩6', 'midi♩6',
    'A♭maj6', 'B♭min6', 'C♯maj6', 'F♯min6')
# Gear (6)
add('⚙+kern', 'kern+⚙', '⚙+proc', 'proc+⚙', '⚙+make',
    'kern+⚙', '⚙+fork', 'fork+⚙', '⚙+pipe', 'pipe+⚙',
    '⚙+mmap', 'mmap+⚙', '⚙+heap', 'heap+⚙')
# Chess words (6)
add('kn♞ght', 'kni♞ht', 'b♝shop', 'bi♝hop',
    'cast♖e', 'cast♜e',
    )
# Dice (6)
add(D[2]+D[5]+D[6]+'kbp',  # 256kbp
    D[6]+D[4]+'kbps',      # 64kbps
    D[6]+D[6]+'mhz6',      # 66mhz6
    D[6]+D[4]+'bit6',      # 64bit6
    D[2]+D[5]+D[6]+'mb',   # 256mb
    D[6]+D[4]+'mb+6',      # 64mb+6
    '2d'+D[6]+D[6]+'p6',   # 2d66p6
    D[6]+D[6]+D[6]+'max',  # 666max
    D[6]+D[6]+D[6]+'=18',  # 666=18
    )
# Atomic (6)
add('⚛bomb6', 'bomb6⚛', '⚛fuse6', '⚛e=mc2', 'e=m⚛c2', 'H⚛ium6',
    '⚛chain', 'chain⚛', '⚛split', 'split⚛')
# Sun/moon (6)
add('☼gold6', '☽luna6', '☾tomb6', '☼dawn6', '☽dusk6',
    '☽silv6', '☾night', 'night☾', '☼light', 'light☼')
# Life (6)
add('☥heal6', '☤heal6', '☥life6', 'heal☥6', 'life☥6',
    '☥potn', 'potn☥', '☤potn', 'potn☤',
    '☥scrll'[:6], '☤scrll'[:6])
# Shamrock (6)
add('☘luck6', '☘gold6', '☘crit6', '☘loot6',
    'lucky☘', 'goldy☘', 'crits☘', 'loots☘')
# Occult (6)
add('boss⛧6', 'doom⛧6', 'void⛧6', 'dark⛧6', 'evil⛧6',
    'chaos⛧', '⛧chaos', '⛧bossd', '⛤altar', 'altar⛤')
# Recycle (6)
add('gc♻buf', '♻heap6', 'heap♻6', '♺ram+6', 'ram+♺6',
    '♻alloc', 'alloc♻', '♺stack', 'stack♺')
# Mining (6)
add('⚒mine6', 'mine⚒6', '⚒gold6', 'gold⚒6', '⚒ore+6',
    '⚒forge', 'forge⚒', '⚒craft', 'craft⚒')
# Fleur (6)
add('⚜rank6', 'rank⚜6', '⚜quest', 'quest⚜', '⚜royal', 'royal⚜',
    '⚜guild', 'guild⚜', '⚜valor', 'valor⚜')
# Formulas (6)
add('F=ma♂6', 'E=hf♩6', 'mc^2☼6', 'baud☿6', 'MHz☿6k', 'kbps☿6',
    'F♂=ma6', '♩=hfv6', 'E♩=hf6', '☼e=mc2')
# Brackets (6)
add('⚞vim⚟', '⚞err⚟', '⚞gg6⚟', '⚞ok6⚟',
    '⚞null⚟'[:6], '⚞nop⚟', '⚞eof⚟', '⚞buf⚟')
# Math (6)
add('∞+∞=∞6', '∞≈∞+∞6'[:6], '∴∞∴∞6k'[:6],
    '2^∞+16', 'e^∞+π6', 'π+∞=∞6'[:6])
# Section (6)
add('§lv999', 'lv999§', '§hp999', 'hp999§', '§xp999', 'xp999§')
# Leet tech (6)
add('0v3rfl', 'sc4nfl', 'd3@dl0', 's3gf4l', 'k3rn3l', 'l1nkls', 'h34pfl',
    'd3@dl+'+'†', 'r00tk+'+'♔')

# Themed 6-char vocab (D&D · Rogue · Wizardry · PLATO · Lynx · DF)
add('ava†ar',   # PLATO Avatar (†=t ✓)
    'titan⚒',   # DF titan + pickaxe endpoint
    'siege⛧',   # DF siege + pentagram endpoint
    'gnoll⛧',   # D&D gnoll + pentagram endpoint
    'moria⛧',   # Rogue moria + pentagram endpoint
    'tutor§',   # PLATO tutor language + section endpoint
    'talko§',   # PLATO Talkomatic + section endpoint
    'ninja†',   # Wizardry ninja + dagger endpoint
    'moody☽',   # DF moody dwarf + crescent endpoint
    'magma☼',   # DF magma + sun endpoint
    'thac0†',   # D&D thac0 + dagger endpoint
    'hali†o',   # Wizardry halito (†=t ✓)
    'ka†ino',   # Wizardry katino (†=t ✓)
    'pedi†5',   # PLATO pedit5 (†=t ✓)
    'werdn♛',   # Wizardry Werdna, queen at endpoint (boss)
    'li†hic',   # DF lithic (†=t ✓)
    'e♝inks',   # Lynx elinks (♝=l ✓)
    )

# ── 7-char ───────────────────────────────────────────────────────────────────
# Leet (7)
add('l33t♔k7', 'l33t♔q7', '1337♔k7',
    'r00t♛k7', 'd00m♚k7', 'h4ck⚙k7',
    'b055♚k7', 'v01d⛧k7', '3l33t♔7',
    'h4x0r♕7', 'k3rn3l⚙', 'd4rk☾k7',
    '0v3rfl♟', 's3gf4lt'[:6]+'†',
    'd3@dl0♠', 'r00tk1t'[:6]+'♔',
    )
# Degree (7)
add('37.0°C7', '98.6°F7', '273.15°'[:7], '-40.0°C'[:7], '100.0°C'[:7],
    '451.0°F'[:7], '-273.1°'[:7])
# Planet (7)
add('♄rings7', '♂+wars7', 'Fe=♂+27', '☿Hg+spd', 'Hg=☿+27',
    '♃Sn+tin', '♄Pb+led')
# Music (7)
add('♩=120bp', '440♩Hz7', 'sid♩647', 'opl♩ad7',
    '8bit♩h7', 'chip♩h7', 'midi♩h7',
    'A♭maj7k', 'B♭min7k', 'C♯maj7k')
# Gear (7)
add('⚙+kern7', 'kern+⚙7', '⚙+proc7', 'proc+⚙7',
    '⚙+mmap7', 'mmap+⚙7', '⚙+heap7', 'heap+⚙7',
    '⚙+fork7', 'fork+⚙7', '⚙+pipe7', 'pipe+⚙7')
# Chess (7)
add('kn♞ght7', 'b♝shop7', 'cast♖e7', 'cast♜e7',
    'kni♞ht7', 'bi♝hop7')
# Dice (7)
add(D[2]+D[5]+D[6]+'kbps',   # 256kbps = 7 chars
    D[6]+D[4]+'kbps7',        # 64kbps7
    D[6]+D[6]+'mhz7k',        # 66mhz7k
    D[6]+D[4]+'bit7k',        # 64bit7k
    D[2]+D[5]+D[6]+'mb+7',    # 256mb+7
    D[6]+D[6]+D[6]+'=max'[:4],# 666=max
    D[6]+D[6]+D[6]+'=18d',    # 666=18d = 7
    '2d'+D[6]+D[6]+'p7k',     # 2d66p7k
    )
# Atomic (7)
add('⚛bomb7k', '⚛fuse7k', '⚛e=mc27', 'e=m⚛c27',
    '⚛chain7', 'chain⚛7', '⚛split7', 'split⚛7',
    '⚛react7', 'react⚛7')
# Sun/moon (7)
add('☼gold7k', '☽luna7k', '☾night7', '☼light7',
    'night☾7', 'light☼7', '☽silv7k', '☾tomb7k',
    '☼alchemy'[:7], '☽silver7'[:7])
# Life (7)
add('☥heal7k', '☤heal7k', '☥life7k', 'heal☥7k',
    '☥potn7k', '☤potn7k', '☥scrll7'[:7], '☤scrll7'[:7],
    'scroll☥'[:7], 'potion☥'[:7])
# Shamrock (7)
add('☘luck7k', '☘gold7k', '☘crit7k', '☘loot7k',
    'lucky☘7', 'goldy☘7', 'crits☘7', 'loots☘7')
# Occult (7)
add('boss⛧7k', 'doom⛧7k', 'void⛧7k', 'dark⛧7k',
    'chaos⛧7', '⛧chaos7', '⛤altar7', 'altar⛤7',
    '⛧dungeon'[:7], '⛧sorcery'[:7])
# Recycle (7)
add('gc♻buf7', '♻heap7k', '♺ram+7k', '♻alloc7',
    'alloc♻7', '♺stack7', 'stack♺7', '♻malloc7'[:7])
# Mining (7)
add('⚒mine7k', '⚒gold7k', '⚒forge7', 'forge⚒7',
    '⚒craft7', 'craft⚒7', '⚒dungeon'[:7])
# Fleur (7)
add('⚜rank7k', '⚜quest7', 'quest⚜7', '⚜royal7',
    'royal⚜7', '⚜guild7', 'guild⚜7', '⚜valor7')
# Formulas (7)
add('F=ma♂7k', 'E=hf♩7k', 'mc^2☼7k', 'baud☿7k',
    'MHz☿7kh', 'kbps☿7k', '☼e=mc27', 'F♂=ma7k')
# Brackets (7)
add('⚞vim⚟7', '⚞null⚟7'[:7], '⚞nop⚟7', '⚞eof⚟7',
    '⚞buf⚟7', '⚞heap⚟7'[:7], '⚞proc⚟7'[:7])
# Math (7)
add('∞+∞=∞7k', '2^∞+167', 'e^∞+π7k', 'π*∞=∞7k'[:7])
# Section (7)
add('§lv9999', 'lv9999§', '§hp9999', 'hp9999§')
# Leet tech (7)
add('0v3rfl0w'[:7], 'd3@dl0ck'[:7], 's3gf4lt7', 'k3rn3l+⚙'[:7],
    'r00tk1t♔'[:7], 'h4x0r♕7k', '3l33t♔7k', 'n00b♟7k')

# Themed 7-char vocab (D&D · Rogue · Wizardry · PLATO · Lynx · DF)
add('can†rip',   # D&D cantrip (†=t ✓)
    'kes†rel',   # Rogue kestrel (†=t ✓)
    'madal†o',   # Wizardry madalto (†=t ✓)
    '†an†rum',   # DF tantrum (both t's → † ✓)
    'mcuris†',   # DF mcurist (†=t endpoint ✓)
    'cen†aur',   # Rogue centaur (†=t ✓)
    'aqua†or',   # Rogue aquator (†=t ✓)
    'kobold⛧',   # D&D kobold + pentagram endpoint
    'yendor⚜',   # Rogue Amulet of Yendor + fleur endpoint
    'werdna⛧',   # Wizardry Werdna + pentagram endpoint
    'trebor♔',   # Wizardry Trebor + king endpoint
    'halito†',   # Wizardry halito + dagger endpoint
    'mogref†',   # Wizardry mogref + dagger endpoint
    'zilwan♯',   # Wizardry zilwan + sharp endpoint
    'bishop§',   # Wizardry bishop class + section endpoint
    'avatar☥',   # PLATO Avatar + ankh endpoint
    'empire⛧',   # PLATO Empire + pentagram endpoint
    'pedit5†',   # PLATO pedit5 + dagger endpoint
    'gopher⚙',   # Lynx gopher protocol + gear endpoint
    'elinks☾',   # Lynx elinks + crescent endpoint
    'keymap§',   # Lynx keymap + section endpoint
    'embark⚒',   # DF embark + pickaxe endpoint
    'lithic†',   # DF lithic + dagger endpoint
    'zlevel⚒',   # DF z-level + pickaxe endpoint
    'medusa♛',   # Rogue medusa + queen endpoint
    )

# ── 8-char ───────────────────────────────────────────────────────────────────
# Leet (8)
add('l33t♔k8l', '1337♔k8l',
    'r00t♛k8l', 'd00m♚k8l', 'h4ck⚙k8l',
    'b055♚k8l', 'v01d⛧k8l', '3l33t♔8l',
    'h4x0r♕8l', 'k3rn3l⚙8'[:8], 'd4rk☾k8l',
    '0v3rfl0w'[:7]+'♟', 'd3@dl0ck'[:7]+'♠',
    's3gf4ult'[:7]+'†', 'r00tk1t♔'[:8-1]+'8',
    )
# Degree (8)
add('37.0°C8k', '98.6°F8k', '273.15°k'[:8], '-40.0°C8'[:8],
    '100.0°C8'[:8], '451.0°F8'[:8], '-273.15°'[:8])
# Planet (8)
add('♄rings8k', '♂+wars8k', 'Fe=♂+8k2', '☿Hg+spd8',
    'Hg=☿+8k2', '♃Sn+tin8', '♄Pb+led8', '♂Fe=war8')
# Music (8)
add('♩=120bpm'[:8], '440♩Hz8k', 'sid♩648k', 'opl♩ad8k',
    '8bit♩h8k', 'chip♩h8k', 'midi♩h8k',
    'A♭maj8kl', 'B♭min8kl', 'C♯maj8kl',
    '♩♪♫♬rune', 'rune♩♪♫♬'[:8])
# Gear (8)
add('⚙+kern8k', 'kern+⚙8k', '⚙+proc8k', 'proc+⚙8k',
    '⚙+mmap8k', 'mmap+⚙8k', '⚙+heap8k', 'heap+⚙8k',
    '⚙+fork8k', 'fork+⚙8k')
# Chess (8)
add('kn♞ght8k', 'b♝shop8k', 'cast♖e8k', 'cast♜e8k',
    'kni♞ht8k', 'bi♝hop8k')
# Dice (8)
add(D[2]+D[5]+D[6]+'kbps8',  # 256kbps8
    D[6]+D[4]+'kbps8k',      # 64kbps8k
    D[6]+D[6]+'mhz8kl',      # 66mhz8kl
    D[6]+D[4]+'bit8kl',      # 64bit8kl
    D[2]+D[5]+D[6]+'mb+8k',  # 256mb+8k
    D[6]+D[6]+D[6]+'=max8',  # 666=max8
    D[6]+D[6]+D[6]+'=18dx',  # 666=18dx
    '2d'+D[6]+D[6]+'p8kl',   # 2d66p8kl
    )
# Atomic (8)
add('⚛bomb8kl', '⚛fuse8kl', '⚛e=mc28l', 'e=m⚛c28l',
    '⚛chain8k', 'chain⚛8k', '⚛split8k', 'split⚛8k',
    '⚛react8k', 'react⚛8k')
# Sun/moon (8)
add('☼gold8kl', '☽luna8kl', '☾night8k', '☼light8k',
    'night☾8k', 'light☼8k', '☽silv8kl', '☾tomb8kl',
    '☽silver8'[:8], '☼alchemy'[:8])
# Life (8)
add('☥heal8kl', '☤heal8kl', '☥life8kl', 'heal☥8kl',
    '☥potn8kl', '☤potn8kl', 'scroll☥8'[:8], 'potion☥8'[:8])
# Shamrock (8)
add('☘luck8kl', '☘gold8kl', '☘crit8kl', '☘loot8kl',
    'lucky☘8k', 'goldy☘8k', 'crits☘8k', 'loots☘8k')
# Occult (8)
add('boss⛧8kl', 'doom⛧8kl', 'void⛧8kl', 'dark⛧8kl',
    'chaos⛧8k', '⛧chaos8k', '⛤altar8k', 'altar⛤8k',
    '⛧dungeon8'[:8], '⛧sorcery8'[:8])
# Recycle (8)
add('gc♻buf8k', '♻heap8kl', '♺ram+8kl', '♻alloc8k',
    'alloc♻8k', '♺stack8k', 'stack♺8k', '♻malloc8k'[:8])
# Mining (8)
add('⚒mine8kl', '⚒gold8kl', '⚒forge8k', 'forge⚒8k',
    '⚒craft8k', 'craft⚒8k', '⚒dungeon8'[:8])
# Fleur (8)
add('⚜rank8kl', '⚜quest8k', 'quest⚜8k', '⚜royal8k',
    'royal⚜8k', '⚜guild8k', 'guild⚜8k', '⚜valor8k')
# Formulas (8)
add('F=ma♂8kl', 'E=hf♩8kl', 'mc^2☼8kl', 'baud☿8kl',
    'MHz☿8khl', 'kbps☿8kl', '☼e=mc28k', 'F♂=ma8kl')
# Brackets (8)
add('⚞vim⚟8k', '⚞null⚟8k'[:8], '⚞heap⚟8k'[:8], '⚞proc⚟8k'[:8],
    '⚞kern⚟8k'[:8])
# Math (8)
add('∞+∞=∞8kl', '2^∞+168k', 'e^∞+π8kl', 'π*∞=∞8kl'[:8])
# Section (8)
add('§lv99999', 'lv99999§', '§hp99999', 'hp99999§')
# Leet tech (8)
add('0v3rfl0w', 'd3@dl0ck', 's3gf4ult', 'k3rn3l+⚙'[:8],
    'r00tk1t♔', 'h4x0r♕8k', '3l33t♔8k', 'n00b♟8kl',
    'd3@dl♠8k', 'l33t♔8kl')

# Themed 8-char vocab (D&D · Rogue · Wizardry · PLATO · Lynx · DF)
add('for†ress',   # DF fortress (†=t ✓)
    '†iefling',   # D&D tiefling (†=t opener ✓)
    'illi†hid',   # D&D illithid (†=t ✓)
    'minecar†',   # DF minecart (†=t endpoint ✓)
    'airfigh†',   # PLATO airfight (†=t endpoint ✓)
    'mahali†o',   # Wizardry mahalito (†=t ✓)
    'makani†o',   # Wizardry makanito (†=t ✓)
    'half♝ing',   # D&D halfling (♝=l ✓)
    'beho♝der',   # D&D beholder (♝=l ✓)
    'mamor♝is',   # Wizardry mamorlis (♝=l ✓)
    'migrant⚒',   # DF migrant + pickaxe endpoint
    'bugbear⛧',   # D&D bugbear + pentagram endpoint
    'aasimar☼',   # D&D aasimar + sun endpoint (celestial)
    'duergar⛧',   # D&D duergar + pentagram endpoint
    'centaur⛧',   # Rogue centaur + pentagram endpoint
    'samurai§',   # Wizardry samurai + section endpoint
    'dumapic⛧',   # Wizardry dumapic + pentagram endpoint
    'griffin†',   # Rogue griffin + dagger endpoint
    'aquifer⚒',   # DF aquifer + pickaxe endpoint
    'cantrip†',   # D&D cantrip + dagger endpoint
    'mahalit⛧',   # Wizardry mahalito truncated + pentagram (⛧=o symmetric)
    'mamorli§',   # Wizardry mamorlis truncated + section endpoint
    )

# ── Validate & bucket ────────────────────────────────────────────────────────
mixed = defaultdict(list)
seen_mixed = defaultdict(set)
FORBIDDEN = set('!○')

for w in RAW_MIXED + MOVED_TO_MIXED:
    w = w.strip()
    if not w:
        continue
    if any(c in FORBIDDEN for c in w):
        continue
    n = len(w)
    if not (1 <= n <= 8):
        continue
    if not (any(c in U_SET for c in w) or _has_word_break(w)):
        continue                      # neither symbol nor word break — plain's job
    if w not in seen_mixed[n]:
        mixed[n].append(w)
        seen_mixed[n].add(w)

# ── Verify ───────────────────────────────────────────────────────────────────
def _plain_err(w):
    if any(c in U_SET for c in w):
        return 'has-u'
    if _has_word_break(w):
        return 'splits'               # multi-word token — belongs in mixed
    return ''


def _mixed_err(w):
    if not (any(c in U_SET for c in w) or _has_word_break(w)):
        return 'plain-like'           # typable single word — belongs in plain
    return ''


def verify(label, data, check):
    ok = True
    for n, words in sorted(data.items()):
        bad = []
        for w in words:
            if len(w) != n:
                bad.append(f'len({w!r})={len(w)}')
            err = check(w)
            if err:
                bad.append(f'{err}:{w!r}')
        print(f'  {label} L{n}: {len(words):6d} words  errs={bad[:3]}')
        if bad:
            ok = False
    return ok

print('=== plain ===')
ok_p = verify('plain', plain, _plain_err)
print('=== mixed ===')
ok_m = verify('mixed', mixed, _mixed_err)
if not (ok_p and ok_m):
    raise SystemExit('vocab verification FAILED — files not written')

# ── Write files ──────────────────────────────────────────────────────────────
def write_plain(path, data):
    lines = [
        '# Vocab words (plain) — typable characters only, each a SINGLE w-word\n',
        '# (no internal word-class break: w/b/e treat these exactly like W/B/E).\n',
        '# Themes: retro computing · dungeon crawler · vim/editor · D&D · Rogue · Wizardry · PLATO · Lynx · Dwarf Fortress.\n',
        '# Lengths 1-2: ≥10.  Lengths 3-8: ≥100 each.\n\n',
    ]
    for n in sorted(data):
        lines.append(f'# --- length {n} ---\n')
        for w in data[n]:
            lines.append(w + '\n')
        lines.append('\n')
    path.write_text(''.join(lines))
    print(f'wrote {path.name}: {sum(len(v) for v in data.values())} words')

def write_mixed(path, data):
    ulist = ' '.join(ALL_U)
    lines = [
        '# Vocab words (mixed) — each token carries an untypable symbol and/or an\n',
        '# internal w/b/e word break (typable punctuation like : ^ + breaks too).\n',
        '# Every symbol below is PUNCTUATION in vim (utf_class 0x20a0-0x27ff): a\n',
        '# symbol next to a letter breaks the word, while an adjacent symbol run\n',
        '# reads as ONE punctuation word. W/B/E always take the whole token.\n',
        f'# Chars: {ulist}\n',
        '# All words carry a trailing space (wide-glyph terminal offset).\n\n',
    ]
    for n in sorted(data):
        lines.append(f'# --- length {n} ---\n')
        for w in data[n]:
            lines.append(w + ' \n')
        lines.append('\n')
    path.write_text(''.join(lines))
    print(f'wrote {path.name}: {sum(len(v) for v in data.values())} words')

write_plain(BASE / 'vocab_plain.txt', plain)
write_mixed(BASE / 'vocab_mixed.txt', mixed)
