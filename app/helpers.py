import re


def get_user_id_and_session(list_of_keys: list) -> list:
    pattern = re.compile(r"user:(\d+):session:([a-f0-9\-]+)")
    extracted_data = []
    for key in list_of_keys:
        match = pattern.search(key.decode("utf-8"))
        if match:
            extracted_user_id = match.group(1)
            extracted_session_id = match.group(2)
            extracted_data.append((extracted_user_id, extracted_session_id))

    return extracted_data
