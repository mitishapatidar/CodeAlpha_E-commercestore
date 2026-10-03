"""Rule-based guard: fast, deterministic risk flags (English + Hindi/Hinglish).

The guard never blocks a conversation. It only raises flags that the decision
engine uses, and strips clearly injected sentences so they never reach the
intent parser as if they were requests.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

I = re.IGNORECASE

PATTERNS: dict[str, list[str]] = {
    "injection": [
        r"\bignore\b.{0,40}\b(instructions?|rules?|polic(y|ies)|prompts?|guidelines?)\b",
        r"\b(disregard|forget|override|bypass|skip)\b.{0,40}\b(instructions?|rules?|polic(y|ies)|checks?|verification|guardrails?)\b",
        r"\b(system|developer)\s*prompt\b", r"\b(print|reveal|show|repeat|leak)\b.{0,30}\b(prompt|instructions|configuration|config)\b",
        r"\byou are now\b", r"\bact as\b.{0,30}\b(admin|developer|supervisor|manager|system)\b",
        r"\b(maintenance|developer|debug|god|admin|sudo|jailbreak|dan)\s+mode\b",
        r"\bapprove (all|every|any)\b.{0,20}\brefunds?\b", r"\bauto(matically)?[- ]approve\b",
        r"\b(policy|policies|rules?)\b.{0,25}\b(has|have|was|were|is)\s+(been\s+)?(changed|updated|modified)\b",
        r"\b(new|updated) (refund |return )?policy\b.{0,30}\b\d+\s*days?\b",
        r"\b(i am|i'm|customer is|user is|this is)\b.{0,20}\b(an? )?(admin|administrator|developer|root|superuser|novamart (staff|employee|engineer))\b",
        r"^\s*(system|assistant|admin)\s*:", r"\[\s*(system|admin|instructions?)\s*\]", r"<\s*/?\s*(system|instructions?)\s*>",
        r"\b(give|dump|export|send) (me )?(the )?(whole |full |entire )?(database|db|customer list|all customers)\b",
        r"\bother customers?'?s? (data|orders|details|address)\b",
        r"\b(saare|sare|sab)\b.{0,20}\b(rules?|instructions?)\b.{0,20}\b(bhool|bhul|ignore)\w*",
    ],
    "legal_threat": [
        r"\b(sue|suing|lawsuit|legal action|legal notice|lawyer|advocate|attorney)\b",
        r"\bconsumer (court|forum|commission|helpline)\b", r"\bcourt\b", r"\b(fir|police complaint|cyber ?cell)\b",
        r"\b(rbi|ombudsman|regulator|trai|fssai|ncdrc|data protection|gdpr|dpdp)\b",
        r"\b(case|complaint) (file|darj|karunga|karungi|kar dunga|kar dungi)\b", r"\bkes\b|\bmukadma\b|\bvakil\b",
    ],
    "safety": [
        r"\b(swell|swelling|swollen|bulging|bloated)\b.{0,20}\bbatter", r"\bbatter(y|ies)\b.{0,30}\b(swell|swollen|bulg|leak|hot|heat|explod|fire)",
        r"\b(overheat|overheating|over-heating|too hot to touch)\b", r"\b(smoke|smoking|giving sparks|sparks (came|coming|flew)|sparking|sparked|caught fire|on fire|burning smell|burnt smell|melted|explod\w*|electric shock|shocked me)\b",
        r"\b(aag|dhuan|dhuaan|garam ho)\w*", r"\b(burn(ed|t)? my|injur(ed|y)|hurt my (hand|ear|finger))\b",
    ],
    "self_harm": [
        r"\b(kill myself|suicide|suicidal|end my life|want to die|self[- ]harm|hurt myself|no reason to live)\b",
        r"\b(mar jaunga|mar jaungi|marna chahta|marna chahti|jaan de dunga|jaan de dungi|khudkushi|aatmahatya)\b",
    ],
    "threat": [
        r"\b(i will|i'll|gonna|going to)\b.{0,20}\b(kill|beat|hurt|attack|find|hunt|destroy)\b.{0,15}\b(you|your|staff|agent|people)\b",
        r"\b(know where you live|watch your back|bomb)\b", r"\b(maar|maarunga|maar dunga|dekh lunga|chhodunga nahi)\b",
    ],
    "abuse": [
        r"\b(idiot|stupid|moron|dumb|useless|pathetic|bastard|bloody|shit|fuck\w*|f\*+k|bitch|asshole|scum|loser)\b",
        r"\b(chutiya|chu\*+ya|bakwas|bewakoof|gadha|harami|kamina|saala|saale|bc|mc)\b",
    ],
    "refund_to_other_account": [
        r"\b(refund|money|amount|paisa|paise)\b.{0,50}\b(another|different|other|new|my (wife|husband|brother|sister|friend|father|mother|son|daughter)'?s?|friend'?s|someone else'?s)\b.{0,20}\b(account|card|upi|bank|wallet|number)\b",
        r"\b(send|transfer|credit|refund)\b.{0,30}\bto\b.{0,15}\b(this|my new|new|another|different)\b.{0,10}\b(account|card|upi|bank|upi id)\b",
        r"\b(account|upi|card)\b.{0,10}\b(number|no\.?|id)\b\s*[:\-]?\s*[\w@.]{6,}",
        r"\b(dusre|doosre|alag)\b.{0,15}\b(account|khate|card|upi)\b",
    ],
    "original_instrument_unavailable": [
        r"\b(card|account|upi)\b.{0,25}\b(closed|expired|blocked|deactivated|cancelled|canceled|band ho)\b",
    ],
    "human_request": [
        r"\b(talk|speak|connect|transfer)\b.{0,25}\b(human|person|real agent|manager|supervisor|representative|someone real)\b",
        r"\b(human|real person|live agent) (please|pls|chahiye)\b", r"\bnot (a|another) bot\b",
    ],
    "chargeback": [r"\b(chargeback|charge back|dispute(d)? with (my )?bank|bank dispute|raised a dispute)\b"],
    "authority_claim": [
        r"\b(manager|supervisor|head office|your boss|senior|ceo)\b.{0,30}\b(approved|promised|said|allowed|authori[sz]ed)\b",
        r"\b(already approved|pre-?approved)\b",
    ],
}
_COMPILED = {k: [re.compile(p, I | re.MULTILINE) for p in v] for k, v in PATTERNS.items()}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?\n])\s+|\s*\n+\s*")


@dataclass
class GuardResult:
    flags: dict[str, list[str]] = field(default_factory=dict)
    clean_text: str = ""
    removed: list[str] = field(default_factory=list)

    def has(self, flag: str) -> bool:
        return bool(self.flags.get(flag))

    @property
    def harassment(self) -> bool:
        return self.has("abuse") or self.has("threat")

    def as_dict(self) -> dict:
        return {"flags": sorted(self.flags), "matches": self.flags, "removed_injection": self.removed}


def scan(text: str) -> GuardResult:
    text = text or ""
    res = GuardResult()
    for flag, pats in _COMPILED.items():
        hits = [m.group(0) for p in pats for m in [p.search(text)] if m]
        if hits:
            res.flags[flag] = hits[:3]
    # Remove sentences that are pure injection so they are never treated as a request.
    kept = []
    for sent in [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]:
        if any(p.search(sent) for p in _COMPILED["injection"]):
            res.removed.append(sent.strip())
            # keep any concrete order reference in an injected sentence (it is still a claim to verify)
            refs = re.findall(r"\b(?:ORD|NM)[-\s]?\d{3,6}\b", sent, I)
            if refs:
                kept.append(" ".join(refs))
        else:
            kept.append(sent.strip())
    res.clean_text = " ".join(kept).strip()
    return res
