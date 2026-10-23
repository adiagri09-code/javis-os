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

# Exact dummy-auth/native enforcement evidence; this does not attest account
# readiness, actual role usage, business quality or candidate/final execution.
# docs/superpowers/evidence/2026-10-23-m2c-native-qualification.json
QUALIFIED_PROFILES = {('win32', '2.1.308',
    'c9796ba22a9221586b36371b36f5b66198d66eb4badf6a4cf4a5f7b07becea53', '0.2.116',
    'claude-isolated-roles-v2', 'aa51b4b98341e27cb2ff5f2a78a42eda86265988066d3a39e79b96b8eef7fb63'):
    '310e6df5c5a0d41297bc4287ee6cbd179db32afac20a3533aad853d23b3fd859'}


def profile_qualification(pin, platform):
    key = (platform, pin["cli_version"], pin["cli_hash"], pin["sdk_version"],
           pin["profile_version"], pin["profile_hash"])
    evidence = QUALIFIED_PROFILES.get(key)
    return evidence if type(evidence) is str and re.fullmatch(r"[0-9a-f]{64}", evidence) else None
