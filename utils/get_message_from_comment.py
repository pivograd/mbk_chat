import re


def get_message_from_comment(comment: str, form_type: str) -> str:
    """
    Формирует сообщение в зависимости от типа заполненной формы на сайте
    """
    if form_type == "quiz":
        floors_match = re.search(r'Сколько этажей вы хотите в доме\?\s*:?\s*([^\n]+)', comment)
        floors = floors_match.group(1).strip() if floors_match else ''

        area_match = re.search(r'Какой площади хотели бы дом\?\s*:?\s*([^\n]+)', comment)
        house_area = area_match.group(1).strip() if area_match else ''

        return f'Здравствуйте, я верно понимаю, что вы хотели получить подборку проектов "этажей: {floors}, площадь: {house_area}"?'

    elif form_type.startswith("Презентация проекта"):
        return "Здравствуйте, я верно понимаю, что вы хотели получить презентацию проекта?"

    else:
        return "Здравствуйте, я верно понимаю, что хотели бы посмотреть каталог проектов?"
