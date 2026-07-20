def use_previous_raw_level(original_filtered_bin):
    def wrapped(raw, old=None, checked_at=None):
        old = old or {}
        item = original_filtered_bin(raw, old, checked_at)
        item["_previousLevel"] = old.get("level", old.get("filteredLevel"))
        return item

    return wrapped
