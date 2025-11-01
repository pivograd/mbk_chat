import re


def get_message_from_comment(comment: str, form_type: str, domain: str) -> str:
    """
    Формирует сообщение в зависимости от типа заполненной формы на сайте
    """
    domain_materials_map = {
        'q.forestvologda.com': 'из бревна и клеенного бруса',
        'spb.forestvologda.com': 'из клеенного бруса',
        'msk.forestvologda.com': 'из клеенного бруса',
        'q-brevno.forestvologda.com': 'из бревна',
    }

    material = domain_materials_map.get(domain, '')

    if form_type == "quiz":
        floors_match = re.search(r'Сколько этажей вы хотите в доме\?\s*:?\s*([^\n]+)', comment)
        floors = floors_match.group(1).strip() if floors_match else ''

        area_match = re.search(r'Какой площади хотели бы дом\?\s*:?\s*([^\n]+)', comment)
        house_area = area_match.group(1).strip() if area_match else ''

        return f'Здравствуйте, я верно понимаю, что вы хотели получить подборку проектов {material} "этажей: {floors}, площадь: {house_area}"?'

    elif form_type.startswith("Презентация проекта"):
        match = re.search(r'«([^»]+)»', form_type)
        project_name = match.group(1) if match else ''
        return f"Здравствуйте, я верно понимаю, что вы хотели получить презентацию проекта {project_name} {material}?"

    else:
        return f"Здравствуйте, я верно понимаю, что хотели бы посмотреть каталог проектов {material}?"
