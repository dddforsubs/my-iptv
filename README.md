# My IPTV — эталонный список каналов

> **Назначение:** это список **желаемых каналов**, а не каталог работающих URL. Отсутствие потока не является основанием удалять канал из эталона.
> **Источники потоков:** только публичный репозиторий [`iptv-org/iptv`](https://github.com/iptv-org/iptv). Не включать персональные IPTV-ключи или случайные источники, не присутствующие в этом репозитории.
> **Основа:** фотография избранного от 10.11.2026 + последняя доступная локальная сборка плейлиста от 10.11.2026 (47 M3U-записей). Содержимое *текущего удалённого* `docs/playlist.m3u` в момент составления README прочитать не удалось, поэтому этот снимок требует сверки после доступа к GitHub.

## 1. Приоритет A: обязательное избранное с фотографии

Эти названия и региональные версии сохраняются независимо от доступности открытого потока. Порядок в таблице — порядок слева направо, сверху вниз на фотографии.

| № | Канал | Предпочтение | ID/пример кандидата в прежнем M3U | Примечание |
|---:|---|---|---|---|
| 1 | Discovery Channel HD | RU / HD | `DiscoveryChannel.ru@SD` | поток есть в предыдущей сборке; фактическое качество проверять |
| 2 | National Geographic HD | RU / HD | `NationalGeographic.ru@SD` | поток есть; 1080p не гарантировано |
| 3 | Nat Geo Wild | RU / HD предпочтительно | `NationalGeographicWild.ru@SD` | предыдущий поток 576p; искать HD |
| 4 | В мире животных HD | RU / HD | `Vmirezhivotnykh.ru@SD` | в предыдущей сборке SD; искать HD |
| 5 | History HD | RU / HD предпочтительно | `History.us@East` | US East — не точное совпадение по языку/региону |
| 6 | H2 (History 2) | RU / HD предпочтительно | `History2LatinAmerica.us@Panregional` | латиноамериканский feed — альтернатива, не эквивалент |
| 7 | viju History HD | RU / HD | `vijuHistory.ru@SD` | в предыдущей сборке, уточнять HD |
| 8 | viju Nature HD | RU / HD | `vijuNature.ru@SD` | в предыдущей сборке, уточнять HD |
| 9 | viju Explore | RU / HD предпочтительно | `vijuExplore.ru@SD` | в предыдущей сборке |
| 10 | Viasat History CEE HD | CEE / HD | — | строго CEE: Polsat Viasat PL не заменяет автоматически |
| 11 | Viasat Nature CEE HD | CEE / HD | — | строго CEE: Polsat Viasat PL не заменяет автоматически |
| 12 | Viasat Explore CEE HD | CEE / HD | — | строго CEE: Polsat Viasat PL не заменяет автоматически |
| 13 | Живая Природа | RU / HD | `Zhivayapriroda.ru@HD` | в предыдущей сборке |
| 14 | 365 дней ТВ | RU | `365daysTV.ru@SD` | в предыдущей сборке |
| 15 | English Club TV | English / HD желательно | `EnglishClubTV.uk@SD` | на фото; отсутствует в проверенном snapshot 47 |
| 16 | MiniMax Мегамир HD | RU / HD | — | не путать с европейским Minimax |
| 17 | MiniMax (название обрезано на фото) | уточнить | — | частично виден нижний ряд; нельзя додумывать Макромир/Микромир |

## 2. Приоритет B: весь сохранённый плейлист

Это **47 записей** из последнего доступного локального M3U (10.11.2026). Запись может быть альтернативным региональным feed или дублировать тот же телеканал в другой группе. При будущем сопоставлении не удалять эти предпочтения молча; совпадающие потоки допускается дедуплицировать с сохранением покрытия.

| № | Канал в плейлисте | `tvg-id` в последней сборке | Группа |
|---:|---|---|---|
| 1 | Discovery Channel | `DiscoveryChannel.ru@SD` | Познавательные RU |
| 2 | National Geographic | `NationalGeographic.ru@SD` | Познавательные RU |
| 3 | National Geographic Wild | `NationalGeographicWild.ru@SD` | Познавательные RU |
| 4 | Animal Planet | `AnimalPlanet.ru@SD` | Познавательные RU |
| 5 | viju History | `vijuHistory.ru@SD` | Познавательные RU |
| 6 | Investigation Discovery | `InvestigationDiscovery.ru@SD` | Познавательные RU |
| 7 | History US East | `History.us@East` | История EN |
| 8 | History 2 Latin America (не H2 CEE) | `History2LatinAmerica.us@Panregional` | Региональные альтернативы |
| 9 | Polsat Viasat History PL (не CEE) | `PolsatViasatHistory.pl@SD` | Региональные альтернативы |
| 10 | Polsat Viasat Nature PL (не CEE) | `PolsatViasatNature.pl@SD` | Региональные альтернативы |
| 11 | Polsat Viasat Explore PL (не CEE) | `PolsatViasatExplore.pl@SD` | Региональные альтернативы |
| 12 | BBC Earth Czechia | `BBCEarth.uk@Czechia` | Региональные альтернативы |
| 13 | Наука | `Nauka.ru@SD` | Познавательные RU |
| 14 | Моя Планета | `MoyaPlaneta.ru@SD` | Познавательные RU |
| 15 | История | `Istoriya.ru@SD` | Познавательные RU |
| 16 | Живая природа HD | `Zhivayapriroda.ru@HD` | Познавательные RU |
| 17 | В мире животных | `Vmirezhivotnykh.ru@SD` | Познавательные RU |
| 18 | viju Nature | `vijuNature.ru@SD` | Познавательные RU |
| 19 | viju Explore | `vijuExplore.ru@SD` | Познавательные RU |
| 20 | 365 дней TV | `365daysTV.ru@SD` | Познавательные RU |
| 21 | RTG TV HD | `RTGTV.ru@HD` | Познавательные RU |
| 22 | Travel+Adventure | `TravelPlusAdventure.ru@SD` | Познавательные RU |
| 23 | Точка РФ | `TochkaRF.ru@SD` | Познавательные RU |
| 24 | Просвещение | `Prosveshchenie.ru@SD` | Познавательные RU |
| 25 | Большая Азия | `BigAsia.ru@SD` | Познавательные RU |
| 26 | Зоопарк | `Zoopark.ru@SD` | Познавательные RU |
| 27 | Documentary+ | `DocumentaryPlus.us@US` | Documentary EN |
| 28 | Documentary+ International | `DocumentaryPlus.us@International` | Documentary EN |
| 29 | Docurama | `Docurama.us@SD` | Documentary EN |
| 30 | History Hit | `HistoryHit.uk@SD` | History EN |
| 31 | Wonder | `Wonder.uk@SD` | Documentary EN |
| 32 | CGTN Documentary | `CGTNDocumentary.cn@SD` | Documentary EN |
| 33 | China Travel | `ChinaTravel.cn@SD` | Travel EN |
| 34 | Discovering China | `DiscoveringChina.cn@SD` | Travel EN |
| 35 | NHK World-Japan | `NHKWorldJapan.jp@SD` | Culture EN |
| 36 | BBC News | `BBCNews.uk@Europe` | World News EN |
| 37 | CNN International | — | World News EN |
| 38 | Al Jazeera English | `AlJazeera.qa@English` | World News EN |
| 39 | France 24 English | `France24.fr@English` | World News EN |
| 40 | DW English | `DW.de@English` | World News EN |
| 41 | Euronews English | `EuronewsEnglish.fr@SD` | World News EN |
| 42 | Bloomberg TV | `BloombergTV.us@US` | Business News EN |
| 43 | CBS News 24/7 | `CBSNews247.us@SD` | US News EN |
| 44 | NBC News NOW | `NBCNewsNOW.us@SD` | US News EN |
| 45 | ABC News Australia | `ABCNews.au@Sydney` | World News EN |
| 46 | CGTN | `CGTN.cn@SD` | World News EN |
| 47 | NHK World-Japan | `NHKWorldJapan.jp@SD` | World News EN |

## 3. Принципы актуализации

1. **Эталон неизменен без согласования.** `README.md` — перечень желаемых каналов. `docs/playlist.m3u` — генерируемый перечень *реально найденных* потоков; `docs/status.json` — список совпадений и отсутствующих источников.
2. Сопоставлять по ID канала и точному feed из `iptv-org` API (`channels.json`, `streams.json`), а не только по названию и не только по `streams/ru.m3u`.
3. Предпочтения: русский звук для русскоязычных каналов, HD/1080p при возможности, точная версия CEE для Viasat. Изменение региона или языка — это **альтернатива**, а не замена того же канала.
4. Не добавлять URL, которого нет в актуальном `iptv-org`. Не принимать HTTP 200 за гарантированно воспроизводимый поток. Отдельно проверять геоблокировки и пометки `Not 24/7`.
5. Не удалять любимый канал из эталона из-за одного отсутствия потока. Если поток не найден — не включать мёртвый URL в M3U, а отметить канал как ожидающий в отчёте.
6. Не подменять `MiniMax Мегамир HD` европейским `Minimax` и не угадывать название частично видимого канала.
7. Сохранять стабильный URL GitHub Pages: `https://dddforsubs.github.io/my-iptv/playlist.m3u`.
8. Публикация M3U должна выполняться **GitHub Actions** по расписанию (раз в сутки) и по `workflow_dispatch` (ручной запуск). ChatGPT Tasks отслеживает изменения и сообщает об исключениях, но не считается механизмом записи в GitHub без явно предоставленного доступа на запись.

## 4. Связанные файлы

- `README.md` — данный эталон и правила.
- `config/favorites.m3u` — машинный список целей, который использует подготовленный ранее Python-генератор.
- `config/extra_watch.json` — дополнительный список целей мониторинга, пока генератор не переведён на чтение README.
- `scripts/update_playlist.py` — подбор источников из `iptv-org`.
- `docs/playlist.m3u` — публикуемый плейлист для Televizo.
- `.github/workflows/update-iptv.yml` — ежедневный и ручной запуск генератора, коммит и деплой GitHub Pages.

> **Важно:** текущая версия генератора читает `config/favorites.m3u` и `config/extra_watch.json`, **а не README**. Для полного соответствия этому эталону его конфигурацию нужно синхронизировать с разделами 1–2 или изменить генератор, чтобы он читал список непосредственно из README.
