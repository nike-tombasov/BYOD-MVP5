## 14.  Процесс MVP 

### 14.1. Прошедшие этапы MVP (использовались фиксированные в коде room data и tokens):

Stage I - первичная разработка - тест LiveKit Server и backend на VPS и Python Publisher (без UI) на Windows- УСПЕШНО - код максимально адаптирован под LiveKit v1.9.11, html прекрасно отрабатывал, Publisher без crashes.

Stage II - теоретическая подготовка и разработка разом расширенного функционала системы - тест локального LiveKit Server (Windows) с backend и publisher UI - ПРОВАЛ - Publisher UI зависал при нажатии на JOIN, терялась связь с LiveKit Server (скорее всего, было нарушение рабочей документации версий, потерян фокус на привязке к LiveKit v1.7 на всей цепочке Stage II)

Stage III - сразу после Stage  II - тест локального LiveKit Server (Windows) с упрощённым publisher (без UI) - УСПЕШНО

Stage IV - переработка теории и плавный ввод функций Publisher UI v0.2 - тест Publisher UI v0.2 и локального LiveKit Server (Windows) на локальном html listener - УСПЕШНО 

### 14.2. Текущий статус Stage V:

1) Необходимость окончательно проработать и реализовать логику multi-publisher multi-channel room и избежать ошибок Listener subscribe
2) Пересобрать Publisher UI с минимальной визуализацей, но максимально подготовленным core engine
3) Реализовать локальный backend на Python, способный отработать multi-publisher multi-channel room до 32 channels
4) Реализовать web page, отвечающий требованиям спецификации и архитектуры

До конца Stage V соблюдать спецификацию и архитектуру, чтобы на следующих Stage разработка шла быстрее и являлась прямым логическим продолжением.