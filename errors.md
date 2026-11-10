# IPTV: ошибки проверки доступности

Накопительный журнал отказов проверки из сети запуска генератора. Проверка выполняется без cookies, авторизации и специальных заголовков доступа. Записи добавляются в конец; ошибка проверки не исключает найденный канал из `docs/playlist.m3u`.

## Проверка 2026-11-10T19:14:01.198451+00:00

- **Discovery Channel HD** (`DiscoveryChannel.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **National Geographic HD** (`NationalGeographic.ru@SD`) — этап `playlist`, HTTP 404: Not Found.
- **Nat Geo Wild** (`NationalGeographicWild.ru@HD`) — этап `playlist`: [Errno 61] Connection refused.
- **365 дней ТВ** (`365daysTV.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **Discovery Channel** (`DiscoveryChannel.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **National Geographic** (`NationalGeographic.ru@SD`) — этап `playlist`, HTTP 404: Not Found.
- **National Geographic Wild** (`NationalGeographicWild.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **Investigation Discovery** (`InvestigationDiscovery.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **History US East** (`History.us@East`) — этап `playlist`, HTTP 403: Forbidden.
- **Наука** (`Nauka.ru@SD`) — этап `playlist`: request timed out.
- **Моя Планета** (`MoyaPlaneta.ru@SD`) — этап `playlist`: request timed out.
- **История** (`Istoriya.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **365 дней TV** (`365daysTV.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **Travel+Adventure** (`TravelPlusAdventure.ru@SD`) — этап `playlist`: request timed out.
- **Зоопарк** (`Zoopark.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **Documentary+ International** (`DocumentaryPlus.us@International`) — этап `playlist`, HTTP 404: Not Found.
- **Docurama** (`Docurama.us@SD`) — этап `playlist`: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired (_ssl.c:1082).
- **Мульт** (`Mult.ru@SD`) — этап `playlist`: request timed out.
- **TiJi** (`TiJi.ru@SD`) — этап `playlist`: request timed out.
- **Nick Jr.** (`NickJr.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **Карусель** (`Carousel.ru@SD`) — этап `playlist`: request timed out.
- **CBeebies** (`BBCFourCBeebies.uk@HD`) — этап `playlist`, HTTP 403: Forbidden.

Среда для проверки 2026-11-10T19:14:01.198451+00:00: local runner network.
