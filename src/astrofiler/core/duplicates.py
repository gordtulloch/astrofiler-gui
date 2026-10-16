"""Duplicate-file and integrity queries over the catalog."""

import logging
import os
from dataclasses import dataclass
from typing import List, Tuple

from peewee import fn

from ..models import fitsFile

logger = logging.getLogger(__name__)


def find_duplicate_hashes() -> List[Tuple[str, int]]:
    """``(content_hash, file_count)`` for every hash shared by more than one catalogued file."""
    count = fn.COUNT(fitsFile.fitsFileId)
    query = (
        fitsFile.select(fitsFile.fitsFileHash, count.alias("n"))
        .where(fitsFile.fitsFileHash.is_null(False))
        .group_by(fitsFile.fitsFileHash)
        .having(count > 1)
        .tuples()
    )
    return [(h, n) for h, n in query]


def files_with_hash(content_hash: str) -> List[fitsFile]:
    """Every catalogued file with *content_hash*, oldest id first (the one to keep)."""
    return list(
        fitsFile.select().where(fitsFile.fitsFileHash == content_hash).order_by(fitsFile.fitsFileId)
    )


@dataclass(frozen=True)
class IntegrityProblem:
    """A catalogued file whose bytes no longer match the hash recorded for it."""

    file: fitsFile
    reason: str  # "missing" or "modified"


def verify_integrity() -> List[IntegrityProblem]:
    """Re-hash every catalogued file on disk and report those that are missing or changed."""
    from .services import get_file_hash_calculator

    calculator = get_file_hash_calculator()
    problems: List[IntegrityProblem] = []
    query = fitsFile.select().where(
        fitsFile.fitsFileHash.is_null(False) & (fitsFile.fitsFileSoftDelete != True)  # noqa: E712
    )
    for record in query:
        path = record.fitsFileName
        if not path or not os.path.exists(path):
            problems.append(IntegrityProblem(record, "missing"))
            continue
        try:
            current = calculator.calculate_sha256(path)
        except Exception:
            logger.warning("Could not hash %s during integrity check", path, exc_info=True)
            problems.append(IntegrityProblem(record, "missing"))
            continue
        if current != record.fitsFileHash:
            problems.append(IntegrityProblem(record, "modified"))
    return problems
