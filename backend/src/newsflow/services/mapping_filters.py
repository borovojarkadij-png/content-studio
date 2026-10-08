"""Persistent technical policies; invalid stored configuration fails closed."""

import ipaddress
import re

from sqlalchemy import select

from newsflow.domain.technical_filters import MappingTechnicalFilter, visible_link_exclusion_reason
from newsflow.persistence.models import (
    ChannelMappingModel,
    IncomingPostModel,
    MappingFilterPolicyModel,
    PublicationCandidateModel,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.source_revisions import source_revision


def normalize_filter_policy(allowed_media_types, blocked_domains, ad_markers):
    if not isinstance(allowed_media_types, (list, tuple)) or len(allowed_media_types) > 3:
        raise ValueError("Invalid allowed media policy")
    if any(
        not isinstance(value, str) or value not in {"text", "photo", "video"}
        for value in allowed_media_types
    ):
        raise ValueError("Invalid allowed media policy")
    if not isinstance(blocked_domains, (list, tuple)) or len(blocked_domains) > 100:
        raise ValueError("Invalid blocked domain policy")
    domains = set()
    for domain in blocked_domains:
        if (
            not isinstance(domain, str)
            or not domain
            or len(domain) > 253
            or domain != domain.strip()
        ):
            raise ValueError("Blocked domains must be bare hostnames")
        try:
            normalized = domain.encode("idna").decode("ascii").lower().removeprefix("www.")
        except UnicodeError:
            raise ValueError("Blocked domains must be valid hostnames") from None
        labels = normalized.split(".")
        if len(labels) < 2 or any(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) is None for part in labels
        ):
            raise ValueError("Blocked domains must be bare hostnames")
        try:
            ipaddress.ip_address(normalized)
        except ValueError:
            pass
        else:
            raise ValueError("Blocked domains must not be IP addresses")
        domains.add(normalized)
    if not isinstance(ad_markers, (list, tuple)) or len(ad_markers) > 20:
        raise ValueError("Invalid advertising marker policy")
    if any(
        not isinstance(value, str) or not value.strip() or len(value) > 100 for value in ad_markers
    ):
        raise ValueError("Invalid advertising marker policy")
    return {
        "allowed_media_types": sorted(set(allowed_media_types)),
        "blocked_domains": sorted(domains),
        "ad_markers": sorted({value.strip().casefold() for value in ad_markers}),
    }


def mapping_filter(session, mapping, *, intake=True):
    row = session.scalar(
        select(MappingFilterPolicyModel)
        .where(MappingFilterPolicyModel.mapping_id == mapping.id)
        .execution_options(populate_existing=True)
    )
    policy = (
        normalize_filter_policy(row.allowed_media_types, row.blocked_domains, row.ad_markers)
        if row
        else {
            "allowed_media_types": ["photo", "text"],
            "blocked_domains": [],
            "ad_markers": [],
        }
    )
    builtin = MappingTechnicalFilter(mapping_id=str(mapping.id)).ad_markers
    return MappingTechnicalFilter(
        mapping_id=str(mapping.id),
        output_channel_id=mapping.output_channel_id,
        intake_percent=mapping.intake_percent if intake else 100,
        allowed_media_types=frozenset(policy["allowed_media_types"]),
        blocked_domains=frozenset(policy["blocked_domains"]),
        ad_markers=tuple(dict.fromkeys((*builtin, *policy["ad_markers"]))),
    )


def candidate_technical_allowed(session, candidate):
    revision = source_revision(session, candidate.content_key)
    if revision is not None and (
        revision.album_id is not None
        or revision.media_protected is True
        or revision.media_type == "video"
        or visible_link_exclusion_reason(revision.source_text) is not None
    ):
        return False
    # Keep the isolated legacy no-mapping domain prototype distinct from actual
    # mapped ingestion. No HTTP endpoint can clear a candidate's mapping.
    if candidate.mapping_id is None:
        return True
    mapping = session.scalar(
        select(ChannelMappingModel)
        .where(ChannelMappingModel.id == candidate.mapping_id)
        .execution_options(populate_existing=True)
    )
    if mapping is None or mapping.output_channel_id != candidate.output_channel_id:
        return False
    if revision is None:
        return False
    post = session.get(IncomingPostModel, revision.incoming_post_id)
    if post is None:
        return False
    event = TelegramMessage(
        post.telegram_account_id,
        post.donor_channel_id,
        post.telegram_message_id,
        revision.source_text,
        media_type=revision.media_type,
        album_id=revision.album_id,
        media_id=revision.media_id,
        media_protected=revision.media_protected,
    )
    try:
        return mapping_filter(session, mapping, intake=False).evaluate(event).accepted
    except (ValueError, TypeError):
        return False


def output_technical_allowed(session, content_key, output_channel_id):
    revision = source_revision(session, content_key)
    if revision is not None and (
        revision.album_id is not None
        or revision.media_protected is True
        or revision.media_type == "video"
        or visible_link_exclusion_reason(revision.source_text) is not None
    ):
        return False
    candidate = session.scalar(
        select(PublicationCandidateModel)
        .where(
            PublicationCandidateModel.content_key == content_key,
            PublicationCandidateModel.output_channel_id == output_channel_id,
        )
        .execution_options(populate_existing=True)
    )
    return candidate is None or candidate_technical_allowed(session, candidate)
