def paginate(items, page, page_size=20):
    start = page * page_size
    end = start + page_size
    return items[start:end]


def get_full_name(user):
    if user.middle_name:
        return f"{user.first_name} {user.middle_name} {user.last_name}"
    return f"{user.first_name} {user.last_name}"
