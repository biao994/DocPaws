"""
知识库索引：manifest diff（document_id -> content_hash）
"""


def compute_diff(
    old_map: dict[str, str],
    new_map: dict[str, str],
) -> dict[str, list[str]]:
    """
    对比两份 manifest，返回 added / deleted / modified / unchanged 的 document_id 列表。
    """
    old_ids = set(old_map.keys())
    new_ids = set(new_map.keys())

    added = sorted(new_ids - old_ids)
    deleted = sorted(old_ids - new_ids)

    common = old_ids & new_ids
    modified: list[str] = []
    unchanged: list[str] = []
    for doc_id in sorted(common):
        if old_map[doc_id] != new_map[doc_id]:
            modified.append(doc_id)
        else:
            unchanged.append(doc_id)

    return {
        "added": added,
        "deleted": deleted,
        "modified": modified,
        "unchanged": unchanged,
    }
