"""Reviewed release registrations for exact native-profile qualification evidence.

Keys bind platform, binary/version, SDK and the complete profile source hash.
Values are SHA-256 of actual qualification evidence retained with the release.
This host source is the registration authority, deliberately outside the profile
hash to avoid a self-referential digest. No environment/HTTP/model can register a
profile. Add an entry only after its native black-box qualification has passed;
changing profile source invalidates the entry. Historical receipts stay readable.
"""
from __future__ import annotations

import re

# roles-v2 is under implementation. There is no qualified release of this profile.
QUALIFIED_PROFILES = {}


def profile_qualification(pin, platform):
    key = (platform, pin["cli_version"], pin["cli_hash"], pin["sdk_version"],
           pin["profile_version"], pin["profile_hash"])
    evidence = QUALIFIED_PROFILES.get(key)
    return evidence if type(evidence) is str and re.fullmatch(r"[0-9a-f]{64}", evidence) else None
