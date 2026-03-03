import boto3
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel

# ── Pydantic models ────────────────────────────────────────────────────────────

CATEGORIES = [
    'Tarot & Divination',
    'Crystals & Gemstones',
    'Spiritual Healing',
    'Energy Work',
    'Meditation',
    'Manifestation',
    'Astrology',
    'General',
]

class BlogPostCreate(BaseModel):
    title:       str
    slug:        str
    category:    str
    excerpt:     str          # 1–2 sentence summary for listing cards
    content:     str          # Full HTML content
    coverImage:  str = ''     # /images/blog/filename.jpg
    readTime:    int = 5      # minutes
    tags:        List[str] = []
    published:   bool = True
    seoTitle:    Optional[str] = None
    seoDesc:     Optional[str] = None
    metaKeywords: Optional[str] = None

class BlogPostUpdate(BaseModel):
    title:       Optional[str] = None
    excerpt:     Optional[str] = None
    content:     Optional[str] = None
    coverImage:  Optional[str] = None
    readTime:    Optional[int] = None
    tags:        Optional[List[str]] = None
    published:   Optional[bool] = None
    category:    Optional[str] = None
    seoTitle:    Optional[str] = None
    seoDesc:     Optional[str] = None
    metaKeywords: Optional[str] = None

class BlogPost(BlogPostCreate):
    id:          str
    author:      str = 'Dr. Usha Bhatt'
    createdAt:   str
    updatedAt:   str
    viewCount:   int = 0

# ── DynamoDB helpers ──────────────────────────────────────────────────────────

def get_table():
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('AWS_REGION', 'ap-south-1'),
        endpoint_url=os.getenv('DYNAMODB_ENDPOINT'),
    )
    return dynamodb.Table(os.getenv('BLOG_TABLE', 'cosmic-blog'))

