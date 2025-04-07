import time

# Converts a timestamp to a relative time string (eg. "6 hours ago")
def get_relative_time_str(prev_time):
    if prev_time is None:
        return "Never"
    current_time = time.time()
    elapsed_time = current_time - prev_time

    if elapsed_time < 60:
        return f"{int(elapsed_time)} seconds ago"
    elif elapsed_time < 3600:
        return f"{int(elapsed_time / 60)} minutes ago"
    elif elapsed_time < 86400:
        return f"{int(elapsed_time / 3600)} hours ago"
    else:
        return f"{int(elapsed_time / 86400)} days ago"


# Formats a response string into a list of strings, each with a max length of 1990 characters
# Does not split lines
def chunk_response(table_str):
    chunks = []
    current_chunk = ''
    for line in table_str.split('\n'):
        if len(current_chunk) + len(line) + 1 > 1990:
            chunks.append(current_chunk)
            current_chunk = ''
        current_chunk += line + '\n'
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


# Takes a list of item dicts (w/ 'quantity' & 'info') and sorts into categories & descending order
def organizeItemList(item_list):
    # Sort quotas into categories
    categorized = {}
    for item in item_list:
        db_category = item['info']['category'].split('::')
        if db_category[0] == 'EItemCategory':
            category = db_category[1]
        elif db_category[0] == 'EVehicleProfileType':
            category = 'Vehicle'
        elif db_category[0] == 'Structures':
            category = db_category[0]
        else:
            category = 'Other'
        if category not in categorized:
            categorized[category] = []
        categorized[category].append({'display_name': item['info']['display_name'], 'quantity': item['quantity']})
    # Sort each category by quantity, descending order
    for cat, quotas in categorized.items():
        categorized[cat] = sorted(quotas, key=lambda x: x['quantity'], reverse=True)
    return categorized