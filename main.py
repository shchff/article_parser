import pymupdf, re, sys


def extract_toc_pages(pdf_path):
    """
    Извлечение текста содержания из PDF-файла с фильтрацией заголовков.
    """
    doc = pymupdf.open(pdf_path)
    toc_text = ""
    start_collecting = False
    last_page_found = False
    last_page_number = len(doc)
    for page_num in range(len(doc)):

        if page_num > last_page_number:
            break

        page = doc.load_page(page_num)
        blocks = page.get_textpage().extractDICT()["blocks"]
        for block in blocks:
            # Проверяем, содержит ли блок ключ "lines"
            if "lines" not in block:
                continue

            for line_data in block["lines"]:
                for span in line_data["spans"]:
                    text = span["text"].strip()

                    # Начинаем сбор с момента нахождения "СОДЕРЖАНИЕ"
                    if "СОДЕРЖАНИЕ" in text:
                        start_collecting = True

                    if start_collecting:
                        # Пропускаем строки, которые выглядят как заголовки
                        if is_header(span):
                            continue
                        toc_text += text + "\n"

                        if not last_page_found:
                            match = re.search(r'(\d+)$', toc_text)
                            if match:
                                last_page_number = int(match.group())
                                last_page_found = True
    if not toc_text:
        raise ValueError("Содержание не найдено.")

    doc.close()

    return toc_text


def is_header(span):
    """
    Проверка, является ли текст в span заголовком (например, жирный текст).
    """
    return "Bold" in span["font"]


def clean_toc_lines(toc_text):
    """
    Обработка текста содержания:
    - Удаление номеров страниц и секций.
    - Объединение строк записей.
    """
    lines = toc_text.splitlines()
    cleaned_lines = []
    buffer = ""

    for line in lines:
        line = line.strip()
        # Если строка заканчивается многоточием с номером страницы, это конец записи
        if re.search(r"\.{4,}\n*\s*\d+$", line) or re.search(r"\.{4,}\n*\s*\d+$", buffer + line):
            if len(buffer) == 0:
                continue

            buffer += " " + line
            cleaned_lines.append(buffer.strip())
            buffer = ""
        else:
            # Если строка не заканчивается многоточием, считаем её продолжением предыдущей
            buffer += " " + line

    # В случае, если остался незаконченный буфер, добавим его
    if buffer:
        cleaned_lines.append(buffer.strip())
    return cleaned_lines


def parse_toc(cleaned_lines):
    """
    Парсинг строк содержания с учетом многоточий.
    """
    articles = []

    # Регулярное выражение для строк с многоточиями
    pattern = re.compile(
        r"(.+?)"  # Название статьи
        r"\s?\.{3,}\s*(\d+)$"  # Многоточия и номер страницы
    )

    for line in cleaned_lines:
        if "..." not in line:  # Пропускаем строки без многоточий
            continue

        match = pattern.match(line)
        if match:
            article_data, page_number = match.groups()
            articles.append({
                "article_data": article_data.strip(),
                "page_number": int(page_number),
            })

        else:
            print(f"Не удалось распарсить строку: {line}")


    return articles


def extract_title_authors_organizations(doc, start_page, toc_data):
    def sort_by_reference(arr1, arr2):
        position_map = {}
        for index, value in enumerate(arr2):
            if value not in position_map:
                position_map[value] = index

        def get_position(value):
            return position_map.get(value, float('inf'))

        in_arr2 = [item for item in arr1 if item in position_map]
        not_in_arr2 = [item for item in arr1 if item not in position_map]

        sorted_in_arr2 = sorted(in_arr2, key=get_position)

        return sorted_in_arr2 + not_in_arr2

    first_page = doc.load_page(start_page)
    header = ""

    blocks = first_page.get_textpage().extractDICT()["blocks"]
    for block in blocks:
        if "lines" not in block:
            continue

        for line_data in block["lines"]:
            for span in line_data["spans"]:
                if is_header(span):
                    text = span["text"].strip()
                    header += text + " "

    header = re.sub(r'\s+', ' ', header)
    header = header.upper()
    header_list = header.split(" ")

    toc_data = toc_data.upper()
    toc_data_list = toc_data.split(" ")

    first_word_in_title = sort_by_reference(toc_data_list, header_list)[0]

    start_collecting_title = False
    stop_collecting_title = False

    stop_collecting = False

    title = ""
    authors_and_organizations = ""

    for block in blocks:
        if stop_collecting:
            break
        if "lines" not in block:
            continue
        for line_data in block["lines"]:
            for span in line_data["spans"]:

                text = span["text"].strip()
                if not stop_collecting_title:
                    if is_header(span):
                        if not start_collecting_title:
                            splited_text = text.split(" ")
                            if not text.isdigit():
                                for word in splited_text:
                                    if first_word_in_title == word:
                                        title += text + " "
                                        start_collecting_title = True
                        else:
                            title += text + " "
                    elif start_collecting_title:
                        authors_and_organizations += text + " "
                        stop_collecting_title = True

                elif not ("email" in text.lower() or "e-mail" in text.lower()):
                    authors_and_organizations += text + " "
                else:
                    stop_collecting = True
                    break


    title = title.strip()


    authors_and_organizations = authors_and_organizations.replace("*", '')
    authors_and_organizations = re.sub(r'\s*\d(,\d)?\s+', '  ', authors_and_organizations)
    authors_and_organizations = re.sub(r'\d,', '', authors_and_organizations)
    authors_and_organizations = re.sub(r'\s+,', ',', authors_and_organizations)
    authors_and_organizations = re.sub(r'\b([A-ZA-Я])\.\s([A-ZА-Я])\.', r'\1.\2.', authors_and_organizations)
    authors_and_organizations = authors_and_organizations.replace(". ", ".~~", 1)
    splited_authors_and_organizations = authors_and_organizations.split("~~")

    if len(splited_authors_and_organizations) == 2:
        authors = splited_authors_and_organizations[0].strip()
        splited_authors_and_organizations[1] = splited_authors_and_organizations[1].strip().replace("  ", "~~")
        organizations = splited_authors_and_organizations[1].split("~~")[0].strip()
        return title, authors, organizations

    return None, None, None


def extract_article_data(doc, article, next_article_page=None):
    """
    Извлекает данные статьи, используя данные из содержания.
    """
    article_data = {
        "title": None,  # Заголовок из содержания
        "authors": None,  # Авторы из содержания
        "organizations": None,
        "references": None,
    }

    toc_data = article["article_data"]
    start_page = article["page_number"] - 1
    end_page = next_article_page - 1 if next_article_page else len(doc) - 1

    article_data["title"], article_data["authors"], article_data["organizations"] = extract_title_authors_organizations(doc, start_page, toc_data)
    print(article_data)


    return article_data


def extract_articles(toc_data, pdf_path):
    """
    Извлекает данные всех статей из PDF.
    """
    doc = pymupdf.open(pdf_path)
    articles = []

    for i, article in enumerate(toc_data):
        next_page = toc_data[i + 1]["page_number"] if i + 1 < len(toc_data) else None
        article_data = extract_article_data(doc, article, next_page)
        articles.append(article_data)

    doc.close()
    return articles


def main(pdf_path):
    """
    Основная функция для извлечения содержания из PDF.
    """
    toc_text = extract_toc_pages(pdf_path)
    cleaned_lines = clean_toc_lines(toc_text)
    toc_data = parse_toc(cleaned_lines)
    articles_info = extract_articles(toc_data, pdf_path)

    return articles_info


# Использование скрипта
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python script.py <pdf_path>")
        sys.exit(1)
    fname = sys.argv[1]
    main(fname)