def to_dec(obj):
    if isinstance(obj, float): return Decimal(str(obj))
    if isinstance(obj, dict):  return {k: to_dec(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [to_dec(i) for i in obj]
    return obj

def from_dec(obj):
    if isinstance(obj, Decimal): return int(obj) if obj == int(obj) else float(obj)
    if isinstance(obj, dict):    return {k: from_dec(v) for k, v in obj.items()}
    if isinstance(obj, list):    return [from_dec(i) for i in obj]
    return obj

# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_posts(
    published_only: bool = True,
    category: Optional[str] = None,
    limit: int = 50,
) -> List[dict]:
    table = get_table()
    resp  = table.scan()
    items = [from_dec(i) for i in resp.get('Items', [])]

    if published_only:
        items = [i for i in items if i.get('published', True)]
    if category and category != 'All':
        items = [i for i in items if i.get('category') == category]

    # Sort newest first
    items.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
    return items[:limit]

def get_post_by_slug(slug: str) -> Optional[dict]:
    table = get_table()
    resp  = table.query(
        IndexName='slug-index',
        KeyConditionExpression=boto3.dynamodb.conditions.Key('slug').eq(slug),
    )
    items = resp.get('Items', [])
    return from_dec(items[0]) if items else None

def get_post(post_id: str) -> Optional[dict]:
    table = get_table()
    resp  = table.get_item(Key={'id': post_id})
    item  = resp.get('Item')
    return from_dec(item) if item else None

def create_post(data: BlogPostCreate) -> dict:
    table = get_table()
    now   = datetime.utcnow().isoformat()
    item  = to_dec({
        'id':          str(uuid.uuid4()),
        'author':      'Dr. Usha Bhatt',
        'createdAt':   now,
        'updatedAt':   now,
        'viewCount':   0,
        **data.dict(),
        'seoTitle':    data.seoTitle or data.title,
        'seoDesc':     data.seoDesc  or data.excerpt,
    })
    table.put_item(Item=item)
    return from_dec(item)

def update_post(post_id: str, data: BlogPostUpdate) -> Optional[dict]:
    table   = get_table()
    updates = {k: v for k, v in data.dict().items() if v is not None}
    updates['updatedAt'] = datetime.utcnow().isoformat()

    expr   = 'SET ' + ', '.join(f'#{k} = :{k}' for k in updates)
    names  = {f'#{k}': k for k in updates}
    values = to_dec({f':{k}': v for k, v in updates.items()})

    resp = table.update_item(
        Key={'id': post_id},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues='ALL_NEW',
    )
    return from_dec(resp.get('Attributes', {}))

def delete_post(post_id: str):
    get_table().delete_item(Key={'id': post_id})

def increment_views(post_id: str):
    get_table().update_item(
        Key={'id': post_id},
        UpdateExpression='ADD viewCount :inc',
        ExpressionAttributeValues={':inc': 1},
    )

def get_related_posts(post_id: str, category: str, limit: int = 3) -> List[dict]:
    """Returns published posts in same category, excluding current post"""
    posts = list_posts(published_only=True, category=category)
    return [p for p in posts if p['id'] != post_id][:limit]

def seed_initial_posts():
    """
    Seeds 6 initial blog posts covering all 3 topic areas.
    Call once from a setup script or admin panel.
    """
    posts = [
        BlogPostCreate(
            title='How Tarot Cards Actually Work: The Science and Spirituality Behind the Cards',
            slug='how-tarot-cards-work',
            category='Tarot & Divination',
            excerpt='Tarot cards are not magic — they are a mirror. Discover how 78 cards can reveal the deeper patterns of your life and why millions turn to them for guidance.',
            readTime=7,
            tags=['tarot', 'divination', 'beginners', 'spirituality'],
            seoTitle='How Tarot Cards Work | The Cosmic Connect',
            seoDesc='Discover the science and spirituality behind Tarot cards. Learn how 78 cards reveal the deeper patterns of your life. Expert guidance from Dr. Usha Bhatt.',
            content='''<p class="lead">Tarot cards have fascinated humanity for centuries. Yet for every person who swears by them, there is another who dismisses them as superstition. The truth, as Dr. Usha Bhatt has found across 20 years of practice, lies somewhere far more interesting than either camp imagines.</p>

<h2>The 78-Card Map of Human Experience</h2>
<p>A standard Tarot deck contains 78 cards divided into two sections: the 22 Major Arcana and the 56 Minor Arcana. The Major Arcana represents the great universal archetypes — The Fool, The High Priestess, The Tower, The World. These are the forces that shape human life across every culture and time period.</p>

<p>The Minor Arcana, divided into four suits (Wands, Cups, Swords, Pentacles), represents the day-to-day experiences of human life: our passions and ambitions (Wands), our emotional lives (Cups), our thoughts and challenges (Swords), and our material world (Pentacles).</p>

<blockquote>"The Tarot does not predict a fixed future. It reveals the energies present in your situation right now — and from that, the most likely trajectories." — Dr. Usha Bhatt</blockquote>

<h2>The Psychology of Tarot</h2>
<p>Swiss psychiatrist Carl Jung spent much of his career studying universal symbols and archetypes — patterns that appear across all human cultures, mythologies, and dreams. He called this the collective unconscious. The Major Arcana maps directly onto these archetypes with striking precision.</p>

<p>When you draw the Tower card — a bolt of lightning striking a tall structure — it does not mean your house will burn down. It represents sudden change, the collapse of structures built on false foundations, and the liberation that can follow upheaval. This is a universally understood human experience, and the image speaks to it directly.</p>

<h2>How a Reading Actually Works</h2>
<p>In a Tarot reading, cards are drawn and placed in a spread — a specific layout where each position represents a different aspect of the question (past, present, future; situation, action, outcome). The reader then interprets the cards in relation to each position and to each other.</p>

<p>The skill is not in memorising 78 definitions. It is in reading the story that the cards tell together — the way the imagery interacts, the balance of suits, the presence of Major or Minor Arcana dominance. An experienced reader like Dr. Bhatt is, in essence, translating a symbolic language.</p>

<h2>What Tarot Cannot Do</h2>
<p>It is important to be clear about this. Tarot cannot predict fixed outcomes. The future is not written — it is created by our choices, energy, and actions. What Tarot can do is illuminate the energies and patterns at play right now, reveal unconscious influences, and help you see your situation from a perspective you may not have considered.</p>

<p>It is a tool for reflection, clarity, and self-awareness — not a substitute for personal responsibility or professional advice.</p>

<h2>Is Tarot Right for You?</h2>
<p>If you are facing a decision and feel unclear, if you are going through a difficult period and seeking perspective, or if you simply want to deepen your self-knowledge — a Tarot reading with Dr. Usha Bhatt may offer exactly the clarity you are looking for.</p>

<p>She offers both in-person readings in New Delhi and remote readings via call or video. Each session is conducted with complete confidentiality and compassion.</p>''',
        ),
        BlogPostCreate(
            title='The 7 Most Powerful Healing Crystals and How to Use Them',
            slug='7-most-powerful-healing-crystals',
            category='Crystals & Gemstones',
            excerpt='From Amethyst to Black Tourmaline, certain crystals carry frequencies that can genuinely shift your energy. Here is Dr. Usha Bhatt\'s guide to the 7 most powerful.',
            readTime=8,
            tags=['crystals', 'healing', 'amethyst', 'rose quartz', 'beginners'],
            seoTitle='7 Most Powerful Healing Crystals | The Cosmic Connect',
            seoDesc='Discover the 7 most powerful healing crystals and how to use them. Expert guide from Dr. Usha Bhatt, Reiki Grand Master and certified Crystal Therapy practitioner.',
            content='''<p class="lead">Not all crystals are created equal. While every stone carries its own unique energy, certain crystals have earned their reputation across centuries of use by healers, mystics, and energy workers worldwide. Here are the seven Dr. Usha Bhatt returns to again and again in her practice.</p>

<h2>1. Amethyst — The Stone of Clarity and Calm</h2>
<p>Amethyst is perhaps the most universally useful healing crystal. Its deep violet frequency resonates with the Third Eye and Crown chakras, making it exceptional for calming an overactive mind, improving sleep, enhancing intuition, and supporting meditation.</p>
<p><strong>How to use it:</strong> Place on your bedside table for improved sleep. Hold during meditation. Wear as jewellery for continuous calming energy throughout the day.</p>

<h2>2. Rose Quartz — The Stone of Unconditional Love</h2>
<p>Rose Quartz works with the Heart chakra and carries one of the gentlest, most nurturing frequencies in the crystal kingdom. It supports self-love (often the most important and neglected love), heals emotional wounds, and opens the heart to giving and receiving love more freely.</p>
<p><strong>How to use it:</strong> Keep in your bedroom or living space. Hold when feeling emotionally overwhelmed. Meditate with it on your heart centre.</p>

<h2>3. Black Tourmaline — The Protector</h2>
<p>In a world of screens, electromagnetic fields, and energy-draining environments, Black Tourmaline has become more relevant than ever. It is the premier protection crystal — grounding, shielding, and transmuting negative energy before it can affect your field.</p>
<p><strong>How to use it:</strong> Place near electronic devices, especially your computer or Wi-Fi router. Keep in your bag when going to crowded or stressful environments. Place at the entrance of your home.</p>

<h2>4. Clear Quartz — The Master Healer</h2>
<p>Clear Quartz amplifies whatever energy surrounds it and within it. This makes it both the most versatile healing crystal and the one that requires the most care — it amplifies your intentions, your energy, and the energy of other crystals nearby.</p>
<p><strong>How to use it:</strong> Program with a specific intention through meditation. Use in crystal grids to amplify the grid\'s purpose. Pair with other crystals to enhance their properties.</p>

<h2>5. Citrine — The Stone of Abundance</h2>
<p>Citrine carries the energy of the sun — warm, energising, and life-giving. It is uniquely unusual among crystals in that it does not absorb negative energy — it transmutes it. It resonates with the Solar Plexus chakra and supports confidence, creativity, and the attraction of abundance.</p>
<p><strong>How to use it:</strong> Keep in your workspace or cash register. Place in the wealth corner of your home (far left corner from your front door). Wear when you need confidence or creative energy.</p>

<h2>6. Lapis Lazuli — The Stone of Truth and Wisdom</h2>
<p>Used by Egyptian pharaohs and healers for thousands of years, Lapis Lazuli connects to the Third Eye and Throat chakras. It supports clear communication, intellectual insight, and the courage to speak your truth. It is particularly powerful for those in leadership roles or facing difficult conversations.</p>
<p><strong>How to use it:</strong> Meditate with it on your forehead. Keep on your desk during important work. Wear as a necklace to support throat chakra energy.</p>

<h2>7. Green Aventurine — The Stone of Opportunity</h2>
<p>Known as the "gambler\'s stone," Green Aventurine is associated with luck, opportunity, and growth — but not in a passive way. It works by aligning you with your highest possibilities and supporting the action needed to achieve them. It resonates with the Heart chakra and also supports physical wellbeing.</p>
<p><strong>How to use it:</strong> Keep in your pocket when entering important meetings or interviews. Place on your windowsill to invite new opportunities. Use in meditation when seeking a new direction.</p>

<h2>How to Care for Your Crystals</h2>
<p>Every crystal absorbs energy from its environment and from you. Regular cleansing is essential. The most effective methods are moonlight overnight (particularly during full moon), sound cleansing with singing bowls, smudging with sage or palo santo, and burying briefly in the earth for grounding.</p>

<p>After cleansing, programme your crystal by holding it, closing your eyes, and clearly stating your intention for it. This focuses its energy specifically for your purpose.</p>''',
        ),
        BlogPostCreate(
            title='What is Reiki and Does It Actually Work? A Balanced Look',
            slug='what-is-reiki-does-it-work',
            category='Spiritual Healing',
            excerpt='Reiki is practised in hospitals across the world, yet it remains deeply misunderstood. Dr. Usha Bhatt — a Reiki Grand Master — offers a clear, balanced explanation.',
            readTime=6,
            tags=['reiki', 'healing', 'energy work', 'wellness'],
            seoTitle='What is Reiki and Does It Work? | The Cosmic Connect',
            seoDesc='A balanced, honest look at Reiki healing — what it is, how it works, what research shows, and what to expect from a session. By Dr. Usha Bhatt, Reiki Grand Master.',
            content='''<p class="lead">Reiki is one of the most widely practised energy healing modalities in the world — and one of the most misunderstood. It is offered in hospitals and hospices in the UK, USA, and India. It is taught in wellness centres globally. And yet many people still ask the fundamental question: does it actually work?</p>

<h2>What Reiki Is</h2>
<p>Reiki (pronounced ray-key) is a Japanese healing technique developed by Mikao Usui in the early 20th century. The word itself translates roughly as "universal life energy" — rei meaning universal/spiritual, ki meaning life force energy (the same concept as prana in Indian tradition, chi in Chinese tradition).</p>

<p>In a Reiki session, the practitioner channels this universal energy through their hands — either by gently placing them on the client's body or hovering above it — to support the body's natural healing processes, reduce stress, and restore energetic balance.</p>

<h2>The Human Energy Field</h2>
<p>The foundation of Reiki — and indeed all energy healing — is the understanding that human beings are not just physical bodies. We are also energetic beings. Every cell in the body generates an electromagnetic field. The heart generates the largest of these, measurable several feet away from the body using modern instruments.</p>

<p>When this energy becomes blocked, depleted, or imbalanced — through stress, trauma, illness, or environmental factors — it is understood to contribute to physical and emotional disturbance. Reiki works to restore flow and balance to this field.</p>

<h2>What Does the Research Say?</h2>
<p>Reiki research is still developing, but what exists is promising. Multiple studies have shown Reiki to be effective at reducing anxiety and pain in clinical settings. A 2017 study in the Journal of Alternative and Complementary Medicine found significant reductions in anxiety, pain, and fatigue in cancer patients receiving Reiki as a complement to conventional treatment. A number of UK NHS trusts and US hospital systems now offer Reiki as a supportive therapy.</p>

<p>It is important to note that Reiki is a complement to, not a replacement for, conventional medical care. Dr. Bhatt is clear about this in every session.</p>

<h2>What a Session With Dr. Usha Bhatt Looks Like</h2>
<p>A session begins with a brief consultation — understanding what you are experiencing physically, emotionally, and energetically. You remain fully clothed and lie on a comfortable treatment table. Dr. Bhatt then works through a series of hand positions over or on the body, typically from head to feet.</p>

<p>Most clients report deep relaxation, warmth, tingling sensations, or emotional release during the session. Some fall asleep. Some experience vivid imagery. Some simply feel a profound sense of peace.</p>

<p>After the session, Dr. Bhatt shares her observations and any guidance for supporting your healing at home.</p>

<h2>Who Benefits Most from Reiki?</h2>
<p>Reiki is beneficial for anyone, but particularly those experiencing chronic stress or anxiety, emotional trauma or grief, chronic pain or illness, burnout or exhaustion, or a sense of being stuck or disconnected from themselves.</p>

<p>It is also deeply supportive for those undergoing medical treatment — not as an alternative to it, but as a way to strengthen resilience, manage side effects, and support the body's healing capacity.</p>''',
        ),
        BlogPostCreate(
            title='Akashic Records: What They Are and What a Reading Can Reveal',
            slug='akashic-records-what-they-are',
            category='Spiritual Healing',
            excerpt='The Akashic Records are described as the cosmic library of every soul\'s journey. Here is what they actually are, how they are accessed, and what a reading can illuminate.',
            readTime=7,
            tags=['akashic records', 'past life', 'soul', 'spirituality'],
            seoTitle='What Are Akashic Records? | The Cosmic Connect',
            seoDesc='Learn what Akashic Records are, how they are accessed, and what a reading reveals. Expert guide from Dr. Usha Bhatt, certified Akashic Records practitioner.',
            content='''<p class="lead">The concept of the Akashic Records appears across ancient traditions under different names — the Book of Life in Judeo-Christian tradition, the Akasha in Sanskrit, the cosmic memory in various mystical schools. Today it is one of the most sought-after spiritual readings, and for good reason.</p>

<h2>The Cosmic Library of Every Soul</h2>
<p>The Akashic Records are understood to be an energetic archive — a vibrational record of every soul's journey across all lifetimes: every thought, every action, every experience, every relationship, every choice. The word "Akasha" comes from Sanskrit, meaning sky or ether — the fifth element beyond earth, water, fire, and air.</p>

<p>Think of it as a vast spiritual database. Every soul has its own record within it — a complete account of who it has been, what it has experienced, and what it has come to learn in this and previous lifetimes.</p>

<h2>Why Access the Akashic Records?</h2>
<p>Many people come for Akashic Records readings when they feel inexplicably stuck — patterns that repeat despite their best efforts, fears they cannot trace to any experience in this lifetime, relationship dynamics that feel strangely familiar, or a persistent sense of a calling they cannot quite identify.</p>

<p>The Akashic Records can shed light on all of these. They reveal the deeper why behind your current life experiences — the soul contracts, past life influences, karmic patterns, and core lessons your soul chose before incarnating into this lifetime.</p>

<h2>What Happens in a Reading</h2>
<p>Dr. Usha Bhatt accesses the Akashic Records through a specific prayer and meditative process that opens the Records for the person she is reading for. This requires the person's full legal name and their willingness to receive the information.</p>

<p>Once open, Dr. Bhatt receives information through a combination of clear knowing, visual impressions, and intuitive messages. She may see past life scenes relevant to your current situation, hear guidance from your soul's masters and teachers, or receive direct answers to the specific questions you bring.</p>

<h2>What a Reading Can Reveal</h2>
<p>Every reading is unique, but common themes include the origins of recurring relationship patterns, past life connections with significant people in your current life, the root of unexplained fears or phobias, your soul's primary life purpose and gifts, and any energetic blocks or karmic agreements that are limiting your progress.</p>

<h2>What It Cannot Do</h2>
<p>An Akashic Records reading is not fortune-telling. It does not tell you exactly what will happen in your future — because the future is shaped by your choices. What it does is reveal the energetic landscape you are working within, so that you can make more informed, aligned choices.</p>

<p>It also does not replace personal responsibility. The information received is always in service of your growth, clarity, and healing — not as a way to bypass the work of living.</p>''',
        ),
        BlogPostCreate(
            title='How to Start a Crystal Grid: A Step-by-Step Beginner\'s Guide',
            slug='how-to-create-crystal-grid',
            category='Crystals & Gemstones',
            excerpt='Crystal grids are one of the most powerful manifestation tools available. Here is exactly how to create your first one — from choosing crystals to activating the grid.',
            readTime=9,
            tags=['crystal grid', 'manifestation', 'beginners', 'crystals'],
            seoTitle='How to Create a Crystal Grid | The Cosmic Connect',
            seoDesc='Step-by-step guide to creating your first crystal grid for manifestation, healing, or protection. Expert instructions from Dr. Usha Bhatt, certified Crystal Therapy practitioner.',
            content='''<p class="lead">A crystal grid is one of the most intentional and powerful tools in the crystal healer's toolkit. Unlike simply placing a crystal on your windowsill, a crystal grid creates a unified energetic field — a geometric arrangement of stones working in concert toward a single, focused intention.</p>

<h2>Why Crystal Grids Work</h2>
<p>Crystals amplify intention. When you combine multiple crystals in a geometric pattern, their individual energies interact and amplify each other — like a choir versus a solo voice. The sacred geometry of the grid further strengthens this by creating a coherent energetic structure that resonates with universal patterns found throughout nature.</p>

<h2>What You Need</h2>
<p>You do not need expensive or rare crystals to create an effective grid. What matters far more is the clarity of your intention and the care you bring to the process. For a beginner grid you will need:</p>
<ul>
<li>A clear quartz point for the centre (the "master crystal")</li>
<li>6–12 supporting crystals chosen for your intention</li>
<li>A flat, undisturbed surface — a wooden board, cloth, or simply a table</li>
<li>A clear quartz point or wand for activation</li>
<li>Optional: a printed sacred geometry template</li>
</ul>

<h2>Step 1: Set Your Intention</h2>
<p>This is the most important step. Your intention is the engine of the grid. Be specific. Not "I want more money" but "I am drawing opportunities for financial abundance aligned with my highest good." Write it down on paper and place it beneath your centre stone.</p>

<h2>Step 2: Cleanse Your Crystals</h2>
<p>Before creating your grid, cleanse every crystal you will be using. You can do this by placing them in moonlight overnight, smudging them with sage or palo santo, placing them on a selenite slab for an hour, or using sound cleansing with a singing bowl. This clears any energies the stones may have absorbed during storage or transit.</p>

<h2>Step 3: Choose Your Crystals</h2>
<p>Select your supporting crystals based on your intention. For abundance: Citrine, Green Aventurine, Pyrite. For love and relationships: Rose Quartz, Rhodonite, Malachite. For protection: Black Tourmaline, Obsidian, Smoky Quartz. For clarity and focus: Clear Quartz, Fluorite, Sodalite. For healing: Amethyst, Green Aventurine, Blue Lace Agate.</p>

<h2>Step 4: Arrange Your Grid</h2>
<p>Begin from the outside and work inward. Place your outer stones first, then the middle ring (if you have one), and finally your centre stone. As you place each stone, state your intention aloud or in your mind. Move deliberately and with presence.</p>

<p>Common geometric patterns include the Flower of Life (excellent for all purposes), the Star of David (particularly for protection and manifestation), concentric circles (for healing and expansion), and simple straight-line arrangements radiating from the centre.</p>

<h2>Step 5: Activate the Grid</h2>
<p>Take your activation wand or a clear quartz point and hold it a few centimetres above the grid. Beginning at the centre stone, slowly trace the energetic connections between all the stones — moving from the centre to each outer stone and back, then connecting outer stones to each other.</p>

<p>As you trace these connections, visualise bright white or golden light flowing through the grid, connecting all the stones into a unified field. State your intention aloud one final time.</p>

<h2>Step 6: Maintain Your Grid</h2>
<p>Leave your grid undisturbed for as long as your intention requires — from a few days to a full lunar cycle. Visit it daily if possible, holding your intention and perhaps adding a brief meditation. Re-activate it every few days by tracing the connections again.</p>

<p>When your intention has manifested or you feel the grid has completed its work, thank your crystals, dismantle the grid mindfully, and cleanse the stones again before storing them.</p>''',
        ),
        BlogPostCreate(
            title='The 7 Chakras Explained: A Complete Beginner\'s Guide',
            slug='7-chakras-explained-beginners-guide',
            category='Energy Work',
            excerpt='Understanding your chakras is the foundation of all energy work. This complete guide covers what each of the 7 chakras is, what it governs, and signs it may be blocked.',
            readTime=10,
            tags=['chakras', 'energy work', 'healing', 'beginners', 'meditation'],
            seoTitle='The 7 Chakras Explained | Complete Guide | The Cosmic Connect',
            seoDesc='Complete beginner\'s guide to the 7 chakras — what they are, what each one governs, signs of imbalance, and how to restore balance. By Dr. Usha Bhatt.',
            content='''<p class="lead">The word chakra comes from Sanskrit, meaning wheel or disc. In yogic and Ayurvedic tradition, chakras are spinning wheels of energy located along the central channel of the body. There are hundreds of chakras in the human energy system, but seven primary ones that most energy healing work focuses on.</p>

<p>Understanding your chakras is not just esoteric knowledge — it is practical self-awareness. When you know which chakra is out of balance, you know where to focus your healing, your attention, and your energy.</p>

<h2>1. Root Chakra (Muladhara) — Base of the Spine</h2>
<p><strong>Colour:</strong> Red | <strong>Element:</strong> Earth | <strong>Governs:</strong> Safety, security, belonging, physical body</p>
<p>The Root chakra is your energetic foundation. It governs your sense of safety and security in the world — your basic survival instincts, your physical body, and your connection to the earth. When balanced, you feel grounded, secure, and at home in your body and your life.</p>
<p><strong>Signs of imbalance:</strong> Chronic anxiety or fear, financial instability, feeling disconnected from your body, lower back problems, digestive issues, feeling ungrounded or "in your head."</p>
<p><strong>How to balance:</strong> Time in nature, walking barefoot, grounding meditation, Root chakra crystals (Red Jasper, Smoky Quartz, Black Tourmaline), physical exercise.</p>

<h2>2. Sacral Chakra (Svadhishthana) — Below the Navel</h2>
<p><strong>Colour:</strong> Orange | <strong>Element:</strong> Water | <strong>Governs:</strong> Creativity, sexuality, pleasure, emotions</p>
<p>The Sacral chakra is the centre of creativity, pleasure, and emotional flow. It governs your relationship with your own emotions, your creative expression, and your capacity for joy and sensuality. When balanced, emotions flow freely, creativity is abundant, and life feels enjoyable.</p>
<p><strong>Signs of imbalance:</strong> Creative blocks, emotional numbness or overwhelm, guilt around pleasure, reproductive or lower abdominal issues, rigidity or excessive indulgence.</p>
<p><strong>How to balance:</strong> Creative expression (art, dance, music), time near water, Sacral chakra crystals (Carnelian, Orange Calcite), emotional journaling.</p>

<h2>3. Solar Plexus Chakra (Manipura) — Above the Navel</h2>
<p><strong>Colour:</strong> Yellow | <strong>Element:</strong> Fire | <strong>Governs:</strong> Personal power, confidence, will, identity</p>
<p>The Solar Plexus is your centre of personal power, confidence, and self-determination. It is where your sense of who you are, what you stand for, and your ability to take decisive action lives. When balanced, you feel confident, self-assured, and clear in your direction.</p>
<p><strong>Signs of imbalance:</strong> Low self-esteem, people-pleasing, difficulty making decisions, need for control, digestive problems, feeling powerless or victimised.</p>
<p><strong>How to balance:</strong> Setting and keeping boundaries, Citrine and Tiger's Eye crystals, core-strengthening exercise, spending time in sunlight, assertiveness practice.</p>

<h2>4. Heart Chakra (Anahata) — Centre of the Chest</h2>
<p><strong>Colour:</strong> Green | <strong>Element:</strong> Air | <strong>Governs:</strong> Love, compassion, connection, forgiveness</p>
<p>The Heart chakra is the bridge between the lower (physical) and upper (spiritual) chakras. It governs our capacity to give and receive love — of all kinds, including self-love. When balanced, relationships feel harmonious, forgiveness flows, and there is a sense of deep connection with others and with life.</p>
<p><strong>Signs of imbalance:</strong> Difficulty trusting, co-dependence, lack of self-love, grief held in the body, heart or lung issues, loneliness despite being around people.</p>
<p><strong>How to balance:</strong> Self-compassion practice, Rose Quartz and Green Aventurine crystals, heart-opening yoga poses, forgiveness meditation, acts of loving kindness.</p>

<h2>5. Throat Chakra (Vishuddha) — Throat</h2>
<p><strong>Colour:</strong> Blue | <strong>Element:</strong> Ether | <strong>Governs:</strong> Communication, truth, expression, listening</p>
<p>The Throat chakra governs all forms of expression and communication — speaking, writing, singing, listening, and creative expression through language. When balanced, you communicate clearly and authentically, speak your truth, and listen with genuine presence.</p>
<p><strong>Signs of imbalance:</strong> Difficulty speaking up, over-talking, dishonesty (with self or others), fear of judgment, throat problems, feeling unheard.</p>
<p><strong>How to balance:</strong> Singing, journaling, speaking your truth in small ways daily, Lapis Lazuli and Blue Lace Agate crystals, throat-opening yoga poses.</p>

<h2>6. Third Eye Chakra (Ajna) — Between the Eyebrows</h2>
<p><strong>Colour:</strong> Indigo | <strong>Element:</strong> Light | <strong>Governs:</strong> Intuition, insight, imagination, wisdom</p>
<p>The Third Eye chakra is your centre of inner knowing, intuition, and spiritual sight. It governs your ability to see beyond the surface of things — to perceive patterns, access inner guidance, and understand life at a deeper level. When balanced, intuition is sharp, the mind is clear, and wisdom guides decision-making.</p>
<p><strong>Signs of imbalance:</strong> Inability to trust intuition, overthinking, poor memory, headaches and eye problems, rigid thinking, difficulty imagining possibilities.</p>
<p><strong>How to balance:</strong> Meditation (especially visualisation), Amethyst and Labradorite crystals, reducing screen time before sleep, dream journaling, time in silence.</p>

<h2>7. Crown Chakra (Sahasrara) — Top of the Head</h2>
<p><strong>Colour:</strong> Violet/White | <strong>Element:</strong> Cosmic Energy | <strong>Governs:</strong> Connection to the divine, consciousness, purpose</p>
<p>The Crown chakra is your connection to something greater than yourself — to the divine, the universe, the source of all life. When balanced, there is a sense of meaning, spiritual connection, and trust in life's unfolding. It is not about religion; it is about the experience of being part of something vast and intelligent.</p>
<p><strong>Signs of imbalance:</strong> Spiritual disconnect, feeling purposeless, excessive materialism, depression, cynicism, or on the other extreme, spiritual bypass (using spirituality to avoid real life).</p>
<p><strong>How to balance:</strong> Meditation, time in nature, Clear Quartz and Selenite crystals, prayer or gratitude practice, service to others.</p>

<h2>Working With Your Chakras</h2>
<p>The most effective chakra healing combines multiple approaches: crystals placed on the body at the relevant chakra point during meditation, specific yoga poses, sound healing with bowls tuned to each chakra's frequency, and the simple but powerful practice of bringing conscious attention and breath to each centre.</p>

<p>Dr. Usha Bhatt offers individual chakra balancing sessions as well as the full Crystal Therapy course, which covers chakra healing in depth for those wanting to work with these energies professionally.</p>''',
        ),
    ]

    for post_data in posts:
        try:
            existing = get_post_by_slug(post_data.slug)
            if not existing:
                create_post(post_data)
                print(f'Created: {post_data.title}')
            else:
                print(f'Skipped (exists): {post_data.slug}')
        except Exception as e:
            print(f'Error creating {post_data.slug}: {e}')
