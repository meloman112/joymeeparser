# Joyme — бот квартир Joymi

## Как пользоваться

1. Пришли боту **ссылку** с параметрами API, например:
   `https://api.joymi.uz/api/v1/announcement/all-in-map-by-radius/?entity_purpose=long_term_rent&entity_type=apartment&c_type=long&max_price=400&lat=41.284&long=69.212&radius=3&category=4`

2. Фильтр сохранится, первый опрос без спама уведомлений.

3. Каждые 30 мин — проверка; **новые** → текст + **все фото** альбомом.

4. `/filters` — список, кнопка 🗑 удаляет фильтр.

5. Inline под объявлением — категория (✅🟡❌❓🗑).

## Команды

- `/filters` — фильтры и удаление
- `/scan` — все фильтры; `/scan abc12345` — один
- `/stats` — по каждому фильтру
- `/list <filter_id> unverified`
- `/apt_<filter_id>_<apt_id>` — карточка + все фото

Параметры поиска в `.env` **не нужны** — только ссылка.
# joymeeparser
