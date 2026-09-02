def add_tag(tag, tags=None):
    if tags is None:
        tags = []
    tags.append(tag)
    return tags


def add_label(label, labels=None):
    if labels is None:
        labels = []
    labels.append(label)
    return labels
