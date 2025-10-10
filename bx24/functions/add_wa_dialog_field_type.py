


def add_wa_dialog_field_type(but, handler):
    """
    Добавить тип поля "WA диалог".
    """
    try:
        params = {
            'USER_TYPE_ID': 'mbkagents',
            'HANDLER': handler,
            'TITLE': 'Диалог с агентом в WA',
        }
        response = but.call_list_method('userfieldtype.add', params)
        return response

    except Exception as e:
        return repr(e)