# AI Writing Tells and Detection Research

**Captured**: 2026-04-08
**Source**: copied from `../../../job-hunter/cv-linkedin/job-research/18_AI_WRITING_TELLS_AND_DETECTION.md` (canonical, 25+ sources). Reproduced here so the in-repo voice rules are self-justifying.

## Why this matters

45% of job seekers used generative AI on resumes (Canva, 2024). 64% of recruiters noticed an uptick in AI-generated CVs (Willo). The signals below are what recruiters, hiring managers, and ATS systems use to flag AI-assisted content. The same signals make a personal blog read fake.

## The Em Dash Problem

### Quantitative data (arXiv:2603.27006)

| Model | Em dashes per 1,000 words |
|---|---|
| GPT-4.1 | 10.62 |
| Claude Opus | 9.09 |
| DeepSeek V3 | 6.95 |
| Human baseline | 3.23 (range 0.33 to 17.12) |
| Meta Llama | 0 (RLHF drove to zero) |

GPT-4o uses ~10x more em dashes than its predecessor. The cause: LLMs are trained on late-1800s and early-1900s books that use ~30% more em dashes than contemporary prose. Markdown formatting in training data reinforces the pattern (arXiv:2603.27006).

Sam Altman publicly confirmed ChatGPT's em dash frequency was adjusted via fine-tuning (seangoedecke.com).

### Hoi-specific evidence

Verified across 37 pre-AI Hoi blogs (2014-2022, ~80,000 words): **zero em dashes**. The single ChatGPT-polished sample in the corpus (blog 04, 270 words) had **7 em dashes**. The contamination is unmistakable when held against the rest of the corpus.

### Recruiter perspective

Recruiters explicitly cite em dashes as a formatting red flag (Willo, Dice.com, PQ Magazine). However, em dash alone is not a reliable detector. Human range (0.33 to 17.12 per 1,000 words) overlaps with LLM output. It is one signal among many, but it is the easiest to spot and the cheapest to fix.

**Our rule**: Ban em dashes from all public-facing content (CV, LinkedIn, README, cover letters, blog posts dated >= 2026-04-07). Internal AI-to-AI docs and pre-cutoff legacy posts are exempt. CI hard-fails on em dashes outside `content/posts/`.

## Full AI Writing Detection Signals

### HIGH reliability (1000x+ more common in AI)

| Signal | What it looks like | Source |
|---|---|---|
| Bold-first bullet pattern | `**Key point:** description` on every bullet | hybridcopynet, arXiv:2510.15061 |
| Unicode arrows as list markers | Using `-->` in prose | arXiv:2510.15061 (Antislop) |
| Noun-heavy nominalisation | Turning verbs into nouns ("the utilization of" vs "using") | PNAS / arXiv:2410.16107 |
| Sentence length uniformity | All sentences roughly same length, no short punchy ones | rarebirdinc.com |
| Negation framing | "It's not X, it's Y" | Wikipedia: Signs of AI writing |

### MEDIUM reliability

| Signal | What it looks like | Source |
|---|---|---|
| Em dash overuse | Using em dashes where commas/periods/colons work | arXiv:2603.27006 |
| Rule of threes | AI groups ideas in sets of three far more than humans | Wikipedia: Signs of AI writing |
| Symmetric paragraph length | All paragraphs roughly equal length | Multiple sources |
| Passive voice overuse | "The project was delivered" vs "I delivered the project" | PNAS study |
| Absence of error | Zero typos, zero informal language | Pangram Labs |

### DECLINING reliability (widely known, being tuned out)

| Signal | Words/phrases | Source |
|---|---|---|
| "Delve" and friends | delve, meticulous, commendable, pivotal, noteworthy | Science Advances |
| Elevated abstract nouns | realm, landscape, tapestry, beacon | Reuters Institute |
| Hedge openers | "It's worth noting that", "It's important to remember" | ai-text-humanizer.com |
| Heavy transitions | "In summary", "Moreover", "Furthermore" | Multiple sources |

## Our Writing Rules (derived from this research)

1. **No em dashes** in public-facing content (CV, LinkedIn, README, cover letters, blog posts dated >= 2026-04-07)
2. **No AI-flagged words** (delve, beacon, testament, leverage, spearhead, synergy, etc., see `11_VOICE_PROFILE.md` anti-vocabulary)
3. **Vary sentence length** deliberately. Short punches, then longer explanatory ones (Hoi's signature: 4 -> 50 -> 8 word swings)
4. **No bold-first bullet pattern** (use plain bullets)
5. **Use contractions** ("I've", "didn't") in appropriate contexts. Sounds human.
6. **Include imperfections** strategically. Real writing has personality. Hoi's corpus preserves typos like "fasts track" and "suprised", and his non-native English tells ("the staffs are").
7. **Specificity test**: "could any other blogger have written this?" If yes, rewrite.
8. **Read-aloud test**: if it sounds unnatural spoken, rewrite it.

## Detection caveat

The 68%/92% rejection/detection figures cited by some sources (nonairesumes.com) originate from vendor-aligned sources selling AI-humanisation services. Treat with scepticism. The reliable rule is: **don't sound generic, don't sound smooth, sound like the specific person you are.**

## Sources

- arXiv:2603.27006. "The Last Fingerprint: How Markdown Training Shapes LLM Prose"
- seangoedecke.com. "Why do AI models use so many em-dashes?"
- arXiv:2410.16107. "Do LLMs Write Like Humans? Variation in Grammatical and Rhetorical Styles" (PNAS)
- Wikipedia. "Signs of AI writing"
- The Conversation. "Too many em dashes? Spotting ChatGPT is still more art than science"
- How-To Geek. "No, an Em Dash Can't Help You Detect AI Text"
- NPR. "Inside the unofficial movement to save the em dash from AI"
- Plagiarism Today. "Em Dashes, Hyphens and Spotting AI Writing"
- Science Advances. "Delving into LLM-assisted writing in biomedical publications"
- arXiv:2502.09606. "Human-LLM Coevolution: Evidence from Academic Writing"
- Reuters Institute. "How AI-generated prose diverges from human writing"
- arXiv:2510.15061. "Antislop: A Comprehensive Framework"
- Willo. "11 Tips to Spot AI-Generated Resumes"
- Dice.com. "5 Ways of Telling You Used AI on Your CV"
- PQ Magazine. "CV and Cover Letter AI Red Flags"
- Pangram Labs. "Comprehensive Guide to Spotting AI Writing Patterns"
- hybridcopynet. "LLM Writing Tropes"
