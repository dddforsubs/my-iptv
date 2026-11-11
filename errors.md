# IPTV: ошибки проверки доступности

Накопительный журнал отказов проверки из сети запуска генератора. Проверка выполняется без cookies, авторизации и специальных заголовков доступа. Записи добавляются в конец. Непроверенный либо проваливший проверку URL не включается в публикуемый `docs/playlist.m3u`; при отсутствии проверенной альтернативы канал сохраняется в эталоне и отмечается отсутствующим в `docs/status.json`.

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

## Проверка 2026-11-10T19:15:19.999134+00:00 — GitHub Actions runner

- **Discovery Channel HD** (`DiscoveryChannel.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **National Geographic HD** (`NationalGeographic.ru@SD`) — этап `playlist`, HTTP 404: Not Found.
- **Nat Geo Wild** (`NationalGeographicWild.ru@HD`) — этап `playlist`: [Errno 111] Connection refused.
- **В мире животных HD** (`Vmirezhivotnykh.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **365 дней ТВ** (`365daysTV.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **Discovery Channel** (`DiscoveryChannel.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **National Geographic** (`NationalGeographic.ru@SD`) — этап `playlist`, HTTP 404: Not Found.
- **National Geographic Wild** (`NationalGeographicWild.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **Animal Planet** (`AnimalPlanet.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **Investigation Discovery** (`InvestigationDiscovery.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **Наука** (`Nauka.ru@SD`) — этап `playlist`: request timed out.
- **Моя Планета** (`MoyaPlaneta.ru@SD`) — этап `playlist`: request timed out.
- **История** (`Istoriya.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **В мире животных** (`Vmirezhivotnykh.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **365 дней TV** (`365daysTV.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **Travel+Adventure** (`TravelPlusAdventure.ru@SD`) — этап `playlist`: request timed out.
- **Зоопарк** (`Zoopark.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **Documentary+ International** (`DocumentaryPlus.us@International`) — этап `playlist`, HTTP 404: Not Found.
- **Docurama** (`Docurama.us@SD`) — этап `playlist`: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired (_ssl.c:1147).
- **Мульт** (`Mult.ru@SD`) — этап `playlist`: request timed out.
- **TiJi** (`TiJi.ru@SD`) — этап `playlist`: request timed out.
- **Nick Jr.** (`NickJr.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **Карусель** (`Carousel.ru@SD`) — этап `playlist`: request timed out.
- **CBeebies** (`BBCFourCBeebies.uk@HD`) — этап `playlist`, HTTP 403: Forbidden.
- **ABC Kids** (`ABCKids.au@Sydney`) — этап `media segment`, HTTP 200: server returned an error page instead of a segment.

## Проверка 2026-11-10T19:24:09.853682+00:00 — local runner network

- **Discovery Channel HD** (`DiscoveryChannel.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **National Geographic HD** (`NationalGeographic.ru@SD`) — этап `playlist`, HTTP 404: Not Found.
- **Nat Geo Wild** (`NationalGeographicWild.ru@HD`) — этап `playlist`: [Errno 61] Connection refused.
- **В мире животных HD** (`Vmirezhivotnykh.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **Discovery Channel** (`DiscoveryChannel.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **National Geographic** (`NationalGeographic.ru@SD`) — этап `playlist`, HTTP 404: Not Found.
- **National Geographic Wild** (`NationalGeographicWild.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **Investigation Discovery** (`InvestigationDiscovery.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **History US East** (`History.us@East`) — этап `playlist`, HTTP 403: Forbidden.
- **Наука** (`Nauka.ru@SD`) — этап `playlist`: request timed out.
- **Моя Планета** (`MoyaPlaneta.ru@SD`) — этап `playlist`: request timed out.
- **История** (`Istoriya.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **В мире животных** (`Vmirezhivotnykh.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **Travel+Adventure** (`TravelPlusAdventure.ru@SD`) — этап `playlist`: request timed out.
- **Зоопарк** (`Zoopark.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **Documentary+ International** (`DocumentaryPlus.us@International`) — этап `playlist`, HTTP 404: Not Found.
- **Docurama** (`Docurama.us@SD`) — этап `playlist`, HTTP 502: Bad Gateway.
- **TiJi** (`TiJi.ru@SD`) — этап `playlist`, HTTP 404: Not Found.
- **CBeebies** (`BBCFourCBeebies.uk@HD`) — этап `playlist`, HTTP 403: Forbidden.

## Проверка 2026-11-10T19:25:21.315959+00:00 — local runner network

- **National Geographic HD** (`NationalGeographic.ru@SD`) — этап `playlist`, HTTP 404: Not Found.
- **Nat Geo Wild** (`NationalGeographicWild.ru@HD`) — этап `playlist`: [Errno 61] Connection refused.
- **В мире животных HD** (`Vmirezhivotnykh.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **National Geographic** (`NationalGeographic.ru@SD`) — этап `playlist`, HTTP 404: Not Found.
- **National Geographic Wild** (`NationalGeographicWild.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **Animal Planet** (`AnimalPlanet.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **Investigation Discovery** (`InvestigationDiscovery.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **History US East** (`History.us@East`) — этап `playlist`, HTTP 403: Forbidden.
- **Наука** (`Nauka.ru@SD`) — этап `playlist`: request timed out.
- **Моя Планета** (`MoyaPlaneta.ru@SD`) — этап `playlist`: request timed out.
- **История** (`Istoriya.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **В мире животных** (`Vmirezhivotnykh.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **Travel+Adventure** (`TravelPlusAdventure.ru@SD`) — этап `playlist`: request timed out.
- **Зоопарк** (`Zoopark.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **Documentary+ International** (`DocumentaryPlus.us@International`) — этап `playlist`, HTTP 404: Not Found.
- **Docurama** (`Docurama.us@SD`) — этап `playlist`, HTTP 502: Bad Gateway.
- **CBeebies** (`BBCFourCBeebies.uk@HD`) — этап `playlist`, HTTP 403: Forbidden.

## Проверка 2026-11-10T19:26:05.491099+00:00 — GitHub Actions runner

- **Discovery Channel HD** (`DiscoveryChannel.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **National Geographic HD** (`NationalGeographic.ru@SD`) — этап `playlist`, HTTP 404: Not Found.
- **Nat Geo Wild** (`NationalGeographicWild.ru@HD`) — этап `playlist`: [Errno 111] Connection refused.
- **В мире животных HD** (`Vmirezhivotnykh.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **Discovery Channel** (`DiscoveryChannel.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **National Geographic** (`NationalGeographic.ru@SD`) — этап `playlist`, HTTP 404: Not Found.
- **National Geographic Wild** (`NationalGeographicWild.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **Animal Planet** (`AnimalPlanet.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **Investigation Discovery** (`InvestigationDiscovery.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **Наука** (`Nauka.ru@SD`) — этап `playlist`: request timed out.
- **Моя Планета** (`MoyaPlaneta.ru@SD`) — этап `playlist`: request timed out.
- **История** (`Istoriya.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **В мире животных** (`Vmirezhivotnykh.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **Travel+Adventure** (`TravelPlusAdventure.ru@SD`) — этап `playlist`: request timed out.
- **Зоопарк** (`Zoopark.ru@SD`) — этап `playlist`, HTTP 403: Forbidden.
- **Documentary+ International** (`DocumentaryPlus.us@International`) — этап `playlist`, HTTP 404: Not Found.
- **Docurama** (`Docurama.us@SD`) — этап `playlist`, HTTP 502: Bad Gateway.
- **CBeebies** (`BBCFourCBeebies.uk@HD`) — этап `playlist`, HTTP 403: Forbidden.

## Новые отказы 2026-11-10T20:47:16.976071+00:00 — local runner network

- **National Geographic HD** (`NationalGeographic.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **Живая Природа** (`Zhivayapriroda.ru@HD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **National Geographic** (`NationalGeographic.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **National Geographic Wild** (`NationalGeographicWild.ru@SD`) — этап `playlist`: credential_in_url.
- **Живая природа HD** (`Zhivayapriroda.ru@HD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **History HD** (`History.us@East`) — этап `candidate matching`: no exact eligible candidate.
- **H2 (History 2)** (`History2LatinAmerica.us@Panregional`) — этап `candidate matching`: no exact eligible candidate.
- **Viasat History CEE HD** (`ViasatHistory.cz@SD`) — этап `candidate matching`: no exact eligible candidate.
- **Viasat Nature CEE HD** (`ViasatNature.cz@SD`) — этап `candidate matching`: no exact eligible candidate.
- **Viasat Explore CEE HD** (`ViasatExplore.cz@SD`) — этап `candidate matching`: no exact eligible candidate.
- **MiniMax Мегамир HD** — этап `candidate matching`: no exact eligible candidate.
- **MiniMax Микромир** — этап `candidate matching`: no exact eligible candidate.
- **Точка РФ** (`TochkaRF.ru@SD`) — этап `candidate matching`: no exact eligible candidate.

## Новые отказы 2026-11-10T20:51:12.251411+00:00 — local runner network

- **National Geographic Wild** (`NationalGeographicWild.ru@SD`) — этап `candidate matching`: no exact eligible candidate.

## Новые отказы 2026-11-10T20:54:43.714737+00:00 — local runner network

- **Nat Geo Wild** (`NationalGeographicWild.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **365 дней ТВ** (`365daysTV.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **365 дней TV** (`365daysTV.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **TiJi** (`TiJi.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.

## Новые отказы 2026-11-10T20:56:25.134491+00:00 — local runner network

- **История** (`Istoriya.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **Зоопарк** (`Zoopark.ru@SD`) — этап `playlist`, HTTP 200: response is not an HLS playlist.
- **Nick Jr.** (`NickJr.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.

## Новые отказы 2026-11-10T20:59:57.824787+00:00 — local runner network

- **Моя Планета** (`MoyaPlaneta.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.
- **История** (`Istoriya.ru@SD`) — этап `media playlist`, HTTP 200: response is not an HLS playlist.

## Новые отказы 2026-11-11T10:56:35.758715+00:00 — GitHub Actions runner

- **H2 (History 2)** — этап `candidate matching`: no exact eligible candidate.

## Новые отказы 2026-11-11T11:37:14.016959+00:00 — local runner network

- **Discovery Channel HD** (`DiscoveryChannel.ru@SD`) — этап `candidate matching`: no exact eligible candidate.
- **Nat Geo Wild** (`NationalGeographicWild.ru@SD`) — этап `candidate matching`: no exact eligible candidate.
- **365 дней ТВ** (`365daysTV.ru@SD`) — этап `candidate matching`: no exact eligible candidate.
- **Discovery Channel** (`DiscoveryChannel.ru@SD`) — этап `candidate matching`: no exact eligible candidate.
- **Animal Planet** (`AnimalPlanet.ru@SD`) — этап `candidate matching`: no exact eligible candidate.
- **Investigation Discovery** (`InvestigationDiscovery.ru@SD`) — этап `candidate matching`: no exact eligible candidate.
- **История** (`Istoriya.ru@SD`) — этап `candidate matching`: no exact eligible candidate.
- **365 дней TV** (`365daysTV.ru@SD`) — этап `candidate matching`: no exact eligible candidate.
- **Travel+Adventure** (`TravelPlusAdventure.ru@SD`) — этап `candidate matching`: no exact eligible candidate.
- **Зоопарк** (`Zoopark.ru@SD`) — этап `candidate matching`: no exact eligible candidate.
- **CBeebies** (`BBCFourCBeebies.uk@HD`) — этап `candidate matching`: no exact eligible candidate.

## Новые отказы 2026-11-11T11:42:31.320264+00:00 — GitHub Actions runner

- **Живая Природа** (`Zhivayapriroda.ru@HD`) — этап `candidate matching`: no exact eligible candidate.
- **Живая природа HD** (`Zhivayapriroda.ru@HD`) — этап `candidate matching`: no exact eligible candidate.
