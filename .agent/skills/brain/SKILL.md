---
name: brain
description: "Центральный роутер рабочих процессов. Используй этот скилл когда: (1) начинаешь новую сложную задачу и нужно определить режим работы, (2) нужно переключиться между режимами (planning/execution/verification/debugging), (3) управляешь многоэтапным проектом. Brain автоматически выбирает оптимальный workflow на основе контекста."
---

# Brain — Центральный роутер рабочих процессов

## Роль

**Identity:** Orchestrator / State Machine Controller  
**Цель:** Определить оптимальный режим работы и направить в нужный workflow

---

## Быстрый старт

1. Определи текущее состояние задачи (см. таблицу ниже)
2. Загрузи соответствующий workflow через `view_file`
3. Следуй инструкциям workflow

---

## Таблица маршрутизации

| Контекст / Триггер | Режим | Workflow | Когда использовать |
|-------------------|-------|----------|-------------------|
| Новая сложная задача | BRIEFING | `/briefing` | Нет чёткой спецификации |
| Готов бриф, нужен план | PLANNING | `/planning` | Есть требования, нужна архитектура |
| Выбор между подходами | REASONING | `/reasoning` | Несколько равноценных вариантов |
| План утверждён | EXECUTION | `/execution` | Пора писать код |
| Код написан | VERIFICATION | `/verification` | Проверить работоспособность |
| Баг, странное поведение | DEBUGGING | `/debugging` | Что-то не работает как ожидалось |
| Проверить гипотезу | HYPOTHESIS | `/hypothesis_testing` | Нужен эксперимент |
| Многоэтапный проект | ORCHESTRATION | `/orchestration` | 5+ связанных задач |
| Нужно исследование | RESEARCH | `/research` | Изучить кодовую базу / документацию |
| Рефакторинг | REFACTORING | `/refactoring` | Улучшить код без изменения поведения |
| Проект завершён | POSTMORTEM | `/postmortem` | Извлечь уроки |
| Передать задачу Gemini | DELEGATION | skill `task-delegator` | Opus создаёт спецификацию для Gemini |

---

## State Machine

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ BRIEFING │────▶│ PLANNING │────▶│ EXECUTE  │────▶│ VERIFY   │
└──────────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
                      │                │                │
                      │                │                │
                      ▼                ▼                ▼
                 ┌─────────┐     ┌─────────┐     ┌─────────┐
                 │REASONING│     │DEBUGGING│     │POSTMORTEM│
                 └─────────┘     └─────────┘     └─────────┘
```

### Правила переходов

| Из состояния | В состояние | Условие |
|--------------|-------------|---------|
| BRIEFING | PLANNING | Бриф готов |
| PLANNING | EXECUTION | План утверждён пользователем |
| PLANNING | REASONING | Нужен выбор подхода |
| EXECUTION | VERIFICATION | Код написан |
| EXECUTION | DEBUGGING | Обнаружен баг |
| VERIFICATION | EXECUTION | Найдены проблемы |
| VERIFICATION | POSTMORTEM | Всё работает |

---

## Определение режима (Decision Tree)

```
Задача от пользователя
         │
         ▼
    Есть ошибка/баг?
    ┌────┴────┐
   YES       NO
    │         │
    ▼         ▼
/debugging  Задача ясна?
            ┌────┴────┐
           YES       NO
            │         │
            ▼         ▼
      Есть план?   /briefing
      ┌────┴────┐
     YES       NO
      │         │
      ▼         ▼
 /execution  /planning
```

---

## Использование

При получении задачи:

1. **Оценить контекст** — используй Decision Tree выше
2. **Определить режим** — по таблице маршрутизации
3. **Загрузить workflow** — `view_file` на `.agent/workflows/{режим}.md`
4. **Следовать инструкциям** — каждый workflow содержит свой процесс

---

## Пути к workflows

- `.agent/workflows/briefing.md`
- `.agent/workflows/planning.md`
- `.agent/workflows/execution.md`
- `.agent/workflows/verification.md`
- `.agent/workflows/debugging.md`
- `.agent/workflows/reasoning.md`
- `.agent/workflows/hypothesis_testing.md`
- `.agent/workflows/orchestration.md`
- `.agent/workflows/research.md`
- `.agent/workflows/refactoring.md`
- `.agent/workflows/postmortem.md`

---

## Маркеры состояния

В сообщениях используй маркеры для ясности:

| Маркер | Режим |
|--------|-------|
| 📋 | BRIEFING |
| 🗺️ | PLANNING |
| 🤔 | REASONING |
| ⚡ | EXECUTION |
| ✅ | VERIFICATION |
| 🐛 | DEBUGGING |
| 🔬 | HYPOTHESIS |
| 🎯 | ORCHESTRATION |
